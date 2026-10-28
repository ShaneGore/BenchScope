# BenchScope

BenchScope is a local-first web application for recording, comparing, and understanding the performance of local language models on an independent coding benchmark. It turns isolated benchmark results into a durable, inspectable history while keeping the proprietary benchmark itself out of this repository.

## Problem

Developers running local language models often produce one-off benchmark results that are hard to compare across model versions, quantisations, inference settings, hardware configurations, and time. BenchScope provides a persistent observatory for those results: import an existing result, inspect it, and compare it with earlier results.

## What the system does

- Imports supported JSON result files, validates required fields, normalises metrics, reports errors, and avoids duplicates where a stable ID or fingerprint is available.
- Persists imported results and supports history, run detail, filtering, and comparison.
- Distinguishes missing metrics from zero values.
- Supports model profiles with name, version, quantisation, endpoint, hardware notes, and benchmark settings.
- Provides a read-only synthetic demo for unauthenticated visitors.
- Supports personal authenticated workspaces in hosted mode, with backend-enforced ownership isolation.
- Real benchmark launch and cancellation are not implemented; both remain tracked by #25. Hosted mode imports results and never runs benchmarks.

## Operating modes

### Local/private mode

- Local result import, persistence, history, detail, and comparison.
- Service binds to the loopback interface by default.
- Real benchmark launch and cancellation are unavailable and tracked by #25.
- Local model endpoints, private benchmark paths, and private artifacts are not exposed.

### Hosted multi-user mode

- Individual users sign in and maintain private profiles and result history.
- Unauthenticated visitors can explore a read-only demo populated with synthetic results.
- Hosted mode does not connect to model endpoints on a user's computer and does not run the private benchmark.
- Independently produced benchmark result files can be imported into hosted workspaces.
- Hosted import processing extracts only allowlisted, non-confidential metrics and metadata and discards the uploaded raw payload.

## Current implementation status

This repository currently contains:

- A React/Vite/TypeScript frontend with Dashboard, Runs, Run Detail, Compare, Import, Profiles, and Benchmark pages.
- A FastAPI backend with local profile, import, persisted run-history/comparison, demo, and benchmark-capability API routes plus `/health` and `/ready`. Benchmark capability discovery is not benchmark execution.
- A hand-authored OpenAPI contract at `openapi.yaml`, derived from the frontend service interface.
- Generated typed frontend contract artifacts at `frontend/src/types/api.generated.ts`.
- Contract tests in `frontend/src/contract/` and `backend/tests/test_contract.py`.
- Environment-selected API services for local/hosted personal data, an anonymous read-only demo service, and mock fixtures for tests.
- Docker Compose support for the static frontend, backend, PostgreSQL, and OpenTelemetry/Prometheus/Loki/Tempo/Grafana.

The results observatory is implemented: supported results can be imported and
persisted, then viewed in history and detail or compared. Real benchmark
launch and cancellation are unavailable and tracked by #25. Backend domain
routes are under `/api/v1`; see `backend/app/main.py` and the routers under
`backend/app/`.

## Expected behavior

- Application starts using documented instructions.
- Valid result files can be imported and remain available after restart.
- Malformed imports produce clear errors and do not create partial records.
- Duplicate imports are identified when a stable source ID or fingerprint is available.
- Imported results display available metrics in history and detail and can be compared.
- Missing metrics are shown as unavailable, never zero.
- Hosted users can only read, alter, or delete their own records.
- Anonymous visitors can use the read-only synthetic demo without an account.
- No proprietary benchmark code, confidential evaluation material, credentials, or private artifacts are committed or publicly served.

## Repository layout

```text
backend/          FastAPI backend and tests
frontend/         React/Vite frontend and tests
openapi.yaml      Initial API contract
_docs/            Product plan, architecture, task tracker, process docs
compose.yaml      Local full application and observability stack
```

## Frontend

From `frontend/`:

```sh
corepack pnpm install --frozen-lockfile
corepack pnpm test
corepack pnpm build
corepack pnpm gen:api
corepack pnpm check:api
```

