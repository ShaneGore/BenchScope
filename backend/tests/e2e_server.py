"""Disposable local API harness for Playwright journeys; never imported by the app."""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import threading
import time
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import jwt
import uvicorn
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from jwt import PyJWKClient
from pydantic import SecretStr
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.config import Settings, resolved_loopback_addresses
from app.database import sqlalchemy_database_url
from app.models import Base, BenchmarkRun
from app.runner import RunResult

ISSUER = "https://benchscope-e2e.invalid"
AUDIENCE = "benchscope-e2e"
JWKS_PORT = 8001
LOCAL_SUBJECTS = ("e2e-owner-a", "e2e-owner-b")
SUCCESS_CONFIG = UUID("00000000-0000-4000-8000-000000000001")
FAILURE_CONFIG = UUID("00000000-0000-4000-8000-000000000002")
TIMEOUT_CONFIG = UUID("00000000-0000-4000-8000-000000000003")


class FakeE2EAdapter:
    """Synthetic outcomes selected by UUID, injected by this harness only."""

    def __init__(self) -> None:
        self.failures = 0

    async def run(self, _profile: dict[str, str | None], config_id: UUID) -> RunResult:
        if config_id == FAILURE_CONFIG and self.failures == 0:
            self.failures += 1
            raise RuntimeError("synthetic adapter failure")
        if config_id == TIMEOUT_CONFIG:
            await asyncio.sleep(5)
        else:
            await asyncio.sleep(0.02)
        return RunResult(quality_score=0.75, prompt_tokens=12)


def _db_urls(schema: str) -> tuple[str, str]:
    if not re.fullmatch(r"benchscope_e2e_[a-f0-9]{16}", schema):
        raise ValueError("Invalid E2E schema name")
    raw_url = os.environ.get("TEST_DATABASE_URL", "")
    if not raw_url:
        raise ValueError(
            "TEST_DATABASE_URL must point to a local PostgreSQL test database"
        )
    base = make_url(raw_url)
    if base.get_backend_name() != "postgresql":
        raise ValueError("TEST_DATABASE_URL must use PostgreSQL")
    if not base.host or not resolved_loopback_addresses(base.host):
        raise ValueError("TEST_DATABASE_URL must resolve exclusively to loopback")
    sql_url = make_url(sqlalchemy_database_url(raw_url))
    scoped_sql_url = sql_url.update_query_dict({"options": f"-csearch_path={schema}"})
    setting_url = (
        base.set(drivername="postgresql")
        .update_query_dict({"options": f"-csearch_path={schema}"})
        .render_as_string(hide_password=False)
    )
    return setting_url, scoped_sql_url.render_as_string(hide_password=False)


def _settings(database_url: str, *, hosted: bool = False) -> Settings:
    os.environ["DATABASE_URL"] = database_url
    settings = Settings(
        app_mode="hosted" if hosted else "local",
        app_env="test",
        local_auth_bypass=False,
        host="127.0.0.1",
        port=int(os.environ.get("PORT", "8000")),
        benchmark_enabled=not hosted,
        benchmark_timeout_seconds=0.25,
        cors_origins=["http://127.0.0.1:5174" if hosted else "http://127.0.0.1:5173"],
        clerk_jwks_url=(
            "https://clerk.example.invalid/.well-known/jwks.json"
            if hosted
            else f"http://127.0.0.1:{JWKS_PORT}/.well-known/jwks.json"
        ),
        clerk_issuer=ISSUER,
        clerk_audience=AUDIENCE,
    )
    if settings.app_env != "test" or settings.local_auth_bypass:
        raise ValueError("E2E authentication profile must stay bypass-free")
    return settings


