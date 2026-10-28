# Task 23 — Local API availability exercise

## Result

**Passed as an injected local outage and API-only recovery.** The exercise
used a unique disposable Compose project, synthetic settings/data, and
loopback-published endpoints. The only injected cause was the intentional API
stop. No hosted service or production behavior was involved; no application
or alert-rule fix is claimed.

All timestamps below are UTC. No credentials, owner identifiers, prompts,
benchmark output, or raw benchmark artifacts were recorded.

## Timeline and sanitized evidence

| Time | Event and result |
|---|---|
| 2026-10-27 05:48:57.675Z | Initial preflight found `127.0.0.1:5432` occupied; fixed API/observability ports were free. Per the then-current gate, the attempt was correctly aborted without starting services or altering the listener. |
| 2026-10-27 05:56:30.443Z | After the PM approved `POSTGRES_PORT`, rechecked fixed ports `8000`, `4318`, `9090`, `3100`, `3200`, `3000` and the DB candidates. All fixed ports and DB host port `15441` were free; selected `15441`. |
| 2026-10-27 05:58:23.347Z | Started local project `benchscope-task23-f5ecf142d10e4cad873d5ad4299a1b4d` in Docker context `desktop-linux` (local Docker Desktop named pipe). The temporary, ignored `.env.task23` contained only synthetic DB/API settings and was not committed. |
| 2026-10-27 05:59:24.570Z | Baseline: DB, API, Prometheus, Grafana, Loki, and Tempo were healthy; collector was running. API `/health` returned HTTP 200; `/ready` returned `{"status":"ready"}`. Prometheus target `api:8000` was `up`, `up{job="api"}` was `1`, and the alert was inactive. |
| 2026-10-27 06:01:54.630Z | Issued `docker compose --env-file .env.task23 -p benchscope-task23-f5ecf142d10e4cad873d5ad4299a1b4d stop api`; API stop completed at 06:01:55.327Z. No other service was stopped. |
| 2026-10-27 06:02:27.633Z | Pending observed: `/health` and `/ready` returned no HTTP response; Prometheus query was `api:8000=0`, target health `down`, `ALERTS{alertname="BenchScopeApiUnavailable"}` had state `pending`, value `1`. Grafana dashboard returned HTTP 200 and its “Local API availability alert” panel displayed `pending`. |
| 2026-10-27 06:04:48.643Z | Firing observed after 173.3 seconds stopped: both API endpoint checks still had no HTTP response; `up` remained `0`; alert state/series was `firing`, value `1`; Grafana dashboard returned HTTP 200. Its alert panel showed the pending and firing states. Compose showed only the API exited (143); DB and observability services remained healthy/running. |
| 2026-10-27 06:05:20.988Z | Before recovery, `pg_isready` reported the disposable DB accepting connections. Sanitized API configuration: `APP_MODE=local`, `APP_ENV=development`, `LOCAL_AUTH_BYPASS=false`, database target `db:5432/benchscope_incident` (credentials redacted). DB config was synthetic user `incident`, database `benchscope_incident` (password redacted). |
| 2026-10-27 06:05:20.988Z | Relevant sanitized logs showed API readiness health checks returning 200 before the stop and a graceful Uvicorn shutdown; PostgreSQL initialization completed and the database reported ready to accept connections. No API trace is expected while its process is stopped. |
| 2026-10-27 06:05:37.435Z | Started only the same project's API. `/ready` succeeded at 06:05:41.545Z. At 06:05:56.601Z, API health was HTTP 200, Prometheus returned `up=1`, and the active alert list no longer contained `BenchScopeApiUnavailable`. |
| 2026-10-27 06:08:26.569Z | Ran the exact project-scoped `promtool test rules /etc/prometheus/api-alert-test.yml`; it returned `SUCCESS` (exit 0) at 06:08:27.653Z, including pending, firing, and resolution expectations. |
| 2026-10-27 06:09:14.666Z | Removed only this project with `down --volumes --remove-orphans --rmi local`; removed `.env.task23`. Cleanup completed at 06:09:18.374Z. |