For Vite/HMR, keep the configured local CORS origins on port 5173. If the
Compose stack is running, stop only its frontend service before starting Vite;
the API and observability services can remain up:

```powershell
docker compose stop frontend
$env:VITE_API_URL = "http://127.0.0.1:8000"
$env:VITE_OTEL_EXPORTER_OTLP_ENDPOINT = "http://127.0.0.1:4318/v1/traces"
corepack pnpm exec vite --host 127.0.0.1 --port 5173 --strictPort
```

Open <http://127.0.0.1:5173>. Stop Vite before restoring the static frontend
with `docker compose start frontend`. Alternatively, use the Compose static
frontend directly without starting Vite. Clear the shell environment variables
when done:

```powershell
Remove-Item Env:VITE_API_URL, Env:VITE_OTEL_EXPORTER_OTLP_ENDPOINT
```

## Backend

From `backend/`:

```sh
uv sync --locked --group dev
uv lock --check
uv run uvicorn app.main:app --reload
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

## CI quality gates

`.github/workflows/ci.yml` runs on pull requests and pushes to `main`. Its
`backend` and `frontend` jobs are blocking quality, test, and API-contract
checks within each workflow run. Repository branch-protection or ruleset
requirements are not verified; see follow-up #26. The backend job uses a health-checked,
ephemeral PostgreSQL service and runs the full test suite, including OpenAPI
contract tests. The frontend build includes `tsc --noEmit`, and `check:api`
verifies generated API types have no drift. No optional checks are included.
The separate Playwright `test:journey` script is not part of this required
workflow.

The workflow has read-only repository permissions and needs no credentials,
private benchmark materials, model weights, GPU, or paid service. Docker image
builds are included without registry login or publishing. CI also builds a
Pages-path-configured static Vite artifact and verifies its asset paths and
separate public API URL. GitHub Pages serves only that static frontend; the
FastAPI API is a separate service. See
`_docs/architecture/deployment.md` for configuration boundaries and the
required pre-provisioning provider/owner checks.

To run the same checks locally, start a disposable PostgreSQL instance and set
`TEST_DATABASE_URL` to its URL. From the repository root in PowerShell:

```powershell
$env:TEST_DATABASE_URL = "postgresql+psycopg://<user>:<password>@127.0.0.1:<port>/<database>"
Push-Location backend
uv sync --locked --group dev
uv lock --check
uv run ruff check .
uv run ruff format --check .
uv run pytest
Pop-Location

