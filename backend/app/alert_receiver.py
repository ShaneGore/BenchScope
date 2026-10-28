from __future__ import annotations

import asyncio
import hmac
import json
import math
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from app.database import create_database_engine
from app.models import IncidentRecord

ALERT_NAME = "BenchScopeApiUnavailable"
WEBHOOK_PATH = "/grafana/v1"
MAX_BODY_BYTES = 16 * 1024
MAX_EVIDENCE_BYTES = 64 * 1024
MAX_SOURCE_BYTES = 256 * 1024
LOOKBACK = timedelta(minutes=5)
TOTAL_TIMEOUT_SECONDS = 10.0
MAX_LOG_LINES = 20
MAX_TRACES = 5
MAX_SPANS_PER_TRACE = 3

PROMETHEUS_URL = "http://prometheus:9090/api/v1/query"
LOKI_URL = "http://loki:3100/loki/api/v1/query_range"
TEMPO_URL = "http://tempo:3200/api/search"
PROMETHEUS_API_QUERY = 'up{job="api"}'
PROMETHEUS_STATUS_QUERY = (
    "sum by (http_response_status_code) "
    "(increase(benchscope_http_server_requests_total"
    '{service_name="benchscope-api"}[5m]))'
)
LOKI_QUERY = '{service_name="benchscope-api"}'
TEMPO_QUERY = '{ resource.service.name = "benchscope-api" }'
FINGERPRINT_PATTERN = re.compile(r"[0-9a-fA-F]{16}\Z")
STATUS_CODE_PATTERN = re.compile(r"[1-5][0-9]{2}\Z")
RFC3339_PATTERN = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})\Z"
)


class InvalidWebhook(ValueError):
    pass


class DuplicateJsonKey(ValueError):
    pass


class DatasourceError(Exception):
    pass


class ResponseTooLarge(Exception):
    pass


def _object_without_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateJsonKey
        result[key] = value
    return result


def _exact_keys(
    value: Any, keys: set[str], optional: set[str] | None = None
) -> dict[str, Any]:
    optional_keys = optional or set()
    if (
        not isinstance(value, dict)
        or not keys.issubset(value)
        or set(value) - keys - optional_keys
    ):
        raise InvalidWebhook
    return value


def _string_map(value: Any) -> dict[str, str]:
    if not isinstance(value, dict) or any(
        not isinstance(key, str) or not isinstance(item, str)
        for key, item in value.items()
    ):
        raise InvalidWebhook
    return value


def _timestamp(value: Any) -> datetime:
    if not isinstance(value, str) or not RFC3339_PATTERN.fullmatch(value):
        raise InvalidWebhook
    try:
        parsed = datetime.fromisoformat(value)
        normalized = parsed.astimezone(UTC)
    except (OverflowError, ValueError):
        raise InvalidWebhook from None
    if parsed.tzinfo is None:
        raise InvalidWebhook
    return normalized