Compose published only loopback endpoints: DB `127.0.0.1:15441->5432`,
API `127.0.0.1:8000->8000`, OTLP `127.0.0.1:4318->4318`, Prometheus
`127.0.0.1:9090->9090`, Loki `127.0.0.1:3100->3100`, Tempo
`127.0.0.1:3200->3200`, and Grafana `127.0.0.1:3000->3000`. The API retained
its internal `db:5432` database URL. `POSTGRES_PORT=15441` changed only the
disposable database's host publication. The listener previously observed on
host port 5432 was not touched.

## Cause, impact, and recovery

The injected cause was the deliberate stop of only this project's API. It
remained stopped for about 222.1 seconds through the API restart. Impact was
limited to the disposable local stack; PostgreSQL and the observability
services stayed healthy. No product/database root cause was inferred and no
application code or alert rule was changed. Recovery was starting the stopped
API after confirming DB health and sanitized API/DB configuration/logs.

## Cleanup verification

After teardown, the exact project had zero containers, volumes, networks, or
project-built API images. `.env.task23` was absent. The selected published
ports `8000`, `4318`, `9090`, `3100`, `3200`, `3000`, and `15441` had no
listeners. No other Compose project or the original 5432 listener was
stopped, altered, or cleaned up.

## Issue #32 — Stage 1 authenticated alert intake

This is a local-only verification of Grafana's managed
`BenchScopeApiUnavailable` rule evaluating Prometheus data and sending a
bearer-authenticated webhook directly to the receiver. It verifies a sanitized incident
record and its resolved update. It does **not** verify AI investigation,
recovery automation, or completion of the course incident-response criterion.
Use synthetic data only. Do not use the repository `.env`, hosted services,
real user data, private benchmark material, external notification targets, or
a mock receiver.

The default published ports (`8000`, `4318`, `9090`, `3100`, `3200`, `3000`)
were occupied, so this disposable project uses alternate loopback ports:
API `18000`, OTLP `14318`, Prometheus `19090`, Loki `13100`, Tempo `13200`,
Grafana `13000`, and PostgreSQL `15442`. A listener-only check found these
alternates free, but recheck immediately before startup. Grafana owns the
notification-driving rule and delivers firing/resolved webhooks directly to
the receiver; no standalone Alertmanager image is needed. Prometheus retains
a non-notifying mirror only for the existing dashboard and `promtool` rule
test.

From the repository root in a clean PowerShell session, confirm the Docker
context is local, the exact disposable project does not already exist, and
all seven alternate TCP ports are free. If any is occupied or the listener
check is uncertain, abort without stopping or changing anything.

```powershell
$project = "benchscope-incident-response-disposable"
$context = docker context show
$endpoint = docker context inspect $context --format '{{.Endpoints.docker.Host}}'
if ($endpoint -notmatch '^(npipe:|unix://)') { throw "Not a local Docker context; abort." }

if (@(docker ps -aq --filter "label=com.docker.compose.project=$project").Count -gt 0) {
  throw "The disposable Compose project already exists; inspect it and abort."
}

$requiredPorts = 18000, 14318, 19090, 13100, 13200, 13000, 15442
try {
  $listeners = [System.Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners()
} catch {
  throw "Port check failed or is uncertain; abort without starting Compose."
}
$busyPorts = @($listeners | Where-Object { $requiredPorts -contains $_.Port })
if ($busyPorts.Count -gt 0) {
  $busyPorts | Sort-Object Port, Address | Format-Table Address, Port
  throw "A required alternate port is occupied; abort without changing its listener."
}
$dbPort = 15442

$requiredImages = @(
  "postgres:17-alpine",
  "prom/prometheus:v3.5.0",
  "grafana/loki:3.5.3",
  "grafana/tempo:2.8.1",
  "grafana/grafana:12.1.1",
  "otel/opentelemetry-collector-contrib:0.136.0",
  "ghcr.io/astral-sh/uv:0.12.5",
  "python:3.12-slim"
)
foreach ($image in $requiredImages) {
  docker image inspect $image *> $null
  if ($LASTEXITCODE -ne 0) { throw "Required image is not cached; do not pull it; abort." }
}
```

