import hashlib
import json
import logging
import os
from collections.abc import Iterator
from copy import deepcopy
from datetime import datetime
from uuid import UUID, uuid4

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import Engine, create_engine, event, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from alembic import command
from app.config import Settings
from app.database import LOCAL_OWNER_ID, sqlalchemy_database_url
from app.main import create_app
from app.models import BenchmarkRun

BACKEND_DIR = os.path.dirname(os.path.dirname(__file__))


@pytest.fixture
def postgres_api() -> Iterator[tuple[TestClient, Engine]]:
    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("Set TEST_DATABASE_URL to run PostgreSQL import integration tests")
    if make_url(database_url).get_backend_name() != "postgresql":
        pytest.fail("TEST_DATABASE_URL must use PostgreSQL")

    admin_engine = create_engine(sqlalchemy_database_url(database_url))
    schema = f"benchscope_import_{uuid4().hex}"
    app_engine: Engine | None = None
    try:
        with admin_engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))

        schema_url = make_url(sqlalchemy_database_url(database_url)).update_query_dict(
            {"options": f"-csearch_path={schema}"}
        )
        app = create_app(
            Settings(
                database_url=SecretStr(schema_url.render_as_string(hide_password=False))
            )
        )
        app_engine = app.state.engine
        assert app_engine is not None
        with app_engine.connect() as connection:
            connection.exec_driver_sql(f'SET search_path TO "{schema}"')
            connection.commit()
            alembic_config = Config(os.path.join(BACKEND_DIR, "alembic.ini"))
            alembic_config.attributes["connection"] = connection
            command.upgrade(alembic_config, "head")
            connection.commit()

        with TestClient(app) as client:
            yield client, app_engine
    finally:
        if app_engine is not None:
            app_engine.dispose()
        with admin_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin_engine.dispose()


def valid_payload() -> dict[str, object]:
    return {
        "format_version": "benchscope.run.v1",
        "source_run_id": "trusted-export-123",
        "profile_snapshot": {
            "name": "Local model",
            "model_name": "example/model",
            "model_version": None,
            "quantisation": "Q4",
        },
        "benchmark_config": {
            "name": "short",
            "temperature": 0.25,
            "max_tokens": 64,
            "reasoning": False,
            "mtp": True,
            "ctx": 2048,
            "seed": 0,
        },
        "started_at": "2026-10-26T10:00:00Z",
        "ended_at": "2026-10-26T10:00:02Z",
        "metrics": {
            "quality_score": 0,
            "pass_rate": 0,
            "prompt_tokens": 0,
            "output_tokens": None,
            "elapsed_ms": 0,
        },
        "hardware_snapshot": {
            "cpu": "Example CPU",
            "gpu": None,
            "ram_gb": 16,
            "gpu_vram_gb": 0,
            "os": "Example OS",
        },
    }


def test_import_normalizes_fields_and_keeps_null_distinct_from_zero(
    postgres_api: tuple[TestClient, Engine],
) -> None:
    client, engine = postgres_api
    response = client.post("/api/v1/runs/import", json=valid_payload())

    assert response.status_code == 201
    result = response.json()
    run = result["run"]
    assert result["ok"] is True
    assert run["owner_id"] == LOCAL_OWNER_ID
    assert run["status"] == "completed"
    assert run["source"] == "imported"
    assert run["profile_snapshot"] == {
        "name": "Local model",
        "model_name": "example/model",
        "model_version": None,
        "quantisation": "Q4",
    }
    assert run["benchmark_config"]["temperature"] == 0.25
    assert run["metrics"]["quality_score"] == 0
    assert run["metrics"]["pass_rate"] == 0
    assert run["metrics"]["prompt_tokens"] == 0
    assert run["metrics"]["output_tokens"] is None
    assert run["metrics"]["ttft_ms"] is None
    assert run["metrics"]["elapsed_ms"] == 0
    assert (
        not {
            "source_run_id",
            "events",
            "artifact_ref",
            "related_run_id",
            "error_message_sanitised",
        }
        & run.keys()
    )

    with Session(engine) as session:
        stored = session.get(BenchmarkRun, UUID(run["id"]))
        assert stored is not None
        assert stored.profile_id is None
        assert stored.source == "imported"
        assert stored.status == "completed"
        assert stored.source_run_id == "trusted-export-123"
        assert stored.import_fingerprint == run["fingerprint"]
        assert stored.quality_score == 0
        assert stored.output_tokens is None
        assert stored.completed_at is not None
        assert stored.error_message_sanitised is None
        assert stored.artifact_ref is None
        assert session.scalar(select(func.count()).select_from(BenchmarkRun)) == 1


