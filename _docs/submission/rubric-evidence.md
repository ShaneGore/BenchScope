# Official rubric evidence matrix

This is the reviewer-facing map from the [official 12-criterion rubric](https://github.com/DataTalksClub/ai-dev-tools-zoomcamp/blob/main/project/README.md)
to BenchScope's implementation and verification. For each criterion it states the
full-credit requirement, the functionality BenchScope implements, what was
actually demonstrated, and direct links to the tests, commits, pull requests,
deployments and verification records. The course reviewer determines the score.

- **Baseline:** `main` at `dd8064ac6e3ebf505acb23fa01f5da051e07747f`, checked on
  2026-11-10.
- **Rubric model:** 12 criteria, 24 points, 10 required to pass.

Requirements below are paraphrased from the official rubric. Evidence labels:

- **P4 verified** — re-checked directly during Phase 4 on 2026-11-10.
- **Phase 3 durable** — recorded during Phase 3 with committed documents,
  workflow runs or immutable IDs.
- **Code + tests** — supported by repository code and automated tests.
- **Historical** — reported earlier, not reproduced in Phase 4.

## Summary

| # | Criterion | Points | Primary evidence |
|---|---|---:|---|
| 1 | [Problem Description](#1-problem-description) | 2 | [README](../../README.md) |
| 2 | [Product Specification](#2-product-specification) | 2 | [Plan](../plan.md) · [Backlog](../tasks.md) · [Tracker](https://github.com/ShaneGore/BenchScope/issues) |
| 3 | [Agent Team Specification](#3-agent-team-specification) | 2 | [Process](../process.md) · [`_docs/team/`](../team/) |
| 4 | [Context Management](#4-context-management) | 2 | [`AGENTS.md`](../../AGENTS.md) · [Architecture index](../architecture/README.md) |
| 5 | [Application](#5-application) | 2 | [Verification log](./submission-checklist.md#dated-verification-log) · [`scripts/verify.py`](../../scripts/verify.py) |
| 6 | [Testing](#6-testing) | 2 | [CI run `42714645314`](https://github.com/ShaneGore/BenchScope/actions/runs/42714645314) |
| 7 | [Containerization](#7-containerization) | 2 | [`compose.yaml`](../../compose.yaml) · [`backend/Dockerfile`](../../backend/Dockerfile) |
| 8 | [Deployment](#8-deployment) | 2 | [Production release evidence](../architecture/production-release.md#current-verified-state) |
| 9 | [CI/CD](#9-cicd) | 3 | [Promotion and rollback evidence](../architecture/production-release.md#promotion-evidence-executed) |
| 10 | [Observability](#10-observability) | 2 | [Metric-to-trace verification](../observability/metric-trace-link.md) |
| 11 | [Alerting on User Impact](#11-alerting-on-user-impact) | 1 | [Phase 3C recovery record](../incidents/phase3c-recovery-demo.md) |
| 12 | [On-Call Agent](#12-on-call-agent) | 2 | [Phase 3C independently verified recovery](../incidents/phase3c-recovery-demo.md) |

---

## 1. Problem Description

**Official full-credit requirement:** the README clearly describes the problem,
the system functionality and expected behaviour.

**Implemented**
- README states the problem: local-LLM benchmark results are scattered across
  JSON files and spreadsheets, making versions, quantisation, reasoning settings
  and incomplete measurements hard to compare.
- It names the intended users, the system's role as an observatory rather than a
  leaderboard, and the expected behaviour as six checkable statements.
- It separates synthetic demo data, user imports and private benchmark material.

**Demonstrated:** document review against the rubric wording (P4 verified).

**Evidence**
- [README](../../README.md) — "What it is", "Who it is for", "Features",
  "Expected behaviour", "Data provenance".
- [Product plan](../plan.md)

**Scope note:** the problem description is documentation, not a runtime
artefact.

---

## 2. Product Specification

**Official full-credit requirement:** a specification exists, there is a publicly
accessible task tracker, tasks define acceptance criteria, and there is evidence
the agents used the tracker.

**Implemented**
- `_docs/plan.md` is the product specification: scope, users, data model,
  API surface, success criteria and deferred work.
- `_docs/tasks.md` is the groomed backlog with per-task acceptance criteria.
- The public GitHub issue tracker is the single source of truth. Issues carry
  groomed acceptance criteria, implementation notes, QA verdicts and PR links.
- The operating procedure requires an assignee and `status: in-progress` before
  work starts, and closure only after QA passes.

**Demonstrated:** tracker inspected during Phase 4 — 0 open PRs, issue #25 open
and labelled `status: in-progress`, all other milestone issues closed with
comments (P4 verified). Issue/PR timelines show the PM → engineer → QA sequence.

**Evidence**
- [Product plan](../plan.md) · [Task backlog](../tasks.md) · [Process](../process.md)
- Public tracker: <https://github.com/ShaneGore/BenchScope/issues>
- Representative groomed/QA issues: [#13](https://github.com/ShaneGore/BenchScope/issues/13),
  [#35](https://github.com/ShaneGore/BenchScope/issues/35),
  [#56](https://github.com/ShaneGore/BenchScope/issues/56),
  [#70](https://github.com/ShaneGore/BenchScope/issues/70)
- Deferred adapter contract: [#25](https://github.com/ShaneGore/BenchScope/issues/25)

**Scope note:** the tracker is genuinely public and used; role handoffs are
visible in issue timelines rather than in a separate generated report.

---

## 3. Agent Team Specification

**Official full-credit requirement:** the project defines the agent team and the
process of how they work together.

**Implemented**
- Three roles with distinct, non-overlapping responsibilities: Product Manager
  (grooming), Software Engineer (implementation), QA (verification only).
- `_docs/process.md` defines the lifecycle: pick issue → PM grooms → engineer
  implements → QA verifies → on FAIL return to engineering → close only on PASS.
- Explicit rules: do not skip grooming, the engineer does not close the issue,
  QA does not fix code, one owner per issue.
- Matching Copilot custom agent definitions exist for all three roles.

**Demonstrated:** document review; the issue tracker shows the sequence in
practice (P4 verified).

**Evidence**
- [`AGENTS.md`](../../AGENTS.md) · [`_docs/process.md`](../process.md)
- [`_docs/team/pm.md`](../team/pm.md) · [`_docs/team/software-engineer.md`](../team/software-engineer.md) · [`_docs/team/qa-engineer.md`](../team/qa-engineer.md)
- [`.github/agents/`](../../.github/agents/)

**Scope note:** all three custom agent definitions name the CLI model ID
`gpt-6-luna`. The QA custom agent previously failed to launch because its
configured model display name was unavailable; the process itself ran with
human-supervised role sessions. This launch caveat is recorded in
[known limitations](./known-limitations.md#agent-team).

---

## 4. Context Management

**Official full-credit requirement:** `AGENTS.md` exists and points to modular
documentation (process, teams, etc.).

**Implemented**
- `AGENTS.md` is short and points to `_docs/process.md`, the three role
  instructions and the matching Copilot agent definitions, plus commands,
  project layout and rules.
- Documentation is modular: product plan, task backlog, process, team roles,
  architecture (boundaries, backend, frontend, deployment), observability,
  incidents, submission and release evidence.
- Context is split so an agent loads only what a task needs rather than one
  monolithic file.

**Demonstrated:** link and path validation during Phase 4 (P4 verified).

**Evidence**
- [`AGENTS.md`](../../AGENTS.md)
- [`_docs/process.md`](../process.md) · [`_docs/team/`](../team/)
- [Architecture index](../architecture/README.md)

**Scope note:** historical agent transcripts are not published; the
documentation distinguishes process from recorded activity.

---

## 5. Application

**Official full-credit requirement:** a full-stack application works end to end,
frontend talks to backend, data persists in a database, and it runs locally with
a single command.

**Implemented**
- React + TypeScript + Vite frontend; FastAPI backend; PostgreSQL persistence
  with Alembic migrations.
- Anonymous read-only demo, Clerk-authenticated personal workspaces, strict v1
  and v2 import, history, detail, comparison, profiles, missing-metric handling.
- Single startup command: `uv run --no-project python scripts/start.py`, which
  generates a missing `.env`, builds and starts frontend, API and database.

**Demonstrated (P4, 2026-11-10):** `scripts/verify.py` built and started the full
containerised stack with PostgreSQL, imported a synthetic result, read it back
through history and detail, and confirmed persistence after an API restart. The
public demo endpoints returned 200 from staging and production; the Pages bundle
references the staging API origin.

**Evidence**
- [README — Run locally](../../README.md#run-locally)
- [Backend API](../architecture/backend/api.md) · [Data model](../architecture/backend/data-model.md)
- [`scripts/start.py`](../../scripts/start.py) · [`compose.yaml`](../../compose.yaml)
- Verification record: [submission checklist — dated log](./submission-checklist.md#dated-verification-log)

**Scope note:** `scripts/start.py` itself was not re-executed in Phase 4; the
equivalent Compose stack and restart persistence were verified. Hosted
production is API-only and the public frontend is staging-backed
([known limitations](./known-limitations.md#deployment)).

---

## 6. Testing

**Official full-credit requirement:** both unit and integration tests exist, run
with a single command, and pass.

**Implemented**
- Backend unit and PostgreSQL integration tests (alert receiver, auth, hosted
  mode, import validation, run history, runner, subprocess adapter, incident
  investigation/repair/recovery, promotion workflow, render deploy hook, smoke).
- Frontend Vitest suites, production build, API-contract check, container
  browser check and Playwright journeys.
- One command runs everything: `uv run --no-project python scripts/verify.py`.

**Demonstrated (P4, 2026-11-10, `main` + documentation change)**
- Ruff: all checks passed; 65 files formatted.
- Backend: **531 passed**, no skips, 159 s.
- Frontend: **18 files, 102 tests passed**.
- Production build and API-contract regeneration: passed.
- Container browser check: read imported result from real API in Chromium.
- Browser journeys: **6 + 3 + 1 = 10 passed**.
- Persistence across API restart: passed.
- The command removed its disposable project, volumes and images.

The one-command verifier defect (revision isolation) was fixed by PR #65
(`2be61f5`) and the fix is on `main`; the Phase 4 run above is the current
evidence and does not inherit the older failure.

**Evidence**
- [README — Verify](../../README.md#verify)
- [`scripts/verify.py`](../../scripts/verify.py)
- [Dated verification log](./submission-checklist.md#dated-verification-log)
- CI run [`42714645314`](https://github.com/ShaneGore/BenchScope/actions/runs/42714645314) — five jobs green

**Scope note:** Windows-specific subprocess safety is tested with synthetic
runners; the real private benchmark adapter is not integrated (#25). Test totals
from different snapshots are not combined: 531 is the Phase 4 snapshot only.

---

## 7. Containerization

**Official full-credit requirement:** the full system including the database runs
via Docker or Docker Compose and starts with a single command.

**Implemented**
- `compose.yaml` defines `frontend` (nginx serving the built static app), `api`
  (FastAPI) and `db` (PostgreSQL 17 with a named volume).
- `backend/Dockerfile` and `frontend/Dockerfile` build production images;
  CI builds both on every PR and push.
- `scripts/start.py` is the supported single command; it selects free ports,
  generates configuration, builds and waits for health.
- `compose.observability.yaml` adds the observability stack.

**Demonstrated (P4):** `scripts/verify.py` used Docker Compose to build and start
`db`, `api` and `frontend`, waited for health, exercised the app and removed the
project and volumes. This proves the complete system, including the database,
starts containerised.

**Evidence**
- [`compose.yaml`](../../compose.yaml) · [`compose.observability.yaml`](../../compose.observability.yaml)
- [`backend/Dockerfile`](../../backend/Dockerfile) · [`frontend/Dockerfile`](../../frontend/Dockerfile)
- [README — Docker Compose](../../README.md#docker-compose)

**Scope note:** plain `docker compose up` expects a suitable `.env`; the
supported single command is `scripts/start.py`. First-run image pulls require
network access.

---

## 8. Deployment

**Official full-credit requirement:** the application is deployed and reachable
at a public URL, or there is a clear demo with the deployment.

**Implemented**
- Public frontend: <https://shanegore.github.io/BenchScope/> (GitHub Pages).
- Staging API: <https://benchscope-staging-api.onrender.com>.
- Production demonstration API: <https://benchscope-production-api.onrender.com>.
- Staging and production are separate Render services, separate Neon databases
  and separate credentials.

**Demonstrated (P4, 2026-11-10)**
- Pages returned HTTP 200; deployed JS references the staging API origin
  (7 matches) and no production API origin.
- Staging `/version` = `dd8064a…`, `/health` 200, `/ready` `{"status":"ready"}`.
- Production `/version` = `dd8064a…`, `/health` 200, `/ready` `{"status":"ready"}`.
- The anonymous demo lists 15 configurations and opens a run detail.
- Production capabilities return `{"enabled":false}`.

**Evidence**
- [README — CI/CD and environments](../../README.md#cicd-and-environments)
- [Deployment design](../architecture/deployment.md)
- [Production release evidence](../architecture/production-release.md#current-verified-state)

**Scope note:** free tiers have no SLA and cold-start. The public frontend is
staging-backed; production is an API-only course demonstration, so production
frontend-to-API connectivity is not exercised.

---

## 9. CI/CD

**Official full-credit requirement:** CI runs tests, CD deploys to dev, and there
is a manual deploy to production.

**Implemented**
- `ci.yml` runs on every pull request and on push to `main`, with five required
  checks: `backend`, `frontend`, `journey`, `container-images`,
  `backend-windows`.
- Main ruleset requires a pull request, resolved review threads, all five checks
  and strict up-to-date checks.
- CD to staging: `deploy-backend.yml` and `deploy-frontend.yml` run after
  successful `main` CI; the Pages frontend deploys automatically.
- Manual production deploy: `promote-production.yml` requires `workflow_dispatch`,
  typed `confirm=promote`, main ancestry, exact-SHA `main` CI, migrations,
  SHA-pinned Render deploy, `/version` and `/ready` waits, minted Clerk tokens
  and the full 13/13 smoke test.
- Rollback and restoration are the same protected workflow with a pinned SHA.

**Demonstrated (P4 + Phase 3 durable)**
- Main CI [`42714645314`](https://github.com/ShaneGore/BenchScope/actions/runs/42714645314): all five jobs success at `dd8064a`.
- Staging deploy [`42714879812`](https://github.com/ShaneGore/BenchScope/actions/runs/42714879812) and Pages [`42714879726`](https://github.com/ShaneGore/BenchScope/actions/runs/42714879726): success at `dd8064a`.
- Production promotion [`42726216077`](https://github.com/ShaneGore/BenchScope/actions/runs/42726216077): success, 13/13.
- Rollback [`42727553382`](https://github.com/ShaneGore/BenchScope/actions/runs/42727553382) and restore [`42728234322`](https://github.com/ShaneGore/BenchScope/actions/runs/42728234322): both success, 13/13.
- Production environment: required reviewer, `prevent_self_review=false`,
  `can_admins_bypass=false`, `main`-only branch policy.

**Evidence**
- [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml) · [`promote-production.yml`](../../.github/workflows/promote-production.yml)
- [Promotion and rollback evidence](../architecture/production-release.md#promotion-evidence-executed)
- Issue #70 evidence comment: <https://github.com/ShaneGore/BenchScope/issues/70#issuecomment-6755310213>

**Scope note:** the main ruleset requires **zero approving reviews**, so code
review is procedural. Production approval is a **self-approval** gate because the
owner is the sole reviewer. The frontend is not promoted to production; only the
API and database are. Earlier promotion attempts failed (URL parsing, masked
Clerk key) and are preserved as historical context in
[production release evidence](../architecture/production-release.md#earlier-failed-promotion-attempts-historical).

---

## 10. Observability

**Official full-credit requirement:** a key user journey is instrumented with
metrics, traces and structured logs that share a trace ID; no customer data or
credentials go to telemetry; and the signals are collected, stored and viewable
in a UI.

**Implemented**
- OpenTelemetry instrumentation on the API; Prometheus metrics, Tempo traces and
  Loki structured logs; Grafana UI; collector pipeline provisioned as code.
- The request counter carries a W3C trace ID as an OpenMetrics **exemplar**, not
  a label; Grafana maps the exemplar to Tempo. Route/method/status labels stay
  bounded.
- Structured logs carry the same trace and span IDs.
- Telemetry excludes prompts, generated code, credentials and customer data.

**Demonstrated (Phase 3 durable, 2026-11-09 at `12c3206`)**
- A synthetic `GET /api/v1/runs` produced a Prometheus exemplar, a Tempo span, a
  Loki request log and an anonymous Grafana Tempo proxy all matching trace
  `802cccdd7ebb4fc79cdd9750c0f8063d`, span `20e0cee9bf281408`.
- The isolated verifier cleaned up its disposable project and volumes.

**Evidence**
- [Metric-to-trace verification](../observability/metric-trace-link.md)
- [Incident evidence](../incidents/task-23.md)

**Scope note:** this is **local** Docker Compose evidence. Hosted staging and
production do not run the monitoring stack, and hosted correlation is not
claimed. The observability verifier was not re-run in Phase 4; the link above is
the durable Phase 3 record.

---

## 11. Alerting on User Impact

**Official full-credit requirement:** at least one alert exists.

**Implemented**
- Grafana provisioned rule `BenchScopeApiUnavailable` evaluates Prometheus
  `up{job="api"}`, i.e. whether the API can be scraped — a user-impact signal,
  not a CPU graph.
- Firing alerts are delivered over the private Compose network to an
  authenticated receiver with an exact bearer secret.
- The receiver rejects unknown alert names and non-firing/resolved payloads,
  persists an incident with sanitised evidence, deduplicates by fingerprint,
  records audit events and queues a repair job.

**Demonstrated (Phase 3 durable)**
- A genuine fault was reproduced by disabling the metrics mount: `/health` and
  `/ready` stayed 200 while `/metrics` returned 404, Prometheus reported `up=0`,
  and the Grafana alert fired after its `for` period.
- The authenticated receiver accepted the alert and persisted an incident.

**Evidence**
- [Phase 3C recovery record](../incidents/phase3c-recovery-demo.md)
- [Incident exercises](../incidents/task-23.md)
- Alert rules: [`observability/grafana/provisioning/alerting/rules.yaml`](../../observability/grafana/provisioning/alerting/rules.yaml)

**Scope note:** the alerting stack runs locally; the hosted production
demonstration does not run this stack. The rule, delivery and incident
persistence are verified in the Phase 3C record.

---

## 12. On-Call Agent

**Official full-credit requirement:** an agent wakes up on an alert and fixes the
issue.

**Implemented**
- An authenticated alert creates an incident and a durable repair job bound to
  the application revision.
- An explicitly started local repair worker claims the job and asks **GPT-6 Luna
  through GitHub Copilot CLI** to investigate.
- The model proposes a patch limited to an allowlist: the metrics enable
  condition, the literal health response and health-contract tests.
- The worker validates the patch, applies it in an isolated worktree, runs tests
  in a restricted container, and opens a **draft** pull request.
- CI runs the five required checks on the draft.
- A human reviews and applies/merges; merge, release and hosted recovery are
  never automated. The automatic executor is disabled.

**Demonstrated end to end (Phase 3 durable)**
1. A real Grafana alert fired after a controlled metrics failure.
2. The authenticated receiver accepted and persisted the incident.
3. The supervised local repair worker dispatched the repair job.
4. GPT-6 Luna performed a genuine investigation and generated a patch.
5. The patch passed allowlist, boundary and isolated-test validation.
6. The worker opened a draft repair PR; the five GitHub CI checks passed.
7. The generated repair was applied in a controlled disposable environment.
8. Independent checks confirmed `/metrics` recovered.
9. Prometheus returned to `up=1`.
10. The Grafana alert resolved and the recovery evidence was recorded.

**Primary evidence:** the
**[Phase 3C independently verified recovery](../incidents/phase3c-recovery-demo.md)**.
A fresh disposable Grafana alert on faulty revision `79ce43c` persisted incident
`33173824-ad32-412e-a158-aabe24c5a310` and repair job
`4783dc6e-c4d6-49ad-bafb-59d69090f4dc`. The recorded GPT-6 Luna patch passed the
allowlist, boundary and isolated-test validators, was applied with owner approval
only to the affected disposable checkout, and recovery was independently
confirmed: `/metrics` exposition restored, Prometheus `up=1`, Grafana alert
cleared, incident `resolved` with an audit event.

The alert-to-draft-PR path was also completed by two supervised runs
(PR [#63](https://github.com/ShaneGore/BenchScope/pull/63) and
PR [#64](https://github.com/ShaneGore/BenchScope/pull/64), both closed and
unmerged as evidence). These show the generation stage; Phase 3C shows the fix.

**Evidence**
- [Phase 3C verified recovery](../incidents/phase3c-recovery-demo.md) — incident,
  recovery and audit evidence
- [Repair demonstration](../incidents/task-23.md#end-to-end-repair-demonstration-2026-11-09)
- [Supervised AI repair](../../README.md#supervised-ai-repair)
- [Alerting evidence](#11-alerting-on-user-impact)

**Scope note:** the repair workflow is supervised. The worker is explicitly
started, is not OS-isolated, may use the operator's GitHub CLI credentials, is
not hosted and has no production credentials. The recovery demonstration ran in
a disposable environment with owner approval; no hosted production service was
changed. These are intentional architectural boundaries. The QA custom agent
launch caveat is separate and recorded in
[known limitations](./known-limitations.md#agent-team).

---

## Peer review — separate mandatory requirement

Independently of these 24 points, the course requires **three peer reviews** of
other participants' projects. This is an owner action on the course platform and
is **not** satisfied by this repository. Verified on 2026-11-10: the active
attempt is **Project 2**, deadline **16 November 2026 (Mon) 23:00** in the
viewer's timezone, and the submission form requires the repository link plus the
**exact commit ID** to evaluate. See
[submission checklist](./submission-checklist.md#submission-platform-facts-verified-2026-11-10).