def parse_grafana_webhook(body: bytes) -> dict[str, Any]:
    try:
        payload = json.loads(
            body,
            object_pairs_hook=_object_without_duplicate_keys,
        )
    except (UnicodeDecodeError, ValueError, RecursionError):
        raise InvalidWebhook from None

    payload = _exact_keys(
        payload,
        {
            "receiver",
            "status",
            "alerts",
            "groupLabels",
            "commonLabels",
            "commonAnnotations",
            "externalURL",
            "version",
            "groupKey",
            "truncatedAlerts",
            "orgId",
            "state",
            "title",
            "message",
        },
    )
    if (
        payload["version"] != "1"
        or not all(
            isinstance(payload[key], str)
            for key in (
                "receiver",
                "status",
                "state",
                "title",
                "message",
                "externalURL",
                "groupKey",
            )
        )
        or type(payload["truncatedAlerts"]) is not int
        or payload["truncatedAlerts"] != 0
        or type(payload["orgId"]) is not int
        or payload["orgId"] < 1
        or payload["state"]
        != ("alerting" if payload["status"] == "firing" else "ok")
        or any(
            len(payload[key]) > MAX_BODY_BYTES for key in ("title", "message")
        )
    ):
        raise InvalidWebhook
    _string_map(payload["groupLabels"])
    _string_map(payload["commonLabels"])
    _string_map(payload["commonAnnotations"])
    if not isinstance(payload["alerts"], list) or len(payload["alerts"]) != 1:
        raise InvalidWebhook

    alert = _exact_keys(
        payload["alerts"][0],
        {
            "status",
            "labels",
            "annotations",
            "startsAt",
            "endsAt",
            "generatorURL",
            "fingerprint",
            "orgId",
        },
        {"silenceURL", "dashboardURL", "panelURL", "values", "valueString"},
    )
    labels = _string_map(alert["labels"])
    _string_map(alert["annotations"])
    for key in ("generatorURL", "silenceURL", "dashboardURL", "panelURL", "valueString"):
        if key in alert and (
            not isinstance(alert[key], str) or len(alert[key]) > MAX_BODY_BYTES
        ):
            raise InvalidWebhook
    if "values" in alert and (
        not isinstance(alert["values"], dict)
        or any(
            not isinstance(key, str)
            or isinstance(value, bool)
            or not isinstance(value, (str, int, float))
            or (isinstance(value, str) and len(value) > 1024)
            or (isinstance(value, float) and not math.isfinite(value))
            for key, value in alert["values"].items()
        )
    ):
        raise InvalidWebhook
    starts_at = _timestamp(alert["startsAt"])
    ends_at = _timestamp(alert["endsAt"])
    fingerprint = alert["fingerprint"]
    status = alert["status"]
    if (
        not isinstance(status, str)
        or status not in {"firing", "resolved"}
        or payload["status"] != status
        or not isinstance(alert["generatorURL"], str)
        or (status == "resolved" and starts_at > ends_at)
        or type(alert["orgId"]) is not int
        or alert["orgId"] != payload["orgId"]
        or not isinstance(fingerprint, str)
        or not FINGERPRINT_PATTERN.fullmatch(fingerprint)
        or not isinstance(labels.get("alertname"), str)
    ):
        raise InvalidWebhook
    return {
        "alert_name": labels["alertname"],
        "status": status,
        "fingerprint": fingerprint.lower(),
        "starts_at": starts_at,
        "ends_at": ends_at,
    }


def _fetch_json(
    method: str,
    url: str,
    params: dict[str, str],
    timeout: float,
) -> Any:
    if method != "GET":
        raise DatasourceError
    request = urllib.request.Request(
        f"{url}?{urllib.parse.urlencode(params)}",
        method="GET",
        headers={"Accept": "application/json"},
    )
    opener = urllib.request.build_opener(_NoRedirect())
    try:
        with opener.open(request, timeout=timeout) as response:
            if response.status != 200:
                raise DatasourceError
            raw = response.read(MAX_SOURCE_BYTES + 1)
    except (OSError, urllib.error.URLError, ValueError):
        raise DatasourceError from None
    if len(raw) > MAX_SOURCE_BYTES:
        raise ResponseTooLarge
    try:
        return json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise DatasourceError from None


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, file, code, message, headers, new_url):
        return None


def _prometheus_api_result(payload: Any) -> str:
    result = payload.get("data", {}).get("result")
    if payload.get("status") != "success" or not isinstance(result, list):
        raise DatasourceError
    if any(not isinstance(item, dict) for item in result):
        raise DatasourceError
    samples = [item.get("value") for item in result]
    if any(
        not isinstance(sample, list)
        or len(sample) != 2
        or not isinstance(sample[1], str)
        for sample in samples
    ):
        raise DatasourceError
    values = [sample[1] for sample in samples]
    if any(value not in {"0", "1"} for value in values):
        raise DatasourceError
    if not values:
        return "unknown"
    return "up" if "1" in values else "down"


