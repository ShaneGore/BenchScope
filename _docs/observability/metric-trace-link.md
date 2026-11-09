# Local metric-to-trace link

## Verification at merged revision `12c3206` (2026-11-09)

The documented isolated verifier below built the current API from
`12c32064f9ef3ac36539fa26cd7a9ccd5315b82b` with build-input fingerprint
`f2aea6ae2b921f084a3df3434985600597c7eb71464e9d7ec42900c237fed00f`.
A synthetic `GET /api/v1/runs` returned an empty page from a disposable
database. The Prometheus exemplar, Tempo span, Loki request log and anonymous
Grafana Tempo proxy matched trace `802cccdd7ebb4fc79cdd9750c0f8063d`; the
request span ID was `20e0cee9bf281408`. The verifier exited successfully and
removed its disposable project, volumes and image. This is local evidence,
not hosted observability verification.

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

From a checkout on Windows with Docker Desktop and PowerShell, run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\verify_metric_trace.ps1
```

The script uses a random Compose project name, a disposable synthetic-only env
file and secret, unique loopback ports, and project-scoped volumes. It never
reads `.env`; every Compose invocation supplies the temporary env file and
explicit project/file paths. It refuses a non-local Docker endpoint, missing
cached service images or Dockerfile bases, or unavailable ports; it never pulls
images or touches an existing Compose project. It builds a uniquely tagged API
image with `--pull=false`, while allowing the locked dependency install to reach
its configured package index over TLS. `uv sync --frozen` uses the committed
lockfile and its artifact hashes; Docker base and service images must already be
local. It records the Git revision and a SHA-256 fingerprint of the Dockerfile
and copied backend inputs (including dirty checkout changes), checks the
fingerprint after build and verification, and checks the running container image
ID against the build.
It starts only that disposable local project with `--no-build --pull never`, runs
`GET /api/v1/runs` with a generated W3C `traceparent`, and removes only its own
containers, volumes, image tag and files afterward. Cleanup failures cause a
nonzero exit. The endpoint returns an empty page from the
newly created project database; the script fails if that database contains a
run. No run data is imported or persisted. The local-only auth bypass is
enabled only in the synthetic API container, and benchmark execution remains
disabled.

The check polls Prometheus for the exact generated trace ID on the
`benchscope_http_server_requests_total` exemplar for
`/api/v1/runs`, verifies the ID is not a series label, then
fetches that ID from Tempo and the anonymous Grafana Tempo proxy, and requires
the actual Loki `HTTP request completed` record to carry that trace ID and the
same request span ID, route, method and status. It prints the actual Prometheus version, locked API telemetry
package versions, pinned local service image versions, exemplar ID, and Tempo
IDs. A nonzero exit means the integration check did not pass; missing images or
ports are reported before Compose starts. The images must already be present
locally; this procedure does not download them.

Docker-free verifier checks run with
`powershell -NoProfile -ExecutionPolicy Bypass -File .\backend\tests\test_metric_trace_verifier.ps1`.

### Fresh-image verification attempt (2026-11-07)

The local bases and service images were present, but the offline fresh build
could not reuse the locked dependency layer and failed fetching `idna==3.20`
with build networking disabled. This attempt was superseded by the successful
current-source run recorded below.

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

## Current-source verification (2026-11-08)

The earlier fresh-build failure was caused by the verifier's `--network none`
build setting, not a Compose parsing or Docker DNS defect. Windows DNS and
TLS-verified HTTPS requests to `pypi.org` and the locked wheel URL on
`files.pythonhosted.org` succeeded (HTTP 200). The Docker BuildKit environment
resolved both hosts and also returned HTTP 200 with TLS verification enabled.
Docker's bridge network had no custom DNS option; a Docker Desktop HTTP(S)
proxy was configured. The Windows uv cache contained the locked
`opentelemetry-api==1.45.1` wheel, but that host cache was not mounted into
BuildKit and did not provide the complete Linux image dependency cache.

The verifier now allows normal network access only for the Dockerfile's
`uv sync --frozen` dependency install while retaining `--pull=false`; package
selection and artifact hashes remain controlled by `uv.lock`, and all base and
observability images must already be local.

Command:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\verify_metric_trace.ps1
```

Verified from main revision `5f3a151b7b963c2e703e41b7b5150c13b0f86606`,
API build-input SHA-256
`d54e05fa4e566a70a36c2661e6b4efb93a7a7fbc7dec409beb245511ba591c9f`,
fresh API image ID
`sha256:831adfda1c34354e723891e06c49121f773eff55d32f4772c69beb4bd5edfbcf`.
The isolated synthetic `GET /api/v1/runs` returned an empty page. Prometheus
exemplar, Tempo span, Loki `HTTP request completed` stream metadata, and the
anonymous Grafana Tempo proxy all matched trace ID
`950ff61eb92744d488d0097a40068c08`; the Tempo/request span ID was
`6382e442c78ee310`. The Loki response placed trace/span and HTTP attributes in
the stream metadata, with the log body and timestamp as a two-element value;
the verifier had incorrectly expected metadata as a third value element.
The verifier now checks the actual Loki response shape and fails if the trace,
span, route, method, status, or log body differs.

The run used Prometheus `3.5.0`, Grafana `12.1.1`, Collector Contrib `0.136.0`,
Tempo `2.8.1`, Loki `3.5.3`, PostgreSQL `17-alpine`, and the locked API
telemetry versions above. Project `benchscope-metric-trace-b1effe78937c` was
removed with its containers, volumes, network, temporary files, and image.
The pre-existing local Compose services remained running. The PowerShell
verifier regression tests and `backend/tests/test_observability.py` passed.
