# BenchScope

BenchScope is a local-first web application for recording, comparing, and understanding the performance of local language models on an independent coding benchmark. It turns isolated benchmark results into a durable, inspectable history while keeping the proprietary benchmark itself out of this repository.

## Problem

Developers running local language models often produce one-off benchmark results that are hard to compare across model versions, quantisations, inference settings, hardware configurations, and time. BenchScope provides a persistent observatory for those results: import an existing result or launch a benchmark against a configured local model endpoint, inspect the outcome, compare it with earlier runs, and recover from failed or interrupted attempts without losing history.

## What the system does

- Records benchmark attempts with model/profile snapshots, configuration, timestamps, status, metrics, hardware information, and sanitised diagnostics.
- Tracks persisted run lifecycle states: `running`, `completed`, `failed`, and `interrupted`. Cancellation is deferred to #25.
- Keeps failed and interrupted attempts in history without presenting them as successful results.
- Distinguishes missing metrics from zero values.
- Supports model profiles with name, version, quantisation, endpoint, hardware notes, and benchmark settings.
- Imports supported JSON result files, validates required fields, normalises metrics, reports errors, and avoids duplicates where a stable ID or fingerprint is available.
- Filters runs by model, status, and date.
- Compares completed runs through history tables and charts.
- Provides a read-only synthetic demo for unauthenticated visitors.
- Supports personal authenticated workspaces in hosted mode, with backend-enforced ownership isolation.
- Runs benchmarks only in local/private mode; hosted mode imports results instead.

## Operating modes

### Local/private mode

- Full workflow, including launching the private benchmark against a configured local model endpoint.
- Service binds to the loopback interface by default.
- Local model endpoints, private benchmark paths, and private artifacts remain local and are not exposed.

### Hosted multi-user mode

- Individual users sign in and maintain private profiles and result history.
- Unauthenticated visitors can explore a read-only demo populated with synthetic results.
- Hosted mode does not connect to model endpoints on a user's computer and does not run the private benchmark.
- Benchmark results can be produced locally and imported into hosted workspaces.
- Hosted import processing extracts only allowlisted, non-confidential metrics and metadata and discards the uploaded raw payload.

## Current implementation status

This repository currently contains:

- A React/Vite/TypeScript frontend with pages for Dashboard, Runs, Run Detail, Compare, Import, Profiles, and Benchmark.
- A FastAPI backend with local profile, import, run-history, demo, and benchmark-capability API routes plus `/health` and `/ready`.
- A hand-authored OpenAPI contract at `openapi.yaml`, derived from the frontend service interface.
- Generated typed frontend contract artifacts at `frontend/src/types/api.generated.ts`.
- Contract tests in `frontend/src/contract/` and `backend/tests/test_contract.py`.
- Environment-selected API services for local/hosted personal data, an anonymous read-only demo service, and mock fixtures for tests.
- Docker Compose support for local backend, PostgreSQL, and OpenTelemetry/Prometheus/Loki/Tempo/Grafana.

Backend domain routes are not yet implemented; the OpenAPI contract is the reconciliation target until FastAPI-generated OpenAPI becomes authoritative.

## Expected behavior

- Application starts using documented instructions.
- Valid result files can be imported and remain available after restart.
- Malformed imports produce clear errors and do not create partial records.
- Duplicate imports are identified when a stable source ID or fingerprint is available.
- A user can select a configured profile and launch a benchmark without blocking the interface.
- Completed runs display available metrics and appear in history.
- Missing metrics are shown as unavailable, never zero.
- Failed or interrupted runs are recorded with useful, sanitised diagnostics.
- A new attempt can follow a failed attempt without overwriting the earlier record.
- History can be filtered and completed runs compared using a meaningful chart.
- Hosted users can only read, alter, or delete their own records.
- Anonymous visitors can use the read-only synthetic demo without an account.
- No proprietary benchmark code, confidential evaluation material, credentials, or private artifacts are committed or publicly served.

## Repository layout

```text
backend/          FastAPI backend and tests
frontend/         React/Vite frontend and tests
openapi.yaml      Initial API contract
_docs/            Product plan, architecture, task tracker, process docs
compose.yaml      Local backend and PostgreSQL stack
```

## Frontend

From `frontend/`:

```sh
corepack pnpm install --frozen-lockfile
corepack pnpm dev
corepack pnpm test
corepack pnpm build
corepack pnpm gen:api
corepack pnpm check:api
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
`backend` and `frontend` jobs are the required quality, test, and API-contract
checks; both fail the workflow on failure. The backend job uses a health-checked,
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

## Local API and PostgreSQL with Compose

Prerequisites: Docker Engine or Docker Desktop with Compose v2.

Compose builds the backend from `backend/` and runs PostgreSQL in a private Compose network. PostgreSQL and the backend ports are published only on `127.0.0.1` for local development and host-run database tests. Private benchmark, model endpoints, and raw artifacts remain on the host and are not mounted or packaged.

1. Copy the example environment file and replace its password placeholder with a local URL-safe password:

   ```sh
   cp .env.example .env
   ```

   Compose requires `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, and `API_PORT`. `POSTGRES_PORT` defaults to 5432.
   The auth bypass is intentionally disabled by default; for offline local API
   work, explicitly set `LOCAL_AUTH_BYPASS=true` in `.env`. Compose passes
   `APP_ENV` and the bypass flag to the backend, which rejects any non-development,
   non-local, or non-loopback combination.

2. Build and start services:

   ```sh
   docker compose up --build --wait
   ```

3. Verify:

   ```sh
   docker compose ps
   curl http://127.0.0.1:8000/health
   curl http://127.0.0.1:8000/ready
   ```

4. Stop while retaining data:

   ```sh
   docker compose down
   ```

   Delete the PostgreSQL volume too:

   ```sh
   docker compose down --volumes
   ```

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

1. Copy `.env.example` to `.env`, set a local URL-safe `POSTGRES_PASSWORD`, and
   set `LOCAL_AUTH_BYPASS=true` (keep `APP_MODE=local` and
   `APP_ENV=development`):

   ```powershell
   Copy-Item .env.example .env
   # Edit .env locally; do not commit it.
   ```

2. Start the stack. The Compose API container applies its Alembic migrations
   before serving requests:

   ```powershell
   docker compose up --build --wait --detach
   docker compose ps
   Invoke-RestMethod http://127.0.0.1:8000/ready
   Invoke-WebRequest http://127.0.0.1:8000/metrics
   Invoke-RestMethod http://127.0.0.1:9090/-/healthy
   Invoke-RestMethod http://127.0.0.1:3100/ready
   Invoke-RestMethod http://127.0.0.1:3200/ready
   Invoke-RestMethod http://127.0.0.1:3000/api/health
   ```

3. Install and run the real-UI journey from `frontend/`. Playwright starts Vite
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

Prerequisites: Docker Engine/Compose v2 with a **local** Docker context, and
the repository's `compose.yaml` and `observability/` files. The required host
TCP ports are `8000` (API), `4318` (OTLP), `9090` (Prometheus), `3100`
(Loki), `3200` (Tempo), `3000` (Grafana), and one PostgreSQL host port. Keep
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

$fixedPorts = 8000, 4318, 9090, 3100, 3200, 3000
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
