import json
import time
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from jwt import PyJWKClient
from pydantic import SecretStr
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.config import ConfigurationError, Settings, load_settings
from app.main import create_app
from app.models import Base, BenchmarkRun, ModelProfile

ISSUER = "https://clerk.example"
AUDIENCE = "benchscope"
JWKS_URL = f"{ISSUER}/.well-known/jwks.json"


@pytest.fixture
def auth_api(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[tuple[TestClient, Engine, rsa.RSAPrivateKey]]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_jwk = json.loads(
        jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key())
    )
    public_jwk.update({"kid": "benchscope-test", "use": "sig", "alg": "RS256"})
    monkeypatch.setattr(
        PyJWKClient, "fetch_data", lambda _client: {"keys": [public_jwk]}
    )
    from app.auth import _jwks_client

    _jwks_client.cache_clear()
    settings = Settings.model_construct(
        app_mode="hosted",
        app_env="production",
        local_auth_bypass=False,
        database_url=SecretStr(f"sqlite:///{tmp_path / 'auth.db'}"),
        cors_origins=["https://dashboard.example"],
        host="0.0.0.0",
        clerk_jwks_url=JWKS_URL,
        clerk_issuer=ISSUER,
        clerk_audience=AUDIENCE,
    )
    app = create_app(settings)
    engine = app.state.engine
    assert engine is not None
    Base.metadata.create_all(engine)
    with TestClient(app) as client:
        yield client, engine, private_key
    engine.dispose()
    _jwks_client.cache_clear()


def _token(
    private_key: rsa.RSAPrivateKey,
    *,
    subject: str = "user-alice",
    issuer: str = ISSUER,
    audience: str = AUDIENCE,
    expires: int | None = None,
) -> str:
    return jwt.encode(
        {
            "sub": subject,
            "iss": issuer,
            "aud": audience,
            "exp": expires or int(time.time()) + 300,
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "benchscope-test"},
    )


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_personal_endpoints_reject_missing_and_invalid_tokens_generically(
    auth_api: tuple[TestClient, Engine, rsa.RSAPrivateKey],
) -> None:
    client, _, private_key = auth_api
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    missing_expiry = jwt.encode(
        {"sub": "user-alice", "iss": ISSUER, "aud": AUDIENCE},
        private_key,
        algorithm="RS256",
        headers={"kid": "benchscope-test"},
    )
    invalid_tokens = [
        "malformed",
        missing_expiry,
        _token(private_key, issuer="https://wrong.example"),
        _token(private_key, audience="other-app"),
        _token(private_key, expires=int(time.time()) - 1),
        _token(other_key),
    ]

    for path in ("/api/v1/profiles", "/api/v1/runs"):
        missing = client.get(path)
        assert missing.status_code == 401
        assert missing.json() == {"detail": "Not authenticated"}
        for token in invalid_tokens:
            response = client.get(path, headers=_headers(token))
            assert response.status_code == 401
            assert response.json() == missing.json()

    imported = client.post("/api/v1/runs/import", json={})
    assert imported.status_code == 401
    assert imported.json() == {"detail": "Not authenticated"}


