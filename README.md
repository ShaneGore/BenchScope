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
Compose network; the database has no host-published port. The backend port is
published only on `127.0.0.1`. The private benchmark, model endpoints, and raw
artifacts remain on the host and are not mounted or packaged.

1. Copy the example environment file and replace its password placeholder with
   a local URL-safe password (hexadecimal characters are recommended):

   ```sh
   cp .env.example .env
   ```

   Compose requires `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, and
   `API_PORT`; missing values produce a configuration error. Keep the
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

## Offline smoke test

From `backend/`, run `uv run pytest tests/test_smoke.py`. This imports the API
shell and verifies that it has no product routes. It needs no database,
network service, GPU, or private benchmark.
