import importlib.util
import io
import json
import os
import subprocess
import sys
import urllib.error
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "generate_smoke_tokens.py"


def load_module():
    spec = importlib.util.spec_from_file_location("generate_smoke_tokens", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class FakeResponse:
    def __init__(self, payload: dict, status: int = 200):
        self._payload = payload
        self._status = status

    def getcode(self) -> int:
        return self._status

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_create_session_sends_expected_request(monkeypatch):
    module = load_module()
    captured = {}

    def fake_urlopen(request, timeout=10.0):
        captured["method"] = request.get_method()
        captured["url"] = request.full_url
        captured["authorization"] = request.headers.get("Authorization")
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse({"id": "sess_123"})

    monkeypatch.setattr(module.urllib.request, "urlopen", fake_urlopen)

    session_id = module.create_session("sk_test_secret", "user_abc")

    assert session_id == "sess_123"
    assert captured["method"] == "POST"
    assert captured["url"] == "https://api.clerk.com/v1/sessions"
    assert captured["authorization"] == "Bearer sk_test_secret"
    assert captured["body"] == {"user_id": "user_abc"}


def test_create_session_token_sends_expected_request(monkeypatch):
    module = load_module()
    captured = {}

    def fake_urlopen(request, timeout=10.0):
        captured["method"] = request.get_method()
        captured["url"] = request.full_url
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse({"jwt": "jwt-token-value"})

    monkeypatch.setattr(module.urllib.request, "urlopen", fake_urlopen)

    token = module.create_session_token(
        "sk_test_secret", "sess_123", expires_in_seconds=60
    )

    assert token == "jwt-token-value"
    assert captured["method"] == "POST"
    assert captured["url"] == "https://api.clerk.com/v1/sessions/sess_123/tokens"
    assert captured["body"] == {"expires_in_seconds": 60}


def test_generate_tokens_creates_two_distinct_users(monkeypatch):
    module = load_module()
    sessions = iter(["sess_a", "sess_b"])
    tokens = iter(["token-a", "token-b"])

    def fake_create_session(secret_key, user_id, **kwargs):
        assert secret_key == "sk_test_secret"
        return next(sessions)

    def fake_create_token(secret_key, session_id, **kwargs):
        assert secret_key == "sk_test_secret"
        return next(tokens)

    monkeypatch.setattr(module, "create_session", fake_create_session)
    monkeypatch.setattr(module, "create_session_token", fake_create_token)

    result = module.generate_tokens("sk_test_secret", "user_a", "user_b")

    assert result == {
        "SMOKE_TEST_TOKEN": "token-a",
        "SMOKE_OTHER_TEST_TOKEN": "token-b",
    }


def test_http_error_does_not_expose_secret_or_token(monkeypatch):
    module = load_module()

    def fake_urlopen(request, timeout=10.0):
        raise urllib.error.HTTPError(
            "https://api.clerk.com/v1/sessions",
            401,
            "Unauthorized",
            {},
            io.BytesIO(b'{"errors":[{"message":"bad key"}]}'),
        )

    monkeypatch.setattr(module.urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(module.SmokeCredentialError) as exc:
        module.create_session("sk_test_secret", "user_a")

    message = str(exc.value)
    assert "sk_test_secret" not in message
    assert "jwt" not in message
    assert "401" in message


def test_invalid_base_url_is_rejected():
    module = load_module()

    with pytest.raises(module.SmokeCredentialError):
        module.create_session("sk_test_secret", "user_a", base_url="http://api.clerk.com")


def test_cli_writes_env_file_without_printing_token(tmp_path, monkeypatch):
    module = load_module()
    output = tmp_path / "smoke.env"

    def fake_generate_tokens(*args, **kwargs):
        return {"SMOKE_TEST_TOKEN": "secret-token", "SMOKE_OTHER_TEST_TOKEN": "other-token"}

    monkeypatch.setattr(module, "generate_tokens", fake_generate_tokens)

    stdout = io.StringIO()
    monkeypatch.setattr(sys, "stdout", stdout)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "generate_smoke_tokens.py",
            "--secret-key",
            "sk_test_secret",
            "--user-a-id",
            "user_a",
            "--user-b-id",
            "user_b",
            "--env-file",
            str(output),
        ],
    )
    exit_code = module.main()

    assert exit_code == 0
    assert "secret-token" not in stdout.getvalue()
    assert "other-token" not in stdout.getvalue()
    content = output.read_text(encoding="utf-8")
    assert "SMOKE_TEST_TOKEN=secret-token" in content
    assert "SMOKE_OTHER_TEST_TOKEN=other-token" in content


def test_cli_requires_credentials():
    env = dict(os.environ)
    env.pop("CLERK_SECRET_KEY", None)
    env.pop("SMOKE_TEST_USER_A_ID", None)
    env.pop("SMOKE_TEST_USER_B_ID", None)
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert result.returncode == 2
    assert "CLERK_SECRET_KEY is required" in (result.stdout + result.stderr)
