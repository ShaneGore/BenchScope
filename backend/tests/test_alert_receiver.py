import asyncio
import json
import logging
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.alert_receiver import (
    ALERT_NAME,
    LOKI_QUERY,
    LOKI_URL,
    MAX_EVIDENCE_BYTES,
    MAX_LOG_LINES,
    MAX_SPANS_PER_TRACE,
    MAX_TRACES,
    PROMETHEUS_API_QUERY,
    PROMETHEUS_STATUS_QUERY,
    PROMETHEUS_URL,
    TEMPO_QUERY,
    TEMPO_URL,
    _bounded_evidence,
    collect_evidence,
    create_receiver_app,
)
from app.models import Base, IncidentRecord

SECRET = "SYNTHETIC_RECEIVER_BEARER_SECRET"
NOW = datetime(2026, 10, 27, 23, 37, 31, 867000, tzinfo=UTC)
START = NOW - timedelta(minutes=2)
TOKEN = "SYNTHETIC_TOKEN_SENTINEL"
OWNER = "SYNTHETIC_OWNER_ID_SENTINEL"
PROMPT = "SYNTHETIC_PRIVATE_PROMPT_SENTINEL"
OUTPUT = "SYNTHETIC_PRIVATE_OUTPUT_SENTINEL"


def _webhook(
    *,
    name: str = ALERT_NAME,
    status: str = "firing",
    fingerprint: str = "0123456789abcdef",
) -> dict:
    starts_at = START.isoformat().replace("+00:00", "Z")
    ends_at = (NOW + timedelta(minutes=2)).isoformat().replace("+00:00", "Z")
    if status == "resolved":
        ends_at = (NOW - timedelta(minutes=1)).isoformat().replace("+00:00", "Z")
    return {
        "receiver": "benchscope-alert-intake",
        "status": status,
        "state": "alerting" if status == "firing" else "ok",
        "orgId": 1,
        "title": f"[{status.upper()}:1] {name}",
        "message": "synthetic local alert",
        "alerts": [
            {
                "status": status,
                "labels": {"alertname": name, "severity": "warning"},
                "annotations": {"summary": "synthetic local alert"},
                "startsAt": starts_at,
                "endsAt": (
                    ends_at
                    if status == "resolved"
                    else "0001-01-01T00:00:00Z"
                ),
                "generatorURL": "http://prometheus:9090/graph",
                "fingerprint": fingerprint,
                "orgId": 1,
                "silenceURL": "http://grafana:3000/alerting/silence",
                "dashboardURL": "",
                "panelURL": "",
                "values": {"A": 0, "C": 1},
                "valueString": "synthetic value",
            }
        ],
        "groupLabels": {"alertname": name},
        "commonLabels": {"alertname": name},
        "commonAnnotations": {"summary": "synthetic local alert"},
        "externalURL": "http://grafana:3000",
        "version": "1",
        "groupKey": "{}",
        "truncatedAlerts": 0,
    }


def _database(tmp_path):
    url = f"sqlite:///{tmp_path / 'alerts.sqlite'}"
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    engine.dispose()
    return url


def _read_records(database_url: str) -> list[IncidentRecord]:
    engine = create_engine(database_url)
    with Session(engine) as session:
        rows = list(session.scalars(select(IncidentRecord).order_by(IncidentRecord.id)))
    engine.dispose()
    return rows


def _source_payloads(sentinel: str = "") -> dict[str, dict]:
    timestamp_ns = str(int(NOW.timestamp() * 1_000_000_000))
    span = {
        "spanID": "private-span-id",
        "startTimeUnixNano": timestamp_ns,
        "durationNanos": "1500000",
        "name": sentinel,
        "attributes": [{"key": "private.output", "value": sentinel}],
    }
    return {
        "prom_api": {
            "status": "success",
            "data": {
                "result": [{"metric": {"job": "api"}, "value": [NOW.timestamp(), "0"]}]
            },
        },
        "prom_status": {
            "status": "success",
            "data": {
                "result": [
                    {
                        "metric": {"http_response_status_code": "503"},
                        "value": [NOW.timestamp(), "2"],
                    }
                ]
            },
        },
        "loki": {
            "status": "success",
            "data": {
                "result": [
                    {
                        "stream": {"service_name": "benchscope-api"},
                        "values": [[timestamp_ns, sentinel]],
                    }
                ]
            },
        },
        "tempo": {
            "traces": [
                {
                    "traceID": "private-trace-id",
                    "startTimeUnixNano": timestamp_ns,
                    "durationMs": 12.5,
                    "spanSet": {"matched": 1, "spans": [span]},
                }
            ]
        },
    }


