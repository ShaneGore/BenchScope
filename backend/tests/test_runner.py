import asyncio
import os
import threading
import time
from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session

from app.config import Settings
from app.database import sqlalchemy_database_url
from app.main import create_app
from app.models import Base, BenchmarkRun, ModelProfile
from app.runner import RunResult


def test_runner_timeout_must_be_finite() -> None:
    with pytest.raises(ValueError):
        Settings(benchmark_timeout_seconds=float("inf"))


class FakeAdapter:
    def __init__(
        self,
        result: RunResult | None = None,
        error: Exception | None = None,
        delay: float = 0,
    ) -> None:
        self.result = result or RunResult()
        self.error = error
        self.delay = delay
        self.calls = 0
        self.received: tuple[dict[str, str | None], UUID] | None = None

    async def run(self, profile: dict[str, str | None], config_id: UUID) -> RunResult:
        self.calls += 1
        self.received = (profile, config_id)
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error is not None:
            raise self.error
        return self.result


@pytest.fixture
def runner_context() -> Iterator[tuple[FastAPI, Engine, FakeAdapter]]:
    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("Set TEST_DATABASE_URL to run PostgreSQL integration tests")
    if make_url(database_url).get_backend_name() != "postgresql":
        pytest.fail("TEST_DATABASE_URL must use PostgreSQL")

    base_engine = create_engine(sqlalchemy_database_url(database_url))
    schema = f"benchscope_runner_{uuid4().hex}"
    adapter = FakeAdapter()
    try:
        with base_engine.begin() as connection:
            connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
        scoped_url = (
            make_url(sqlalchemy_database_url(database_url))
            .update_query_dict({"options": f"-csearch_path={schema}"})
            .render_as_string(hide_password=False)
        )
        app = create_app(
            Settings(
                database_url=SecretStr(scoped_url),
                app_env="development",
                local_auth_bypass=True,
                benchmark_enabled=True,
                benchmark_timeout_seconds=1,
            ),
            benchmark_adapter=adapter,
        )
        engine = app.state.engine
        assert engine is not None
        Base.metadata.create_all(engine)
        yield app, engine, adapter
        engine.dispose()
    finally:
        with base_engine.begin() as connection:
            connection.exec_driver_sql(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        base_engine.dispose()


def _create_profile(client: TestClient) -> UUID:
    response = client.post(
        "/api/v1/profiles",
        json={
            "name": "synthetic profile",
            "model_name": "test/model",
            "model_version": "v1",
            "quantisation": "q4",
            "endpoint_url": "http://127.0.0.1:8000",
            "inference_config": {"synthetic_secret": "not-for-run-snapshot"},
        },
    )
    assert response.status_code == 201
    return UUID(response.json()["id"])


def _wait_for_status(client: TestClient, run_id: UUID, expected: str) -> dict:
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        response = client.get(f"/api/v1/benchmark/runs/{run_id}")
        assert response.status_code == 200
        if response.json()["status"] == expected:
            return response.json()
        time.sleep(0.01)
    raise AssertionError(f"Run {run_id} did not reach {expected}")


def test_runner_auth_owner_scope_and_profile_validation(
    runner_context: tuple[FastAPI, Engine, FakeAdapter],
) -> None:
    app, engine, _ = runner_context
    with TestClient(app) as client:
        own_profile_id = _create_profile(client)
        with Session(engine) as session:
            foreign_profile = ModelProfile(
                owner_id="someone-else",
                name="foreign",
                model_name="foreign/model",
            )
            foreign_run = BenchmarkRun(
                owner_id="someone-else",
                source="launched",
                status="failed",
                profile_snapshot={"name": "foreign", "model_name": "foreign/model"},
                benchmark_config={"config_id": str(uuid4())},
                started_at=datetime.now(UTC),
            )
            session.add_all([foreign_profile, foreign_run])
            session.commit()
            foreign_profile_id = foreign_profile.id
            foreign_run_id = foreign_run.id

        assert (
            client.post(
                "/api/v1/benchmark/runs",
                json={"profile_id": str(foreign_profile_id), "config_id": str(uuid4())},
            ).status_code
            == 404
        )
        assert client.get(f"/api/v1/benchmark/runs/{foreign_run_id}").status_code == 404
        assert (
            client.post(
                "/api/v1/benchmark/runs",
                json={
                    "profile_id": str(own_profile_id),
                    "config_id": "not-a-uuid",
                },
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/v1/benchmark/runs",
                json={
                    "profile_id": str(own_profile_id),
                    "config_id": str(uuid4()),
                    "command": "no caller command",
                },
            ).status_code
            == 422
        )


def test_success_persists_allowlisted_metrics_and_sanitized_profile_snapshot(
    runner_context: tuple[FastAPI, Engine, FakeAdapter],
) -> None:
    app, engine, adapter = runner_context
    adapter.result = RunResult(quality_score=0.75, prompt_tokens=12)
    config_id = uuid4()
    with TestClient(app) as client:
        profile_id = _create_profile(client)
        response = client.post(
            "/api/v1/benchmark/runs",
            json={"profile_id": str(profile_id), "config_id": str(config_id)},
        )
        assert response.status_code == 202
        started = response.json()
        result = _wait_for_status(client, UUID(started["id"]), "completed")

    assert adapter.received == (
        {
            "name": "synthetic profile",
            "model_name": "test/model",
            "model_version": "v1",
            "quantisation": "q4",
        },
        config_id,
    )
    assert result["metrics"]["quality_score"] == 0.75
    assert result["metrics"]["prompt_tokens"] == 12
    assert result["metrics"]["pass_rate"] is None
    assert result["metrics"]["ttft_ms"] is None
    assert result["metrics"]["output_tokens"] is None
    with Session(engine) as session:
        run = session.get(BenchmarkRun, UUID(started["id"]))
        assert run is not None
        assert run.profile_snapshot == adapter.received[0]
        assert run.benchmark_config == {"config_id": str(config_id)}
        assert run.status == "completed"
        assert run.completed_at is not None
        assert run.quality_score == 0.75
        assert run.prompt_tokens == 12
        assert run.pass_rate is None
        assert "endpoint_url" not in run.profile_snapshot
        assert "inference_config" not in run.profile_snapshot


def test_single_flight_rejects_without_creating_a_row(
    runner_context: tuple[FastAPI, Engine, FakeAdapter],
) -> None:
    app, engine, adapter = runner_context
    adapter.delay = 0.2
    with TestClient(app) as client:
        profile_id = _create_profile(client)
        payload = {"profile_id": str(profile_id), "config_id": str(uuid4())}
        accepted = client.post("/api/v1/benchmark/runs", json=payload)
        assert accepted.status_code == 202
        rejected = client.post("/api/v1/benchmark/runs", json=payload)
        assert rejected.status_code == 409
        _wait_for_status(client, UUID(accepted.json()["id"]), "completed")

    with Session(engine) as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(BenchmarkRun)
                .where(BenchmarkRun.source == "launched")
            )
            == 1
        )
    assert adapter.calls == 1


