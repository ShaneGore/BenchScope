import logging
from uuid import UUID

import psycopg
import pytest
from fastapi import Body
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.config import ConfigurationError, Settings, load_settings
from app.main import app as default_app
from app.main import create_app, database_is_ready


def test_default_app_exposes_liveness_and_correlated_logs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    correlation_id = "4a9cb0c4-8e92-46f2-a61e-9449bc06be82"
    with caplog.at_level(logging.INFO, logger="app.request"):
        response = TestClient(default_app).get(
            "/health", headers={"X-Correlation-ID": correlation_id}
        )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["X-Correlation-ID"] == correlation_id
    assert any(record.correlation_id == correlation_id for record in caplog.records)
    assert correlation_id in caplog.text


def test_personal_endpoint_authenticates_before_database_access() -> None:
    response = TestClient(default_app).get("/api/v1/profiles")

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


def test_invalid_hosted_settings_fail_without_exposing_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_MODE", "hosted")
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql://user:secret-password@example.invalid/db"
    )
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    monkeypatch.delenv("HOST", raising=False)

    with pytest.raises(ConfigurationError) as error:
        load_settings()

    assert "CORS_ORIGINS" in str(error.value)
    assert "HOST" in str(error.value)
    assert "secret-password" not in str(error.value)


def test_hosted_settings_load_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_MODE", "hosted")
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql://user:password@db.example/benchscope"
    )
    monkeypatch.setenv("CORS_ORIGINS", '["https://dashboard.example"]')
    monkeypatch.setenv("HOST", "0.0.0.0")
    monkeypatch.setenv("CLERK_JWKS_URL", "https://clerk.example/.well-known/jwks.json")
    monkeypatch.setenv("CLERK_ISSUER", "https://clerk.example")
    monkeypatch.setenv("CLERK_AUTHORIZED_PARTIES", '["https://dashboard.example"]')

    settings = load_settings()

    assert settings.app_mode == "hosted"
    assert settings.bind_host == "0.0.0.0"
    assert settings.cors_allow_origins == ["https://dashboard.example"]


def test_hosted_configuration_rejects_wildcard_origins() -> None:
    with pytest.raises(ValueError, match="wildcard"):
        Settings(
            app_mode="hosted",
            database_url=SecretStr("postgresql://localhost/benchscope"),
            cors_origins=["https://*.example.com"],
            host="0.0.0.0",
            clerk_jwks_url="https://clerk.example/.well-known/jwks.json",
            clerk_issuer="https://clerk.example",
            clerk_authorized_parties=["https://dashboard.example"],
        )


def test_local_configuration_defaults_to_loopback_and_permissive_cors() -> None:
    settings = Settings()

    assert settings.bind_host == "127.0.0.1"
    assert settings.cors_allow_origins == ["*"]


def test_non_loopback_bind_requires_explicit_hosted_mode() -> None:
    with pytest.raises(ValueError, match="APP_MODE=hosted"):
        Settings(host="0.0.0.0")


def test_cors_is_restricted_to_configured_origin() -> None:
    app = create_app(Settings(cors_origins=["https://dashboard.example"]))
    client = TestClient(app)
    allowed = client.options(
        "/health",
        headers={
            "Origin": "https://dashboard.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    denied = client.options(
        "/health",
        headers={
            "Origin": "https://other.example",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert allowed.status_code == 200
    assert allowed.headers["Access-Control-Allow-Origin"] == "https://dashboard.example"
    assert denied.status_code == 400
    assert "Access-Control-Allow-Origin" not in denied.headers
    UUID(allowed.headers["X-Correlation-ID"])


def test_health_does_not_depend_on_database_and_readiness_checks_it() -> None:
    checked_urls: list[str | None] = []
    app = create_app(readiness_probe=lambda url: checked_urls.append(url) or False)
    client = TestClient(app)

    assert client.get("/health").status_code == 200
    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "not_ready"}
    assert checked_urls == [None]


def test_readiness_returns_success_only_when_probe_succeeds() -> None:
    app = create_app(
        Settings(database_url=SecretStr("postgresql://db.example/benchscope")),
        readiness_probe=lambda url: url == "postgresql://db.example/benchscope",
    )

    response = TestClient(app).get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_database_probe_checks_the_database_not_only_its_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, int]] = []

    def unavailable(database_url: str, connect_timeout: int) -> None:
        calls.append((database_url, connect_timeout))
        raise psycopg.OperationalError("unavailable")

    monkeypatch.setattr("app.main.psycopg.connect", unavailable)

    assert database_is_ready(None) is False
    assert database_is_ready("postgresql://db.example/benchscope") is False
    assert database_is_ready("sqlite:///:memory:") is True
    assert calls == [("postgresql://db.example/benchscope", 2)]


def test_unhandled_errors_are_sanitized_and_keep_correlation_id(
    caplog: pytest.LogCaptureFixture,
) -> None:
    app = create_app()

    def fail() -> None:
        raise RuntimeError("private-password")

    app.add_api_route("/test-error", fail)
    with caplog.at_level(logging.ERROR, logger="app.request"):
        response = TestClient(app, raise_server_exceptions=False).get("/test-error")

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    assert UUID(response.headers["X-Correlation-ID"])
    assert "private-password" not in caplog.text


def test_validation_error_has_documented_sanitized_shape() -> None:
    app = create_app()

    def validate(amount: int = Body(embed=True)) -> dict[str, int]:
        return {"amount": amount}

    app.add_api_route("/test-validation", validate, methods=["POST"])

    response = TestClient(app).post("/test-validation", json={"amount": "secret-input"})

    assert response.status_code == 422
    assert response.json()["detail"]["amount"]
    assert "secret-input" not in response.text