def _credentials(path: Path) -> dict[str, Any]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    kid = uuid4().hex
    public_jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(public_key))
    public_jwk.update({"kid": kid, "use": "sig", "alg": "RS256"})
    tokens = {
        subject: jwt.encode(
            {
                "sub": subject,
                "iss": ISSUER,
                "aud": AUDIENCE,
                "exp": int(time.time()) + 600,
            },
            private_key,
            algorithm="RS256",
            headers={"kid": kid},
        )
        for subject in LOCAL_SUBJECTS
    }

    class JwksHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path != "/.well-known/jwks.json":
                self.send_error(404)
                return
            body = json.dumps({"keys": [public_jwk]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format: str, *_args: object) -> None:
            pass

    jwks_server = ThreadingHTTPServer(("127.0.0.1", JWKS_PORT), JwksHandler)
    jwks_thread = threading.Thread(target=jwks_server.serve_forever, daemon=True)
    jwks_thread.start()
    return {
        "jwks_server": jwks_server,
        "jwks_thread": jwks_thread,
        "tokens": tokens,
    }


def _write_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(state), encoding="utf-8")
    temporary.replace(path)


def _serve() -> None:
    schema = os.environ["E2E_SCHEMA"]
    hosted = os.environ.get("APP_MODE") == "hosted"
    setting_url, sql_url = _db_urls(schema)
    base_engine = create_engine(
        sqlalchemy_database_url(os.environ["TEST_DATABASE_URL"])
    )
    jwks: dict[str, Any] | None = None
    api_engine = None
    state_path = Path(os.environ["E2E_STATE_FILE"])
    state: dict[str, Any] = {
        "mode": "hosted" if hosted else "local",
        "jwks_fetches": 0,
        "tokens": {},
    }
    try:
        with base_engine.begin() as connection:
            connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
        settings = _settings(setting_url, hosted=hosted)
        api_engine = create_engine(sql_url)
        Base.metadata.create_all(api_engine)

        adapter = None
        if not hosted:
            jwks = _credentials(state_path)
            state["tokens"] = jwks["tokens"]
            state["subjects"] = LOCAL_SUBJECTS
            _write_state(state_path, state)
            adapter = FakeE2EAdapter()
        else:
            original_fetch_data = PyJWKClient.fetch_data

            def count_jwks_fetch(client: PyJWKClient):
                state["jwks_fetches"] += 1
                _write_state(state_path, state)
                return original_fetch_data(client)

            PyJWKClient.fetch_data = count_jwks_fetch
            _write_state(state_path, state)

        from app.main import create_app

        app = create_app(settings, benchmark_adapter=adapter)
        uvicorn.run(
            app,
            host=settings.bind_host,
            port=settings.port,
            log_level="warning",
        )
    finally:
        if jwks is not None:
            jwks["jwks_server"].shutdown()
            jwks["jwks_thread"].join()
            jwks["jwks_server"].server_close()
        if api_engine is not None:
            api_engine.dispose()
        with base_engine.begin() as connection:
            connection.exec_driver_sql(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        base_engine.dispose()
        state_path.unlink(missing_ok=True)


def _recover(profile_id: UUID, owner_id: str) -> None:
    schema = os.environ["E2E_SCHEMA"]
    setting_url, sql_url = _db_urls(schema)
    engine = create_engine(sql_url)
    profile_snapshot = {"name": "E2E lifecycle profile", "model_name": "synthetic/e2e"}
    config_id = uuid4()
    try:
        with Session(engine) as session:
            run = BenchmarkRun(
                owner_id=owner_id,
                source="launched",
                status="running",
                profile_id=profile_id,
                profile_snapshot=profile_snapshot,
                benchmark_config={"config_id": str(config_id)},
                started_at=datetime.now(UTC),
            )
            session.add(run)
            session.commit()
            run_id = run.id

        settings = Settings(
            app_mode="local",
            app_env="test",
            local_auth_bypass=False,
            database_url=SecretStr(setting_url),
            host="127.0.0.1",
            benchmark_enabled=True,
        )
        from app.main import create_app

        with TestClient(create_app(settings)):
            pass
        print(run_id)
    finally:
        engine.dispose()


def _cleanup() -> None:
    schema = os.environ["E2E_SCHEMA"]
    _, _ = _db_urls(schema)
    engine = create_engine(sqlalchemy_database_url(os.environ["TEST_DATABASE_URL"]))
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
    finally:
        engine.dispose()
        Path(os.environ["E2E_STATE_FILE"]).unlink(missing_ok=True)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "recover":
        _recover(UUID(sys.argv[2]), sys.argv[3])
    elif len(sys.argv) > 1 and sys.argv[1] == "cleanup":
        _cleanup()
    else:
        _serve()