def test_adapter_failure_is_sanitized_and_retry_creates_linked_attempt(
    runner_context: tuple[FastAPI, Engine, FakeAdapter],
) -> None:
    app, engine, adapter = runner_context
    adapter.error = RuntimeError("prompt generated-code private-secret")
    with TestClient(app) as client:
        profile_id = _create_profile(client)
        start = client.post(
            "/api/v1/benchmark/runs",
            json={"profile_id": str(profile_id), "config_id": str(uuid4())},
        )
        original_id = UUID(start.json()["id"])
        failed = _wait_for_status(client, original_id, "failed")
        assert failed["error_category"] == "adapter_error"
        assert failed["error_message_sanitised"] == "Benchmark adapter failed."
        assert "private-secret" not in str(failed)

        adapter.error = None
        retry = client.post(f"/api/v1/runs/{original_id}/retry")
        assert retry.status_code == 202
        retry_id = UUID(retry.json()["id"])
        assert retry_id != original_id
        retried = _wait_for_status(client, retry_id, "completed")
        assert retried["related_run_id"] == str(original_id)

    with Session(engine) as session:
        previous = session.get(BenchmarkRun, original_id)
        attempt = session.get(BenchmarkRun, retry_id)
        assert previous is not None and previous.status == "failed"
        assert attempt is not None and attempt.related_run_id == original_id


