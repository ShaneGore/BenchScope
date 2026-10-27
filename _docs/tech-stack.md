# BenchScope — Technology Stack Decision

**Status:** Stack choices are candidates; public React frontend on GitHub Pages and a separately hosted API/database are the intended layout. Provider terms, current limits, payment-method requirements, and $0 recurring-cost eligibility must be verified before provisioning. Architecture, backlog and agent roles are out of scope for this document.
**Source of requirements:** `_docs/plan.md` (unchanged).
**Decision principle:** Prefer technologies already used successfully in the owner's course projects, keep recurring cost at $0, and keep the private benchmark and local model endpoints out of the public hosted environment.

---

## 1. Selected stack (one clear choice per layer)

| Layer | Decision |
|---|---|
| Frontend | React + Vite + TypeScript (SPA) |
| Frontend package manager | `pnpm` |
| Frontend hosting | GitHub Pages (static site, public repository) |
| Frontend build/deploy | GitHub Actions |
| Backend framework | FastAPI (Python 3.12) |
| Python environment/deps | `uv` with `pyproject.toml` + committed `uv.lock` |
| Database | PostgreSQL |
| Local database | PostgreSQL via Docker Compose |
| Hosted database | Neon (candidate; verify current terms) |
| Migration tool | Alembic (SQLAlchemy 2.x) |
| ORM/data layer | SQLAlchemy 2.x |
| Authentication provider | Clerk (candidate; verify current terms and limits) |
| Identity verification | FastAPI dependency verifies Clerk JWT via JWKS; Clerk `sub` is the owner key |
| API hosting | Render (candidate; verify current terms) |
| API contract/validation | Pydantic v2 models + FastAPI-generated OpenAPI; TS types generated from OpenAPI |
| Benchmark execution | In-process, single-flight (local mode only): `asyncio` + `asyncio.create_subprocess_exec`, DB-backed status, `asyncio.wait_for` timeout, startup reconciliation |
| Job infrastructure | None (no Redis/Celery/Kubernetes) |
| Local orchestration | Docker Compose (app + Postgres + full Grafana observability stack) |
| Container base | Multi-stage Dockerfiles (backend via `uv`, frontend via Node build) |
| Observability (local) | OpenTelemetry (FastAPI + React) → OTLP; Prometheus + Loki + Tempo + Grafana, self-hosted in Compose |
| Observability (hosted) | Optional Grafana Cloud Free for hosted API telemetry; not required for MVP |
| CI/CD | GitHub Actions (quality, test, API contract, static Pages-path, and non-publishing Docker image builds) |
| Error monitoring | None by default (add only if a concrete need justifies it; Sentry not included) |
| Testing (backend) | pytest + pytest-asyncio + HTTPX |
| Testing (frontend) | Vitest + React Testing Library |
| Testing (e2e) | Playwright |
| Lint/format (Python) | ruff (lint + format) |
| Type checking (Python) | Not currently configured |
| Lint/format (TS) | No frontend lint script currently configured |

## 2. Why this stack (rationale and trade-offs)

### 2.1 Backend: FastAPI + SQLAlchemy 2 + Alembic + PostgreSQL
- **Familiarity:** FastAPI, Pydantic, SQLAlchemy 2, Uvicorn, pytest/HTTPX are already used successfully in multiple course projects. Lowest friction and highest confidence.
- **Fit:** Async-friendly (needed for non-blocking benchmark runs), strong request validation via Pydantic, automatic OpenAPI for frontend type generation, clean dependency-injection for ownership checks.
- **PostgreSQL over SQLite:** Multi-user hosted mode, concurrent writes, production parity. SQLite remains usable via `DATABASE_URL` override for quick local experiments (TeamFlow pattern), but Postgres is canonical; integration tests run against Postgres to avoid dialect drift.
- **Trade-off accepted:** Two runtimes (Python + Node build) and a frontend build step. Acceptable given the React/Vite requirement and the value of a typed SPA.

