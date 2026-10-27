from fastapi import FastAPI

from app.main import app


def test_application_registers_health_personal_and_demo_routes() -> None:
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
        "/api/v1/benchmark/capabilities",
        "/api/v1/demo/runs",
        "/api/v1/demo/runs/{id}",
    }