def test_timeout_cancels_and_awaits_adapter_coroutine(
    runner_context: tuple[FastAPI, Engine, FakeAdapter],
) -> None:
    app, _, _adapter = runner_context
    cleaned_up = threading.Event()

    class SlowAdapter:
        async def run(
            self, profile: dict[str, str | None], config_id: UUID
        ) -> RunResult:
            try:
                await asyncio.sleep(1)
            finally:
                cleaned_up.set()
            return RunResult()

    app.state.settings.benchmark_timeout_seconds = 0.02
    app.state.benchmark_adapter = SlowAdapter()
    with TestClient(app) as client:
        profile_id = _create_profile(client)
        response = client.post(
            "/api/v1/benchmark/runs",
            json={"profile_id": str(profile_id), "config_id": str(uuid4())},
        )
        result = _wait_for_status(client, UUID(response.json()["id"]), "failed")
    assert result["error_category"] == "timeout"
    assert result["error_message_sanitised"] == "Benchmark execution timed out."
    assert cleaned_up.is_set()


def test_start_is_unavailable_without_adapter_and_does_not_create_run(
    runner_context: tuple[FastAPI, Engine, FakeAdapter],
) -> None:
    app, engine, _ = runner_context
    app.state.benchmark_adapter = None
    with TestClient(app) as client:
        profile_id = _create_profile(client)
        response = client.post(
            "/api/v1/benchmark/runs",
            json={"profile_id": str(profile_id), "config_id": str(uuid4())},
        )
        assert response.status_code == 503
        assert response.json() == {
            "detail": "Benchmark runner is unavailable because no adapter is configured"
        }
    with Session(engine) as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(BenchmarkRun)
                .where(BenchmarkRun.source == "launched")
            )
            == 0
        )


def test_startup_reconciles_stale_running_runs(
    runner_context: tuple[FastAPI, Engine, FakeAdapter],
) -> None:
    app, engine, _ = runner_context
    with Session(engine) as session:
        profile = ModelProfile(
            owner_id="local",
            name="stale",
            model_name="test/model",
        )
        session.add(profile)
        session.flush()
        run = BenchmarkRun(
            owner_id="local",
            source="launched",
            status="running",
            profile_id=profile.id,
            profile_snapshot={"name": "stale", "model_name": "test/model"},
            benchmark_config={"config_id": str(uuid4())},
            started_at=datetime.now(UTC),
        )
        session.add(run)
        session.commit()
        run_id = run.id

    with TestClient(app) as client:
        response = client.get(f"/api/v1/benchmark/runs/{run_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "interrupted"
    assert response.json()["error_category"] == "interrupted"
    assert response.json()["error_message_sanitised"] == (
        "Run interrupted by application restart."
    )


def test_runner_routes_are_absent_when_disabled_or_hosted() -> None:
    unauthenticated = create_app(Settings(benchmark_enabled=True))
    with TestClient(unauthenticated) as client:
        assert (
            client.get(
                "/api/v1/benchmark/runs/00000000-0000-0000-0000-000000000001"
            ).status_code
            == 401
        )

    disabled = create_app(Settings(benchmark_enabled=False))
    with TestClient(disabled) as client:
        assert (
            client.get(
                "/api/v1/benchmark/runs/00000000-0000-0000-0000-000000000001"
            ).status_code
            == 404
        )

    hosted = create_app(
        Settings(
            app_mode="hosted",
            benchmark_enabled=True,
            database_url=SecretStr("postgresql://db.example/benchscope"),
            cors_origins=["https://dashboard.example"],
            host="0.0.0.0",
            clerk_jwks_url="https://clerk.example/.well-known/jwks.json",
            clerk_issuer="https://clerk.example",
            clerk_audience="benchscope",
        )
    )
    with TestClient(hosted) as client:
        assert (
            client.get(
                "/api/v1/benchmark/runs/00000000-0000-0000-0000-000000000001"
            ).status_code
            == 404
        )