def test_verified_subject_scopes_all_personal_record_operations(
    auth_api: tuple[TestClient, Engine, rsa.RSAPrivateKey],
) -> None:
    client, engine, private_key = auth_api
    alice = _headers(_token(private_key, subject="user-alice"))
    bob = _headers(_token(private_key, subject="user-bob"))

    own_profile = client.post(
        "/api/v1/profiles",
        headers=alice,
        json={"name": "Alice profile", "model_name": "alice/model"},
    )
    forged_owner = client.post(
        "/api/v1/profiles",
        headers=alice,
        json={
            "name": "Forged",
            "model_name": "forged/model",
            "owner_id": "user-bob",
        },
    )
    assert own_profile.status_code == 201
    assert own_profile.json()["owner_id"] == "user-alice"
    assert forged_owner.status_code == 422

    with Session(engine) as session:
        foreign_profile = ModelProfile(
            owner_id="user-bob",
            name="Bob profile",
            model_name="bob/model",
        )
        foreign_run = BenchmarkRun(
            owner_id="user-bob",
            source="imported",
            status="completed",
            profile_snapshot={"name": "Bob", "model_name": "bob/model"},
            benchmark_config={"name": "short"},
            started_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        own_run = BenchmarkRun(
            owner_id="user-alice",
            source="imported",
            status="completed",
            profile_snapshot={"name": "Alice", "model_name": "alice/model"},
            benchmark_config={"name": "short"},
            started_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        session.add_all([foreign_profile, foreign_run, own_run])
        session.commit()
        foreign_profile_id = foreign_profile.id
        foreign_run_id = foreign_run.id
        own_run_id = own_run.id

    assert [
        item["owner_id"]
        for item in client.get("/api/v1/profiles", headers=alice).json()
    ] == ["user-alice"]
    assert (
        client.get(f"/api/v1/profiles/{foreign_profile_id}", headers=alice).status_code
        == 404
    )
    assert (
        client.patch(
            f"/api/v1/profiles/{foreign_profile_id}",
            headers=alice,
            json={"name": "Stolen"},
        ).status_code
        == 404
    )
    assert (
        client.delete(
            f"/api/v1/profiles/{foreign_profile_id}", headers=alice
        ).status_code
        == 404
    )

    listed = client.get("/api/v1/runs?owner_id=user-bob", headers=alice).json()
    assert [item["owner_id"] for item in listed["items"]] == ["user-alice"]
    assert (
        client.get(f"/api/v1/runs/{foreign_run_id}", headers=alice).status_code == 404
    )
    assert (
        client.delete(f"/api/v1/runs/{foreign_run_id}", headers=alice).status_code
        == 404
    )
    assert (
        client.get(
            "/api/v1/runs/compare",
            params={"ids": f"{own_run_id},{foreign_run_id}"},
            headers=alice,
        ).status_code
        == 404
    )
    assert client.get(f"/api/v1/runs/{foreign_run_id}", headers=bob).status_code == 200

    with Session(engine) as session:
        assert session.get(ModelProfile, foreign_profile_id).name == "Bob profile"
        assert session.get(BenchmarkRun, foreign_run_id) is not None


def test_import_owner_is_verified_subject_not_request_data(
    auth_api: tuple[TestClient, Engine, rsa.RSAPrivateKey],
) -> None:
    client, _, private_key = auth_api
    token = _headers(_token(private_key, subject="user-importer"))
    payload = {
        "format_version": "benchscope.run.v1",
        "profile_snapshot": {"name": "Imported", "model_name": "model"},
        "benchmark_config": {"name": "short"},
        "started_at": "2026-01-01T00:00:00Z",
        "ended_at": "2026-01-01T00:00:01Z",
    }

    imported = client.post("/api/v1/runs/import", headers=token, json=payload)
    assert imported.status_code == 201
    assert imported.json()["run"]["owner_id"] == "user-importer"

    payload["owner_id"] = "attacker"
    rejected = client.post("/api/v1/runs/import", headers=token, json=payload)
    assert rejected.status_code == 422


def test_bypass_policy_fails_closed_for_invalid_combinations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert Settings().local_auth_bypass is False
    assert Settings(app_env="development", local_auth_bypass=True).bind_host_is_loopback
    assert Settings(
        app_env="development", local_auth_bypass=True, host="localhost"
    ).bind_host_is_loopback

    for values in (
        {"app_env": "production"},
        {"app_env": "staging"},
        {"app_mode": "hosted"},
        {"host": "0.0.0.0"},
    ):
        with pytest.raises(ValueError):
            Settings(**{"app_env": "development", "local_auth_bypass": True, **values})

    monkeypatch.setenv("LOCAL_AUTH_BYPASS", "true")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("APP_MODE", "local")
    with pytest.raises(ConfigurationError, match="LOCAL_AUTH_BYPASS"):
        load_settings()


def test_bad_token_never_appears_in_auth_response(
    auth_api: tuple[TestClient, Engine, rsa.RSAPrivateKey],
) -> None:
    client, _, _ = auth_api
    token = "do-not-log-this-token"
    response = client.get("/api/v1/profiles", headers=_headers(token))
    assert response.status_code == 401
    assert token not in response.text
