# Local metric-to-trace link

The request counter carries a W3C trace ID as an OpenMetrics exemplar, not as a
metric label. The route, method, and status-code labels remain bounded. The
Prometheus scrape negotiates OpenMetrics, and Grafana maps the exemplar's
`trace_id` to the provisioned Tempo data source. The local journey dashboard
shows exemplars on its request-rate panel.

## Compatibility evidence

The locked Python versions are `opentelemetry-sdk==1.45.1`,
`opentelemetry-exporter-prometheus==0.66b1`, and `prometheus-client==0.26.0`.
The installed OpenTelemetry Prometheus reader's collector does not render SDK
exemplars; the pre-change `/metrics` output therefore had no exemplar syntax.
The installed Prometheus client does support `Counter.inc(exemplar=...)` and
OpenMetrics exposition. BenchScope uses it for the existing request-counter
name while OpenTelemetry continues to export the request-duration histogram.

The local stack versions are Prometheus `3.5.0`, Grafana `12.1.1`, OpenTelemetry
Collector Contrib `0.136.0`, and Tempo `2.8.1` (the runtime Prometheus and
Grafana version commands and the Compose image tags were checked). Prometheus
3.5.0 negotiates OpenMetrics 1.0.0 and requires
`--enable-feature=exemplar-storage`; the flag was observed empty before enabling
it, and Prometheus returned no exemplars until the flag was set. Grafana's
provisioned Prometheus data source maps the exemplar label `trace_id` to an
external relative URL served by Grafana's Tempo data-source proxy.

## Reproduce in an isolated synthetic Compose project

From a clean checkout on Windows with Docker Desktop and PowerShell, run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\verify_metric_trace.ps1
```

The script uses a random Compose project name, a temporary synthetic-only env
file and secret, unique loopback ports, and project-scoped volumes. It never
reads `.env`; every Compose invocation supplies the temporary env file and
explicit project/file paths. It refuses a non-local Docker endpoint, missing
cached images, or unavailable ports; it never pulls images or touches an
existing Compose project. It uses `benchscope-issue35-api:latest` without
rebuilding when that image is cached. If it is absent, it builds the API only
when both Dockerfile base images are cached. Both paths use Compose's explicit
`--pull never`. It starts only that disposable local project, runs
`GET /api/v1/runs` with a generated W3C `traceparent`, and removes only its own
containers and volumes afterward. The endpoint returns an empty page from the
newly created project database; the script fails if that database contains a
run. No run data is imported or persisted. The local-only auth bypass is
enabled only in the synthetic API container, and benchmark execution remains
disabled.

The check polls Prometheus for the exact generated trace ID on the
`benchscope_http_server_requests_total` exemplar for
`/api/v1/runs`, verifies the ID is not a series label, then
fetches that ID from Tempo and compares it with the decoded trace IDs on the
returned spans. It prints the actual Prometheus version, locked API telemetry
package versions, pinned local service image versions, exemplar ID, and Tempo
IDs. A nonzero exit means the integration check did not pass; missing images or
ports are reported before Compose starts. The images must already be present
locally; this procedure does not download them.

## Viewer-safe trace access and Explore limitation

The issue's current Compose settings grant anonymous users only the `Viewer`
role, disable the login form, and disallow sign-ups. Grafana's versioned
[role-permission table for 12.1](https://grafana.com/docs/grafana/v12.1/administration/roles-and-permissions/)
states that Viewer does **not** have **Access Explore** permission (Editor and
organization administrator do), so Viewer still cannot follow an internal link
into Explore. The Prometheus data source instead configures the exemplar
destination label `Trace` as the external relative URL
`/api/datasources/proxy/uid/tempo/api/traces/${__value.raw}`. Grafana substitutes
the exact exemplar value and proxies the request through the provisioned Tempo
data source. This link returns the trace response directly without granting
Explore or changing login/role settings. The isolated verifier checks the route
anonymously for the exact generated exemplar ID and confirms the returned spans
retain it.

## Follow-up verification evidence (2026-10-28)

An initial run failed closed because the local Docker engine lacked
`ghcr.io/astral-sh/uv:0.12.5` and `python:3.12-slim`; it did not pull images or
start a Compose project. After adding the cached API-image path, the synthetic
E2E completed using `benchscope-issue35-api:latest` without rebuilding or
pulling. Prometheus reported version `3.5.0`; API telemetry packages were
`opentelemetry-sdk==1.45.1`,
`opentelemetry-exporter-prometheus==0.66b1`, and
`prometheus-client==0.26.0`. Compose image versions were Prometheus `3.5.0`,
Collector Contrib `0.136.0`, Tempo `2.8.1`, Loki `3.5.3`, and PostgreSQL
`17-alpine`.

The synthetic `GET /api/v1/runs` returned an empty page. Prometheus exposed the
`benchscope_http_server_requests_total` exemplar with `trace_id` set to
`dc29896827f5473997f4bdf521de2486`; Tempo returned a span with the exact same
trace ID. The trace ID was verified absent from the metric series labels. The
run's random project was `benchscope-metric-trace-8d636c9f7e84`; after script
cleanup, Docker reported no containers, volumes, or networks with that project
label. The seven pre-existing `benchscope` containers retained their IDs and
running states. This live synthetic check supplements the focused backend
observability tests.

The Viewer-safe Grafana proxy path was then verified in an isolated run using
cached `benchscope-issue35-api:latest` and `grafana/grafana:12.1.1`, without a
rebuild or pull. The synthetic request produced exemplar and Tempo trace ID
`d34a2a7790c34e1da12083a82ab43a3c`. An unauthenticated GET to
`/api/datasources/proxy/uid/tempo/api/traces/d34a2a7790c34e1da12083a82ab43a3c`
returned a span with that exact ID. The Grafana proxy and direct Tempo lookup
both preserved the ID. The project was
`benchscope-metric-trace-e60f2fedad5f`; cleanup removed its containers,
volumes, and network, while the existing root services remained running.
Prometheus `3.5.0`, Grafana `12.1.1`, Collector Contrib `0.136.0`, Tempo
`2.8.1`, Loki `3.5.3`, PostgreSQL `17-alpine`, and the API telemetry package
versions above are the verified versions. Viewer-safe direct trace access now
works; Explore remains unavailable to the default Viewer.

The backend test `test_request_metric_exposes_exact_trace_as_openmetrics_exemplar`
also sends a synthetic request to the harmless empty-run-list route and verifies
that the OpenMetrics counter sample's exemplar exactly matches the exported
span trace ID. Existing tests continue to check that trace IDs, owner IDs, and
run IDs are absent from metric labels and that trace/log correlation is
preserved.
