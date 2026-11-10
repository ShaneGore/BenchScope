# Submission text and reviewer instructions

Copy-ready text for the course platform and portfolio, plus a short reviewer
guide. All statements are limited to what the repository, workflows and recorded
evidence support.

---

## A. Short description

> **BenchScope — a local-first observatory for coding-benchmark results.**
>
> Running local language models produces benchmark results that scatter across
> JSON files and spreadsheets, making model versions, quantisation, reasoning
> settings and incomplete measurements hard to compare. BenchScope imports a
> supported result once, validates and normalises it, and keeps a durable,
> inspectable history. Users can browse anonymous published configurations or
> sign in to import their own results, then compare coding accuracy, generation
> speed and configuration choices — without the private benchmark ever leaving
> the local machine.
>
> Built with React/TypeScript, FastAPI and PostgreSQL, containerised with Docker
> Compose, and deployed with GitHub Actions, a staging environment and a
> protected manual production release. It includes correlated OpenTelemetry
> observability, a user-impact alert, and a supervised AI incident-repair
> workflow that produces a CI-checked draft patch for human approval.

---

## B. Detailed technical description

### Problem and users

Local-LLM evaluation output is usually a one-off file. Comparing two runs means
remembering which model build, quantisation, temperature, context length or
reasoning setting produced each number, and silently treating missing
measurements as zero. BenchScope gives developers, reviewers and course
assessors a persistent observatory: import a result, keep it, and compare it
honestly.

### Why it was built

The project applies the full course workflow to one real problem rather than a
set of disconnected exercises. It had to demonstrate a complete application with
a specification written before the code, an agent team, a public tracker, tests,
containers, deployment, CI/CD with a rollback path, observability, a real alert
and a responder agent.

### Application functionality

- **Strict import** of `benchscope.run.v1` and `benchscope.run.v2` JSON, with
  field validation, duplicate detection and raw-payload discard.
- **Persistent history and detail** with status/model/date filters and stable
  ordering.
- **Comparison** with explicit configuration differences; personal v2 runs also
  enforce benchmark identity, release, manifest digest and task-set
  compatibility.
- **Anonymous demo** — an immutable synthetic catalogue served over GET-only
  endpoints.
- **Owner isolation** — Clerk-authenticated hosted mode, server-side ownership
  from the verified JWT subject, generic 404s for foreign records.
- **Missing-data semantics** — nullable metrics stay `null`; incomplete task
  coverage never becomes a misleading pass rate.
- **Model profiles** — hardware and inference settings, with endpoint and
  credential fields rejected in hosted mode.
- **Local-only benchmark seam** — single-flight, cancellation, timeout and
  Windows process-tree safety, exercised with synthetic adapters.

### Architecture and technology

| Layer | Technology |
|---|---|
| Frontend | React, Vite, TypeScript, pnpm, Vitest, Playwright |
| Backend | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic |
| Database | PostgreSQL 17 locally; Neon Postgres hosted |
| Auth | Clerk (hosted); guarded local identity |
| Observability | OpenTelemetry, Prometheus, Grafana, Loki, Tempo |
| Hosting | GitHub Pages, Render Free, Neon Free |
| CI/CD | GitHub Actions, five required checks |

### How AI development tools were used

Development ran through an agent team orchestrated from the main session: a
Product Manager groomed each issue into checkable acceptance criteria, a Software
Engineer implemented one groomed task with tests, and a QA role verified the
running result and returned PASS/FAIL without editing code. GitHub Copilot custom
agent definitions encode the three roles; `AGENTS.md` is a short index into
modular context so each task loads only the documentation it needs. The agent
history is visible in the public issue and pull-request timeline.

AI is also part of the **runtime product**: GPT-6 Luna through GitHub Copilot CLI
investigates a firing alert and proposes an allowlisted patch.

### Testing strategy

One command, `uv run --no-project python scripts/verify.py`, provisions a
disposable PostgreSQL database, installs locked dependencies and runs lint,
backend unit/integration tests, frontend tests, the production build, the API
contract check, a container browser check and the browser journeys. The Phase 4
run on `main` passed Ruff, 531 backend tests with no skips, 102 frontend tests,
the build, the contract check, 10 browser journeys and a restart-persistence
check, then removed its disposable resources.

### Containerization

