# BenchScope

BenchScope is a local-first web application for recording, comparing, and understanding the performance of local language models on an independent coding benchmark. It turns isolated benchmark results into a durable, inspectable history while keeping the proprietary benchmark itself out of this repository.

## Problem

Developers running local language models often produce one-off benchmark results that are hard to compare across model versions, quantisations, inference settings, hardware configurations, and time. BenchScope provides a persistent observatory for those results: import an existing result or launch a benchmark against a configured local model endpoint, inspect the outcome, compare it with earlier runs, and recover from failed or interrupted attempts without losing history.

## What the system does

- Records benchmark attempts with model/profile snapshots, configuration, timestamps, status, metrics, hardware information, and sanitised diagnostics.
- Tracks run lifecycle states: `running`, `completed`, `failed`, `interrupted`, and `cancelled`.
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
- A FastAPI backend shell with `/health` and `/ready` endpoints.
- A hand-authored OpenAPI contract at `openapi.yaml`, derived from the frontend service interface.
- Generated typed frontend contract artifacts at `frontend/src/types/api.generated.ts`.
- Contract tests in `frontend/src/contract/` and `backend/tests/test_contract.py`.
- A mock frontend service backed by browser storage for development and tests.
- Docker Compose support for local backend plus PostgreSQL.

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
pnpm install
pnpm dev
pnpm test
pnpm build
pnpm gen:api
pnpm check:api
```

## Backend

From `backend/`:

```sh
uv sync
uv run uvicorn app.main:app --reload
uv run pytest
uv run ruff check .
uv run ruff format .
```

## API contract

- Initial committed artifact: repository-root `openapi.yaml`.
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