def _fetcher(payloads: dict[str, dict] | None = None, calls: list | None = None):
    payloads = payloads or _source_payloads()
    calls = calls if calls is not None else []

    def fetch(method, url, params, timeout):
        calls.append((method, url, dict(params), timeout))
        if url == PROMETHEUS_URL and params["query"] == PROMETHEUS_API_QUERY:
            return payloads["prom_api"]
        if url == PROMETHEUS_URL and params["query"] == PROMETHEUS_STATUS_QUERY:
            return payloads["prom_status"]
        if url == LOKI_URL:
            return payloads["loki"]
        if url == TEMPO_URL:
            return payloads["tempo"]
        raise AssertionError("Unexpected datasource target")

    return fetch, calls


def _post(client, payload: dict, secret: str = SECRET):
    return client.post(
        "/grafana/v1",
        content=json.dumps(payload),
        headers={
            "Authorization": f"Bearer {secret}",
            "Content-Type": "application/json",
        },
    )


def test_firing_alert_queries_fixed_read_only_sources_and_persists_sanitized_evidence(
    tmp_path, caplog
) -> None:
    database_url = _database(tmp_path)
    fetch_json, calls = _fetcher(_source_payloads(OUTPUT))
    app = create_receiver_app(
        database_url, secret=SECRET, fetch_json=fetch_json, clock=lambda: NOW
    )

    with caplog.at_level(logging.INFO), TestClient(app) as client:
        response = _post(client, _webhook())

    assert response.status_code == 200
    assert response.json() == {"status": "recorded", "evidence_status": "complete"}
    assert len(calls) == 4
    assert all(call[0] == "GET" and 0 < call[3] <= 10 for call in calls)
    assert [call[1] for call in calls] == [
        PROMETHEUS_URL,
        PROMETHEUS_URL,
        LOKI_URL,
        TEMPO_URL,
    ]
    assert [calls[0][2]["query"], calls[1][2]["query"]] == [
        PROMETHEUS_API_QUERY,
        PROMETHEUS_STATUS_QUERY,
    ]
    assert calls[2][2]["query"] == LOKI_QUERY
    assert calls[3][2]["q"] == TEMPO_QUERY
    assert calls[0][2]["time"] == f"{NOW.timestamp():.6f}"
    assert int(calls[2][2]["end"]) - int(calls[2][2]["start"]) == 300_000_000_000
    assert int(calls[3][2]["end"]) - int(calls[3][2]["start"]) == 300
    (record,) = _read_records(database_url)
    assert record.alert_name == ALERT_NAME
    assert record.alert_status == "firing"
    assert record.evidence_status == "complete"
    evidence = json.dumps(record.evidence)
    assert record.evidence["prometheus"]["api"] == "down"
    assert record.evidence["prometheus"]["http_responses"] == [
        {"status_code": "503", "count": 2.0}
    ]
    assert record.evidence["logs"]["entries"]
    assert record.evidence["traces"]["traces"][0]["span_count"] == 1
    assert all(
        sentinel not in evidence + response.text + caplog.text
        for sentinel in (SECRET, TOKEN, OWNER, PROMPT, OUTPUT)
    )