Push-Location frontend
corepack pnpm install --frozen-lockfile
corepack pnpm test
corepack pnpm build
corepack pnpm check:api
$env:VITE_BASE_PATH = "/pages-preview/"
$env:VITE_API_URL = "https://api.example.invalid"
corepack pnpm exec vite build --outDir dist-pages
node scripts/check-static-build.mjs dist-pages
Remove-Item Env:VITE_BASE_PATH, Env:VITE_API_URL
Pop-Location
Remove-Item Env:TEST_DATABASE_URL
```

## API contract

- Initial committed artifact: repository-root `openapi.yaml`.
- Hosted personal endpoints require a Clerk session JWT. Configure the backend with `CLERK_JWKS_URL`, `CLERK_ISSUER`, and `CLERK_AUDIENCE`; configure hosted frontend builds with `VITE_APP_MODE=hosted` and its Clerk publishable key through `VITE_CLERK_PUBLISHABLE_KEY`.
- `LOCAL_AUTH_BYPASS` defaults to `false`. To explicitly enable offline local auth, set `APP_ENV=development`, `APP_MODE=local`, and `LOCAL_AUTH_BYPASS=true`; `HOST` must resolve only to loopback. `APP_ENV` defaults to `production`, and any invalid bypass combination fails startup.
- Regenerate frontend types: `cd frontend && pnpm gen:api`.
- Check generated types for drift: `cd frontend && pnpm check:api`.
- FastAPI-generated OpenAPI becomes authoritative after backend feature work; reconcile `openapi.yaml` before integrating the real API client.

## Local application stack with Compose

Prerequisites: Docker Engine or Docker Desktop with Compose v2. The host ports
5173 (frontend), 8000 (API), 4318 (OTLP), 9090 (Prometheus), 3100 (Loki),
3200 (Tempo), 3000 (Grafana), and 5432 (PostgreSQL by default) must be
available. Compose publishes them on `127.0.0.1` only.

Copy `.env.example` to `.env` and replace the password placeholder with a
local URL-safe password (`Copy-Item .env.example .env` in PowerShell, or
`cp .env.example .env` elsewhere). For offline local API use, set
`LOCAL_AUTH_BYPASS=true`; it is disabled by default and only accepted in
development/local mode. Never enable the bypass in a hosted deployment.

The alert receiver reads its bearer secret from a Compose secret file; Grafana
provisioning reads the same value from `.env`. Generate the secret without
printing or committing it:

```powershell
New-Item -ItemType Directory -Force secrets | Out-Null
$bytes = New-Object byte[] 32
$rng = [Security.Cryptography.RandomNumberGenerator]::Create()
$rng.GetBytes($bytes)
$secret = [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+', 'x').Replace('/', 'y')
[IO.File]::WriteAllText("secrets/alert-receiver-bearer", $secret, [Text.Encoding]::ASCII)
$envFile = [IO.File]::ReadAllText(".env")
$envFile = [regex]::Replace($envFile, '(?m)^ALERT_RECEIVER_BEARER=.*$', "ALERT_RECEIVER_BEARER=$secret")
[IO.File]::WriteAllText(".env", $envFile)
[Array]::Clear($bytes, 0, $bytes.Length)
$rng.Dispose()
Remove-Variable secret
```

Before starting Compose, confirm the selected Docker context points to a local
engine. In PowerShell:

```powershell
$context = docker context show
$endpoint = docker context inspect $context --format '{{.Endpoints.docker.Host}}'
if ($endpoint -notmatch '^(npipe:|unix://)') { throw "Not a local Docker context; abort." }
```

Start the full application and observability stack with one command:

```powershell
docker compose up --build --wait --detach
```

The frontend is built as a static site with API and OTLP URLs pointing to the
loopback-published services. The API applies database migrations before it
becomes healthy.

| Service | URL |
| --- | --- |
| BenchScope | <http://127.0.0.1:5173> |
| API health / readiness | <http://127.0.0.1:8000/health> / <http://127.0.0.1:8000/ready> |
| Grafana | <http://127.0.0.1:3000> |
| Prometheus | <http://127.0.0.1:9090> |
| Loki | <http://127.0.0.1:3100> |
| Tempo | <http://127.0.0.1:3200> |

`API_PORT` can change the API's host port; rebuild the frontend when changing
it because `VITE_API_URL` is embedded at build time. `POSTGRES_PORT` changes
the PostgreSQL host port and defaults to 5432. The API still connects to the
database over the private Compose network.

Stop safely while keeping PostgreSQL and observability data:

```sh
docker compose down
```

This removes containers and the Compose network but retains named volumes.
Only use `docker compose down --volumes` when intentionally deleting that
persistent data.

### PostgreSQL migrations and integration tests

From `backend/`, set `DATABASE_URL` to the local Compose database URL and run
`uv run alembic upgrade head` to apply the baseline. For integration tests,
set `TEST_DATABASE_URL` to a disposable PostgreSQL database; the test creates
and drops its own isolated schema. It refuses non-PostgreSQL URLs and skips
when the variable is unset. For example, in PowerShell:

```powershell
$env:DATABASE_URL = "postgresql+psycopg://<user>:<password>@127.0.0.1:<port>/<database>"
uv run alembic upgrade head
$env:TEST_DATABASE_URL = $env:DATABASE_URL
uv run pytest tests/test_postgres_storage.py
Remove-Item Env:DATABASE_URL, Env:TEST_DATABASE_URL
```

### Local frontend/API browser smoke

The local-mode frontend uses `VITE_API_URL` for FastAPI and sends privacy-safe
browser traces to the local OTLP collector. Compose binds every service to
loopback; no hosted telemetry endpoint or external notification receiver is
configured. Local authentication bypass is only for a developer workstation.

The Playwright journey starts its own Vite server on port 5173, so do not start
Compose's `frontend` service at the same time. First copy `.env.example` to
`.env` and configure its password and local auth bypass as described above.

Start only the API and observability services required by the journey. The
Compose API container applies its Alembic migrations before serving requests:

```powershell
docker compose up --build --wait --detach db api alert-receiver otel-collector prometheus loki tempo grafana
docker compose ps
Invoke-RestMethod http://127.0.0.1:8000/ready
Invoke-WebRequest http://127.0.0.1:8000/metrics
Invoke-RestMethod http://127.0.0.1:9090/-/healthy
Invoke-RestMethod http://127.0.0.1:3100/ready
Invoke-RestMethod http://127.0.0.1:3200/ready
Invoke-RestMethod http://127.0.0.1:3000/api/health
```

Install and run the real-UI journey from `frontend/`. Playwright starts Vite
with `VITE_API_URL=http://127.0.0.1:8000` and
`VITE_OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4318/v1/traces`:

```powershell
Push-Location frontend
corepack pnpm install --frozen-lockfile
corepack pnpm exec playwright install chromium
corepack pnpm test:journey
Pop-Location
```

The journey imports one synthetic valid run, views it in history and detail,
and submits an invalid import. Browser request spans and FastAPI spans carry
W3C trace context into Tempo; FastAPI's structured, payload-free request logs
go to Loki. Open Grafana at
`http://127.0.0.1:3000/d/benchscope-local-journey/benchscope-local-journey`.
The dashboard shows route/status request rates, validation/server failures,
alert state, and correlated logs. Open Tempo Explore from the dashboard to
search `benchscope-frontend` traces and follow the trace-to-log link.

Run the controlled alert test from the repository root. The API stays up;
synthetic `up` samples prove the alert's pending, firing, and resolution
transitions:

```powershell
docker compose run --rm --no-deps --entrypoint promtool prometheus test rules /etc/prometheus/api-alert-test.yml
```

### Task 23: disposable local API-availability incident exercise

This is a **local-development-only** exercise of the existing
`BenchScopeApiUnavailable` alert, not a production or hosted behavior test.
It injects an API outage by stopping only the API in a uniquely named,
disposable Compose project. Use synthetic settings and data; do not use hosted
URLs, real user data, an external receiver, or a developer's persistent Compose
project/database. All Compose-published endpoints are loopback-only.

The authenticated Grafana-managed alert rule and webhook procedure added for
issue #32 is documented in [`_docs/incidents/task-23.md`](./_docs/incidents/task-23.md)
under “Issue #32 — Stage 1 alert intake”. Grafana evaluates the API-down rule
against Prometheus and delivers firing/resolved notifications directly to the
receiver over the Compose network. Prometheus retains a non-notifying mirror
for the existing dashboard and `promtool` rule test. The procedure uses its own
ignored synthetic
configuration and Compose project with alternate loopback ports (API `18000`,
OTLP `14318`, Prometheus `19090`, Loki `13100`, Tempo `13200`, Grafana `13000`,
PostgreSQL `15442`) and preflights each before startup. The earlier Task 23
result above does not claim that alert delivery was exercised.

Prerequisites: Docker Engine/Compose v2 with a **local** Docker context, and
the repository's `compose.yaml` and `observability/` files. The required host
TCP ports are `5173` (frontend), `8000` (API), `4318` (OTLP), `9090`
(Prometheus), `3100` (Loki), `3200` (Tempo), `3000` (Grafana), and one
PostgreSQL host port. Keep
the fixed API/observability ports unchanged. Use PostgreSQL host port `5432`
when free; if it is occupied, choose a verified-free alternate (for example
`15441`) through `POSTGRES_PORT`. Compose still connects the API to the DB at
`db:5432`. Never stop or alter an existing listener.

In a clean PowerShell session from the repository root, confirm the local
Docker context and preflight all published ports:

```powershell
$context = docker context show
$endpoint = docker context inspect $context --format '{{.Endpoints.docker.Host}}'
if ($endpoint -notmatch '^(npipe:|unix://)') { throw "Not a local Docker context; abort." }

$fixedPorts = 5173, 8000, 4318, 9090, 3100, 3200, 3000
try {
  $listeners = [System.Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners()
} catch {
  throw "Port check failed or is uncertain; abort without starting Compose."
}
$busyFixed = @($listeners | Where-Object { $fixedPorts -contains $_.Port })
if ($busyFixed.Count -gt 0) {
  $busyFixed | Sort-Object Port, Address | Format-Table Address, Port
  throw "A fixed API/observability port is occupied; abort without changing its listener."
}
$dbPort = 5432
if (@($listeners | Where-Object { $_.Port -eq 5432 }).Count -gt 0) {
  $dbPort = 15441
  while (@($listeners | Where-Object { $_.Port -eq $dbPort }).Count -gt 0 -and $dbPort -lt 15500) { $dbPort++ }
}
if ($dbPort -ge 15500 -or @($listeners | Where-Object { $_.Port -eq $dbPort }).Count -gt 0) {
  throw "No verified-free PostgreSQL host port found; abort without changing any listener."
}
Write-Output "Using verified-free PostgreSQL host port $dbPort"
```

Only after that check succeeds, create a unique project name and temporary
`.env.task23` file in the worktree. It is ignored by Git and must be removed
after cleanup. Use only synthetic settings; do not use the repository `.env`
or any existing project:

```powershell
$project = "benchscope-task23-$([guid]::NewGuid().ToString('N'))"
$bytes = New-Object byte[] 24
$rng = [Security.Cryptography.RandomNumberGenerator]::Create()
$rng.GetBytes($bytes)
$password = [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+', 'x').Replace('/', 'y')
@"
POSTGRES_DB=benchscope_incident
POSTGRES_USER=incident
POSTGRES_PASSWORD=$password
POSTGRES_PORT=$dbPort
API_PORT=8000
APP_MODE=local
APP_ENV=development
LOCAL_AUTH_BYPASS=false
BENCHMARK_ENABLED=false
"@ | Set-Content -Encoding ascii .env.task23

try {
  $listeners = [System.Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners()
} catch {
  Remove-Item .env.task23
  throw "Final port check failed or is uncertain; abort without starting Compose."
}
$selectedPorts = $fixedPorts + $dbPort
$busy = @($listeners | Where-Object { $selectedPorts -contains $_.Port })
if ($busy.Count -gt 0) {
  $busy | Sort-Object Port, Address | Format-Table Address, Port
  Remove-Item .env.task23
  throw "A selected port became occupied; abort without changing its listener."
}

docker compose --env-file .env.task23 -p $project up --build --wait --detach
docker compose --env-file .env.task23 -p $project ps
Invoke-RestMethod http://127.0.0.1:8000/ready
Invoke-RestMethod http://127.0.0.1:9090/-/healthy
Invoke-RestMethod http://127.0.0.1:3000/api/health
curl.exe --fail 'http://127.0.0.1:9090/api/v1/query?query=up%7Bjob%3D%22api%22%7D'
```

Before injection, confirm `db`, `api`, Prometheus, and Grafana are healthy;
`/ready` succeeds and the Prometheus query value is `1`. The approved alert is
`up{job="api"} == 0` for `1m`. Capture UTC timestamps, the target/query,
service health, and alert state without recording credentials or raw
benchmark/user data.

Stop only this project's API. Capture the pending state while it remains
stopped, then leave it stopped for at least 90 seconds and capture the firing
state. Both `/health` and `/ready` must fail with a non-success HTTP response;
Prometheus must report `up{job="api"} == 0`. Inspect the alert in Prometheus
(`http://127.0.0.1:9090/alerts`) and the local Grafana dashboard/alert UI
(`http://127.0.0.1:3000/d/benchscope-local-journey/benchscope-local-journey`).
Do not rely on a particular operating-system connection-error string.

```powershell
docker compose --env-file .env.task23 -p $project stop api
Start-Sleep -Seconds 20
# Report only HTTP status (0 means no HTTP response; do not assert an OS error string).
function Get-HttpStatus($url) {
  try { return [int](Invoke-WebRequest -UseBasicParsing -Uri $url -TimeoutSec 3).StatusCode }
  catch { if ($_.Exception.Response) { return [int]$_.Exception.Response.StatusCode }; return 0 }
}
"health=$(Get-HttpStatus 'http://127.0.0.1:8000/health') ready=$(Get-HttpStatus 'http://127.0.0.1:8000/ready')"
Invoke-RestMethod 'http://127.0.0.1:9090/api/v1/query?query=up%7Bjob%3D%22api%22%7D'
Invoke-RestMethod 'http://127.0.0.1:9090/api/v1/alerts'
Invoke-RestMethod 'http://127.0.0.1:9090/api/v1/query?query=ALERTS%7Balertname%3D%22BenchScopeApiUnavailable%22%7D'
Start-Sleep -Seconds 70
# Repeat endpoint/query/alert checks; inspect the alert panel in Grafana.
```

Before recovery, confirm the database remains healthy with
`docker compose --env-file .env.task23 -p $project exec db pg_isready -U incident -d benchscope_incident`.
Inspect API/database logs with
`docker compose --env-file .env.task23 -p $project logs --no-color --tail 100 api db`.
Inspect the stopped API container's non-secret settings (`APP_MODE`,
`APP_ENV`, `LOCAL_AUTH_BYPASS`, and the `DATABASE_URL` host/database only);
never print or record credentials. Confirm the database target is the
synthetic `db` service. Then restore only the API and verify readiness, target,
and alert resolution after the next scrape/evaluation:

