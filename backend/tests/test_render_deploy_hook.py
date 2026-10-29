import subprocess
import sys
import urllib.error
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "render_deploy_hook.py"
SMOKE = ROOT / "scripts" / "smoke_test.py"


def _load_module():
    import importlib.util

    spec = importlib.util.spec_from_file_location("render_deploy_hook", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_build_deploy_url_preserves_secret_query_parameter():
    module = _load_module()
    hook_url = "https://api.render.com/deploy/srv-123?key=secret-value"
    ref = "a" * 40
    result = module.build_deploy_url(hook_url, ref)

    parsed = urlparse(result)
    query = parse_qs(parsed.query)
    assert parsed.scheme == "https"
    assert parsed.netloc == "api.render.com"
    assert query["key"] == ["secret-value"]
    assert query["ref"] == [ref]
    assert result.count("?") == 1


def test_build_deploy_url_replaces_existing_ref():
    module = _load_module()
    hook_url = "https://api.render.com/deploy/srv-123?key=secret&ref=oldref"
    ref = "b" * 40
    result = module.build_deploy_url(hook_url, ref)
    query = parse_qs(urlparse(result).query)
    assert query["ref"] == [ref]
    assert query["key"] == ["secret"]


def test_build_deploy_url_rejects_malformed_url():
    module = _load_module()
    with pytest.raises(ValueError):
        module.build_deploy_url("not-a-url", "a" * 40)


def test_build_deploy_url_rejects_bad_sha():
    module = _load_module()
    with pytest.raises(ValueError):
        module.build_deploy_url("https://api.render.com/deploy/srv-123?key=secret", "not-a-sha")


def test_trigger_deploy_redacts_failures(monkeypatch):
    module = _load_module()

    class FakeError(Exception):
        pass

    def fail(_request, timeout=30):
        raise urllib.error.HTTPError(
            "https://api.render.com/deploy/srv-123?key=secret",
            404,
            "Not Found",
            {},
            None,
        )

    monkeypatch.setattr(module.urllib.request, "urlopen", fail)
    with pytest.raises(module.DeployHookError) as exc:
        module.trigger_deploy("https://api.render.com/deploy/srv-123?key=secret", "a" * 40)
    assert "secret" not in str(exc.value)
    assert "api.render.com" not in str(exc.value)


def test_smoke_full_mode_requires_token():
    result = subprocess.run(
        [sys.executable, str(SMOKE), "--api-url", "http://127.0.0.1:8000", "--mode", "full"],
        capture_output=True,
        check=False,
        text=True,
        env={"SMOKE_FRONTEND_URL": "http://127.0.0.1:8000", "PATH": __import__("os").environ.get("PATH", "")},
    )
    assert result.returncode != 0
    assert "SMOKE_TEST_TOKEN" in (result.stdout + result.stderr)


def test_smoke_production_mode_requires_token():
    result = subprocess.run(
        [sys.executable, str(SMOKE), "--api-url", "http://127.0.0.1:8000", "--mode", "production"],
        capture_output=True,
        check=False,
        text=True,
        env={"SMOKE_FRONTEND_URL": "http://127.0.0.1:8000", "PATH": __import__("os").environ.get("PATH", "")},
    )
    assert result.returncode != 0
    assert "SMOKE_TEST_TOKEN" in (result.stdout + result.stderr)


def test_smoke_health_mode_does_not_require_token():
    result = subprocess.run(
        [sys.executable, str(SMOKE), "--api-url", "http://127.0.0.1:1", "--mode", "health"],
        capture_output=True,
        text=True,
        check=False,
    )
    # The health request itself fails, but argument/configuration validation passes.
    assert "SMOKE_TEST_TOKEN" not in (result.stdout + result.stderr)
