import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.mark.parametrize(
    ("app_mode", "benchmark_enabled", "expected"),
    [
        ("local", True, True),
        ("local", False, False),
        ("hosted", True, False),
        ("hosted", False, False),
    ],
)
def test_capability_is_exact_and_runner_routes_remain_local_only(
    app_mode: str, benchmark_enabled: bool, expected: bool
) -> None:
    settings = Settings.model_construct(
        app_mode=app_mode, benchmark_enabled=benchmark_enabled
    )
    client = TestClient(create_app(settings))

    capability = client.get("/api/v1/benchmark/capabilities")
    assert capability.status_code == 200
    assert capability.json() == {"enabled": expected}

    runner = client.get("/api/v1/benchmark/runs/00000000-0000-0000-0000-000000000001")
    assert runner.status_code == (401 if expected else 404)