### 2.2 Frontend: React + Vite + TypeScript
Required by preference and best fit for an interactive dashboard with charts, filters, and auth UI. Vite gives fast dev feedback. TypeScript keeps the API contract honest (types generated from OpenAPI).

### 2.3 Python tooling: `uv` + `pyproject.toml` + `uv.lock`
Required by preference. `uv` is fast, reproducible, and already in use. The committed lockfile makes CI and Docker builds deterministic.

### 2.4 Authentication: Clerk (candidate; implementation verifies JWTs via JWKS)
- **Decision:** Clerk is the current provider candidate. Its current terms, limits, payment-method requirements, and suitability for the $0 recurring-cost constraint are unverified and must be checked before provisioning.
- **Justification:**
  - **Development friction:** Clerk ships a first-class React SDK and straightforward JWT verification in Python (JWKS), so sign-in/out/session protection are mostly configuration, not code. This directly satisfies "prefer a maintained provider over custom auth logic."
  - **Secure ownership enforcement:** Clerk provides a stable, opaque user ID (`sub`) used as the owner key on every profile/run record; a backend dependency resolves the current user from the verified JWT and injects it into route handlers. No passwords, sessions, or tokens are stored by us.
  - **Local + hosted parity:** The same Clerk instance (or a separate dev instance) works in both modes, so there is one code path. The default-disabled offline bypass (`LOCAL_AUTH_BYPASS=true`) is accepted only with `APP_ENV=development`, `APP_MODE=local`, and a loopback-only effective bind host; `APP_ENV` defaults to `production`, and all invalid combinations fail startup.
  - **Why not the others:** Auth0 is mature but heavier to configure and pricier at scale; Supabase Auth couples identity to a Supabase project/Postgres and tempts RLS-based access control (the plan requires server-side enforcement in app code, not DB policies); FastAPI Users / Django auth would mean owning password flows, recovery, and session security — exactly what the plan says to avoid. Django auth would also force a Django backend, losing the FastAPI/React/OTel alignment.
- **Trade-off:** External SaaS dependency for identity and small vendor lock-in on user IDs (mitigated by storing only the opaque `sub`, which is portable). Recheck current terms and limits before any hosted use.

### 2.5 Benchmark execution and recovery: in-process, single-flight, no queue
- **Decision:** One benchmark at a time, launched with `asyncio.create_subprocess_exec` inside a FastAPI background task, status persisted to Postgres, reconciled on startup. Available in local mode only.
- **Rationale:** The plan forbids distributed queues/Kubernetes "without a demonstrated need," and MVP needs only one run at a time. An in-process approach is testable (inject a fake runner), records timeouts (`asyncio.wait_for`), failures (exit codes + captured stderr, sanitised), and interrupted runs (startup reconciliation marks stale `running` rows `interrupted`). No Redis/Celery/worker fleet to operate.
- **Trade-off accepted:** Runs die with the process; recovery is "mark interrupted + user retries," which matches the plan. Horizontal scaling of the runner is out of scope.

### 2.6 Observability: OpenTelemetry + Prometheus + Loki + Tempo + Grafana (local)
- **Decision:** Reuse the exact stack from the Order Tracker project for local development.
- **Rationale:** Already proven; satisfies "correlated metrics, structured logs, traces in a dashboard" and "at least one actionable alert." Local dev runs the full stack in Compose. Hosted telemetry is optional and not required for MVP. Any hosted telemetry provider's terms and payment requirements must be verified before use. No Sentry is added unless a concrete need justifies the extra service.

