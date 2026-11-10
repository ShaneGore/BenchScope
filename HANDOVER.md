# HANDOVER

Maintenance and portfolio handover for BenchScope. Read
[README.md](./README.md) first for the product overview; this document covers
what another engineer needs to operate and continue the project safely.

## Purpose

BenchScope is a local-first observatory for coding-benchmark results. It imports
supported result files, keeps a durable history, and compares coding accuracy,
generation speed and configuration choices without publishing the private
benchmark.

## Architecture summary

```
Browser (React + Vite + TypeScript, GitHub Pages)
   |  Clerk JWT for personal data
   v
FastAPI (Python 3.12, Render) ---> PostgreSQL (Neon) / local Docker Postgres
   |  Alembic migrations, owner-scoped SQLAlchemy models
   +-- local-only benchmark runner seam (never hosted)
   +-- OpenTelemetry -> Collector -> Prometheus / Tempo / Loki -> Grafana
                                   +-- alert -> authenticated receiver -> incident + repair job
```

- Frontend: `frontend/` (React, Vite, TypeScript, pnpm, Vitest, Playwright).
- Backend: `backend/` (FastAPI, Pydantic v2, SQLAlchemy 2, Alembic).
- Static assets: `_docs/images/`, `frontend/public/`.
- Observability: `observability/` (provisioned datasources, dashboards, alerts).
- Scripts: `scripts/` (`start.py`, `verify.py`, `smoke_test.py`, token minting).

## Public URLs and repository

| Item | URL |
|---|---|
| Repository | <https://github.com/ShaneGore/BenchScope> |
| Public frontend (staging-backed) | <https://shanegore.github.io/BenchScope/> |
| Staging API | <https://benchscope-staging-api.onrender.com> |
| Production demo API | <https://benchscope-production-api.onrender.com> |
| Task tracker | <https://github.com/ShaneGore/BenchScope/issues> |
| Production/rollback evidence | <https://github.com/ShaneGore/BenchScope/issues/70#issuecomment-6755310213> |

## Local setup