Only after that preflight succeeds, make the dedicated ignored configuration
file `.env.incident-response-disposable` and its ignored Compose-secret file.
Both credentials below are generated randomly and remain local. The bearer is
provided to the receiver as a Compose secret and to Grafana through the ignored
local Compose environment file; it is never printed.

```powershell
New-Item -ItemType Directory -Force secrets | Out-Null
$bytes = New-Object byte[] 32
$rng = [Security.Cryptography.RandomNumberGenerator]::Create()
$rng.GetBytes($bytes)
$dbPassword = [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+', 'x').Replace('/', 'y')
$rng.GetBytes($bytes)
$bearer = [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+', 'x').Replace('/', 'y')
[IO.File]::WriteAllText((Join-Path $PWD "secrets/alert-receiver-bearer"), $bearer, [Text.Encoding]::ASCII)
[Array]::Clear($bytes, 0, $bytes.Length)
$rng.Dispose()

@"
POSTGRES_DB=benchscope_incident
POSTGRES_USER=incident
POSTGRES_PASSWORD=$dbPassword
POSTGRES_PORT=$dbPort
API_PORT=18000
OTLP_PORT=14318
PROMETHEUS_PORT=19090
LOKI_PORT=13100
TEMPO_PORT=13200
GRAFANA_PORT=13000
ALERT_RECEIVER_SECRET_FILE=./secrets/alert-receiver-bearer
ALERT_RECEIVER_BEARER=$bearer
APP_MODE=local
APP_ENV=development
LOCAL_AUTH_BYPASS=false
BENCHMARK_ENABLED=false
"@ | Set-Content -Encoding ascii .env.incident-response-disposable
Remove-Variable dbPassword, bearer

docker compose --env-file .env.incident-response-disposable -p $project config --quiet
try {
  $listeners = [System.Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners()
} catch {
  throw "Final port check failed; abort without starting Compose."
}
if (@($listeners | Where-Object { $requiredPorts -contains $_.Port }).Count -gt 0) {
  throw "An alternate port became occupied; abort without changing its listener."
}
# Run only after confirming every required image is cached; do not pull images.
docker compose --env-file .env.incident-response-disposable -p $project up --build --pull never --wait --detach
docker compose --env-file .env.incident-response-disposable -p $project ps
```

Do not substitute `.env` or start the default Compose project. The receiver
has no published host port; Grafana reaches it at
`http://alert-receiver:8001/grafana/v1` on the private Compose network. This
project publishes its API, OTLP, Prometheus, Loki, Tempo, Grafana, and database only on the alternate
loopback ports above; the normal Compose defaults remain unchanged.

Verify the API, Prometheus, Loki, Tempo, and Grafana health URLs; confirm
`up{job="api"}` is `1`, the alert is clear, and no existing incident record
is being mistaken for this exercise. Then stop only this project's API and
wait long enough for Grafana's one-minute rule and webhook delivery:

```powershell
Invoke-RestMethod http://127.0.0.1:18000/ready
Invoke-RestMethod http://127.0.0.1:19090/-/healthy
Invoke-RestMethod http://127.0.0.1:13100/ready
Invoke-RestMethod http://127.0.0.1:13200/ready
Invoke-RestMethod http://127.0.0.1:13000/api/health
curl.exe --fail 'http://127.0.0.1:19090/api/v1/query?query=up%7Bjob%3D%22api%22%7D'
docker compose --env-file .env.incident-response-disposable -p $project stop api
Start-Sleep -Seconds 100
Invoke-RestMethod "http://127.0.0.1:19090/api/v1/alerts"
curl.exe --fail 'http://127.0.0.1:19090/api/v1/query?query=ALERTS%7Balertname%3D%22BenchScopeApiUnavailable%22%2Calertstate%3D%22firing%22%7D'
docker compose --env-file .env.incident-response-disposable -p $project exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -F "|" -c "SELECT alert_status, evidence_status FROM incident_records ORDER BY received_at DESC LIMIT 1"'
```