### 2.7 Hosting: GitHub Pages (frontend) + Render Free (API) + Neon Free (database)
- **Candidate layout:** Public React frontend on GitHub Pages; FastAPI on Render; PostgreSQL on Neon. Provider terms, current limits, payment-method requirements, and $0 recurring-cost eligibility must be reverified immediately before provisioning and approved by the owner. None are configured by issue #20.
- **Rationale:**
  - **GitHub Pages** serves the static Vite build only; it cannot run the backend, database, benchmark, or runner. Current eligibility and usage terms require a pre-provisioning check.
  - **Render** is the API host candidate; its free-tier behavior, sleep/cold-start characteristics, persistence, limits, and payment requirements are unverified for the selected service.
  - **Neon** is the PostgreSQL candidate; persistence, quotas, billing, backup, and payment requirements must be verified for the selected plan.
- **Trade-off:** Provider availability, terms, quotas, billing, filesystem behavior, cold starts, backups, and migrations cannot be assumed from this candidate design. No fallback may be provisioned without the same terms check and owner approval; see `_docs/architecture/deployment.md`.

### 2.8 Testing strategy
- Backend: pytest + HTTPX against a real Postgres (Compose service in CI) for integration/ownership tests; unit tests with fakes for the runner and normalisation.
- Frontend: Vitest + RTL for components; Playwright for the critical journeys (import, compare, auth).
- CI runs everything without the private benchmark or GPU by using a fake runner adapter and synthetic fixtures (required by success criteria #12).

## 3. Multi-user isolation and the local/hosted boundary

### 3.1 Multi-user isolation
- Every personal record (profile, run) carries an `owner_id` column populated from the verified Clerk JWT `sub`; never from request body or query params.
- A FastAPI dependency (`get_current_user`) verifies the JWT against Clerk's JWKS and returns the user id; route handlers filter all reads/writes by `owner_id`.
- Authorization is enforced server-side in every handler and covered by tests that mutate record IDs in requests (success criteria #18). Client-side hiding is never relied upon.
- The anonymous demo workspace is read-only and contains only synthetic data; no auth required to view it.

### 3.2 Local/private mode
- Single codebase; mode selected by `APP_MODE=local|hosted` (plus `BIND_HOST`).
- Full application and database run locally (Docker Compose: app + Postgres + full Grafana stack).
- The private benchmark runner can execute against a locally configured model endpoint.
- Local development may use `LOCAL_AUTH_BYPASS=true` only when `APP_ENV=development`, `APP_MODE=local`, and the effective bind host resolves exclusively to loopback; the setting defaults to false and `APP_ENV` defaults to production.
- Private benchmark paths and endpoint credentials come from env/`.env.local` (gitignored) and never leave the machine.

### 3.3 Hosted demonstration mode
- The React frontend is served from GitHub Pages (static, public repository).
- FastAPI and PostgreSQL are hosted separately on free tiers (Render Free + Neon Free).
- Visitors can explore synthetic, read-only demonstration data without an account.
- Signed-in users (Clerk) can manage their own imported results and history.
- Private benchmark execution and access to users' localhost model endpoints remain disabled.
- The hosted API must not expose any private benchmark implementation or artifacts; imports extract only allowlisted, non-confidential metrics and discard the raw payload.

### 3.4 GitHub Pages, Vite and client-side routing
- GitHub Pages serves static files only. A repository project site is served beneath a path such as `/<repo-name>/`, not the domain root.
- Configure Vite's `base` for the production build to match the repository/project path (e.g. `/<repo-name>/`). Keep `base: '/'` for local development. Do not hard-code the final repository name or URL until it is confirmed; drive it from an environment variable (e.g. `VITE_BASE_PATH`) with a documented default, and set it in the GitHub Actions build.
- Ensure all asset paths are relative to `base` (Vite handles this when `base` is configured). Avoid absolute root paths in code.
- Routing: GitHub Pages returns 404 for unknown paths, so client-side routes break on refresh/deep link unless handled. Prefer **hash-based routing** (`HashRouter`) for the simplest robust option; alternatively use `BrowserRouter` with a `404.html` fallback that rewrites to `index.html`. Hash routing is preferred unless clean URLs become a requirement.
- Development vs production builds differ: dev server runs at root with HMR and local API proxy; production build is static, uses the configured `base`, and points at the hosted API via a build-time public env var (`VITE_API_URL`). No secrets are embedded in the frontend bundle.
- The frontend calls the separately hosted FastAPI API. Configure the API URL per environment via `VITE_API_URL` (public, not secret). FastAPI CORS must be restricted to the expected frontend origins (the GitHub Pages URL and local dev origins); no wildcard origins in production.

## 4. GitHub Pages: eligibility and usage restrictions to recheck

Source: GitHub Docs, "GitHub Pages limits" (https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits).

- **Eligibility and current cost/payment terms:** not verified for this task. Confirm against current GitHub documentation and obtain owner approval before enabling Pages.
- **Static only:** Pages serves static files. It cannot run the FastAPI backend, database, private benchmark, or background runner. These are hosted separately.
- **Limits and usage restrictions:** review the current official Pages limits and applicable GitHub terms before provisioning. Do not rely on previously recorded limits as current.

## 5. Unresolved feasibility questions (private benchmark interface)

The private benchmark integration is the principal technical risk (plan §11). The following must be verified before finalising the runner and import normaliser. Do not invent these details.

### Must verify (minimum facts)
1. **Command/API interface:** Is it a CLI executable, a Python module, an HTTP service, or a library? Exact invocation, arguments, environment variables, working directory, and how the model endpoint is supplied.
2. **Result production:** Does it write a JSON file (path/format/atomicity), print to stdout, or return via API? Where, and how is the output location controlled?
3. **Exit behaviour:** Exit codes for success/failure, timeout behaviour, partial output on failure, whether runs can be cancelled.
4. **Result schema:** Exact JSON structure, field names/types, which metrics are always present vs optional, run/model identifiers, timestamps, versioning; sample real (sanitised) export.
5. **Runtime dependencies:** Python/runtime version, required packages, whether it can run in the app container or needs a separate environment, GPU/CPU requirements, filesystem/network access, secrets/config.
6. **Local model endpoint:** Protocol (e.g. OpenAI-compatible/Ollama/custom), base URL shape, auth, model name format, streaming support, expected concurrency and timeouts.
7. **Sanitisation allowlist:** Which fields are safe to import/store; which must be discarded (prompts, reference answers, generated code, raw artifacts, secrets).
8. **Performance characteristics:** Typical run duration and resource usage, to set sane timeout defaults and UI expectations.
9. **Concurrency/idempotency:** Whether only one run at a time is truly required by the benchmark itself, and how duplicate/retried runs are identified (for import dedupe).

### Decisions we can make now (independent of the above)
- Web framework, ORM, database, migrations, auth provider, frontend, observability, Docker, CI/CD, testing tools, mode separation, ownership enforcement, subprocess-based runner skeleton (timeout + status + recovery), no distributed queues, OpenAPI contract approach.

### Decisions that must stay open until investigation
- Exact runner adapter interface and command construction; result normalisation mapping; timeout defaults; whether the benchmark runs in the app container or a sibling container; hardware snapshot fields; model profile field set; endpoint configuration schema; which metrics are guaranteed available; import dedupe key.

## 6. Hosted provider checks ($0 recurring-cost constraint)

The following are candidates, not verified or provisioned services. Current
eligibility, terms, usage limits, persistence, cold-start behavior, billing,
and payment-method requirements remain unverified. Immediately before
provisioning, check the official sources linked in
`_docs/architecture/deployment.md`, confirm the selected option satisfies the
$0 recurring-cost constraint, and obtain owner approval. Do not provision a
fallback before performing the same checks and obtaining approval.

| Candidate | Intended role | Verify before provisioning |
|---|---|---|
| GitHub Pages | Static frontend | Eligibility, applicable terms, usage restrictions, and limits |
| Render | FastAPI API | Free-tier availability, cold starts, persistence, service limits, and payment requirements |
| Neon | PostgreSQL | Plan limits, data persistence/restore, billing, and payment requirements |
| Clerk (if used) | Authentication | Plan terms, limits, billing, and payment requirements |
| Grafana Cloud (optional) | Hosted API telemetry | Current terms, limits, billing, and payment requirements |

CI image builds and the Pages-path artifact check do not require any hosted
provider or credential. Provider-dependent cold-start, persistence, quota, and
migration behavior must not be inferred from this candidate table.

## 7. Deployment and delivery workflow (deployment not implemented)

1. A pull request runs backend, frontend, static base-path, and non-publishing
   image build checks (GitHub Actions).
2. After owner approval and current provider-term checks, configure a
   development environment with synthetic data.
3. Use issue #21 for hosted verification before any production promotion.
4. Promote frontend and API separately only after review and explicit owner
   approval.
5. Follow the documented rollback procedure only after the selected provider's
   procedure is verified.

This is a proposed staged workflow; hosted deployment and rollback have not
been exercised. Deploying the static frontend to GitHub Pages does **not**
deploy the backend; the API is a separate service.

## 8. Alternatives rejected (summary)

- **Django + server-rendered templates (Chorely pattern):** rejected because the plan calls for a React dashboard with charts and a maintained external auth provider; Django would discard the React/Vite preference and complicate the OTel/Prometheus observability alignment.
- **Next.js full-stack (Option 2):** rejected because serverless hosting conflicts with long-running benchmark subprocesses; would force containerised deploy anyway, losing Next's main advantage while keeping one less-familiar runtime boundary for Python benchmark integration.
- **.NET (Option 3):** rejected despite strong background-service primitives; lower familiarity and higher toolchain weight for an MVP, with no material benefit over FastAPI for this scope.
- **Go (Option 4):** rejected; weaker ecosystem for validation/charts and more manual auth wiring, for no meaningful MVP benefit.
- **Auth0 / Supabase Auth / FastAPI Users:** rejected in favour of Clerk (see §2.4).
- **Redis/Celery/Kubernetes:** rejected per plan non-goals; in-process single-flight runner suffices.
- **Alternative hosting providers:** no fallback is approved. Any future option requires the same current-terms, payment-method, $0-cost, and owner-approval checks before provisioning.
- **Sentry:** not added by default; local Grafana/OpenTelemetry covers development observability. Hosted telemetry is optional and needs separate approval.

## 9. Consequences

- The project is a Python (FastAPI) + TypeScript (React) monorepo with Postgres, Clerk, and Docker Compose, matching the owner's strongest existing skill set.
- The public frontend is a static Vite build on GitHub Pages; the API and database are separate provider candidates. Deploying the frontend does not deploy the backend.
- Local and hosted modes share one codebase and one auth mechanism; mode is an env switch, not a fork.
- Benchmark execution is intentionally simple and in-process, and disabled in hosted mode.
- Observability and CI/CD reuse proven patterns, reducing operational risk.
- The main remaining risk is the private benchmark interface, which gates runner and importer implementation (see §5). Provider limits, terms, payment requirements, cold starts, persistence, backups, and migrations remain checks before hosted use.

## 10. Open questions (to resolve during architecture planning)

1. Exact private benchmark command/API and result schema (§5).
2. Verify current provider terms, payment-method requirements, and $0 recurring-cost eligibility before selecting any host or database.
3. Whether Clerk terms and limits satisfy the approved hosted requirements.
4. Whether the hosted database candidate satisfies current cost, persistence, and recovery requirements.
5. Final repository name and GitHub Pages base path (drives Vite `base`).
6. Whether frontend TS types are generated in CI via `openapi-typescript` or hand-maintained.
7. ~~Naming/convention for the local auth bypass and how it is guarded in production builds.~~ Resolved by issue #14: `LOCAL_AUTH_BYPASS=false` by default; enabling it requires `APP_ENV=development`, `APP_MODE=local`, and loopback bind.
8. Whether the anonymous demo dataset is seeded at deploy time or shipped as a fixture.
9. Whether hosted telemetry via Grafana Cloud Free is worth the added configuration.