@pytest.mark.parametrize(
    "case",
    [
        "unsupported_version",
        "unknown_root_field",
        "unknown_alert_field",
        "multiple_alerts",
        "invalid_timestamp",
        "invalid_timestamp_offset",
        "inconsistent_status",
        "invalid_state",
        "invalid_fingerprint",
        "duplicate_json_key",
    ],
)
def test_invalid_webhooks_are_rejected_without_queries_or_records(
    tmp_path, case
) -> None:
    database_url = _database(tmp_path)
    fetch_json, calls = _fetcher()
    payload = _webhook()
    raw_body = None
    if case == "unsupported_version":
        payload["version"] = "5"
    elif case == "unknown_root_field":
        payload["query"] = PROMPT
    elif case == "unknown_alert_field":
        payload["alerts"][0]["command"] = "do not execute"
    elif case == "multiple_alerts":
        payload["alerts"].append(payload["alerts"][0])
    elif case == "invalid_timestamp":
        payload["alerts"][0]["startsAt"] = "yesterday"
    elif case == "invalid_timestamp_offset":
        payload["alerts"][0]["startsAt"] = "0001-01-01T00:00:00+23:59"
    elif case == "inconsistent_status":
        payload["status"] = "resolved"
    elif case == "invalid_state":
        payload["alerts"][0]["status"] = "pending"
    elif case == "invalid_fingerprint":
        payload["alerts"][0]["fingerprint"] = "../../private"
    elif case == "duplicate_json_key":
        raw_body = b'{"version":"4","version":"5"}'
    app = create_receiver_app(
        database_url, secret=SECRET, fetch_json=fetch_json, clock=lambda: NOW
    )

    with TestClient(app) as client:
        response = client.post(
            "/grafana/v1",
            content=raw_body if raw_body is not None else json.dumps(payload),
            headers={
                "Authorization": f"Bearer {SECRET}",
                "Content-Type": "application/json",
            },
        )

    assert response.status_code == 400
    assert response.json() == {"status": "invalid_payload"}
    assert calls == []
    assert _read_records(database_url) == []


def test_authentication_and_missing_secret_fail_closed_before_collection(
    tmp_path, caplog
):
    database_url = _database(tmp_path)
    fetch_json, calls = _fetcher()
    app = create_receiver_app(
        database_url, secret=SECRET, fetch_json=fetch_json, clock=lambda: NOW
    )
    raw_payload = json.dumps(_webhook()).replace(
        "synthetic local alert", TOKEN + OWNER + PROMPT + OUTPUT
    )
    with caplog.at_level(logging.INFO), TestClient(app) as client:
        absent = client.post("/grafana/v1", content=raw_payload)
        invalid = client.post(
            "/grafana/v1",
            content=raw_payload,
            headers={"Authorization": f"Bearer {TOKEN}"},
        )

    assert absent.status_code == invalid.status_code == 401
    assert calls == []
    assert _read_records(database_url) == []
    assert all(
        value not in absent.text + invalid.text + caplog.text
        for value in (TOKEN, OWNER, PROMPT, OUTPUT, SECRET)
    )

    unconfigured = create_receiver_app(
        database_url, secret="", fetch_json=fetch_json, clock=lambda: NOW
    )
    with TestClient(unconfigured) as client:
        assert client.get("/ready").status_code == 503
        unavailable = _post(client, _webhook())
    assert unavailable.status_code == 503
    assert calls == []
    assert _read_records(database_url) == []


def test_oversized_body_is_rejected_before_collection(tmp_path) -> None:
    database_url = _database(tmp_path)
    fetch_json, calls = _fetcher()
    app = create_receiver_app(
        database_url, secret=SECRET, fetch_json=fetch_json, clock=lambda: NOW
    )

    with TestClient(app) as client:
        response = client.post(
            "/grafana/v1",
            content=b"x" * (16 * 1024 + 1),
            headers={
                "Authorization": f"Bearer {SECRET}",
                "Content-Type": "application/json",
            },
        )

    assert response.status_code == 413
    assert calls == []
    assert _read_records(database_url) == []


def test_unknown_alert_and_resolved_without_match_are_acknowledged_noops(tmp_path):
    database_url = _database(tmp_path)
    fetch_json, calls = _fetcher()
    app = create_receiver_app(
        database_url, secret=SECRET, fetch_json=fetch_json, clock=lambda: NOW
    )

    with TestClient(app) as client:
        unknown = _post(client, _webhook(name="OtherAlert"))
        resolved = _post(client, _webhook(status="resolved"))

    assert unknown.status_code == resolved.status_code == 200
    assert unknown.json() == {"status": "ignored"}
    assert resolved.json() == {"status": "resolved"}
    assert calls == []
    assert _read_records(database_url) == []


def test_resolved_notification_updates_one_record_without_recollecting(tmp_path):
    database_url = _database(tmp_path)
    fetch_json, calls = _fetcher()
    app = create_receiver_app(
        database_url, secret=SECRET, fetch_json=fetch_json, clock=lambda: NOW
    )
    with TestClient(app) as client:
        assert _post(client, _webhook()).json()["status"] == "recorded"
        resolved = _webhook(status="resolved")
        assert _post(client, resolved).json() == {"status": "resolved"}
        assert _post(client, resolved).json() == {"status": "resolved"}

    (record,) = _read_records(database_url)
    assert record.alert_status == "resolved"
    assert record.resolved_at == NOW.replace(tzinfo=None)
    assert record.evidence_status == "complete"
    assert len(calls) == 4