Grafana's `BenchScopeApiUnavailable` rule must be firing and the database row
must show `firing|complete` for complete evidence. The Prometheus mirror may
also show firing, but it has no notification route. `firing|partial` or
`firing|failed` proves authenticated webhook delivery but records incomplete
diagnostics; record that state without describing the evidence as complete.
No row means delivery was not verified. The receiver writes no record for
missing or invalid authentication, and it stores no raw webhook or datasource
response.

Restart only this project's API. Wait for readiness and `up=1`; allow up to
60 seconds for Grafana's 30-second evaluation and notification intervals to
deliver the resolved webhook. Then confirm the same incident row is resolved
rather than duplicated:

```powershell
docker compose --env-file .env.incident-response-disposable -p $project start api
Invoke-RestMethod http://127.0.0.1:18000/ready
Start-Sleep -Seconds 60
curl.exe --fail 'http://127.0.0.1:19090/api/v1/query?query=up%7Bjob%3D%22api%22%7D'
Invoke-RestMethod http://127.0.0.1:19090/api/v1/alerts
docker compose --env-file .env.incident-response-disposable -p $project exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -F "|" -c "SELECT alert_status, evidence_status FROM incident_records ORDER BY received_at DESC LIMIT 1"'
```

Before cleanup, verify that every container carries the exact
`com.docker.compose.project=benchscope-incident-response-disposable` label.
Remove only that verified project, its disposable volumes, generated local
image, configuration file, and secret file. Verify that no project-labelled
containers or volumes remain. If project identity is uncertain, do not run
`down`.

```powershell
$containers = @(docker ps -aq --filter "label=com.docker.compose.project=$project")
if ($containers.Count -eq 0) { throw "Project containers not found; inspect before cleanup." }
$labels = docker inspect --format '{{ index .Config.Labels "com.docker.compose.project" }}' $containers
if (@($labels | Where-Object { $_ -ne $project }).Count -gt 0) { throw "Project identity mismatch; do not clean up." }
docker compose --env-file .env.incident-response-disposable -p $project down --volumes --remove-orphans --rmi local
Remove-Item .env.incident-response-disposable
Remove-Item secrets/alert-receiver-bearer
docker ps -a --filter "label=com.docker.compose.project=$project"
docker volume ls --filter "label=com.docker.compose.project=$project"
```

This exercise demonstrates only authenticated local alert delivery, persistent
deduplication, and bounded sanitized evidence. It does not demonstrate AI
investigation, recovery automation, or completion of the course criterion.

## Issue #33 — Stage 2 read-only investigation

The local `app.incident_investigation` runner accepts only a persisted
`IncidentRecord` with a schema-valid Stage 1 evidence bundle in `complete` or
`partial` state, serialized at no more than 64 KiB. It sends only the
allowlisted evidence, completion status, and truncation flags in the prompt.
It stores a summary only after capability checks, selected/effective model
checks, model-specific usage validation, UTF-8/4 KiB bounds, and sentinel checks
pass. Post-call usage is not proof of pre-request authorization or a cost limit.
It adds no recovery or benchmark operation.

The unmerged Stage 2 migration uses revision `0005_incident_summary`, short
enough for Alembic's default PostgreSQL `VARCHAR(32)` version column. The
previous 35-character revision was replaced based on the report that it had
not been applied to PostgreSQL; no database was inspected or modified here.
If any database has the old revision, inspect its state and reconcile it
explicitly before upgrading; do not blindly stamp it. Open PR #38 has a
separate `0005_cancelled_run_status` migration with the same
`0004_incident_records` parent. If PR #38 merges first, reconcile the Stage 2
migration history with the merged head before applying it.