def _prometheus_status_result(payload: Any) -> list[dict[str, Any]]:
    result = payload.get("data", {}).get("result")
    if payload.get("status") != "success" or not isinstance(result, list):
        raise DatasourceError
    response_counts = []
    for item in result:
        if not isinstance(item, dict):
            raise DatasourceError
        metric = item.get("metric")
        value = item.get("value")
        code = (
            metric.get("http_response_status_code")
            if isinstance(metric, dict)
            else None
        )
        if (
            not isinstance(code, str)
            or not STATUS_CODE_PATTERN.fullmatch(code)
            or not isinstance(value, list)
            or len(value) != 2
            or not isinstance(value[1], str)
        ):
            raise DatasourceError
        try:
            count = float(value[1])
        except ValueError:
            raise DatasourceError from None
        if not math.isfinite(count) or count < 0:
            raise DatasourceError
        response_counts.append({"status_code": code, "count": count})
    return response_counts


def _loki_result(payload: Any) -> tuple[list[dict[str, str]], bool]:
    streams = payload.get("data", {}).get("result")
    if payload.get("status") != "success" or not isinstance(streams, list):
        raise DatasourceError
    timestamps: list[datetime] = []
    for stream in streams:
        values = stream.get("values") if isinstance(stream, dict) else None
        if not isinstance(values, list):
            raise DatasourceError
        for pair in values:
            if (
                not isinstance(pair, list)
                or len(pair) != 2
                or not isinstance(pair[0], str)
                or not pair[0].isdigit()
            ):
                raise DatasourceError
            try:
                timestamps.append(
                    datetime.fromtimestamp(int(pair[0]) / 1_000_000_000, UTC)
                )
            except (OverflowError, OSError, ValueError):
                raise DatasourceError from None
    timestamps.sort(reverse=True)
    return (
        [{"timestamp": stamp.isoformat()} for stamp in timestamps[:MAX_LOG_LINES]],
        len(timestamps) > MAX_LOG_LINES,
    )


def _nanosecond_value(value: Any) -> int:
    if isinstance(value, str) and value.isdigit():
        return int(value)
    if type(value) is int and value >= 0:
        return value
    raise DatasourceError


def _duration_value(value: Any, *, integer_string: bool = False) -> float:
    if integer_string and isinstance(value, str) and value.isdigit():
        value = int(value)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise DatasourceError
    try:
        duration = float(value)
    except OverflowError:
        raise DatasourceError from None
    if not math.isfinite(duration) or duration < 0:
        raise DatasourceError
    return duration


def _tempo_result(payload: Any) -> tuple[list[dict[str, Any]], bool, bool]:
    traces = payload.get("traces")
    if not isinstance(traces, list):
        raise DatasourceError
    records: list[dict[str, Any]] = []
    spans_truncated = False
    for trace in traces[:MAX_TRACES]:
        if not isinstance(trace, dict):
            raise DatasourceError
        start = trace.get("startTimeUnixNano")
        duration = trace.get("durationMs")
        span_set = trace.get("spanSet", {})
        spans = span_set.get("spans", []) if isinstance(span_set, dict) else None
        if not isinstance(spans, list):
            raise DatasourceError
        start_ns = _nanosecond_value(start)
        duration_ms = _duration_value(duration)
        try:
            started_at = datetime.fromtimestamp(start_ns / 1_000_000_000, UTC)
        except (OverflowError, OSError, ValueError):
            raise DatasourceError from None
        kept_spans = []
        for span in spans[:MAX_SPANS_PER_TRACE]:
            if not isinstance(span, dict):
                raise DatasourceError
            span_start = _nanosecond_value(span.get("startTimeUnixNano"))
            span_duration = _duration_value(
                span.get("durationNanos", 0), integer_string=True
            )
            try:
                span_time = datetime.fromtimestamp(span_start / 1_000_000_000, UTC)
            except (OverflowError, OSError, ValueError):
                raise DatasourceError from None
            kept_spans.append(
                {
                    "started_at": span_time.isoformat(),
                    "duration_ms": span_duration / 1_000_000,
                }
            )
        matched = (
            span_set.get("matched", len(spans)) if isinstance(span_set, dict) else 0
        )
        if type(matched) is not int or matched < len(spans):
            matched = len(spans)
        spans_truncated |= matched > MAX_SPANS_PER_TRACE
        records.append(
            {
                "started_at": started_at.isoformat(),
                "duration_ms": duration_ms,
                "span_count": matched,
                "spans": kept_spans,
            }
        )
    return records, len(traces) > MAX_TRACES, spans_truncated


