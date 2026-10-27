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

Run the controlled alert test (the API stays up; synthetic `up` samples prove
pending, firing, and resolution) from the repository root:

```powershell
docker compose run --rm --no-deps --entrypoint promtool prometheus test rules /etc/prometheus/api-alert-test.yml
```

The local alert is `up{job="api"} == 0` pending for 1 minute. To verify the
live path as well, stop only the local API for 90 seconds and inspect
`BenchScopeApiUnavailable` in Grafana/Prometheus; restart it and wait for the
next scrape/evaluation to resolve the alert. The operator action is to inspect
`/ready` and API/database logs, then restart the API only after confirming the
database and configuration. No external notification receiver is configured.

Stop with `docker compose down`; add `--volumes` only when intentionally
deleting the local database and telemetry history.

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
