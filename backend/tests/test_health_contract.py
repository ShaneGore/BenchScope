from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoint_reports_service_liveness():
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_metrics_endpoint_is_mounted_when_telemetry_is_enabled():
    metrics_mounted = any(
        getattr(route, "path", None) == "/metrics" for route in app.routes
    )

    assert metrics_mounted is app.state.telemetry.enabled