`compose.yaml` defines the complete core stack: an nginx-served frontend, the
FastAPI API and PostgreSQL 17 with a named volume. `scripts/start.py` is the
supported single command; `compose.observability.yaml` adds the telemetry and
alerting stack.

### CI/CD and deployment

`ci.yml` runs on every pull request and push to `main` with five required checks.
A successful `main` run automatically deploys the staging API and the Pages
frontend. Production is a separate API and Neon database, released only through a
manual, protected `workflow_dispatch` workflow that verifies the exact SHA,
applies migrations, pins the Render deploy, mints short-lived Clerk tokens and
runs a 13-check authenticated smoke suite. A rollback and restoration rehearsal
both passed, retained the same synthetic records and kept the schema compatible.

### Observability and alerting

OpenTelemetry emits metrics, traces and structured logs. The request counter
carries the W3C trace ID as an OpenMetrics exemplar, so Grafana can jump from a
metric to the matching Tempo trace; Loki logs carry the same trace and span IDs.
A Grafana availability rule on `up{job="api"}` alerts on user impact rather than
CPU. A reproduced metrics outage fired the alert while `/health` stayed 200.

### Supervised AI incident repair and verified recovery

An authenticated alert persists an incident and a repair job. An explicitly
started worker asks GPT-6 Luna to investigate, validates the proposed patch
against an allowlist, applies it in an isolated worktree, runs restricted tests
and opens a **draft** pull request. Two supervised runs completed that path and
are retained as evidence. A later disposable exercise replayed the recorded
patch with owner approval and independently confirmed recovery. Merge, release
and hosted recovery are never automated.

### Engineering challenges

- Distinguishing genuinely passing tests from a verifier that leaked the
  container revision into the test environment; fixed by PR #65.
- Keeping benchmark execution strictly local while the hosted app shares code.
- Making rollback meaningful with forward-only migrations: only
  schema-compatible revisions are safe targets.
- Preventing the AI repair worker from becoming an unattended production actor.

### Lessons learned

Honest missing-data semantics matter more than a tidy leaderboard. Observable
failure beats a green dashboard: an alert on `up` caught a broken metrics mount
that health checks missed. Evidence is only as good as its snapshot — test
totals, SHAs and workflow runs must be recorded with their revision.

### Known limitations

The private benchmark adapter is not integrated (#25). Observability and alerting
are local, not hosted. The public frontend is staging-backed; production is
API-only. Hosted AI repair is disabled and the demonstrated recovery was
supervised in a disposable environment. Free tiers have no SLA. `quality_score`
remains null until an authoritative definition exists. The main ruleset requires
zero approving reviews, so the production approval is a self-approval gate.

---

## C. Reviewer instructions

1. **Start with the [README](../../README.md).** It states the problem, users,
   features, expected behaviour and architecture in about five minutes.
2. **Open the app:** <https://shanegore.github.io/BenchScope/>. Use the anonymous
   demo; no account is needed. Allow a minute for a free-tier cold start.
3. **Follow the [demo walkthrough](./demo-walkthrough.md)** for a 5–8 minute
   tour with exact URLs.
4. **Score against the [rubric evidence matrix](./rubric-evidence.md).** Each of
   the 12 criteria lists the official full-credit requirement, implemented
   functionality, demonstrated evidence, direct links and scope notes.
5. **Check the tracker:** <https://github.com/ShaneGore/BenchScope/issues>.
   Closed issues carry acceptance criteria, implementation notes and QA verdicts.
   [#25](https://github.com/ShaneGore/BenchScope/issues/25) is genuinely open and
   represents the deferred private adapter.
6. **CI/CD:** start at run [`42714645314`](https://github.com/ShaneGore/BenchScope/actions/runs/42714645314)
   then the staging deploys and the promotion/rollback runs linked in
   [production-release.md](../architecture/production-release.md).
7. **Observability and incidents:** [metric-trace-link.md](../observability/metric-trace-link.md)
   and [phase3c-recovery-demo.md](../incidents/phase3c-recovery-demo.md).
8. **Security and limits:** [security-review.md](./security-review.md) and
   [known-limitations.md](./known-limitations.md).

The private benchmark runner is intentionally **not** publicly reproducible. Its
inputs, expected outputs and raw results are not in the repository, and reviewers
do not need them to assess any criterion.
