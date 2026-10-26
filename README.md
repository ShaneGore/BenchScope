# BenchScope

BenchScope is a React/Vite frontend and FastAPI backend. The backend currently provides a health/readiness API shell.

## Frontend

From `frontend/`, run `pnpm install`, `pnpm dev`, `pnpm test`, or `pnpm build`.

## Backend

From `backend/`, run `uv sync`, `uv run uvicorn app.main:app --reload`,
`uv run pytest`, or `uv run ruff check .`.

## Local API and PostgreSQL with Compose

Prerequisites: Docker Engine or Docker Desktop with the Compose v2 plugin.
Compose builds the backend from `backend/` and runs PostgreSQL in a private
Compose network. PostgreSQL and the backend ports are published only on
`127.0.0.1` for local development and host-run tests. The private benchmark,
model endpoints, and raw artifacts remain on the host and are not mounted or
packaged.

1. Copy the example environment file and replace its password placeholder with
   a local URL-safe password (hexadecimal characters are recommended):

   ```sh
   cp .env.example .env
   ```

   Compose requires `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, and
   `API_PORT`; `POSTGRES_PORT` defaults to 5432. Keep the
   PostgreSQL username, database name, and password URL-safe because the
   backend connection URL is assembled from them.

2. Build and start the services, waiting until both health checks pass:

   ```sh
   docker compose up --build --wait
   ```

3. Verify service status with `docker compose ps`, then check the API on the
   configured local port (8000 in `.env.example`):

   ```sh
   curl http://127.0.0.1:8000/health
   curl http://127.0.0.1:8000/ready
   ```

   Both endpoints should return HTTP 200; `/ready` confirms PostgreSQL is
   reachable. On Windows PowerShell, use
   `Invoke-RestMethod http://127.0.0.1:8000/health` and
   `Invoke-RestMethod http://127.0.0.1:8000/ready`.

4. Stop the services while retaining local database data:

   ```sh
   docker compose down
   ```

   To also delete the local PostgreSQL volume and its data, run
   `docker compose down --volumes`.

### PostgreSQL migrations and integration tests

From `backend/`, set `DATABASE_URL` to the local Compose database URL and run
`uv run alembic upgrade head` to apply the baseline. For integration tests,
set `TEST_DATABASE_URL` to a disposable PostgreSQL database; the test creates
and drops its own isolated schema. It refuses non-PostgreSQL URLs and skips
when the variable is unset. For example, in PowerShell:

```powershell
$env:TEST_DATABASE_URL = "postgresql+psycopg://benchscope:replace-with-a-local-url-safe-password@127.0.0.1:5432/benchscope"
uv run pytest tests/test_postgres_storage.py
Remove-Item Env:TEST_DATABASE_URL
```

Pre-auth local storage fixtures use the fixed owner id `local`; owner ids are
not accepted from callers.

## Offline smoke test

From `backend/`, run `uv run pytest tests/test_smoke.py`. This imports the API
shell and verifies that it has no product routes. It needs no database,
network service, GPU, or private benchmark.
