from fastapi import FastAPI

from app.main import app


def test_application_shell_has_only_health_routes() -> None:
    assert isinstance(app, FastAPI)
    assert {route.path for route in app.routes} == {"/health", "/ready"}
