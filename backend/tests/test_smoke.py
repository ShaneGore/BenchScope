from fastapi import FastAPI

from app.main import app


def test_application_shell_registers_health_and_profile_routes() -> None:
    assert isinstance(app, FastAPI)
    assert set(app.openapi()["paths"]) == {
        "/health",
        "/ready",
        "/api/v1/profiles",
        "/api/v1/profiles/{id}",
        "/api/v1/runs",
        "/api/v1/runs/compare",
        "/api/v1/runs/{id}",
        "/api/v1/runs/import",
    }