```powershell
docker compose --env-file .env.task23 -p $project start api
Invoke-RestMethod http://127.0.0.1:8000/ready
curl.exe --fail 'http://127.0.0.1:9090/api/v1/query?query=up%7Bjob%3D%22api%22%7D'
Invoke-RestMethod http://127.0.0.1:9090/api/v1/alerts
```

Wait for the `up` value to return to `1` and for
`BenchScopeApiUnavailable` to disappear from the active alert list after the
next scrape/evaluation.

Run the exact rule test against the same disposable project:

```powershell
docker compose --env-file .env.task23 -p $project run --rm --no-deps --entrypoint promtool prometheus test rules /etc/prometheus/api-alert-test.yml
```

Record only sanitized target/query results, alert transitions, service state,
and relevant API/database log/config findings in `_docs/incidents/task-23.md`.
No API trace is expected while its process is stopped. This is recovery from
the injected API stop, not an application-code or root-cause fix.

Clean up only after verifying `$project` is the unique disposable project
created above. Never run `down` against an unqualified/default or other
project. Remove that project's containers, network, and synthetic database
and telemetry volumes, delete the temporary environment file, and verify no
containers/volumes with its Compose project label remain:

```powershell
docker compose --env-file .env.task23 -p $project down --volumes --remove-orphans --rmi local
Remove-Item .env.task23
docker ps -a --filter "label=com.docker.compose.project=$project"
docker volume ls --filter "label=com.docker.compose.project=$project"
```

Confirm the project's published listeners are gone. If a port is later
occupied by another listener, do not stop or alter it. The alert is local-only;
no hosted or production service, external telemetry, or notification receiver
is involved.

Ordinary `docker compose down` retains database and telemetry volumes. Use
`--volumes` only when intentionally deleting them, and only for this verified
disposable project.

Pre-auth local storage fixtures use the fixed owner id `local`; owner ids are
not accepted from callers.

## Offline smoke test

From `backend/`, run:

```sh
uv run pytest tests/test_smoke.py
```

This imports the API shell and verifies that it has no product routes. It needs no database, network service, GPU, or private benchmark.

## Privacy and safety

- The proprietary benchmark implementation, prompts, reference answers, hidden test identifiers, generated code, and confidential evaluation material must not be committed or publicly served.
- Private local artifacts are never served publicly by the dashboard.
- Hosted import processing stores only allowlisted, non-confidential metrics and metadata.
- The application does not download models or manage inference-server lifecycles.
- Benchmark integration must not accept arbitrary commands from browser requests.
