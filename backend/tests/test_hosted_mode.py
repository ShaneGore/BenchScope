import json
import logging
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app.auth import current_owner
from app.config import Settings
from app.main import create_app
from app.models import Base, BenchmarkRun, ModelProfile
from app.runner import RunResult


@pytest.fixture
def hosted_api(
    tmp_path: Path,
) -> Iterator[tuple[TestClient, Engine, FastAPI]]:
    settings = Settings.model_construct(
        app_mode="hosted",
        app_env="production",
        local_auth_bypass=False,
        database_url=SecretStr(f"sqlite:///{tmp_path / 'hosted.db'}"),
        cors_origins=["https://dashboard.example"],
        host="0.0.0.0",
        clerk_jwks_url="https://clerk.example/.well-known/jwks.json",
        clerk_issuer="https://clerk.example",
        clerk_audience="benchscope",
    )
    app = create_app(settings)
    engine = app.state.engine
    assert engine is not None
    Base.metadata.create_all(engine)
    before_startup = _count_rows(engine)
    with TestClient(app) as client:
        assert _count_rows(engine) == before_startup
        yield client, engine, app


def _count_rows(engine: Engine) -> tuple[int, int]:
    with Session(engine) as session:
        return (
            session.scalar(select(func.count()).select_from(ModelProfile)) or 0,
            session.scalar(select(func.count()).select_from(BenchmarkRun)) or 0,
        )


def _import_payload() -> dict[str, object]:
    return {
        "format_version": "benchscope.run.v1",
        "source_run_id": "synthetic-export-01",
        "profile_snapshot": {
            "name": "Sample Model",
            "model_name": "sample/model",
            "model_version": None,
            "quantisation": "Q4",
        },
        "benchmark_config": {"name": "synthetic-demo", "max_tokens": 64},
        "started_at": "2026-10-26T10:00:00Z",
        "ended_at": "2026-10-26T10:00:01Z",
        "metrics": {},
        "hardware_snapshot": {"cpu": "Demo CPU"},
    }


def test_anonymous_demo_reads_are_deterministic_sanitized_and_personal_data_stays_protected(
    hosted_api: tuple[TestClient, Engine, FastAPI],
) -> None:
    client, _engine, _app = hosted_api
    first = client.get("/api/v1/demo/runs")
    second = client.get("/api/v1/demo/runs")

    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    runs = first.json()
    assert [run["id"] for run in runs] == ["demo-run-01", "demo-run-02"]
    detail = client.get(f"/api/v1/demo/runs/{runs[0]['id']}")
    assert detail.status_code == 200
    assert detail.json() == runs[0]
    missing_demo = client.get("/api/v1/demo/runs/missing-id")
    assert missing_demo.status_code == 404
    assert missing_demo.json() == {"detail": "Demo run not found"}
    assert runs[1]["metrics"]["ttft_ms"] is None

    rendered = json.dumps(runs).casefold()
    for prohibited in (
        "endpoint_url",
        "api_key",
        "credential",
        "artifact_ref",
        "private",
        "prompt_set",
        "raw_output",
        "error_message",
        "owner_id",
    ):
        assert prohibited not in rendered

    assert client.get("/api/v1/profiles").status_code == 401
    assert client.get("/api/v1/runs").status_code == 401
    assert (
        client.get("/api/v1/runs/00000000-0000-0000-0000-000000000001").status_code
        == 401
    )


def test_demo_is_get_only_and_has_no_startup_or_read_database_side_effects(
    hosted_api: tuple[TestClient, Engine, FastAPI],
) -> None:
    client, engine, _app = hosted_api
    before = _count_rows(engine)
    fixture_before = client.get("/api/v1/demo/runs").json()
    run_id = "demo-run-01"

    for method in ("post", "patch", "delete"):
        assert getattr(client, method)("/api/v1/demo/runs").status_code == 405
        assert getattr(client, method)(f"/api/v1/demo/runs/{run_id}").status_code == 405
    fixture_after = client.get("/api/v1/demo/runs")
    assert fixture_after.status_code == 200
    assert fixture_after.json() == fixture_before
    assert client.get(f"/api/v1/demo/runs/{run_id}").status_code == 200
    assert _count_rows(engine) == before == (0, 0)


