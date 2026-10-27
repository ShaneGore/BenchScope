import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from alembic import command
from app.config import Settings
from app.database import LOCAL_OWNER_ID, sqlalchemy_database_url
from app.main import create_app
from app.models import BenchmarkRun

BACKEND_DIR = os.path.dirname(os.path.dirname(__file__))


@pytest.fixture
def history_api() -> Iterator[tuple[TestClient, Engine]]:
    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("Set TEST_DATABASE_URL to run PostgreSQL run history tests")
    if make_url(database_url).get_backend_name() != "postgresql":
        pytest.fail("TEST_DATABASE_URL must use PostgreSQL")

    admin_engine = create_engine(sqlalchemy_database_url(database_url))
    schema = f"benchscope_history_{uuid4().hex}"
    app_engine: Engine | None = None
    try:
        with admin_engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))

        schema_url = make_url(sqlalchemy_database_url(database_url)).update_query_dict(
            {"options": f"-csearch_path={schema}"}
        )
        app = create_app(
            Settings(
                app_env="development",
                local_auth_bypass=True,
                database_url=SecretStr(
                    schema_url.render_as_string(hide_password=False)
                ),
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


def _make_run(
    *,
    owner_id: str = LOCAL_OWNER_ID,
    model: str = "example/model",
    status: str = "completed",
    started_at: datetime = datetime(2026, 1, 1, tzinfo=UTC),
    id: UUID | None = None,
    **values: object,
) -> BenchmarkRun:
    return BenchmarkRun(
        id=id or uuid4(),
        owner_id=owner_id,
        source="imported",
        status=status,
        profile_snapshot={"name": "Snapshot", "model_name": model},
        benchmark_config={"name": "short"},
        started_at=started_at,
        completed_at=started_at + timedelta(seconds=1)
        if status == "completed"
        else None,
        **values,
    )


def _save(engine: Engine, *runs: BenchmarkRun) -> None:
    with Session(engine, expire_on_commit=False) as session:
        session.add_all(runs)
        session.commit()


def test_list_run_filters_dates_empty_and_invalid_values(
    history_api: tuple[TestClient, Engine],
) -> None:
    client, engine = history_api
    first = _make_run(started_at=datetime(2026, 1, 1, 10, tzinfo=UTC))
    second = _make_run(
        model="example/model",
        status="failed",
        started_at=datetime(2026, 1, 1, 11, tzinfo=UTC),
    )
    third = _make_run(
        model="other/model",
        started_at=datetime(2026, 1, 1, 12, tzinfo=UTC),
    )
    fourth = _make_run(
        model="example/model",
        status="interrupted",
        started_at=datetime(2026, 1, 1, 13, tzinfo=UTC),
    )
    other_owner = _make_run(
        owner_id="someone-else",
        started_at=datetime(2026, 1, 1, 14, tzinfo=UTC),
    )
    _save(engine, first, second, third, fourth, other_owner)

    by_model = client.get("/api/v1/runs", params={"model": "example/model"}).json()
    by_status = client.get("/api/v1/runs", params={"status": "failed"}).json()
    by_from = client.get(
        "/api/v1/runs", params={"from": "2026-01-01T12:00:00+02:00"}
    ).json()
    by_to = client.get("/api/v1/runs", params={"to": "2026-01-01T12:00:00Z"}).json()
    combined = client.get(
        "/api/v1/runs",
        params={
            "model": "example/model",
            "status": "completed",
            "from": "2026-01-01T12:00:00+02:00",
            "to": "2026-01-01T12:00:00Z",
        },
    ).json()
    empty = client.get("/api/v1/runs", params={"model": "missing/model"}).json()

    assert {item["id"] for item in by_model["items"]} == {
        str(first.id),
        str(second.id),
        str(fourth.id),
    }
    assert [item["id"] for item in by_status["items"]] == [str(second.id)]
    assert {item["id"] for item in by_from["items"]} == {
        str(first.id),
        str(second.id),
        str(third.id),
        str(fourth.id),
    }
    assert {item["id"] for item in by_to["items"]} == {
        str(first.id),
        str(second.id),
    }
    assert [item["id"] for item in combined["items"]] == [str(first.id)]
    assert empty == {"items": [], "next_cursor": None, "has_more": False}
    assert client.get("/api/v1/runs", params={"status": "unknown"}).status_code == 422
    assert (
        client.get("/api/v1/runs", params={"from": "2026-01-01T10:00:00"}).status_code
        == 422
    )
    assert (
        client.get(
            "/api/v1/runs",
            params={
                "from": "2026-01-01T10:00:00Z",
                "to": "2026-01-01T10:00:00Z",
            },
        ).status_code
        == 422
    )
    assert client.get("/api/v1/runs", params={"limit": 101}).status_code == 422


def test_cursor_pagination_is_deterministic_and_filter_scoped(
    history_api: tuple[TestClient, Engine],
) -> None:
    client, engine = history_api
    started_at = datetime(2026, 1, 1, 10, tzinfo=UTC)
    ordered = [
        _make_run(id=UUID(int=value), started_at=started_at) for value in (1, 2, 3)
    ]
    foreign = _make_run(
        owner_id="someone-else",
        id=UUID(int=4),
        started_at=started_at,
    )
    _save(engine, *ordered, foreign)

    first_page = client.get("/api/v1/runs", params={"limit": 1})
    first_data = first_page.json()
    second_page = client.get(
        "/api/v1/runs",
        params={"limit": 1, "cursor": first_data["next_cursor"]},
    )
    second_data = second_page.json()

    assert first_data["items"][0]["id"] == str(ordered[2].id)
    assert first_data["has_more"] is True
    assert second_data["items"][0]["id"] == str(ordered[1].id)
    assert second_data["has_more"] is True
    assert client.get(
        "/api/v1/runs",
        params={"model": "different", "cursor": str(ordered[2].id)},
    ).json() == {"detail": "Invalid cursor"}
    assert client.get("/api/v1/runs", params={"cursor": str(foreign.id)}).json() == {
        "detail": "Invalid cursor"
    }
    assert client.get("/api/v1/runs", params={"cursor": str(uuid4())}).json() == {
        "detail": "Invalid cursor"
    }
    invalid_cursor = client.get("/api/v1/runs", params={"cursor": "not-a-uuid"})
    assert invalid_cursor.status_code == 422
    assert invalid_cursor.json() == {"detail": "Invalid cursor"}


def test_detail_and_delete_are_owner_scoped_and_preserve_child_runs(
    history_api: tuple[TestClient, Engine],
) -> None:
    client, engine = history_api
    owned = _make_run()
    child = _make_run(related_run_id=owned.id)
    foreign = _make_run(owner_id="someone-else")
    _save(engine, owned, child, foreign)

    assert client.get(f"/api/v1/runs/{owned.id}").status_code == 200
    owned_missing = client.get(f"/api/v1/runs/{uuid4()}")
    other_owner = client.get(f"/api/v1/runs/{foreign.id}")
    assert owned_missing.status_code == other_owner.status_code == 404
    assert owned_missing.json() == other_owner.json() == {"detail": "Run not found"}

    assert client.delete(f"/api/v1/runs/{foreign.id}").status_code == 404
    with Session(engine) as session:
        assert session.get(BenchmarkRun, foreign.id) is not None

    assert client.delete(f"/api/v1/runs/{owned.id}").status_code == 204
    with Session(engine) as session:
        assert session.get(BenchmarkRun, owned.id) is None
        surviving_child = session.get(BenchmarkRun, child.id)
        assert surviving_child is not None
        assert surviving_child.related_run_id is None


def test_compare_rejects_invalid_batches_and_returns_only_owned_completed_runs(
    history_api: tuple[TestClient, Engine],
) -> None:
    client, engine = history_api
    completed_with_null = _make_run(quality_score=None, pass_rate=0)
    completed_zero = _make_run(quality_score=0, pass_rate=None)
    failed = _make_run(status="failed")
    interrupted = _make_run(status="interrupted")
    running = _make_run(status="running")
    foreign = _make_run(owner_id="someone-else")
    _save(
        engine,
        completed_with_null,
        completed_zero,
        failed,
        interrupted,
        running,
        foreign,
    )

    response = client.get(
        "/api/v1/runs/compare",
        params={
            "ids": ",".join(
                str(run.id)
                for run in (
                    interrupted,
                    completed_zero,
                    running,
                    completed_with_null,
                    failed,
                )
            )
        },
    )
    assert response.status_code == 200
    compared = response.json()
    assert [item["id"] for item in compared] == [
        str(completed_zero.id),
        str(completed_with_null.id),
    ]
    assert compared[0]["metrics"]["quality_score"] == 0
    assert compared[0]["metrics"]["pass_rate"] is None
    assert compared[1]["metrics"]["quality_score"] is None
    assert compared[1]["metrics"]["pass_rate"] == 0

    missing = client.get(
        "/api/v1/runs/compare",
        params={"ids": f"{completed_zero.id},{uuid4()}"},
    )
    non_owned = client.get(
        "/api/v1/runs/compare",
        params={"ids": f"{completed_zero.id},{foreign.id}"},
    )
    assert missing.status_code == non_owned.status_code == 404
    assert missing.json() == non_owned.json() == {"detail": "Run not found"}
    assert (
        client.get(
            "/api/v1/runs/compare",
            params={"ids": f"{completed_zero.id},{failed.id}"},
        ).status_code
        == 422
    )
    assert (
        client.get(
            "/api/v1/runs/compare",
            params={"ids": f"{completed_zero.id},{completed_zero.id}"},
        ).status_code
        == 422
    )
    assert (
        client.get(
            "/api/v1/runs/compare", params={"ids": f"{completed_zero.id},bad"}
        ).status_code
        == 422
    )
    assert (
        client.get(
            "/api/v1/runs/compare", params={"ids": str(completed_zero.id)}
        ).status_code
        == 422
    )
