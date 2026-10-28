import os
import re
import time
from uuid import UUID

from opentelemetry import context, trace
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import (
    BatchLogRecordProcessor,
    LogRecordExporter,
    SimpleLogRecordProcessor,
)
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    SimpleSpanProcessor,
    SpanExporter,
)
from opentelemetry.trace import Span, Status, StatusCode
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from prometheus_client import (
    CollectorRegistry,
    make_asgi_app,
)
from prometheus_client import Counter as PrometheusCounter
from starlette.types import ASGIApp, Message, Receive, Scope, Send

OTEL_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").rstrip("/")
_API_PREFIX = "/api/v1"
_UUID = re.compile(r"[0-9a-fA-F-]{36}\Z")
_PROPAGATOR = TraceContextTextMapPropagator()


def _route_template(method: str, path: str) -> str | None:
    if method == "POST" and path == f"{_API_PREFIX}/runs/import":
        return f"{_API_PREFIX}/runs/import"
    if method == "GET" and path == f"{_API_PREFIX}/runs":
        return f"{_API_PREFIX}/runs"
    detail_prefix = f"{_API_PREFIX}/runs/"
    identifier = path.removeprefix(detail_prefix)
    if (
        method == "GET"
        and path.startswith(detail_prefix)
        and _UUID.fullmatch(identifier)
    ):
        try:
            UUID(identifier)
        except ValueError:
            return None
        return f"{detail_prefix}{{id}}"
    return None


class Telemetry:
    def __init__(
        self,
        enabled: bool = True,
        trace_exporter: SpanExporter | None = None,
        log_exporter: LogRecordExporter | None = None,
    ) -> None:
        self.enabled = enabled
        self.registry = CollectorRegistry()
        self.requests = PrometheusCounter(
            "benchscope_http_server_requests",
            "HTTP requests for the observed import and run-view journey",
            ("http_route", "http_request_method", "http_response_status_code"),
            registry=self.registry,
        )
        reader = PrometheusMetricReader(
            disable_target_info=True,
            scope_info_enabled=False,
            resource_attribute_filter=lambda key: key == "service.name",
            registry=self.registry,
        )
        resource = Resource({"service.name": "benchscope-api"})
        self.trace_provider = TracerProvider(resource=resource)
        self.logger_provider = LoggerProvider(resource=resource)
        self.meter_provider = MeterProvider(resource=resource, metric_readers=[reader])

        if enabled:
            try:
                if trace_exporter is not None:
                    self.trace_provider.add_span_processor(
                        SimpleSpanProcessor(trace_exporter)
                    )
                elif OTEL_ENDPOINT:
                    self.trace_provider.add_span_processor(
                        BatchSpanProcessor(
                            OTLPSpanExporter(endpoint=f"{OTEL_ENDPOINT}/v1/traces")
                        )
                    )
                if log_exporter is not None:
                    self.logger_provider.add_log_record_processor(
                        SimpleLogRecordProcessor(log_exporter)
                    )
                elif OTEL_ENDPOINT:
                    self.logger_provider.add_log_record_processor(
                        BatchLogRecordProcessor(
                            OTLPLogExporter(endpoint=f"{OTEL_ENDPOINT}/v1/logs")
                        )
                    )
            except Exception:  # noqa: BLE001
                # A malformed or unavailable exporter must not prevent API startup.
                self.trace_provider = TracerProvider(resource=resource)
                self.logger_provider = LoggerProvider(resource=resource)

        self.tracer = self.trace_provider.get_tracer("benchscope.api")
        meter = self.meter_provider.get_meter("benchscope.api")
        self.duration = meter.create_histogram(
            "benchscope_http_server_request_duration_seconds",
            unit="s",
            description="HTTP request duration for the observed journey",
        )
        self.logger = self.logger_provider.get_logger("benchscope.api")
        self.metrics_app = make_asgi_app(registry=self.registry)

    def close(self) -> None:
        self.trace_provider.shutdown()
        self.logger_provider.shutdown()
        self.meter_provider.shutdown()

    def record_request(
        self, span: Span, route: str, method: str, status_code: int, elapsed: float
    ) -> None:
        attributes = {
            "http.route": route,
            "http.request.method": method,
            "http.response.status_code": status_code,
        }
        try:
            metric_labels = {
                "http_route": route,
                "http_request_method": method,
                "http_response_status_code": str(status_code),
            }
            span_context = span.get_span_context()
            if span_context.is_valid:
                self.requests.labels(**metric_labels).inc(
                    exemplar={"trace_id": f"{span_context.trace_id:032x}"}
                )
            else:
                self.requests.labels(**metric_labels).inc()
            self.duration.record(elapsed, attributes)
            if status_code >= 400:
                span.set_status(Status(StatusCode.ERROR))
            self.logger.emit(
                body="HTTP request completed",
                attributes=attributes,
            )
        except Exception:  # noqa: BLE001, S110
            # Telemetry is best-effort; it must not affect API requests.
            pass


class RequestTelemetryMiddleware:
    def __init__(self, app: ASGIApp, telemetry: Telemetry) -> None:
        self.app = app
        self.telemetry = telemetry

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not self.telemetry.enabled:
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "GET").upper()
        route = _route_template(method, scope.get("path", ""))
        if route is None:
            await self.app(scope, receive, send)
            return

        carrier = {
            name.decode("latin-1"): value.decode("latin-1")
            for name, value in scope.get("headers", [])
            if name.lower() in {b"traceparent", b"tracestate"}
        }
        parent = _PROPAGATOR.extract(carrier)
        started = time.perf_counter()
        response_status = 500
        span = self.telemetry.tracer.start_span(
            f"{method} {route}",
            context=parent,
            attributes={"http.route": route, "http.request.method": method},
        )
        context_token = context.attach(parent)

        async def send_with_metrics(message: Message) -> None:
            nonlocal response_status
            if message["type"] == "http.response.start":
                response_status = message["status"]
            await send(message)

        try:
            with trace.use_span(span, end_on_exit=False):
                await self.app(scope, receive, send_with_metrics)
        finally:
            try:
                span.set_attribute("http.response.status_code", response_status)
                with trace.use_span(span, end_on_exit=False):
                    self.telemetry.record_request(
                        span,
                        route,
                        method,
                        response_status,
                        time.perf_counter() - started,
                    )
            except Exception:  # noqa: BLE001, S110
                pass
            finally:
                context.detach(context_token)
                try:
                    span.end()
                except Exception:  # noqa: BLE001, S110
                    # Export failures must not replace the API response.
                    pass