def _empty_source(status: str) -> dict[str, Any]:
    return {"status": status}


def _bounded_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    if len(json.dumps(evidence, separators=(",", ":"), allow_nan=False).encode()) <= (
        MAX_EVIDENCE_BYTES
    ):
        return evidence
    return {
        "status": "failed",
        "reason": "evidence_size_limit",
        "truncated": {"logs": False, "traces": False, "spans": False},
        "prometheus": _empty_source("failed"),
        "logs": _empty_source("failed"),
        "traces": _empty_source("failed"),
    }


def _nanoseconds(timestamp: datetime) -> int:
    delta = timestamp - datetime(1970, 1, 1, tzinfo=UTC)
    return (
        (delta.days * 86_400 + delta.seconds) * 1_000_000 + delta.microseconds
    ) * 1_000


async def collect_evidence(
    received_at: datetime,
    *,
    fetch_json: Callable[[str, str, dict[str, str], float], Any] = _fetch_json,
    monotonic: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    end = received_at.astimezone(UTC)
    start = end - LOOKBACK
    end_seconds = end.timestamp()
    start_ns = str(_nanoseconds(start))
    end_ns = str(_nanoseconds(end))
    deadline = monotonic() + TOTAL_TIMEOUT_SECONDS
    calls = [
        (
            "prometheus",
            "api",
            PROMETHEUS_URL,
            {"query": PROMETHEUS_API_QUERY, "time": f"{end_seconds:.6f}"},
            _prometheus_api_result,
        ),
        (
            "prometheus",
            "http_responses",
            PROMETHEUS_URL,
            {"query": PROMETHEUS_STATUS_QUERY, "time": f"{end_seconds:.6f}"},
            _prometheus_status_result,
        ),
        (
            "logs",
            "entries",
            LOKI_URL,
            {
                "query": LOKI_QUERY,
                "start": start_ns,
                "end": end_ns,
                "limit": str(MAX_LOG_LINES + 1),
                "direction": "BACKWARD",
            },
            _loki_result,
        ),
        (
            "traces",
            "traces",
            TEMPO_URL,
            {
                "q": TEMPO_QUERY,
                "start": str(int(start.timestamp())),
                "end": str(int(end.timestamp())),
                "limit": str(MAX_TRACES + 1),
                "spanSetLimit": str(MAX_SPANS_PER_TRACE + 1),
            },
            _tempo_result,
        ),
    ]
    result: dict[str, Any] = {
        "collected_at": end.isoformat(),
        "lookback_seconds": int(LOOKBACK.total_seconds()),
        "prometheus": {},
        "logs": {},
        "traces": {},
        "truncated": {"logs": False, "traces": False, "spans": False},
    }
    successes = 0
    failures = 0
    for source, result_key, url, params, sanitizer in calls:
        remaining = deadline - monotonic()
        if remaining <= 0:
            if source == "prometheus":
                result[source][f"{result_key}_status"] = "timeout"
            else:
                result[source] = _empty_source("timeout")
            failures += 1
            continue
        try:
            raw = await asyncio.wait_for(
                asyncio.to_thread(fetch_json, "GET", url, params, remaining),
                timeout=remaining,
            )
            if source == "prometheus":
                result[source][result_key] = sanitizer(raw)
                result[source][f"{result_key}_status"] = "ok"
                result[source]["status"] = "ok"
            elif source == "logs":
                entries, truncated = sanitizer(raw)
                result[source] = {"status": "ok", "entries": entries}
                result["truncated"]["logs"] = truncated
            else:
                traces, truncated, spans_truncated = sanitizer(raw)
                result[source] = {"status": "ok", "traces": traces}
                result["truncated"]["traces"] = truncated
                result["truncated"]["spans"] = spans_truncated
            successes += 1
        except TimeoutError:
            if source == "prometheus":
                result[source][f"{result_key}_status"] = "timeout"
            else:
                result[source] = _empty_source("timeout")
            failures += 1
        except (
            DatasourceError,
            ResponseTooLarge,
            ValueError,
            TypeError,
            AttributeError,
            OverflowError,
            OSError,
        ):
            if source == "prometheus":
                result[source][f"{result_key}_status"] = "failed"
            else:
                result[source] = _empty_source("failed")
            failures += 1
    api_status = result["prometheus"].get("api_status")
    response_status = result["prometheus"].get("http_responses_status")
    if api_status != response_status:
        result["prometheus"]["status"] = (
            "partial" if api_status == "ok" or response_status == "ok" else "failed"
        )
    elif api_status != "ok":
        result["prometheus"]["status"] = api_status or "failed"
    if failures == 0:
        result["status"] = "complete"
    elif successes:
        result["status"] = "partial"
    else:
        result["status"] = "failed"
    return _bounded_evidence(result)


def _read_secret(secret_file: Path | None) -> str | None:
    if secret_file is None:
        return None
    try:
        secret = secret_file.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        return None
    return secret or None


def create_receiver_app(
    database_url: str | None = None,
    *,
    secret: str | None = None,
    secret_file: Path | None = None,
    fetch_json: Callable[[str, str, dict[str, str], float], Any] = _fetch_json,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> FastAPI:
    if secret is None:
        configured_path = os.environ.get("ALERT_RECEIVER_SECRET_FILE")
        secret_file = secret_file or (
            Path(configured_path) if configured_path else None
        )
    else:
        secret_file = None
    configured_database_url = (
        database_url if database_url is not None else os.environ.get("DATABASE_URL")
    )
    engine = create_database_engine(configured_database_url)
    factory = sessionmaker(bind=engine, expire_on_commit=False) if engine else None

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        try:
            yield
        finally:
            if engine is not None:
                engine.dispose()

    async def evidence_collector(received_at: datetime) -> dict[str, Any]:
        return await collect_evidence(received_at, fetch_json=fetch_json)

    app = FastAPI(
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.state.session_factory = factory
    app.state.engine = engine

    def configured_secret() -> str | None:
        return secret if secret is not None else _read_secret(secret_file)

    def database_ready() -> bool:
        if factory is None:
            return False
        try:
            with factory() as session:
                session.execute(select(1))
                session.execute(select(IncidentRecord.id).limit(0))
        except SQLAlchemyError:
            return False
        return True

    @app.get("/ready")
    def ready() -> JSONResponse:
        is_ready = bool(configured_secret()) and database_ready()
        return JSONResponse(
            status_code=200 if is_ready else 503,
            content={"status": "ready" if is_ready else "not_ready"},
        )

    @app.post(WEBHOOK_PATH)
    async def receive_alert(request: Request) -> JSONResponse:
        shared_secret = configured_secret()
        if not shared_secret:
            return JSONResponse(status_code=503, content={"status": "not_ready"})

        auth_headers = request.headers.getlist("authorization")
        if len(auth_headers) != 1:
            return JSONResponse(status_code=401, content={"status": "unauthorized"})
        parts = auth_headers[0].split(" ", 1)
        if (
            len(parts) != 2
            or parts[0].lower() != "bearer"
            or not hmac.compare_digest(parts[1].encode(), shared_secret.encode())
        ):
            return JSONResponse(status_code=401, content={"status": "unauthorized"})

        content_type = request.headers.get("content-type", "").split(";", 1)[0].strip()
        if content_type != "application/json":
            return JSONResponse(status_code=415, content={"status": "invalid_payload"})
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > MAX_BODY_BYTES:
                    return JSONResponse(
                        status_code=413, content={"status": "payload_too_large"}
                    )
            except ValueError:
                return JSONResponse(
                    status_code=400, content={"status": "invalid_payload"}
                )
        body = bytearray()
        async for chunk in request.stream():
            if len(body) + len(chunk) > MAX_BODY_BYTES:
                return JSONResponse(
                    status_code=413, content={"status": "payload_too_large"}
                )
            body.extend(chunk)
        try:
            alert = parse_grafana_webhook(bytes(body))
        except InvalidWebhook:
            return JSONResponse(status_code=400, content={"status": "invalid_payload"})

        if alert["alert_name"] != ALERT_NAME:
            return JSONResponse(status_code=200, content={"status": "ignored"})
        if factory is None:
            return JSONResponse(status_code=503, content={"status": "not_ready"})

        received_at = clock().astimezone(UTC)
        key = (alert["fingerprint"], alert["starts_at"])
        if alert["status"] == "resolved":
            try:
                with factory() as session:
                    record = session.scalar(
                        select(IncidentRecord).where(
                            IncidentRecord.fingerprint == key[0],
                            IncidentRecord.starts_at == key[1],
                        )
                    )
                    if record is not None and record.alert_status != "resolved":
                        record.alert_status = "resolved"
                        record.ends_at = alert["ends_at"]
                        record.resolved_at = received_at
                        session.commit()
            except SQLAlchemyError:
                return JSONResponse(status_code=503, content={"status": "not_ready"})
            return JSONResponse(status_code=200, content={"status": "resolved"})

        record_id = uuid4()
        initial_evidence = {
            "status": "failed",
            "reason": "collection_not_finished",
            "truncated": {"logs": False, "traces": False, "spans": False},
        }
        try:
            with factory() as session:
                existing = session.scalar(
                    select(IncidentRecord.id).where(
                        IncidentRecord.fingerprint == key[0],
                        IncidentRecord.starts_at == key[1],
                    )
                )
                if existing is not None:
                    return JSONResponse(
                        status_code=200, content={"status": "duplicate"}
                    )
                session.add(
                    IncidentRecord(
                        id=record_id,
                        alert_name=ALERT_NAME,
                        fingerprint=key[0],
                        starts_at=key[1],
                        ends_at=alert["ends_at"],
                        alert_status="firing",
                        evidence_status="failed",
                        evidence=initial_evidence,
                        received_at=received_at,
                    )
                )
                try:
                    session.commit()
                except IntegrityError:
                    session.rollback()
                    return JSONResponse(
                        status_code=200, content={"status": "duplicate"}
                    )
        except SQLAlchemyError:
            return JSONResponse(status_code=503, content={"status": "not_ready"})

        evidence = await evidence_collector(received_at)
        evidence = _bounded_evidence(evidence)
        evidence_status = evidence.get("status")
        if evidence_status not in {"complete", "partial", "failed"}:
            evidence = {
                **_bounded_evidence({}),
                "status": "failed",
                "reason": "collection_failed",
            }
            evidence_status = "failed"
        try:
            with factory() as session:
                record = session.get(IncidentRecord, record_id)
                if record is not None:
                    record.evidence = evidence
                    record.evidence_status = evidence_status
                    session.commit()
        except SQLAlchemyError:
            return JSONResponse(status_code=503, content={"status": "not_ready"})
        return JSONResponse(
            status_code=200,
            content={"status": "recorded", "evidence_status": evidence_status},
        )

    return app


app = create_receiver_app()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
