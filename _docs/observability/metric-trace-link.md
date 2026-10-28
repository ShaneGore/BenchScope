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
provisioned Prometheus data source maps the exemplar label `trace_id` to Tempo's
data-source UID `tempo`.

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
existing Compose project. It starts only that disposable local project, runs
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

## Grafana 12.1.1 access limitation

The issue's current Compose settings grant anonymous users only the `Viewer`
role, disable the login form, and disallow sign-ups. Grafana's versioned
[role-permission table for 12.1](https://grafana.com/docs/grafana/v12.1/administration/roles-and-permissions/)
states that Viewer does **not** have **Access Explore** permission (Editor and
organization administrator do). Therefore the anonymous Viewer can see the
dashboard exemplar but cannot follow its Grafana **Trace** link into Explore.
There is no sign-in path or authenticated Viewer account provisioned by this
local Compose configuration. Creating an Editor/Admin or weakening the
anonymous role just to make the link work would be an unsafe privilege change;
this procedure does neither. A user who already has an authorized Grafana
account in a separately configured local instance can sign in there and use
the dashboard link, but that is not reproducible from this clean checkout.

The exemplar's exact ID and the isolated script's direct Tempo trace lookup
verify correlation independently of Grafana permissions. However, the
Grafana-UI navigation criterion remains **not verified for the default local
Viewer** until the project has a safe, explicitly authorized local-account
provisioning path. The permission limitation is not evidence that the metric or
trace data is incompatible.

## Follow-up verification evidence (2026-10-28)

The focused backend observability tests pass (4 tests). The synthetic Compose
script's preflight failed closed because the local Docker engine did not have
`ghcr.io/astral-sh/uv:0.12.5` or `python:3.12-slim`, which are required to
build this checkout's API image. It did not pull images, create a Compose
project, start services, or produce a new trace ID; therefore this follow-up
does not claim a live metric-to-Tempo integration pass. Prometheus `3.5.0`,
Grafana `12.1.1`, Collector Contrib `0.136.0`, Loki `3.5.3`, and Tempo `2.8.1`
images were already available locally. The Grafana Viewer/Explore limitation
above was independently checked against Grafana's 12.1 role-permission table.

The backend test `test_request_metric_exposes_exact_trace_as_openmetrics_exemplar`
also sends a synthetic request to the harmless empty-run-list route and verifies
that the OpenMetrics counter sample's exemplar exactly matches the exported
span trace ID. Existing tests continue to check that trace IDs, owner IDs, and
run IDs are absent from metric labels and that trace/log correlation is
preserved.