def test_deduplication_is_stable_and_scoped_to_owner(
    postgres_api: tuple[TestClient, Engine],
) -> None:
    client, engine = postgres_api
    payload = valid_payload()
    fingerprint = hashlib.sha256(
        b"benchscope.run.v1\0source_run_id\0trusted-export-123"
    ).hexdigest()
    with Session(engine) as session:
        session.add(
            BenchmarkRun(
                owner_id="another-owner",
                source="imported",
                status="completed",
                profile_snapshot={},
                source_run_id="trusted-export-123",
                import_fingerprint=fingerprint,
                started_at=datetime.fromisoformat("2026-10-26T10:00:00+00:00"),
            )
        )
        session.commit()

    created = client.post("/api/v1/runs/import", json=payload)
    changed = deepcopy(payload)
    changed["metrics"] = {"quality_score": 0.5}
    duplicate = client.post("/api/v1/runs/import", json=changed)
    assert created.status_code == 201
    assert duplicate.status_code == 409
    assert duplicate.json()["status"] == 409
    assert duplicate.json()["errors"][0]["field"] == "source_run_id"
    assert "already been imported" in duplicate.json()["errors"][0]["message"]

    fallback = valid_payload()
    fallback.pop("source_run_id")
    first = client.post("/api/v1/runs/import", json=fallback)
    same = client.post("/api/v1/runs/import", json=fallback)
    other_summary = deepcopy(fallback)
    other_summary["metrics"] = {"quality_score": 0.25}
    different = client.post("/api/v1/runs/import", json=other_summary)
    assert first.status_code == 201
    assert same.status_code == 409
    assert different.status_code == 201
    with Session(engine) as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(BenchmarkRun)
                .where(BenchmarkRun.owner_id == LOCAL_OWNER_ID)
            )
            == 3
        )


def test_unknown_and_private_fields_are_rejected_without_echo_or_write(
    postgres_api: tuple[TestClient, Engine],
    caplog: pytest.LogCaptureFixture,
) -> None:
    client, engine = postgres_api
    caplog.set_level(logging.INFO)
    disallowed = [
        ("owner_id", "private-owner"),
        ("status", "running"),
        ("source", "launched"),
        ("prompt", "private prompt value"),
        ("generated_code", "private generated code"),
        ("api_key", "private credential"),
        ("profile_id", "private profile id"),
        ("fingerprint", "client fingerprint"),
        ("events", []),
        ("artifact_ref", "private artifact"),
        ("error_message", "private error"),
        ("raw_output", "private raw output"),
        ("private_task_id", "private task"),
    ]
    for field, private_value in disallowed:
        payload = valid_payload()
        payload[field] = private_value
        response = client.post("/api/v1/runs/import", json=payload)
        assert response.status_code == 422
        assert str(private_value) not in response.text
        assert str(private_value) not in caplog.text

    for field in ("prompt_set", "concurrency"):
        payload = valid_payload()
        payload["benchmark_config"][field] = "private config"
        response = client.post("/api/v1/runs/import", json=payload)
        assert response.status_code == 422
        assert "private config" not in response.text

    response = client.post(
        "/api/v1/runs/import",
        content=b'{"format_version":"benchscope.run.v1","secret":"raw-secret"',
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 422
    assert "raw-secret" not in response.text
    assert (
        client.post(
            "/api/v1/runs/import",
            content=b"{}",
            headers={"content-type": "text/plain"},
        ).status_code
        == 422
    )

    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(BenchmarkRun)) == 0


@pytest.mark.parametrize(
    "change",
    [
        lambda value: value.update(format_version="benchscope.run.v2"),
        lambda value: value.update(started_at="2026-10-26T10:00:00"),
        lambda value: value["metrics"].update(prompt_tokens=1.5),
        lambda value: value["metrics"].update(quality_score=-1),
        lambda value: value["metrics"].update(pass_rate=2),
        lambda value: value["metrics"].update(elapsed_ms=1.5),
        lambda value: value.pop("ended_at"),
    ],
)
def test_unsupported_invalid_and_missing_values_return_422_without_writes(
    postgres_api: tuple[TestClient, Engine],
    change,
) -> None:
    client, engine = postgres_api
    payload = valid_payload()
    change(payload)
    response = client.post("/api/v1/runs/import", json=payload)

    assert response.status_code == 422
    assert response.json()["ok"] is False
    assert response.json()["errors"]
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(BenchmarkRun)) == 0


def test_import_transaction_failure_rolls_back(
    postgres_api: tuple[TestClient, Engine],
) -> None:
    client, engine = postgres_api

    def fail_after_insert(
        _connection, _cursor, statement: str, _parameters, _context, _executemany
    ) -> None:
        if "INSERT INTO benchmark_runs" in statement:
            raise RuntimeError("injected failure")

    event.listen(engine, "after_cursor_execute", fail_after_insert)
    try:
        response = client.post("/api/v1/runs/import", json=valid_payload())
    finally:
        event.remove(engine, "after_cursor_execute", fail_after_insert)

    assert response.status_code == 500
    assert "injected failure" not in response.text
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(BenchmarkRun)) == 0


def test_streaming_upload_size_boundary_and_above(
    postgres_api: tuple[TestClient, Engine],
) -> None:
    client, _engine = postgres_api
    body = json.dumps(valid_payload(), separators=(",", ":")).encode()
    client.app.state.settings.max_upload_bytes = len(body)

    at_limit = client.post(
        "/api/v1/runs/import",
        content=body,
        headers={"content-type": "application/json"},
    )
    over_limit = client.post(
        "/api/v1/runs/import",
        content=iter((body, b" ")),
        headers={"content-type": "application/json"},
    )

    assert at_limit.status_code == 201
    assert over_limit.status_code == 413
    assert over_limit.json()["status"] == 413