The adapter is **blocked from making model requests**, including direct calls
to `invoke`. Its candidate arguments retain exactly `--model=gpt-6-luna`, an
empty `--available-tools=` filter and disabled built-in MCPs; they do not
grant `--allow-all-tools`. They are not claimed to enforce a safe runtime
policy. Read-only flags alone do not rule out read or network tools.
The preflight is designed to inspect only `--help`, permissions help, and
`--version`, but actual subprocess creation is currently blocked on all
platforms, including for preflight. Mocked preflight normalizes wrapped
permissions text. Such documentation can describe the
intended filter, and version parsing can show argument acceptance, but neither
establishes that the runtime exposes no tools before a request. Even an empty
`serverTools` list in a response is post-call evidence, not pre-request proof.
The CLI's requirement for a non-interactive tool permission remains unresolved
without a broad grant.

An arbitrary GitHub token is not proof of an existing Copilot entitlement.
Likewise a caller's cost opt-in, a soft credit cap, and post-session usage
metadata do not verify applicable usage limits before a request. The provider
therefore reports tool restrictions, entitlement, and usage/cost as unverified
regardless of token or opt-in. The output parsers remain available for mocked
validation, not as authorization to invoke.

Earlier local checks reported Copilot CLI 1.0.103 with automatic updates
enabled, while a separate check with `--no-auto-update` used bundled 1.0.81.
The current provider arguments do **not** include `--no-auto-update`, and no
current runtime version is asserted. The bundled 1.0.81 did not accept flags such as
`--disable-client-telemetry`, `--max-ai-credits`, or
`--usage-output-file`; those flags were rejected before a model request. The
1.0.103 help documents `--usage-output-file` as final, post-session usage and
`--max-ai-credits` as a minimum-30-credit **soft cap** that may be exceeded by
a response. Neither provides a pre-request authorization or usage check.

After adding the required `--allow-all-tools` permission flag while retaining
the empty `--available-tools=` filter, a bounded synthetic probe used the
production model and prompt flags under the then-existing Windows Job Object
cleanup, whose interruption and complete containment were not proven.
The CLI process log records a successful model-call event, but its captured
JSON event output exceeded both 16 KiB and a diagnostic 64 KiB bound. The
runner therefore could not parse selected/effective model metadata or a
sanitized summary, and no summary was stored. Usage was not captured; the
attempt may have consumed Copilot usage. No fallback model, OAuth flow, new
entitlement, benchmark, or hosted service was used. The live acceptance
criterion remains unmet.

Stage 1's `app.alert_receiver` collects and persists evidence; it neither imports
nor calls the investigator. No alert-receiver endpoint, callback, or background
task triggers investigation. The runner exposes Python functions requiring an
explicit caller, database session, record ID, and provider; no automatic
integration or host-side command is provided. Compose runs the receiver in a
backend container; the backend image does not install Copilot CLI or bridge it
to the host. A host CLI and its credentials are not automatically available
inside that container. No container-to-host execution path has been implemented
or verified.

The automated tests use fake providers and mocked CLI preflight output. They
exercise validation and fail-closed gates, including process-creation guards;
they are **not evidence that a live investigation works**. A POSIX process
group cannot contain descendants that escape it, and the former Windows
implementation did not protect the entire startup and cancellation lifecycle.
No platform currently has verified complete containment, cancellation cleanup,
or a 60-second total deadline. The former process launcher and cleanup code
were removed; no cleanup or timeout coverage is claimed. Before enabling any
subprocess, prove full-tree containment and interruption-safe cleanup, including
startup and the total deadline, on that platform. Effective live model identity,
tool-policy enforcement, and authorization/usage limits also remain unverified.
Stage 2 stays incomplete.
