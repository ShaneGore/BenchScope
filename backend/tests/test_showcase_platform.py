"""Regression tests for deployment identity, startup preservation and skip policy."""

import importlib.util
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

ROOT = Path(__file__).resolve().parents[2]


def script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


@pytest.mark.parametrize(
    "build,provider,expected",
    [
        ("a" * 40, "b" * 40, "a" * 40),
        ("unknown", "b" * 40, "b" * 40),
        ("secret-value", "private-provider-value", "unknown"),
    ],
)
def test_version_exposes_only_valid_commit_metadata(
    monkeypatch, build, provider, expected
):
    monkeypatch.setenv("APP_REVISION", build)
    monkeypatch.setenv("RENDER_GIT_COMMIT", provider)
    response = TestClient(create_app()).get("/version")
    assert response.status_code == 200
    assert response.json() == {"revision": expected}


class FakeTime:
    def __init__(self):
        self.now = 0

    def clock(self):
        return self.now

    def sleep(self, amount):
        self.now += amount


def test_old_healthy_release_cannot_pass_deployment_verification():
    module = script("wait_for_deployment")
    timer = FakeTime()

    def fetch(url):
        return (
            {"revision": "a" * 40} if url.endswith("/version") else {"status": "ready"}
        )

    with pytest.raises(module.DeploymentVerificationError, match="expected commit"):
        module.wait_for_revision(
            "https://api.example",
            "b" * 40,
            timeout=3,
            interval=1,
            fetch=fetch,
            clock=timer.clock,
            pause=timer.sleep,
        )
    assert timer.now == 3


def test_deployment_waits_for_new_revision_and_readiness_together():
    module = script("wait_for_deployment")
    timer = FakeTime()

    def fetch(url):
        if url.endswith("/version"):
            return {"revision": ("a" if timer.now < 1 else "b") * 40}
        return {"status": "not_ready" if timer.now < 2 else "ready"}

    module.wait_for_revision(
        "https://api.example",
        "b" * 40,
        timeout=4,
        interval=1,
        fetch=fetch,
        clock=timer.clock,
        pause=timer.sleep,
    )
    assert timer.now == 2


def test_deployment_rejects_unknown_expected_revision():
    module = script("wait_for_deployment")
    with pytest.raises(ValueError, match="exact"):
        module.wait_for_revision("https://api.example", "main")


def test_start_preserves_existing_configuration(monkeypatch, tmp_path):
    module = script("start")
    monkeypatch.setattr(module, "ROOT", tmp_path)
    existing = "POSTGRES_PASSWORD=existing\nAPP_MODE=local\nAPP_ENV=development\nLOCAL_AUTH_BYPASS=false\n"
    (tmp_path / ".env").write_text(existing)
    for name in ("APP_MODE", "APP_ENV", "LOCAL_AUTH_BYPASS", "POSTGRES_PASSWORD"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(RuntimeError, match="existing configuration was preserved"):
        module.prepare_environment()
    assert (tmp_path / ".env").read_text() == existing


def test_start_core_does_not_need_alert_secrets(monkeypatch, tmp_path):
    module = script("start")
    monkeypatch.setattr(module, "ROOT", tmp_path)
    (tmp_path / ".env.example").write_text(
        "POSTGRES_PASSWORD=replace-with-a-local-url-safe-password\nAPP_MODE=local\nAPP_ENV=development\nLOCAL_AUTH_BYPASS=false\n"
    )
    for name in ("APP_MODE", "APP_ENV", "LOCAL_AUTH_BYPASS", "POSTGRES_PASSWORD"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(
        module,
        "run",
        lambda *args, **kwargs: type("Result", (), {"stdout": "a" * 40})(),
    )
    env = module.prepare_environment()
    assert env["LOCAL_AUTH_BYPASS"] == "true"
    assert len(env["POSTGRES_PASSWORD"]) == 48
    assert not (tmp_path / "secrets").exists()


def test_verification_rejects_skipped_database_tests(tmp_path):
    module = script("verify")
    report = tmp_path / "report.xml"
    report.write_text(
        '<testsuite><testcase name="database"><skipped message="Set TEST_DATABASE_URL" /></testcase></testsuite>'
    )
    with pytest.raises(RuntimeError, match="Unexpected backend skip"):
        module.verify_backend_report(report)


def test_selected_ports_are_distinct_and_free():
    module = script("verify")
    ports = module.free_ports(8)
    assert len(set(ports)) == 8
    assert all(0 < int(port) < 65536 for port in ports)


def test_backend_workflows_resolve_and_verify_requested_revision():
    for filename in ("deploy-backend.yml", "promote-production.yml"):
        content = (ROOT / ".github" / "workflows" / filename).read_text()
        assert 'selected_ref="${INPUT_REF:-main}"' in content
        assert "git rev-parse HEAD" in content
        assert "git merge-base --is-ancestor HEAD origin/main" in content
        assert "legacy revision lacks deployment identity support" in content
        assert "SELECTED_REF: ${{ steps.revision.outputs.sha }}" in content
        assert "EXPECTED_REVISION: ${{ steps.revision.outputs.sha }}" in content
        assert "python scripts/wait_for_deployment.py" in content
        assert "curl --fail --silent" not in content
