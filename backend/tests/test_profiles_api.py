from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.database import LOCAL_OWNER_ID
from app.main import create_app
from app.models import Base, BenchmarkRun, ModelProfile


@pytest.fixture
def local_api(tmp_path: Path) -> Iterator[tuple[TestClient, Engine]]:
    database_url = f"sqlite:///{tmp_path / 'profiles.db'}"
    app = create_app(Settings(database_url=SecretStr(database_url)))
    Base.metadata.create_all(app.state.engine)
    with TestClient(app) as client:
        yield client, app.state.engine


@pytest.fixture
def hosted_api(tmp_path: Path) -> Iterator[tuple[TestClient, Engine]]:
    database_url = f"sqlite:///{tmp_path / 'hosted-profiles.db'}"
    settings = Settings.model_construct(
        app_mode="hosted", database_url=SecretStr(database_url)
    )
    app = create_app(settings)
    Base.metadata.create_all(app.state.engine)
    with TestClient(app) as client:
        yield client, app.state.engine


def _create(client: TestClient, **values: object):
    return client.post(
        "/api/v1/profiles",
        json={"name": "Local model", "model_name": "example/model", **values},
    )


def test_local_profile_crud_keeps_data_as_data(
    local_api: tuple[TestClient, Engine],
) -> None:
    client, engine = local_api
    response = _create(
        client,
        endpoint_url="http://localhost:9000/v1/completions",
        inference_config={"temperature": 0.2},
        hardware_notes="GPU 1",
    )

    assert response.status_code == 201
    profile = response.json()
    assert profile["owner_id"] == "local"
    assert profile["endpoint_url"] == "http://localhost:9000/v1/completions"
    assert profile["inference_config"] == {"temperature": 0.2}
    profile_id = profile["id"]

    assert client.get("/api/v1/profiles").json() == [profile]
    assert client.get(f"/api/v1/profiles/{profile_id}").json() == profile
    updated = client.patch(
        f"/api/v1/profiles/{profile_id}",
        json={"quantisation": "Q4_K_M", "endpoint_url": "http://127.0.0.1:8001"},
    )
    assert updated.status_code == 200
    assert updated.json()["quantisation"] == "Q4_K_M"
    assert updated.json()["endpoint_url"] == "http://127.0.0.1:8001"

    with Session(engine) as session:
        run = BenchmarkRun(
            owner_id=LOCAL_OWNER_ID,
            source="imported",
            status="completed",
            profile_id=UUID(profile["id"]),
            profile_snapshot={"name": "Local model", "model_name": "example/model"},
            started_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        session.add(run)
        session.commit()
        run_id = run.id

    deleted = client.delete(f"/api/v1/profiles/{profile_id}")
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/profiles/{profile_id}").status_code == 404
    assert client.get("/api/v1/profiles").json() == []
    with Session(engine) as session:
        run = session.get(BenchmarkRun, run_id)
        assert run is not None
        assert run.profile_id is None
        assert run.profile_snapshot == {
            "name": "Local model",
            "model_name": "example/model",
        }


def test_profiles_are_isolated_to_fixed_local_owner(
    local_api: tuple[TestClient, Engine],
) -> None:
    client, engine = local_api
    with Session(engine) as session:
        other = ModelProfile(
            owner_id="another-local-user",
            name="Other profile",
            model_name="other/model",
        )
        session.add(other)
        session.commit()
        other_id = other.id

    assert client.get("/api/v1/profiles").json() == []
    assert client.get(f"/api/v1/profiles/{other_id}").status_code == 404
    assert (
        client.patch(
            f"/api/v1/profiles/{other_id}", json={"name": "Changed"}
        ).status_code
        == 404
    )
    assert client.delete(f"/api/v1/profiles/{other_id}").status_code == 404

    missing_id = "00000000-0000-0000-0000-000000000001"
    assert client.get(f"/api/v1/profiles/{missing_id}").status_code == 404
    assert (
        client.patch(
            f"/api/v1/profiles/{missing_id}", json={"name": "Changed"}
        ).status_code
        == 404
    )
    assert client.delete(f"/api/v1/profiles/{missing_id}").status_code == 404


def test_invalid_create_and_patch_are_rejected_without_writes(
    local_api: tuple[TestClient, Engine],
) -> None:
    client, engine = local_api
    invalid = _create(client, owner_id="attacker", api_key="do-not-return")
    missing_required = client.post("/api/v1/profiles", json={"name": "Missing model"})
    too_long = _create(client, name="x" * 256)
    embedded_userinfo = _create(
        client, endpoint_url="http://user:private-token@localhost/v1"
    )
    embedded_query_secret = _create(
        client, endpoint_url="http://localhost/v1?api_key=private-token"
    )

    assert invalid.status_code == 422
    assert missing_required.status_code == 422
    assert too_long.status_code == 422
    assert embedded_userinfo.status_code == 422
    assert embedded_query_secret.status_code == 422
    assert "do-not-return" not in invalid.text
    assert "private-token" not in embedded_userinfo.text
    assert "private-token" not in embedded_query_secret.text
    assert client.get("/api/v1/profiles").json() == []

    profile = _create(client).json()
    invalid_update = client.patch(
        f"/api/v1/profiles/{profile['id']}",
        json={"name": "Changed", "credential": "do-not-return"},
    )
    null_name = client.patch(f"/api/v1/profiles/{profile['id']}", json={"name": None})
    empty_update = client.patch(f"/api/v1/profiles/{profile['id']}", json={})
    embedded_secret_update = client.patch(
        f"/api/v1/profiles/{profile['id']}",
        json={
            "name": "Changed",
            "endpoint_url": "http://localhost/v1?api_key=private-token",
        },
    )

    assert invalid_update.status_code == 422
    assert null_name.status_code == 422
    assert empty_update.status_code == 422
    assert embedded_secret_update.status_code == 422
    assert "do-not-return" not in invalid_update.text
    assert "private-token" not in embedded_secret_update.text
    assert (
        client.get(f"/api/v1/profiles/{profile['id']}").json()["name"] == "Local model"
    )
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(ModelProfile)) == 1


