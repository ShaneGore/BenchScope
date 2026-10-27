from fastapi import FastAPI

from app.main import app


def test_application_shell_registers_health_and_profile_routes() -> None:
    assert isinstance(app, FastAPI)
    assert set(app.openapi()["paths"]) == {
        "/health",
        "/ready",
        "/profiles",
        "/profiles/{id}",
        "/runs/import",
    }
