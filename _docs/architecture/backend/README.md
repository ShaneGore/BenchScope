# Backend architecture (FastAPI)

## 1. Stack

FastAPI (Python 3.12), Pydantic v2, SQLAlchemy 2.x, Alembic, Uvicorn. Deps via `uv` with committed `uv.lock`. PostgreSQL (local Docker Compose; hosted Neon Free). Auth via Clerk JWT verified through JWKS; `sub` is the owner key.

## 2. Module layout (proposed)

```
backend/
  app/
    main.py              # FastAPI app factory, middleware, router mount
    config.py            # Settings from env (pydantic-settings)
    db.py                # engine, session, dependency
    auth.py              # Clerk JWT verification, current_user dependency
    models/              # SQLAlchemy ORM models
    schemas/             # Pydantic request/response models
    api/                 # Routers: health, profiles, runs, imports, demo
    services/            # Business logic: import normalisation, comparison
    runner/              # Benchmark runner (local mode only)
      adapter.py         # BenchmarkAdapter seam (private)
      lifecycle.py       # single-flight, status, timeout, reconciliation
    observability/       # OTel setup, metrics, logging
  alembic/              # migrations
  tests/
  Dockerfile
  pyproject.toml
  uv.lock
```

Frontend and backend are separate top-level folders (per request): `frontend/`, `backend/`. They share only the OpenAPI contract (TS types generated from FastAPI's `/openapi.json`).

## 3. Request flow

1. Request enters FastAPI; CORS middleware validates origin (hosted) / permissive (local).
2. Auth dependency verifies Clerk JWT (hosted) or resolves local bypass user (local dev, guarded).
3. Router validates body via Pydantic; service layer applies business rules.
4. SQLAlchemy session (request-scoped) reads/writes with `owner_id` filter.
5. Response serialised via Pydantic; OTel spans/metrics recorded.

## 4. Auth

- Hosted: Clerk JWT in `Authorization: Bearer`. Verify signature via JWKS (cached), validate `iss`/`aud`/exp. Extract `sub` → `owner_id`. No custom password scheme.
- Local dev: optional bypass (`LOCAL_AUTH_BYPASS=true`) resolves a fixed local user id; must be impossible to enable in production builds (config guard + documented).
- Anonymous demo: separate read-only endpoints with no owner context; no writes.

## 5. Runner (local only)

See `runner.md`. In-process, single-flight (`asyncio` + `asyncio.create_subprocess_exec`), DB-backed status, `asyncio.wait_for` timeout, startup reconciliation of stale "running" rows. Disabled in hosted mode (endpoints absent).

## 6. Storage

- PostgreSQL canonical. `DATABASE_URL` override allows SQLite for quick experiments (not canonical; integration tests run on Postgres).
- Migrations via Alembic; never hand-edit prod schema.
- Owner-scoped indexes on `owner_id`.

## 7. Observability

- OpenTelemetry (FastAPI + (frontend) React) → OTLP.
- Local: Prometheus + Loki + Tempo + Grafana in Compose.
- Hosted: optional Grafana Cloud Free for API telemetry.
- Structured JSON logs; no prompts/code/secrets.

## 8. Error handling

- Pydantic validation errors → 422 with field details.
- Domain errors → typed HTTP exceptions with sanitised messages.
- Unhandled → 500 with correlation id; details in logs only.

## 9. Configuration (env)

Key settings: `APP_MODE`, `DATABASE_URL`, `CLERK_JWKS_URL`, `CLERK_ISSUER`, `CLERK_AUDIENCE`, `CORS_ORIGINS`, `BENCHMARK_ENABLED`, `BENCHMARK_ADAPTER`, `LOCAL_AUTH_BYPASS`, `MAX_UPLOAD_BYTES`, `OTEL_EXPORTER_OTLP_ENDPOINT`. All via pydantic-settings; no secrets in code.