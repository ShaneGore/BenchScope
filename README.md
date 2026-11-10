# BenchScope

A local-first observatory for coding-benchmark results. Import a result once, keep an inspectable history, and compare coding accuracy, generation speed and configuration choices across local language models — without publishing the private benchmark.

[![CI](https://github.com/ShaneGore/BenchScope/actions/workflows/ci.yml/badge.svg)](https://github.com/ShaneGore/BenchScope/actions/workflows/ci.yml)
[![Licence: MIT](https://img.shields.io/badge/licence-MIT-blue.svg)](LICENSE)

**Live demo:** https://shanegore.github.io/BenchScope/ · **Staging API:** https://benchscope-staging-api.onrender.com/ready · **Production demo API:** https://benchscope-production-api.onrender.com/version · **Task tracker:** https://github.com/ShaneGore/BenchScope/issues

The public demo is read-only and needs no account. Free-tier services can take about a minute to wake after inactivity; the UI offers Retry if loading fails.

![BenchScope demo comparison](./_docs/images/comparison.png)

## Contents

- [What it is](#what-it-is) · [Who it is for](#who-it-is-for) · [Features](#features)
- [Expected behaviour](#expected-behaviour) · [Architecture](#architecture) · [Data provenance](#data-provenance)
- [Run locally](#run-locally) · [Verify](#verify) · [Docker Compose](#docker-compose)
- [CI/CD and environments](#cicd-and-environments) · [Promotion and rollback](#promotion-and-rollback)
- [Observability](#observability) · [Alerting](#alerting) · [Supervised AI repair](#supervised-ai-repair)
- [Agent team and process](#agent-team-and-process) · [Task tracking](#task-tracking)
- [Security and privacy](#security-and-privacy) · [Known limitations](#known-limitations)
- [Documentation](#documentation) · [Licence](#licence)

## What it is

Local LLM evaluations usually end up as disconnected JSON files or spreadsheet rows. Model versions, quantisation, reasoning settings and incomplete measurements make results hard to interpret and harder to compare over time.

BenchScope turns supported result files into validated, persistent records with explicit configuration snapshots and honest missing-data semantics. It is an observatory, not a leaderboard: it stores what the benchmark recorded, keeps unmeasured values `null`, and explains when two results are not directly comparable.

## Who it is for

- Developers running local or hosted language models who want a durable history of coding-benchmark results.
- Reviewers who need to see run configuration, task outcomes and comparisons without access to the private evaluation harness.
- Course and portfolio reviewers assessing a complete full-stack application with tests, deployment, observability and an incident-response workflow.

## Features

- **Import and persist** — strict `benchscope.run.v1` and `benchscope.run.v2` JSON contracts, validation, duplicate detection, PostgreSQL storage and Alembic migrations.
- **Inspect and compare** — run history with filters, run detail, task outcomes, side-by-side metrics, pass-rate and throughput charts. Personal v2 comparisons enforce benchmark identity, release, manifest digest and task-set compatibility.
- **Keep workspaces private** — Clerk sign-in in hosted mode, backend-enforced owner scoping, generic 404s for missing or foreign records.
- **Anonymous demo** — an immutable synthetic catalogue served over GET-only endpoints; no account, database seed or write path.
- **Missing is not zero** — nullable metrics remain `null` and render as unavailable; incomplete v2 task coverage never becomes a misleading pass rate.
- **Model profiles** — hardware and inference settings, with endpoint and credential fields rejected in hosted mode.
- **Local benchmark seam** — a local-only runner interface with single-flight enforcement, cancellation, timeout and Windows process-tree safety, exercised with synthetic adapters.
- **Operate and verify** — containerised local stack, five required CI jobs, automatic staging deployment, protected manual production promotion, a rehearsed rollback, local correlated telemetry and a supervised incident-response workflow.

## Expected behaviour

The product specification and acceptance criteria live in the [product plan](./_docs/plan.md), the [task backlog](./_docs/tasks.md) and the public issue tracker. The behaviours a reviewer can check directly are:

1. The public demo lists published configurations and opens each result without signing in.
2. Selecting two or more results produces a comparison with explicit configuration differences; unavailable metrics stay unavailable.
3. A signed-in user can import a supported result, see it in history, reopen it, and compare it only with their own comparable runs.
4. Another signed-in user cannot read, change or compare the first user's runs.
5. Hosted mode never exposes benchmark launch routes; `/api/v1/benchmark/capabilities` returns `{"enabled":false}`.
6. The full stack starts with one command and the test suite runs with one command.

The current rubric mapping, with evidence and limitations, is in the [rubric evidence matrix](./_docs/submission/rubric-evidence.md).

## Architecture

```
Browser (React + Vite + TypeScript, GitHub Pages)
   |  HTTPS, Clerk JWT for personal data
   v
FastAPI (Python 3.12, Render)  --->  PostgreSQL (Neon) / local Docker Postgres
   |  Alembic migrations, owner-scoped SQLAlchemy models
   |
   +-- local-only benchmark runner seam (never hosted)
   +-- OpenTelemetry -> Collector -> Prometheus / Tempo / Loki -> Grafana
                                   |
                                   +-- alert rule -> authenticated receiver -> incident + repair job
```

| Layer | Technology |
|---|---|
| Frontend | React, Vite, TypeScript, pnpm, Vitest, Playwright |
| Backend | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic |
| Database | PostgreSQL 17 locally; Neon Postgres in the hosted environments |
| Auth | Clerk (hosted); guarded local development identity |
| Observability | OpenTelemetry, Prometheus, Grafana, Loki, Tempo |
| Hosting | GitHub Pages (frontend), Render Free (API), Neon Free (database) |
| CI/CD | GitHub Actions with five required checks |

Detailed architecture: [system](./_docs/architecture/README.md) · [boundaries](./_docs/architecture/boundaries.md) · [backend API](./_docs/architecture/backend/api.md) · [data model](./_docs/architecture/backend/data-model.md) · [frontend](./_docs/architecture/frontend/README.md) · [deployment design](./_docs/architecture/deployment.md).

## Data provenance

BenchScope contains two clearly different kinds of data:

| Kind | Where it comes from | What is published |
|---|---|---|
| **Synthetic demo catalogue** | An immutable in-code fixture of 15 configurations, derived from the owner's Local-LLM-Coding-Benchmark-v2 summaries. Values are aggregate summaries; the fixture is served read-only. | Published by the anonymous demo endpoints and shown in the UI. |
| **User imports** | A signed-in user imports a supported v1/v2 JSON result file produced by the external benchmark. The server stores only allowlisted metrics and metadata and discards the raw upload. | Visible only to that owner. The production database additionally holds two `smoke-test-run-*` rows owned by a synthetic smoke identity and two `neon-verify-*` rows owned by the guarded local identity, created during provisioning verification. All four are synthetic. |
| **Private benchmark material** | Prompts, reference answers, hidden tests, raw trials, generated code and evaluation paths. | Never stored, logged, served or committed. |

The demo numbers are **not** produced by BenchScope and are not a controlled ranking: configurations differ in reasoning, MTP, context and inference settings, and some measurements are unavailable. The README's [demo methodology](#demo-methodology) records the aggregate caveats.

## Demo methodology

The catalogue contains 15 configurations from the owner's Local-LLM-Coding-Benchmark-v2 results: 13 local configurations and two hosted OpenRouter configurations, each recording 47 tasks. Passing requires import plus public and hidden checks. One Ternary Bonsai reasoning-on run records one provider error (`29/47 passed · 47/47 recorded · 1 provider error`). Throughput values are the benchmark's recorded generation throughput; the two hosted configurations have no throughput value. Reasoning, MTP and context settings differ between runs, so the catalogue is not a controlled ranking. Raw trials and evaluation material remain private; published summaries expose aggregate metrics and configuration labels.

## Run locally

Requirements: [uv](https://docs.astral.sh/uv/), Docker Desktop (or Docker Engine with Compose v2) and, for the test suite, Node.js 22 with Corepack.

From the repository root:

```powershell
uv run --no-project python scripts/start.py
```

Open **http://127.0.0.1:5173**. The command creates a missing ignored `.env` with a random PostgreSQL password and explicit local-development authentication, then builds and starts the frontend, API and database. Existing `.env` files are preserved; configuration errors explain what needs updating.

Default ports are 5173, 8000 and 5432; set `FRONTEND_PORT`, `API_PORT` and `POSTGRES_PORT` in `.env` if they are occupied. Data survives container restarts. Stop the core stack with:

```powershell
uv run --no-project python scripts/start.py --stop
```

The PostgreSQL volume is retained on stop.

For local Grafana, Prometheus, Loki, Tempo, OpenTelemetry collection and alert intake:

```powershell
uv run --no-project python scripts/start.py --observability
uv run --no-project python scripts/start.py --stop --observability
```

Try importing the [synthetic example](frontend/public/examples/synthetic-run.json), also downloadable from the Import page. Its values are invented for onboarding and testing; they are not benchmark measurements. Re-importing it demonstrates duplicate detection.

### Local benchmark execution

Benchmark execution is local-only and disabled by default. Hosted mode never mounts the runner routes, regardless of `BENCHMARK_ENABLED`. The current adapter seam is exercised with synthetic runners; the real private runner contract is tracked in [#25](https://github.com/ShaneGore/BenchScope/issues/25) and is not integrated.

## Verify

With Docker running:

```powershell
uv run --no-project python scripts/verify.py
```

The command provisions a disposable PostgreSQL database, installs locked dependencies, runs backend lint and unit/integration tests, frontend tests and production build, API-contract checks, a container browser check, and the browser journeys. It selects isolated local ports and removes its own test resources afterwards. Failed checks produce a nonzero exit code.

Individual suites:

```powershell
cd backend; uv run pytest
cd frontend; corepack pnpm test
cd frontend; corepack pnpm test:journey
```

PostgreSQL integration tests require a disposable `TEST_DATABASE_URL`; the root verifier provides one. The latest recorded result and its limits are in the [verification log](./_docs/submission/submission-checklist.md#dated-verification-log).

## Docker Compose

`compose.yaml` defines the complete core stack:

| Service | Purpose |
|---|---|
| `frontend` | Built static frontend served by nginx |
| `api` | FastAPI backend |
| `db` | PostgreSQL 17 with a named volume |

`compose.observability.yaml` adds `otel-collector`, `prometheus`, `loki`, `tempo`, `grafana` and `alert-receiver`. The supported single command is `scripts/start.py`, which generates configuration, selects free ports, builds and waits for health. Plain `docker compose up` is supported for inspection but expects a suitable `.env`.

## CI/CD and environments

GitHub Actions runs:

| Workflow | Trigger | Purpose |
|---|---|---|
| `ci.yml` | Pull request; push to `main` | Five checks: `backend`, `frontend`, `journey`, `container-images`, `backend-windows` |
| `deploy-backend.yml` | Successful `main` CI | Automatic staging API deployment to Render, followed by authenticated smoke tests |
| `deploy-frontend.yml` / `pages-deploy.yml` | Successful `main` CI / manual | GitHub Pages frontend deployment |
| `promote-production.yml` | Manual `workflow_dispatch` | Protected production promotion with exact-SHA CI gate, migrations, deploy hook, revision wait and smoke tests |

The main ruleset requires a pull request, resolved review threads and all five checks, with **zero required approving reviews**. Independent code review is therefore procedural, not enforced.

| Environment | URL | Revision | Deployment |
|---|---|---|---|
| Public Pages frontend | https://shanegore.github.io/BenchScope/ | Built from `main`; Pages record `42714879726` | Automatic after successful `main` CI, staging-backed API |
| Staging API | https://benchscope-staging-api.onrender.com | `dd8064ac6e3ebf505acb23fa01f5da051e07747f` | Automatic after successful `main` CI |
| Production demo API | https://benchscope-production-api.onrender.com | `dd8064ac6e3ebf505acb23fa01f5da051e07747f` | Manual, protected environment approval |

The production demonstration is **backend/API-focused**: the public Pages frontend remains connected to staging. Production is verified directly through `/version`, `/health`, `/ready` and the authenticated synthetic smoke suite.

## Promotion and rollback

Production promotion uses the existing workflow, never the Render dashboard:

```powershell
gh workflow run promote-production.yml --ref main -f confirm=promote -f ref=<40-char-sha>
```

The run pauses at the protected `production` environment, checks that the SHA is an ancestor of `main` with successful `main` push CI, runs `alembic upgrade head`, triggers the Render deploy hook with `?ref=<sha>`, waits for `/version` and `/ready`, mints short-lived Clerk tokens, and runs the full smoke test.

The rollback path was rehearsed on 2026-11-10:

| Step | Revision | Run |
|---|---|---|
| Rollback | `ab6ea5dc10d18059071f06696478edc0b1c46284` | [42727553382](https://github.com/ShaneGore/BenchScope/actions/runs/42727553382) |
| Restore | `dd8064ac6e3ebf505acb23fa01f5da051e07747f` | [42728234322](https://github.com/ShaneGore/BenchScope/actions/runs/42728234322) |

Both runs required environment approval, passed 13/13 smoke checks, retained the same four synthetic run UUIDs and left the schema at `0008`. Migrations are forward-only; the rehearsal restored schema-compatible application revisions and did **not** perform a database downgrade. See the [production runbook](./_docs/architecture/production-release.md#rollback-and-restoration-evidence-executed).

## Observability

The local stack instruments a synthetic API request and correlates it across all three signals:

- **Metrics** — a bounded request counter with a W3C trace ID as an OpenMetrics exemplar, plus request-duration histograms.
- **Traces** — OpenTelemetry spans exported to Tempo.
- **Logs** — structured request logs in Loki carrying the same trace ID and span ID.

Grafana maps the exemplar to Tempo and exposes the trace through an anonymous Tempo proxy, so a Viewer can follow a metric to a trace without Explore. An isolated verifier checks the exemplar, span, log and Grafana proxy for one generated trace ID. Recorded evidence: trace `802cccdd7ebb4fc79cdd9750c0f8063d` at revision `12c3206`. See [metric-to-trace verification](./_docs/observability/metric-trace-link.md).

Telemetry is **local**; the hosted staging and production APIs do not run this monitoring stack. No prompts, generated code, credentials or customer data are recorded in telemetry.

## Alerting

Grafana evaluates a provisioned availability rule, `BenchScopeApiUnavailable`, against Prometheus `up{job="api"}`. A firing alert is delivered over the private Compose network to an authenticated alert receiver, which:

- requires the exact bearer secret from a local secret file;
- accepts only known alert names and firing/resolved payloads;
- persists an incident with sanitised Prometheus, Loki and Tempo evidence;
- deduplicates by alert fingerprint;
- records audit events and queues a repair job bound to the application revision.

A genuine fault was reproduced by disabling the metrics mount: `/health` and `/ready` stayed 200 while `/metrics` returned 404, Prometheus reported `up=0`, and the Grafana alert fired after its `for` period. Evidence: [Phase 3C recovery record](./_docs/incidents/phase3c-recovery-demo.md) and [incident exercises](./_docs/incidents/task-23.md).

## Supervised AI repair

BenchScope demonstrates a **supervised** incident-response flow, not autonomous production recovery:

1. A real Grafana alert fires and is accepted by the authenticated receiver.
2. The incident and repair job are persisted with complete, sanitised evidence.
3. An explicitly started local repair worker claims the job and asks GPT-6 Luna through GitHub Copilot CLI to investigate.
4. The model proposes a patch limited to an allowlist: the metrics enable condition, the literal health response, and health-contract tests.
5. The worker validates the patch, applies it in an isolated worktree, and runs tests in a restricted container.
6. On success it opens a **draft** pull request; CI runs the five required checks.
7. A human reviews and merges; merge, release and hosted recovery are never automated.

Two supervised runs completed the real alert-to-draft-PR path (PRs [#63](https://github.com/ShaneGore/BenchScope/pull/63) and [#64](https://github.com/ShaneGore/BenchScope/pull/64), both closed and unmerged as evidence). A later Phase 3C exercise replayed the recorded PR #64 patch against a fresh disposable incident, applied it with owner approval only to the affected disposable API, and independently verified recovery: `/metrics` exposition restored, Prometheus `up=1`, Grafana alert cleared, incident `resolved` with an audit event. This was a labelled replay, not a new model invocation, and the automatic executor remains disabled.

The worker is operator-supervised because its host process is not an OS sandbox and it can use the operator's GitHub CLI credentials. It is not hosted and has no production credentials. See [known limitations](./_docs/submission/known-limitations.md).

## Agent team and process

Three roles work against checkable acceptance criteria:

| Role | Responsibility | Instructions |
|---|---|---|
| Product Manager | Grooms one issue, rewrites it with checkable acceptance criteria, moves out-of-scope work to follow-ups | [`_docs/team/pm.md`](./_docs/team/pm.md) |
| Software Engineer | Implements one groomed task with tests, does not close the issue | [`_docs/team/software-engineer.md`](./_docs/team/software-engineer.md) |
| QA Engineer | Checks the running result against every criterion and reports PASS/FAIL, without fixing code | [`_docs/team/qa-engineer.md`](./_docs/team/qa-engineer.md) |

The orchestrator launches the roles, returns QA failures to engineering, and closes an issue only after PASS. The pipeline is described in [`_docs/process.md`](./_docs/process.md); custom Copilot agent definitions are in [`.github/agents/`](./.github/agents/). All three definitions use the verified CLI model ID `gpt-6-luna`. Historical QA-agent launch limitations are documented honestly in [known limitations](./_docs/submission/known-limitations.md).

## Task tracking

The public tracker is the single source of truth: https://github.com/ShaneGore/BenchScope/issues

Issues carry groomed acceptance criteria, implementation notes, QA verdicts and links to pull requests. Representative evidence:

- Product specification and backlog: [`_docs/plan.md`](./_docs/plan.md), [`_docs/tasks.md`](./_docs/tasks.md)
- Frontend/API integration and review: [#13](https://github.com/ShaneGore/BenchScope/issues/13)
- Metric-to-trace verification: [#35](https://github.com/ShaneGore/BenchScope/issues/35)
- Showcase improvements: [#56](https://github.com/ShaneGore/BenchScope/issues/56)
- Production setup and rollback rehearsal: [#70](https://github.com/ShaneGore/BenchScope/issues/70)
- Private adapter contract (open): [#25](https://github.com/ShaneGore/BenchScope/issues/25)

## Security and privacy

- **Private benchmark stays out.** Prompts, reference answers, hidden tests, raw trials, generated code and evaluation paths are never committed, served or logged.
- **Ownership is server-side.** `owner_id` comes only from the verified JWT subject (or the guarded local identity); every lookup is owner-scoped and returns a generic 404 for foreign IDs.
- **Hosted mode is restricted.** Benchmark routes are not mounted, profile endpoint/credential fields are rejected, and CORS uses an explicit origin allowlist with no wildcards.
- **Uploads are bounded and allowlisted.** Streaming size limits, strict schemas, unknown-field rejection and no raw-payload retention.
- **Secrets stay out of the frontend.** Only public `VITE_*` build values are shipped; database URLs, Clerk secret keys and deploy hooks remain server- or environment-scoped.
- **Production approval is a self-approval gate.** GitHub enforces the required reviewer, but the sole owner reviews their own deployment; independent review is not enforced.

See [boundaries](./_docs/architecture/boundaries.md) and the [security review](./_docs/submission/security-review.md).

## Known limitations

- The private benchmark runner adapter is **not integrated**; [#25](https://github.com/ShaneGore/BenchScope/issues/25) remains open and the runner is exercised with synthetic adapters only.
- The hosted public frontend uses the staging API; production frontend-to-API connectivity is not exercised.
- Observability and alerting are verified in local Docker Compose, not as a hosted monitoring stack.
- The repair workflow is supervised and its automatic recovery executor is disabled; verified recovery was a replay applied with owner approval in a disposable environment.
- `quality_score` remains `null` until an authoritative definition exists.
- Hosted services use free tiers with no SLA, cold starts, limited history and no backup guarantee.
- Rate limiting specifics remain undefined.

The full, dated list is in [known limitations](./_docs/submission/known-limitations.md).

## Documentation

| Topic | Document |
|---|---|
| Submission evidence matrix (12 criteria) | [`_docs/submission/rubric-evidence.md`](./_docs/submission/rubric-evidence.md) |
| Reviewer walkthrough (5–8 minutes) | [`_docs/submission/demo-walkthrough.md`](./_docs/submission/demo-walkthrough.md) |
| Submission text and reviewer instructions | [`_docs/submission/submission-text.md`](./_docs/submission/submission-text.md) |
| Maintenance and portfolio handover | [`HANDOVER.md`](./HANDOVER.md) |
| Production release and rollback runbook | [`_docs/architecture/production-release.md`](./_docs/architecture/production-release.md) |
| Deployment design | [`_docs/architecture/deployment.md`](./_docs/architecture/deployment.md) |
| Incident evidence | [`_docs/incidents/phase3c-recovery-demo.md`](./_docs/incidents/phase3c-recovery-demo.md) |
| Security review | [`_docs/submission/security-review.md`](./_docs/submission/security-review.md) |
| Known limitations | [`_docs/submission/known-limitations.md`](./_docs/submission/known-limitations.md) |
| Product plan | [`_docs/plan.md`](./_docs/plan.md) |
| Agent process | [`AGENTS.md`](./AGENTS.md), [`_docs/process.md`](./_docs/process.md) |

## Licence

First-party code uses the [MIT Licence](LICENSE). Private benchmark materials and third-party dependencies retain their own licences. The demo catalogue contains aggregate summaries only; no private benchmark material is redistributed.
