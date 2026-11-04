# BenchScope

BenchScope is a local-first observatory for importing, comparing, and understanding local LLM coding-benchmark results. It turns isolated benchmark runs into a durable, inspectable history while keeping the proprietary benchmark itself out of this repository.

[![CI](https://github.com/ShaneGore/BenchScope/actions/workflows/ci.yml/badge.svg)](https://github.com/ShaneGore/BenchScope/actions/workflows/ci.yml)

**Live demo:** https://shanegore.github.io/BenchScope/
**API readiness:** https://benchscope-staging-api.onrender.com/ready

The hosted API may need about a minute to wake after inactivity. Please wait; if loading fails, use Retry. The demo is read-only.

![BenchScope dashboard](./_docs/images/dashboard.png)

### Showcase data

The demo contains all 15 configurations from the owner's Local-LLM-Coding-Benchmark-v2 results: 13 local model and reasoning-mode configurations and two paid, hosted OpenRouter configurations. Each records 47 tasks; a pass requires a solution to import and pass both public and hidden checks. One Bonsai reasoning-on trial encountered a provider error, which is identified in the demo.

For the local configurations, throughput is the mean output tokens per request-second over trials with a measured rate, rounded to one decimal. It is not aggregate run throughput; the Bonsai reasoning-on mean uses 46 measurements and the other local means use 47. Throughput is unavailable for the hosted runs. Settings differ, including reasoning, MTP and context size, so the results should not be treated as a controlled ranking. Only two runs have verified driver-log boundaries; missing timestamps and unavailable metrics are shown as unavailable. The demo publishes aggregate values and model/configuration labels, while private benchmark materials and raw trials remain private.

## Key features

- Validated benchmark result import for v1 and v2 contracts.
- Persistent run history, detail views, and compatible-run comparison.
- Model profiles with version, quantisation, endpoint, and hardware notes.
- Read-only public demo of all 15 available real benchmark configurations for unauthenticated visitors.
- Clerk authentication with backend-enforced owner isolation.
- Docker Compose full-stack local setup with PostgreSQL and observability.
- Five-job CI on Linux and Windows, including process-tree safety tests.
- Automatic staging deployment and documented rollback.
- OpenTelemetry metrics, traces, and structured logs.
- Alerting and supervised AI-assisted incident recovery.
- Local Windows subprocess safety foundation for future benchmark execution.

## Honest limitation

Real benchmark launch and cancellation are not yet connected to the private runner. Issue #25 remains open. The local subprocess adapter is implemented and tested with synthetic runners only; no full private benchmark has been executed by BenchScope.

## Architecture

- Frontend: React, Vite, TypeScript
- Backend: Python 3.12, FastAPI, SQLAlchemy, Alembic
- Database: PostgreSQL
- Authentication: Clerk
- Observability: OpenTelemetry, Prometheus, Grafana, Loki, Tempo
- Deployment: GitHub Pages, Render Free, Neon Free

See the [architecture overview](_docs/architecture/README.md) for details.

## Local quick start

Prerequisites: Docker Desktop or Docker Engine with Compose v2, Node.js with Corepack/pnpm, and available local ports 5432, 8000, and 5173. From the repository root, copy `.env.example` to `.env`, set a local URL-safe `POSTGRES_PASSWORD`, and set `APP_ENV=development`, `APP_MODE=local`, and `LOCAL_AUTH_BYPASS=true`. The bypass is for a local workstation only. Start PostgreSQL and the API (the API container applies migrations):

```powershell
docker compose up --build --wait db api
```

In another shell, copy `frontend/.env.example` to `frontend/.env`, set `VITE_APP_MODE=local` and `VITE_API_URL=http://127.0.0.1:8000`, then start the frontend:

```powershell
cd frontend
corepack pnpm install --frozen-lockfile
corepack pnpm dev
```

Open the URL printed by Vite. To run the complete observability stack, the alert receiver also needs a local bearer secret; see the Compose configuration and incident documentation. For host-run backend tests, install Python 3.12 and uv; PostgreSQL integration tests need a disposable `TEST_DATABASE_URL`.

## Testing

```powershell
cd backend
uv run ruff format --check .
uv run ruff check .
uv run pytest
```

```powershell
cd frontend
corepack pnpm test
corepack pnpm build
```

## Documentation

- [Setup and architecture](_docs/architecture/README.md)
- [Agent workflow and project instructions](AGENTS.md)
- [Course submission evidence](_docs/submission/submission-checklist.md)
- [Incident runbooks](_docs/incidents/)
- [Known limitations](_docs/submission/known-limitations.md)

## Project status

- [Issue #21](https://github.com/ShaneGore/BenchScope/issues/21): hosted deployment and rollback evidence.
- [Issue #25](https://github.com/ShaneGore/BenchScope/issues/25): real runner contract and integration remain open.
- CI/CD: five checks run in the workflow; branch protection must be verified in repository settings
- Hosting uses free-tier services; check current provider limits and charges.


## Import contracts

BenchScope supports two result contracts.

### v1

- Legacy benchmark result import.
- Validates required fields and normalises metrics.
- Preserves missing metrics as `null` rather than converting them to zero.
- Detects duplicates using a stable ID or fingerprint where available.

### v2

- Adds benchmark identity, release, canonical manifest SHA-256, and expected task IDs.
- Records per-task pass/fail outcomes.
- Distinguishes missing tasks from failed tasks.
- Keeps `pass_rate` null unless task coverage is complete.
- Keeps `quality_score` null until an authoritative scoring definition exists.
- Enforces strict comparison compatibility by benchmark release and manifest.

## Operating modes

### Local mode

- Imports and persists results locally.
- Binds to loopback by default.
- Does not launch or cancel the private benchmark.
- Never exposes local model endpoints or private benchmark paths.

### Hosted multi-user mode

- Users sign in with Clerk.
- Profiles and run history are owner-scoped.
- Unauthenticated visitors can use a read-only demo.
- Hosted mode imports independently produced result files.
- Hosted import processing stores only allowlisted non-confidential metrics and metadata and discards the uploaded raw payload.

### Anonymous demo mode

- Read-only benchmark summaries, including the hosted OpenRouter configurations.
- No import, profile editing, deletion, or personal record access.
- Used for public demonstrations without exposing private data.

## Expected behaviour

- The application starts using documented commands.
- Valid result files can be imported.
- Invalid imports are rejected without corrupting persisted data.
- Missing metrics remain null.
- Incomplete task coverage does not become a misleading score.
- Comparisons are restricted to compatible benchmark manifests and releases.
- Personal records are isolated by authenticated owner identity.

## Privacy and safety

- Private prompts, reference answers, hidden tests, generated code, raw model responses, and confidential benchmark paths are never committed or publicly served.
- Hosted import processing stores only allowlisted non-confidential metrics and metadata.
- Benchmark integration must not accept arbitrary commands from browser requests.
- The private benchmark is not executed in hosted mode.

## Known limitations

- Issue #25 remains open.
- Real benchmark launch and cancellation are not implemented.
- The local subprocess adapter is implemented and tested with synthetic runners only.
- `quality_score` remains null until an authoritative definition exists.
- Observability dashboards and alerts are verified in local Docker Compose.
- Alert intake does not automatically invoke the investigator, and the permitted local recovery requires operator approval. An autonomous alert-to-fix chain has not been demonstrated.

## Licence

First-party BenchScope code is licensed under the MIT Licence; see [LICENSE](./LICENSE). Third-party dependencies and private benchmark materials remain subject to their own licences.