def test_firing_deduplication_survives_receiver_restart(tmp_path):
    database_url = _database(tmp_path)
    first_fetcher, first_calls = _fetcher()
    first_app = create_receiver_app(
        database_url, secret=SECRET, fetch_json=first_fetcher, clock=lambda: NOW
    )
    with TestClient(first_app) as first_client:
        assert _post(first_client, _webhook()).json()["status"] == "recorded"

    second_fetcher, second_calls = _fetcher()
    second_app = create_receiver_app(
        database_url, secret=SECRET, fetch_json=second_fetcher, clock=lambda: NOW
    )
    with TestClient(second_app) as second_client:
        duplicate = _post(second_client, _webhook())

    assert duplicate.status_code == 200
    assert duplicate.json() == {"status": "duplicate"}
    assert len(first_calls) == 4
    assert second_calls == []
    assert len(_read_records(database_url)) == 1


def test_injection_strings_are_ignored_and_telemetry_output_is_allowlisted(
    tmp_path, caplog
) -> None:
    database_url = _database(tmp_path)
    payloads = _source_payloads(TOKEN + OWNER + PROMPT + OUTPUT)
    payloads["prom_api"]["data"]["result"][0]["metric"]["owner_id"] = OWNER
    payloads["prom_api"]["data"]["result"][0]["value"][0] = PROMPT
    payloads["prom_status"]["data"]["result"][0]["metric"]["private_prompt"] = PROMPT
    payloads["prom_status"]["data"]["result"][0]["value"][0] = OUTPUT
    payloads["loki"]["data"]["result"][0]["values"] *= 25
    payloads["tempo"]["traces"] *= 6
    payloads["tempo"]["traces"] = [
        {
            **trace,
            "traceID": TOKEN,
            "rootTraceName": PROMPT,
            "spanSet": {
                "matched": 4,
                "spans": trace["spanSet"]["spans"] * (MAX_SPANS_PER_TRACE + 1),
            },
        }
        for trace in payloads["tempo"]["traces"]
    ]
    fetch_json, calls = _fetcher(payloads)
    app = create_receiver_app(
        database_url, secret=SECRET, fetch_json=fetch_json, clock=lambda: NOW
    )
    payload = _webhook()
    payload["alerts"][0]["labels"].update(
        {
            "query": "delete from incident_records",
            "path": "../../private",
            "command": "run shell",
            "owner_id": OWNER,
        }
    )
    payload["alerts"][0]["annotations"]["prompt"] = PROMPT
    payload["alerts"][0]["annotations"]["private_output"] = OUTPUT
    payload["commonAnnotations"]["token"] = TOKEN

    with caplog.at_level(logging.INFO), TestClient(app) as client:
        response = _post(client, payload)

    assert response.status_code == 200
    assert [call[1] for call in calls] == [
        PROMETHEUS_URL,
        PROMETHEUS_URL,
        LOKI_URL,
        TEMPO_URL,
    ]
    (record,) = _read_records(database_url)
    assert record.evidence["truncated"] == {
        "logs": True,
        "traces": True,
        "spans": True,
    }
    assert len(record.evidence["logs"]["entries"]) == MAX_LOG_LINES
    assert len(record.evidence["traces"]["traces"]) == MAX_TRACES
    assert all(
        len(trace["spans"]) == MAX_SPANS_PER_TRACE
        for trace in record.evidence["traces"]["traces"]
    )
    retained = json.dumps(record.evidence)
    for sentinel in (SECRET, TOKEN, OWNER, PROMPT, OUTPUT):
        assert sentinel not in retained + response.text + caplog.text


