import re
from uuid import uuid4

from fastapi.testclient import TestClient
from opentelemetry.sdk._logs.export import InMemoryLogRecordExporter
from opentelemetry.sdk.trace.export import SpanExporter
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from pydantic import SecretStr
from sqlalchemy import create_engine

from app.config import Settings
from app.main import create_app
from app.models import Base
from app.observability import Telemetry

TRACE_ID = "4bf92f3577b34da6a3ce929d0e0e4736"
SPAN_ID = "00f067aa0ba902b7"
PROMPT = "PRIVATE_PROMPT_SENTINEL"
CODE = "GENERATED_CODE_SENTINEL"
OUTPUT = "BENCHMARK_OUTPUT_SENTINEL"
TOKEN = "AUTH_TOKEN_SENTINEL"


def _client(tmp_path, telemetry: Telemetry) -> TestClient:
    database_path = tmp_path / "observability.sqlite"
    engine = create_engine(f"sqlite:///{database_path}")
    Base.metadata.create_all(engine)
    engine.dispose()
    return TestClient(
        create_app(
            Settings(
                app_env="development",
                local_auth_bypass=True,
                database_url=SecretStr(f"sqlite:///{database_path}"),
            ),
            telemetry=telemetry,
        )
    )


def _synthetic_invalid_import() -> dict[str, object]:
    return {
        "format_version": "benchscope.run.v1",
        "profile_snapshot": {
            "name": PROMPT,
            "model_name": "synthetic/model",
        },
        "benchmark_config": {"name": "synthetic"},
        "started_at": "2026-10-26T10:00:00Z",
        "ended_at": "2026-10-26T10:00:02Z",
        "prompt": PROMPT,
        "generated_code": CODE,
        "stdout": OUTPUT,
        "stderr": OUTPUT,
        "api_key": TOKEN,
        "owner_id": TOKEN,
    }


def test_journey_telemetry_is_correlated_and_payload_free(tmp_path) -> None:
    spans = InMemorySpanExporter()
    logs = InMemoryLogRecordExporter()
    telemetry = Telemetry(trace_exporter=spans, log_exporter=logs)
    run_id = str(uuid4())

    with _client(tmp_path, telemetry) as client:
        invalid = client.post(
            "/api/v1/runs/import?private_query=" + PROMPT,
            json=_synthetic_invalid_import(),
            headers={
                "traceparent": f"00-{TRACE_ID}-{SPAN_ID}-01",
                "Authorization": f"Bearer {TOKEN}",
            },
        )
        history = client.get(
            "/api/v1/runs?model=" + PROMPT,
            headers={"traceparent": f"00-{TRACE_ID}-{SPAN_ID}-01"},
        )
        detail = client.get(
            f"/api/v1/runs/{run_id}",
            headers={"traceparent": f"00-{TRACE_ID}-{SPAN_ID}-01"},
        )
        metrics = client.get("/metrics").text

    assert invalid.status_code == 422
    assert PROMPT not in invalid.text
    assert history.status_code == 200
    assert detail.status_code == 404

    exported_spans = spans.get_finished_spans()
    assert [span.name for span in exported_spans] == [
        "POST /api/v1/runs/import",
        "GET /api/v1/runs",
        "GET /api/v1/runs/{id}",
    ]
    assert all(f"{span.context.trace_id:032x}" == TRACE_ID for span in exported_spans)
    assert all(span.parent.span_id == int(SPAN_ID, 16) for span in exported_spans)
    assert all("run.id" not in span.attributes for span in exported_spans)
    assert all("http.url" not in span.attributes for span in exported_spans)

    exported = repr(exported_spans) + repr(logs.get_finished_logs()) + metrics
    assert all(
        sentinel not in exported for sentinel in (PROMPT, CODE, OUTPUT, TOKEN, run_id)
    )

    log_records = logs.get_finished_logs()
    assert len(log_records) == 3
    assert all(
        record.log_record.trace_id == int(TRACE_ID, 16) for record in log_records
    )
    assert all(
        record.log_record.span_id == span.context.span_id
        for record, span in zip(log_records, exported_spans, strict=True)
    )
    assert "benchscope_http_server_requests_total" in metrics
    assert 'http_route="/api/v1/runs/{id}"' in metrics
    assert not re.search(
        r"trace[_-]?id|owner[_-]?id|run[_-]?id", metrics, re.IGNORECASE
    )


def test_request_metric_exposes_exact_trace_as_openmetrics_exemplar(tmp_path) -> None:
    spans = InMemorySpanExporter()
    telemetry = Telemetry(trace_exporter=spans)

    with _client(tmp_path, telemetry) as client:
        response = client.get(
            "/api/v1/runs",
            headers={"traceparent": f"00-{TRACE_ID}-{SPAN_ID}-01"},
        )
        metrics = client.get(
            "/metrics",
            headers={"Accept": "application/openmetrics-text; version=1.0.0"},
        ).text

    assert response.status_code == 200
    metric_sample = next(
        line
        for line in metrics.splitlines()
        if line.startswith("benchscope_http_server_requests_total{")
        and 'http_route="/api/v1/runs"' in line
    )
    assert f'# {{trace_id="{TRACE_ID}"}}' in metric_sample
    assert "trace_id" not in metric_sample.split("} ", maxsplit=1)[0]
    assert [f"{span.context.trace_id:032x}" for span in spans.get_finished_spans()] == [
        TRACE_ID
    ]


class _BrokenSpanExporter(SpanExporter):
    def export(self, spans):
        raise RuntimeError("exporter is unavailable")

    def shutdown(self) -> None:
        pass

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True


def test_export_failure_does_not_break_validation_response(tmp_path) -> None:
    telemetry = Telemetry(trace_exporter=_BrokenSpanExporter())

    with _client(tmp_path, telemetry) as client:
        response = client.post("/api/v1/runs/import", json=_synthetic_invalid_import())

    assert response.status_code == 422
    assert PROMPT not in response.text


def test_hosted_app_does_not_expose_or_export_local_telemetry() -> None:
    spans = InMemorySpanExporter()
    logs = InMemoryLogRecordExporter()
    telemetry = Telemetry(
        enabled=False,
        trace_exporter=spans,
        log_exporter=logs,
    )
    settings = Settings(
        app_mode="hosted",
        database_url=SecretStr("postgresql://db.example/benchscope"),
        cors_origins=["https://dashboard.example"],
        host="0.0.0.0",
        clerk_jwks_url="https://clerk.example/.well-known/jwks.json",
        clerk_issuer="https://clerk.example",
        clerk_audience="benchscope",
    )

    with TestClient(create_app(settings, telemetry=telemetry)) as client:
        assert client.get("/metrics").status_code == 404
        assert client.get("/api/v1/runs").status_code == 401

    assert spans.get_finished_spans() == ()
    assert logs.get_finished_logs() == ()