def test_hosted_profiles_reject_endpoint_credentials_and_unsupported_config_without_writes(
    hosted_api: tuple[TestClient, Engine, FastAPI],
) -> None:
    client, engine, app = hosted_api
    app.dependency_overrides[current_owner] = lambda: "user-alice"

    valid = client.post(
        "/api/v1/profiles", json={"name": "Hosted profile", "model_name": "sample"}
    )
    assert valid.status_code == 201
    profile = valid.json()
    assert profile["endpoint_url"] is None
    assert profile["inference_config"] is None
    assert (
        client.patch(
            f"/api/v1/profiles/{profile['id']}", json={"inference_config": None}
        ).status_code
        == 200
    )

    invalid_creates = [
        {"endpoint_url": "http://127.0.0.1:8080"},
        {"api_key_ref": "credential-reference"},
        {"inference_config": {}},
    ]
    for rejected_fields in invalid_creates:
        response = client.post(
            "/api/v1/profiles",
            json={"name": "Rejected", "model_name": "sample", **rejected_fields},
        )
        assert response.status_code == 422
        assert "127.0.0.1" not in response.text
        assert "credential-reference" not in response.text

    invalid_updates = [
        {"name": "Changed", "endpoint_url": None},
        {"name": "Changed", "api_key": "do-not-echo"},
        {"name": "Changed", "inference_config": {}},
    ]
    for rejected_fields in invalid_updates:
        response = client.patch(
            f"/api/v1/profiles/{profile['id']}", json=rejected_fields
        )
        assert response.status_code == 422
        assert "do-not-echo" not in response.text

    current = client.get(f"/api/v1/profiles/{profile['id']}").json()
    assert current["name"] == "Hosted profile"
    assert current["endpoint_url"] is None
    assert current["inference_config"] is None
    assert _count_rows(engine) == (1, 0)


def test_hosted_import_persists_only_allowlisted_fields_and_rejects_private_values(
    hosted_api: tuple[TestClient, Engine, FastAPI],
    caplog: pytest.LogCaptureFixture,
) -> None:
    client, engine, app = hosted_api
    app.dependency_overrides[current_owner] = lambda: "user-alice"
    caplog.set_level(logging.INFO)

    valid = client.post("/api/v1/runs/import", json=_import_payload())
    assert valid.status_code == 201
    returned = valid.json()["run"]
    assert returned["owner_id"] == "user-alice"
    assert returned["profile_snapshot"] == {
        "name": "Sample Model",
        "model_name": "sample/model",
        "model_version": None,
        "quantisation": "Q4",
    }
    assert returned["metrics"]["ttft_ms"] is None
    assert "source_run_id" not in returned
    assert "raw_payload" not in returned
    with Session(engine) as session:
        stored = session.get(BenchmarkRun, UUID(returned["id"]))
        assert stored is not None
        assert stored.owner_id == "user-alice"
        assert stored.source_run_id == "synthetic-export-01"
        assert stored.profile_snapshot == returned["profile_snapshot"]
        assert stored.artifact_ref is None
        assert stored.error_message_sanitised is None
        assert _count_rows(engine) == (0, 1)

    prohibited = (
        ("raw_payload", None, "private-raw-body"),
        ("profile_snapshot", "generated_output", "private-generated-output"),
        ("benchmark_config", "prompt", "private-prompt"),
        ("metrics", "raw_output", "private-raw-output"),
        ("hardware_snapshot", "api_key", "private-credential"),
    )
    for top_level, nested, value in prohibited:
        payload = _import_payload()
        if nested is None:
            payload[top_level] = value
        else:
            nested_value = payload[top_level]
            assert isinstance(nested_value, dict)
            nested_value[nested] = value
        response = client.post("/api/v1/runs/import", json=payload)
        assert response.status_code == 422
        assert value not in response.text
        assert value not in caplog.text
        assert response.json()["ok"] is False
        assert response.json()["status"] == 422
        assert response.json()["errors"]

    assert _count_rows(engine) == (0, 1)