def test_datasource_failures_are_explicit_and_never_complete(tmp_path):
    database_url = _database(tmp_path)
    successful_fetcher, _ = _fetcher()

    def failing_fetch(method, url, params, timeout):
        if url == PROMETHEUS_URL:
            raise TimeoutError
        return successful_fetcher(method, url, params, timeout)

    app = create_receiver_app(
        database_url, secret=SECRET, fetch_json=failing_fetch, clock=lambda: NOW
    )
    with TestClient(app) as client:
        response = _post(client, _webhook())

    assert response.json() == {"status": "recorded", "evidence_status": "partial"}
    (record,) = _read_records(database_url)
    assert record.evidence_status == "partial"
    assert record.evidence["status"] == "partial"
    assert record.evidence["prometheus"]["status"] == "timeout"

    all_timeout = create_receiver_app(
        database_url,
        secret=SECRET,
        fetch_json=lambda *_: (_ for _ in ()).throw(TimeoutError),
        clock=lambda: NOW,
    )
    with TestClient(all_timeout) as client:
        failed = _post(client, _webhook(fingerprint="1111111111111111"))
    assert failed.json() == {"status": "recorded", "evidence_status": "failed"}
    assert any(
        record.evidence["status"] == "failed" for record in _read_records(database_url)
    )


def test_datasource_errors_are_sanitized_and_mark_partial(tmp_path, caplog):
    database_url = _database(tmp_path)
    successful_fetcher, _ = _fetcher()
    error_sentinel = "DATASOURCE_PRIVATE_ERROR_SENTINEL"

    def failing_fetch(method, url, params, timeout):
        if url == LOKI_URL:
            raise OSError(error_sentinel)
        return successful_fetcher(method, url, params, timeout)

    app = create_receiver_app(
        database_url, secret=SECRET, fetch_json=failing_fetch, clock=lambda: NOW
    )
    with caplog.at_level(logging.ERROR), TestClient(app) as client:
        response = _post(client, _webhook())

    (record,) = _read_records(database_url)
    assert response.json() == {"status": "recorded", "evidence_status": "partial"}
    assert record.evidence["status"] == "partial"
    assert record.evidence["logs"] == {"status": "failed"}
    assert (
        error_sentinel not in json.dumps(record.evidence) + response.text + caplog.text
    )


def test_unexpected_collection_error_is_not_acknowledged_as_recorded(tmp_path):
    database_url = _database(tmp_path)
    app = create_receiver_app(
        database_url,
        secret=SECRET,
        fetch_json=lambda *_: (_ for _ in ()).throw(RuntimeError("unexpected")),
        clock=lambda: NOW,
    )

    with TestClient(app, raise_server_exceptions=False) as client:
        response = _post(client, _webhook())

    assert response.status_code == 500
    (record,) = _read_records(database_url)
    assert record.alert_status == "firing"
    assert record.evidence_status == "failed"
    assert record.evidence["reason"] == "collection_not_finished"


def test_total_budget_stops_additional_datasource_queries() -> None:
    clock = [0.0]
    calls = []

    def fetch(method, url, params, timeout):
        calls.append((url, params, timeout))
        clock[0] += 11
        return _source_payloads()["prom_api"]

    evidence = asyncio.run(
        collect_evidence(NOW, fetch_json=fetch, monotonic=lambda: clock[0])
    )

    assert len(calls) == 1
    assert calls[0][2] == 10
    assert evidence["status"] == "partial"
    assert evidence["prometheus"]["api"] == "down"
    assert evidence["logs"]["status"] == "timeout"


def test_oversized_serialized_evidence_is_failed_and_bounded() -> None:
    evidence = _bounded_evidence(
        {"status": "complete", "value": "x" * MAX_EVIDENCE_BYTES}
    )

    assert evidence["status"] == "failed"
    assert evidence["reason"] == "evidence_size_limit"
    assert len(json.dumps(evidence).encode()) < MAX_EVIDENCE_BYTES


def test_receiver_readiness_requires_database_table_and_secret_file(tmp_path) -> None:
    database_url = _database(tmp_path)
    secret_file = tmp_path / "secret"
    app = create_receiver_app(database_url, secret_file=secret_file)
    with TestClient(app) as client:
        assert client.get("/ready").status_code == 503

    secret_file.write_text("  \n", encoding="utf-8")
    app = create_receiver_app(database_url, secret_file=secret_file)
    with TestClient(app) as client:
        assert client.get("/ready").status_code == 503

    secret_file.write_text("synthetic-secret", encoding="utf-8")
    app = create_receiver_app(database_url, secret_file=secret_file)
    with TestClient(app) as client:
        assert client.get("/ready").status_code == 200


def test_readiness_is_false_when_incident_table_is_absent(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'without-table.sqlite'}"
    app = create_receiver_app(database_url, secret=SECRET)
    with TestClient(app) as client:
        assert client.get("/ready").status_code == 503
