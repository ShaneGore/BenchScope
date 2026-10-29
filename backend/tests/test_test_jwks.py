import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from jwt import PyJWKClientConnectionError
from pydantic import SecretStr

from app.auth import _jwks_client
from app.config import Settings


def _settings(url: str, **values: object) -> Settings:
    settings: dict[str, object] = {
        "app_mode": "local",
        "app_env": "test",
        "local_auth_bypass": False,
        "host": "127.0.0.1",
        "database_url": SecretStr("postgresql://db.example.invalid/benchscope"),
        "cors_origins": ["https://dashboard.example.invalid"],
        "clerk_jwks_url": url,
        "clerk_issuer": "https://issuer.example.invalid",
        "clerk_authorized_parties": ["https://dashboard.example.invalid"],
    }
    settings.update(values)
    return Settings(**settings)


def test_http_jwks_is_allowed_for_test_local_loopback_only() -> None:
    settings = _settings("http://127.0.0.1:8001/jwks")

    assert settings.test_local_http_jwks
    assert settings.local_auth_bypass is False


@pytest.mark.parametrize(
    ("values", "message"),
    [
        ({"app_env": "production"}, "HTTP CLERK_JWKS_URL"),
        ({"app_mode": "hosted"}, "HTTP CLERK_JWKS_URL"),
        ({"local_auth_bypass": True}, "LOCAL_AUTH_BYPASS"),
        ({"host": "0.0.0.0"}, "Non-loopback HOST"),
    ],
)
def test_http_jwks_rejects_other_profiles(
    values: dict[str, object], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        _settings("http://127.0.0.1/jwks", **values)


@pytest.mark.parametrize("resolution", ["unresolved", "mixed"])
def test_http_jwks_rejects_unresolved_or_non_loopback_dns(
    monkeypatch: pytest.MonkeyPatch, resolution: str
) -> None:
    original_getaddrinfo = socket.getaddrinfo

    def fake_getaddrinfo(host: str, *args: object, **kwargs: object):
        if host == "jwks.example.invalid":
            if resolution == "unresolved":
                raise socket.gaierror("name resolution failed")
            return [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 0)),
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("203.0.113.10", 0)),
            ]
        return original_getaddrinfo(host, *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
    with pytest.raises(ValueError, match="loopback-only"):
        _settings("http://jwks.example.invalid/jwks")


def test_http_test_fetcher_does_not_follow_redirects() -> None:
    class RedirectHandler(BaseHTTPRequestHandler):
        requests = 0

        def do_GET(self) -> None:
            type(self).requests += 1
            self.send_response(302)
            self.send_header("Location", "http://203.0.113.10/jwks")
            self.end_headers()

        def log_message(self, _format: str, *_args: object) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), RedirectHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    _jwks_client.cache_clear()
    try:
        client = _jwks_client(
            f"http://127.0.0.1:{server.server_port}/jwks",
            allow_test_http=True,
        )
        with pytest.raises(PyJWKClientConnectionError):
            client.fetch_data()
        assert RedirectHandler.requests == 1
    finally:
        server.shutdown()
        thread.join()
        server.server_close()
        _jwks_client.cache_clear()
