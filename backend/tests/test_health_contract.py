from fastapi.testclient import TestClient

from app.main import app, create_app
from app.observability import Telemetry


def test_health_endpoint_reports_service_liveness():
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_metrics_endpoint_is_mounted_when_telemetry_is_enabled():
    telemetry = Telemetry(enabled=True)
    test_app = create_app(telemetry=telemetry)

    with TestClient(test_app) as client:
        response = client.get("/metrics")

    assert response.status_code == 200