Requirements: [uv](https://docs.astral.sh/uv/), Docker Desktop or Docker Engine
with Compose v2, and Node.js 22 with Corepack for the test suite.

```powershell
uv run --no-project python scripts/start.py
```

Open <http://127.0.0.1:5173>. The script generates a missing ignored `.env` with
a random local PostgreSQL password and explicit local-development auth, then
builds and starts frontend, API and database. It preserves existing `.env`
files.

Stop:

```powershell
uv run --no-project python scripts/start.py --stop
```

The PostgreSQL volume is retained on stop.

## Single-command testing

```powershell
uv run --no-project python scripts/verify.py
```

Runs Ruff, backend unit/integration tests against a disposable PostgreSQL,
frontend tests and build, the API-contract check, a container browser check and
the browser journeys, then removes its disposable resources. Individual suites:

```powershell
cd backend; uv run pytest
cd frontend; corepack pnpm test
cd frontend; corepack pnpm test:journey
```

## Docker Compose

`compose.yaml` defines the core stack: `frontend` (nginx), `api` (FastAPI) and
`db` (PostgreSQL 17 with a named volume). `compose.observability.yaml` adds
`otel-collector`, `prometheus`, `loki`, `tempo`, `grafana` and `alert-receiver`.

```powershell
uv run --no-project python scripts/start.py --observability
uv run --no-project python scripts/start.py --stop --observability
```

## Environments and CI workflows

| Workflow | Trigger | Purpose |
|---|---|---|
| `ci.yml` | PR; push to `main` | Five required checks: `backend`, `frontend`, `journey`, `container-images`, `backend-windows` |
| `deploy-backend.yml` | Successful `main` CI | Automatic staging API deploy + authenticated smoke |
| `deploy-frontend.yml` / `pages-deploy.yml` | Successful `main` CI / manual | GitHub Pages frontend |
| `promote-production.yml` | Manual `workflow_dispatch` | Protected production promotion/rollback |

Main ruleset: pull request required, review threads resolved, five required
checks, strict up-to-date checks, **0 approving reviews**.

Production environment: custom branch policy (`main`), required reviewer
`ShaneGore`, `prevent_self_review=false`, `can_admins_bypass=false`.

Staging and `github-pages` are branch-restricted with no required reviewers,
which is why staging deploys automatically.

## Staging deployment

Automatic after a successful `main` CI run. Verify:

```powershell
curl.exe https://benchscope-staging-api.onrender.com/version
curl.exe https://benchscope-staging-api.onrender.com/ready
```

`/version` must return the full `main` SHA.

## Manual production promotion

```powershell
gh workflow run promote-production.yml --ref main -f confirm=promote -f ref=<40-char-sha>
```

Then approve the protected `production` environment. The workflow requires main
ancestry, exact-SHA `main` push CI, migrations, a SHA-pinned Render deploy,
`/version` and `/ready` match, minted Clerk tokens and a 13-check smoke suite.
Never deploy from the Render dashboard.

## Verified rollback procedure

The rollback is an **application revision** rollback using the same workflow:

```powershell
gh workflow run promote-production.yml --ref main -f confirm=promote -f ref=<previous-compatible-sha>
```

- Only revisions with a compatible Alembic head are safe; migrations are
  forward-only.
- Verify `/version`, `/ready`, 13/13 smoke, and that existing synthetic runs
  remain.
- Restore the approved revision through the same workflow.
- Never run `alembic downgrade` or a destructive database operation.

Executed rehearsal: rollback [`42727553382`](https://github.com/ShaneGore/BenchScope/actions/runs/42727553382)
to `ab6ea5d`, restore [`42728234322`](https://github.com/ShaneGore/BenchScope/actions/runs/42728234322)
to `dd8064a`; both 13/13, same schema, same four synthetic run UUIDs. See
[production-release.md](./_docs/architecture/production-release.md#rollback-and-restoration-evidence-executed).

## Configuration: names only

Never commit values. Production GitHub environment:

- Secrets: `PRODUCTION_DATABASE_URL`, `PRODUCTION_RENDER_DEPLOY_HOOK_URL`,
  `PRODUCTION_CLERK_SECRET_KEY`.
- Variables: `PRODUCTION_SMOKE_API_URL`, `PRODUCTION_SMOKE_FRONTEND_URL`,
  `PRODUCTION_SMOKE_TEST_USER_A_ID`, `PRODUCTION_SMOKE_TEST_USER_B_ID`.

Render runtime: `APP_MODE`, `APP_ENV`, `HOST`, `DATABASE_URL`, `CORS_ORIGINS`,
`CLERK_JWKS_URL`, `CLERK_ISSUER`, `CLERK_AUTHORIZED_PARTIES`,
`BENCHMARK_ENABLED`.

Staging GitHub secrets/variables use the same names without the `PRODUCTION_`
prefix.

Local: `.env` generated by `scripts/start.py`; see `.env.example` for names.

`CORS_ORIGINS` and `CLERK_AUTHORIZED_PARTIES` must be JSON arrays of origins,
e.g. `["https://shanegore.github.io"]`. `CLERK_AUDIENCE` is not used.

## Observability

Local only. OpenTelemetry → Collector → Prometheus (metrics + exemplars), Tempo
(traces), Loki (logs), Grafana (UI). The request counter carries the W3C trace ID
as an exemplar, not a label. Evidence: trace `802cccdd7ebb4fc79cdd9750c0f8063d`
in [metric-trace-link.md](./_docs/observability/metric-trace-link.md).

Hosted staging and production do **not** run this stack.

## Incident response and AI repair

1. Grafana rule `BenchScopeApiUnavailable` fires on `up{job="api"}`.
2. The authenticated alert receiver persists an incident with sanitised evidence,
   deduplicates by fingerprint, writes audit events and queues a repair job.
3. An **explicitly started** worker claims the job and asks GPT-6 Luna (GitHub
   Copilot CLI) to investigate.
4. The patch is allowlist-limited (metrics enable condition, literal health
   response, health-contract tests), validated, applied in an isolated worktree,
   tested in a restricted container, then opened as a **draft** PR.
5. A human reviews and merges/applies. Merge, release and hosted recovery are
   never automated; the automatic executor is disabled.

Start it only for a deliberate exercise:

```powershell
uv run --no-project python scripts/start.py --observability --repair-worker
```

Evidence: [phase3c-recovery-demo.md](./_docs/incidents/phase3c-recovery-demo.md),
[task-23.md](./_docs/incidents/task-23.md), PRs
[#62](https://github.com/ShaneGore/BenchScope/pull/62),
[#63](https://github.com/ShaneGore/BenchScope/pull/63),
[#64](https://github.com/ShaneGore/BenchScope/pull/64),
[#67](https://github.com/ShaneGore/BenchScope/pull/67).

## Required supervision and approval

- The repair worker is not OS-isolated and may use the operator's GitHub CLI
  credentials. Keep it foreground, operator-supervised and single-instance.
- Production promotion requires environment approval. The owner is the sole
  reviewer, so this is a self-approval gate.
- Never let the worker merge, release or touch hosted production.

## Security and privacy boundaries

- Prompts, reference answers, hidden tests, raw trials, generated code and
  evaluation paths are never committed, served or logged.
- Ownership comes only from the verified JWT subject; foreign ids return 404.
- Hosted mode does not mount benchmark routes; profiles reject endpoint and
  credential fields; CORS is an explicit allowlist.
- Uploads are size-bounded and schema-validated; raw payloads are discarded.
- Only public `VITE_*` values ship to the browser.
- See [security-review.md](./_docs/submission/security-review.md).

## Free-tier constraints

Render Free sleeps after 15 minutes and shares 750 instance-hours per workspace
per month. Neon Free scales to zero, has a 6-hour history and one manual
snapshot — **not** a backup. Clerk uses a Development application for synthetic
smoke users. No SLA; cold starts are expected.

## Known limitations and deferred work

- **Issue [#25](https://github.com/ShaneGore/BenchScope/issues/25) remains open:
  the private benchmark runner adapter contract is unresolved and the runner is
  intentionally not integrated.** The private runner stays separate from the
  public application. Do not execute, copy, publish or expose private benchmark
  inputs, expected outputs or raw results. Keep the issue open until its
  acceptance criteria are met.
- Hosted frontend is staging-backed; production is API-only.
- Observability and alerting are local.
- Hosted AI repair is disabled; verified recovery was a supervised replay in a
  disposable environment.
- `quality_score` remains null until an authoritative definition exists.
- Global rate-limiting specifics are undefined.
- The main ruleset requires zero approving reviews.
- QA custom agent launch previously failed on a model-name mismatch; the
  definitions now name `gpt-6-luna`, but a successful launch is not
  re-demonstrated.

Full list: [known-limitations.md](./_docs/submission/known-limitations.md).

## Course submission (portfolio context)

If this repository is being used for the DataTalksClub AI Dev Tools Zoomcamp
2026 submission: the active attempt is Project 2, deadline **16 November 2026
(Mon) 23:00** in the platform viewer's timezone. The form requires the
repository link and the **exact commit ID** to evaluate, and the course
separately requires **three peer reviews**. Those are owner actions; the
repository cannot satisfy them. See
[submission-checklist.md](./_docs/submission/submission-checklist.md#submission-platform-facts-verified-2026-11-10).

## Key documentation

| Topic | Document |
|---|---|
| Reviewer evidence matrix | [_docs/submission/rubric-evidence.md](./_docs/submission/rubric-evidence.md) |
| Demo walkthrough | [_docs/submission/demo-walkthrough.md](./_docs/submission/demo-walkthrough.md) |
| Submission text | [_docs/submission/submission-text.md](./_docs/submission/submission-text.md) |
| Production runbook | [_docs/architecture/production-release.md](./_docs/architecture/production-release.md) |
| Deployment design | [_docs/architecture/deployment.md](./_docs/architecture/deployment.md) |
| Rollback | [_docs/rollback.md](./_docs/rollback.md) |
| Security review | [_docs/submission/security-review.md](./_docs/submission/security-review.md) |
| Metric-to-trace | [_docs/observability/metric-trace-link.md](./_docs/observability/metric-trace-link.md) |
| Verified recovery | [_docs/incidents/phase3c-recovery-demo.md](./_docs/incidents/phase3c-recovery-demo.md) |
| Product plan | [_docs/plan.md](./_docs/plan.md) |
| Backlog | [_docs/tasks.md](./_docs/tasks.md) |
| Agent process | [AGENTS.md](./AGENTS.md), [_docs/process.md](./_docs/process.md) |
