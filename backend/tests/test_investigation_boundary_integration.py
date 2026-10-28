import os
import socket
import threading
import time
from pathlib import Path
from uuid import uuid4

import uvicorn
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import investigation_boundary as boundary
from app.models import Base, IncidentRecord
from tests.test_incident_investigation import _database_record


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _start_server(app, port: int) -> tuple[uvicorn.Server, threading.Thread]:
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.05)
    assert server.started, "boundary server did not start"
    return server, thread


def _stop_server(server, thread):
    server.should_exit = True
    thread.join(timeout=10)


def test_boundary_real_http_fetches_sanitised_evidence(tmp_path):
    db_path = tmp_path / "boundary.sqlite"
    db_url = f"sqlite:///{db_path}"
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        record = _database_record(session)
        record_id = record.id
    engine.dispose()

    app = boundary.create_investigation_boundary_app(db_url, secret="boundary-secret")
    port = _free_port()
    server, thread = _start_server(app, port)
    try:
        payload = boundary.fetch_persisted_evidence(
            f"http://127.0.0.1:{port}", record_id, "boundary-secret", timeout=5
        )
        assert payload["record_id"] == str(record_id)
        assert payload["evidence_status"] == "complete"
        assert "prometheus" in payload["evidence"]
        assert "SYNTHETIC" not in str(payload)
    finally:
        _stop_server(server, thread)


def test_boundary_real_http_rejects_auth_and_bad_ids(tmp_path):
    db_path = tmp_path / "boundary.sqlite"
    db_url = f"sqlite:///{db_path}"
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    engine.dispose()

    app = boundary.create_investigation_boundary_app(db_url, secret="boundary-secret")
    port = _free_port()
    server, thread = _start_server(app, port)
    try:
        import urllib.error
        import urllib.request

        url = f"http://127.0.0.1:{port}/v1/incidents/00000000-0000-0000-0000-000000000000/evidence"
        for headers in ({}, {"Authorization": "Bearer wrong"}):
            request = urllib.request.Request(url, headers=headers)
            try:
                urllib.request.urlopen(request, timeout=5)
                raise AssertionError("expected HTTP error")
            except urllib.error.HTTPError as exc:
                assert exc.code in (401, 404)

        bad_url = f"http://127.0.0.1:{port}/v1/incidents/not-a-uuid/evidence"
        request = urllib.request.Request(bad_url, headers={"Authorization": "Bearer boundary-secret"})
        try:
            urllib.request.urlopen(request, timeout=5)
            raise AssertionError("expected HTTP error")
        except urllib.error.HTTPError as exc:
            assert exc.code == 400
    finally:
        _stop_server(server, thread)


def test_boundary_real_http_missing_record_returns_404(tmp_path):
    db_path = tmp_path / "boundary.sqlite"
    db_url = f"sqlite:///{db_path}"
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    engine.dispose()

    app = boundary.create_investigation_boundary_app(db_url, secret="boundary-secret")
    port = _free_port()
    server, thread = _start_server(app, port)
    try:
        import urllib.error
        import urllib.request

        missing = uuid4()
        url = f"http://127.0.0.1:{port}/v1/incidents/{missing}/evidence"
        request = urllib.request.Request(url, headers={"Authorization": "Bearer boundary-secret"})
        try:
            urllib.request.urlopen(request, timeout=5)
            raise AssertionError("expected HTTP error")
        except urllib.error.HTTPError as exc:
            assert exc.code == 404
    finally:
        _stop_server(server, thread)


def test_boundary_real_http_redacts_sensitive_values(tmp_path):
    db_path = tmp_path / "boundary.sqlite"
    db_url = f"sqlite:///{db_path}"
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        record = _database_record(session)
        record.evidence["secret"] = "SYNTHETIC_SECRET_SENTINEL"
        session.commit()
        record_id = record.id
    engine.dispose()

    app = boundary.create_investigation_boundary_app(db_url, secret="boundary-secret")
    port = _free_port()
    server, thread = _start_server(app, port)
    try:
        payload = boundary.fetch_persisted_evidence(
            f"http://127.0.0.1:{port}", record_id, "boundary-secret", timeout=5
        )
        assert payload["evidence"].get("secret") == "[redacted]" or "SYNTHETIC_SECRET_SENTINEL" not in str(payload)
    finally:
        _stop_server(server, thread)