def test_hosted_endpoints_remain_owner_scoped(
    hosted_api: tuple[TestClient, Engine, FastAPI],
) -> None:
    client, engine, app = hosted_api
    owner = {"id": "user-alice"}
    app.dependency_overrides[current_owner] = lambda: owner["id"]
    profile = client.post(
        "/api/v1/profiles",
        json={"name": "Alice profile", "model_name": "alice/model"},
    ).json()
    payload = _import_payload()
    payload["source_run_id"] = "alice-run"
    run = client.post("/api/v1/runs/import", json=payload).json()["run"]

    with Session(engine) as session:
        bob_profile = ModelProfile(
            owner_id="user-bob", name="Bob profile", model_name="bob/model"
        )
        bob_run = BenchmarkRun(
            owner_id="user-bob",
            source="imported",
            status="completed",
            profile_snapshot={"name": "Bob", "model_name": "bob/model"},
            benchmark_config={"name": "synthetic-demo"},
            started_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        session.add_all([bob_profile, bob_run])
        session.commit()
        bob_profile_id = bob_profile.id
        bob_run_id = bob_run.id

    assert [item["owner_id"] for item in client.get("/api/v1/profiles").json()] == [
        "user-alice"
    ]
    assert client.get(f"/api/v1/profiles/{bob_profile_id}").status_code == 404
    assert client.get(f"/api/v1/runs/{bob_run_id}").status_code == 404
    assert (
        client.get(
            "/api/v1/runs/compare",
            params={"ids": f"{run['id']},{bob_run_id}"},
        ).status_code
        == 404
    )
    assert client.delete(f"/api/v1/runs/{bob_run_id}").status_code == 404

    owner["id"] = "user-bob"
    assert client.get(f"/api/v1/profiles/{bob_profile_id}").status_code == 200
    assert client.get(f"/api/v1/runs/{bob_run_id}").status_code == 200
    assert profile["owner_id"] == run["owner_id"] == "user-alice"


def test_hosted_runner_routes_are_absent_when_enabled_and_adapter_is_never_called(
    tmp_path: Path,
) -> None:
    class CountingAdapter:
        calls = 0

        async def run(
            self, _profile: dict[str, str | None], _config_id: UUID
        ) -> RunResult:
            self.calls += 1
            raise AssertionError("Hosted mode must not invoke the adapter")

    settings = Settings.model_construct(
        app_mode="hosted",
        app_env="production",
        local_auth_bypass=False,
        database_url=SecretStr(f"sqlite:///{tmp_path / 'runner.db'}"),
        cors_origins=["https://dashboard.example"],
        host="0.0.0.0",
        clerk_jwks_url="https://clerk.example/.well-known/jwks.json",
        clerk_issuer="https://clerk.example",
        clerk_audience="benchscope",
        benchmark_enabled=True,
    )
    adapter = CountingAdapter()
    app = create_app(settings, benchmark_adapter=adapter)
    engine = app.state.engine
    assert engine is not None
    Base.metadata.create_all(engine)

    with TestClient(app) as client:
        assert (
            client.get(
                "/api/v1/benchmark/runs/00000000-0000-0000-0000-000000000001"
            ).status_code
            == 404
        )
        assert (
            client.post(
                "/api/v1/benchmark/runs",
                json={"profile_id": str(uuid4()), "config_id": str(uuid4())},
            ).status_code
            == 404
        )
        assert (
            client.post(
                f"/api/v1/runs/{uuid4()}/retry",
            ).status_code
            == 404
        )
        assert _count_rows(engine) == (0, 0)

    assert adapter.calls == 0
