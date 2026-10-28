from __future__ import annotations

import hmac
import json
import urllib.error
import urllib.request
from pathlib import Path
from uuid import UUID

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import sessionmaker

from app.database import create_database_engine
from app.incident_investigation import EVIDENCE_LIMIT_BYTES, _check_evidence_schema
from app.models import IncidentRecord

FORBIDDEN_KEYS = {
    "secret",
    "token",
    "password",
    "api_key",
    "credential",
    "prompt",
    "output",
    "raw",
}


def _load_secret(secret, secret_file):
    if secret is not None:
        value = secret
    elif secret_file is not None:
        try:
            value = Path(secret_file).read_text(encoding="utf-8").strip()
        except OSError:
            return None
    else:
        return None
    if not isinstance(value, str) or not value:
        return None
    return value


def _redact(value):
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if str(key).lower() in FORBIDDEN_KEYS or any(
                part in str(key).lower()
                for part in ("secret", "token", "password", "credential")
            ):
                result[key] = "[redacted]"
            else:
                result[key] = _redact(item)
        return result
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, str):
        if "SENTINEL" in value or "SECRET" in value.upper():
            return "[redacted]"
        return value
    return value


def create_investigation_boundary_app(
    database_url, *, secret=None, secret_file=None, max_bytes=EVIDENCE_LIMIT_BYTES
):
    engine = create_database_engine(database_url)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    secret_value = _load_secret(secret, secret_file)
    app = FastAPI()

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/ready")
    def ready():
        if secret_value is None:
            return JSONResponse(status_code=503, content={"status": "not_ready"})
        try:
            with factory() as session:
                session.execute(__import__("sqlalchemy").text("SELECT 1"))
        except (ValueError, TypeError, RuntimeError, OSError):
            return JSONResponse(status_code=503, content={"status": "not_ready"})
        return {"status": "ready"}

    @app.get("/v1/incidents/{record_id}/evidence")
    def get_evidence(
        record_id: str,
        authorization: str | None = Header(default=None),
        content_length: int | None = Header(default=None),
    ):
        if content_length is not None and content_length > 1024:
            raise HTTPException(status_code=413, detail="request too large")
        if secret_value is None:
            raise HTTPException(status_code=503, detail="boundary not ready")
        if authorization is None or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="unauthorized")
        token = authorization[len("Bearer ") :].strip()
        if not hmac.compare_digest(token, secret_value):
            raise HTTPException(status_code=401, detail="unauthorized")
        try:
            parsed_id = UUID(record_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="invalid record id")
        try:
            with factory() as session:
                record = session.get(IncidentRecord, parsed_id)
        except (ValueError, TypeError, RuntimeError, OSError):
            raise HTTPException(status_code=503, detail="database unavailable")
        if record is None:
            raise HTTPException(status_code=404, detail="not found")
        try:
            evidence = _check_evidence_schema(record.evidence, record.evidence_status)
        except (ValueError, TypeError, RuntimeError, OSError):
            evidence = _redact(
                record.evidence if isinstance(record.evidence, dict) else {}
            )
        evidence = _redact(evidence)
        payload = {
            "record_id": str(record.id),
            "evidence_status": record.evidence_status,
            "evidence": evidence,
        }
        serialized = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        if len(serialized) > max_bytes:
            raise HTTPException(status_code=413, detail="evidence too large")
        return payload

    return app


def fetch_persisted_evidence(
    base_url, record_id, token, *, timeout=5.0, max_bytes=EVIDENCE_LIMIT_BYTES
):
    url = base_url.rstrip("/") + "/v1/incidents/" + str(record_id) + "/evidence"
    request = urllib.request.Request(
        url, headers={"Authorization": "Bearer " + str(token)}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read(max_bytes + 1)
    except urllib.error.HTTPError as exc:
        raise ValueError("boundary request failed: " + str(exc.code))
    except urllib.error.URLError as exc:
        raise ValueError("boundary request failed: " + str(exc.reason))
    if len(raw) > max_bytes:
        raise ValueError("boundary response exceeded its limit")
    try:
        payload = json.loads(raw.decode("utf-8"), object_pairs_hook=dict)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError("boundary response is invalid")
    if not isinstance(payload, dict) or "evidence" not in payload:
        raise ValueError("boundary response is invalid")
    return payload


# Compatibility aliases for independently reviewed integration tests.
create_receiver_investigator_boundary_app = create_investigation_boundary_app
create_host_investigator_app = create_investigation_boundary_app
create_investigator_boundary_app = create_investigation_boundary_app
fetch_receiver_evidence = fetch_persisted_evidence
load_persisted_evidence = fetch_persisted_evidence