@pytest.mark.parametrize(
    ("endpoint_url", "secret"),
    [
        ("http://user:" + "malformed-secret@[::1", "malformed-secret"),
        ("http://localhost/v1?sig=private-token", "private-token"),
        ("http://localhost/v1?signature=private-token", "private-token"),
        ("ftp://localhost/v1", "ftp://localhost"),
        ("http:///v1", "/v1"),
    ],
)
@pytest.mark.parametrize("operation", ["create", "update"])
def test_invalid_endpoint_urls_are_rejected_without_writes(
    local_api: tuple[TestClient, Engine],
    endpoint_url: str,
    secret: str,
    operation: str,
) -> None:
    client, engine = local_api
    profile = _create(client).json() if operation == "update" else None
    if operation == "create":
        response = _create(client, endpoint_url=endpoint_url)
    else:
        response = client.patch(
            f"/api/v1/profiles/{profile['id']}", json={"endpoint_url": endpoint_url}
        )

    assert response.status_code == 422
    assert secret not in response.text
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(ModelProfile)) == int(
            profile is not None
        )
    if profile is not None:
        stored = client.get(f"/api/v1/profiles/{profile['id']}").json()
        assert stored["endpoint_url"] is None


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("endpoint_url", "http://private.example/v1"),
        ("inference_config", {"api_key": "private-token"}),
    ],
)
def test_hosted_create_rejects_local_only_fields_without_persistence(
    hosted_api: tuple[TestClient, Engine], field: str, value: object
) -> None:
    client, engine = hosted_api

    response = _create(client, **{field: value})

    assert response.status_code == 422
    assert "private-token" not in response.text
    assert "private.example" not in response.text
    assert client.get("/api/v1/profiles").json() == []
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(ModelProfile)) == 0


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("endpoint_url", "http://private.example/v1"),
        ("inference_config", {"api_key": "private-token"}),
    ],
)
def test_hosted_update_rejects_local_only_fields_without_partial_write(
    hosted_api: tuple[TestClient, Engine], field: str, value: object
) -> None:
    client, engine = hosted_api
    profile = _create(client).json()

    response = client.patch(
        f"/api/v1/profiles/{profile['id']}",
        json={"name": "Changed", field: value},
    )

    assert response.status_code == 422
    assert "private-token" not in response.text
    assert "private.example" not in response.text
    stored = client.get(f"/api/v1/profiles/{profile['id']}").json()
    assert stored["name"] == "Local model"
    assert stored["endpoint_url"] is None
    assert stored["inference_config"] is None
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(ModelProfile)) == 1


def test_hosted_rejects_present_endpoint_even_when_null_and_credential_fields(
    hosted_api: tuple[TestClient, Engine],
) -> None:
    client, _ = hosted_api
    endpoint = _create(client, endpoint_url=None)
    credential = _create(client, api_key_ref="secret-reference")
    profile = _create(client).json()
    credential_update = client.patch(
        f"/api/v1/profiles/{profile['id']}", json={"api_key": "private-token"}
    )

    assert endpoint.status_code == 422
    assert credential.status_code == 422
    assert credential_update.status_code == 422
    assert "secret-reference" not in credential.text
    assert "private-token" not in credential_update.text
    assert client.get("/api/v1/profiles").json() == [profile]


def test_hosted_accepts_null_inference_config_update(
    hosted_api: tuple[TestClient, Engine],
) -> None:
    client, _ = hosted_api
    profile = _create(client).json()

    response = client.patch(
        f"/api/v1/profiles/{profile['id']}", json={"inference_config": None}
    )

    assert response.status_code == 200
    assert response.json()["inference_config"] is None
