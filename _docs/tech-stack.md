# BenchScope — Technology Stack Decision

**Status:** Decided (MVP). Updated to reflect final decision: public React frontend on GitHub Pages; API and database hosted separately on free tiers. Architecture, backlog and agent roles are out of scope for this document.
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
| Hosted database | Neon Free (preferred candidate; verify current terms) |
| Migration tool | Alembic (SQLAlchemy 2.x) |
| ORM/data layer | SQLAlchemy 2.x |
| Authentication provider | Clerk Hobby (free, preferred; verify current free-tier limits) |
| Identity verification | FastAPI dependency verifies Clerk JWT via JWKS; Clerk `sub` is the owner key |
| API hosting | Render Free web service (preferred candidate; verify current terms) |
| API contract/validation | Pydantic v2 models + FastAPI-generated OpenAPI; TS types generated from OpenAPI |
| Benchmark execution | In-process, single-flight (local mode only): `asyncio` + `asyncio.create_subprocess_exec`, DB-backed status, `asyncio.wait_for` timeout, startup reconciliation |
| Job infrastructure | None (no Redis/Celery/Kubernetes) |
| Local orchestration | Docker Compose (app + Postgres + full Grafana observability stack) |
| Container base | Multi-stage Dockerfiles (backend via `uv`, frontend via Node build) |
| Observability (local) | OpenTelemetry (FastAPI + React) → OTLP; Prometheus + Loki + Tempo + Grafana, self-hosted in Compose |
| Observability (hosted) | Optional Grafana Cloud Free for hosted API telemetry; not required for MVP |
| CI/CD | GitHub Actions (required tests, Ruff checks, and API contract checks; Docker image builds deferred to #20) |
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

### 2.4 Authentication: Clerk Hobby (chosen over Auth0, Supabase Auth, FastAPI Users, Django auth)
- **Decision:** Clerk Hobby (free tier), verified as JWTs in FastAPI via its JWKS endpoint.
- **Justification:**
  - **Development friction:** Clerk ships a first-class React SDK and straightforward JWT verification in Python (JWKS), so sign-in/out/session protection are mostly configuration, not code. This directly satisfies "prefer a maintained provider over custom auth logic."
  - **Secure ownership enforcement:** Clerk provides a stable, opaque user ID (`sub`) used as the owner key on every profile/run record; a backend dependency resolves the current user from the verified JWT and injects it into route handlers. No passwords, sessions, or tokens are stored by us.
  - **Cost:** Hobby tier is $0 with no credit card required: up to 50,000 MRU (monthly retained users) per application, unlimited applications, 3 dashboard seats, 5 user impersonations/month, prebuilt UI for sign-up/sign-in/profile, custom domain, fixed 7-day session, 1-day application logs. Pro features (MFA, satellite domains, custom session lifetime, SMS auth) require payment — the MVP does not require them; if MFA becomes required at $0, fall back to Supabase Auth or Firebase Auth.
  - **Local + hosted parity:** The same Clerk instance (or a separate dev instance) works in both modes, so there is one code path. The default-disabled offline bypass (`LOCAL_AUTH_BYPASS=true`) is accepted only with `APP_ENV=development`, `APP_MODE=local`, and a loopback-only effective bind host; `APP_ENV` defaults to `production`, and all invalid combinations fail startup.
  - **Why not the others:** Auth0 is mature but heavier to configure and pricier at scale; Supabase Auth couples identity to a Supabase project/Postgres and tempts RLS-based access control (the plan requires server-side enforcement in app code, not DB policies); FastAPI Users / Django auth would mean owning password flows, recovery, and session security — exactly what the plan says to avoid. Django auth would also force a Django backend, losing the FastAPI/React/OTel alignment.
- **Trade-off accepted:** External SaaS dependency for identity and small vendor lock-in on user IDs (mitigated by storing only the opaque `sub`, which is portable). Free tier limits (50k MRU) are ample for an MVP/demo; exceeding them requires a paid plan.

### 2.5 Benchmark execution and recovery: in-process, single-flight, no queue
- **Decision:** One benchmark at a time, launched with `asyncio.create_subprocess_exec` inside a FastAPI background task, status persisted to Postgres, reconciled on startup. Available in local mode only.
- **Rationale:** The plan forbids distributed queues/Kubernetes "without a demonstrated need," and MVP needs only one run at a time. An in-process approach is testable (inject a fake runner), records timeouts (`asyncio.wait_for`), failures (exit codes + captured stderr, sanitised), and interrupted runs (startup reconciliation marks stale `running` rows `interrupted`). No Redis/Celery/worker fleet to operate.
- **Trade-off accepted:** Runs die with the process; recovery is "mark interrupted + user retries," which matches the plan. Horizontal scaling of the runner is out of scope.

### 2.6 Observability: OpenTelemetry + Prometheus + Loki + Tempo + Grafana (local)
- **Decision:** Reuse the exact stack from the Order Tracker project for local development.
- **Rationale:** Already proven; satisfies "correlated metrics, structured logs, traces in a dashboard" and "at least one actionable alert." Local dev runs the full stack in Compose. For the hosted demo, telemetry is optional: Grafana Cloud Free (no credit card, $0 forever, 14-day retention) can receive hosted API telemetry if desired, but is not required for MVP. No Sentry is added unless a concrete need justifies the extra service.

### 2.7 Hosting: GitHub Pages (frontend) + Render Free (API) + Neon Free (database)
- **Decision:** Public React frontend on GitHub Pages; FastAPI on Render Free; PostgreSQL on Neon Free.
- **Rationale:**
  - **GitHub Pages** is $0 for a public repository, fits a portfolio/educational project, and serves the static Vite build. It cannot run the backend, database, benchmark, or runner — those live elsewhere.
  - **Render Free** web service hosts the FastAPI app at $0 (spin-down after 15 min idle, cold start, 512 MB RAM, ephemeral filesystem, no persistent disks/SSH/one-off jobs). Acceptable for a demo; cold starts are a known UX limitation.
  - **Neon Free** provides persistent Postgres at $0 (100 CU-hours/project/month, 1 GB storage/project, 20 GB account-wide, scale to zero after 5 min, 6 h restore history). Unlike Render's free Postgres (30-day expiry), Neon does not expire data, so it is the preferred hosted database.
- **Trade-off accepted:** Free tiers impose cold starts, storage/compute caps, and no backups beyond Neon's short restore window. The hosted demo is not production-grade; documented limits and fallbacks apply (see §6).

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

## 4. GitHub Pages: eligibility and usage restrictions (verified against official docs)

Source: GitHub Docs, "GitHub Pages limits" (https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits).

- **Eligibility:** GitHub Pages is available in public repositories with GitHub Free, and in public/private repositories with GitHub Pro/Team/Enterprise. The repository will be public for the educational demonstration, so Pages is available at $0.
- **Static only:** Pages serves static files. It cannot run the FastAPI backend, database, private benchmark, or background runner. These are hosted separately.
- **Usage limits:** recommended 1 GB source repository; published site no larger than 1 GB; deployments time out after 10 minutes; soft bandwidth limit 100 GB/month; soft limit 10 builds/hour (waived when building/publishing with a custom GitHub Actions workflow); rate limits may apply.
- **Usage restrictions:** Pages is not intended/allowed as free web hosting for an online business, e-commerce, or commercial SaaS; not for sensitive transactions (passwords, credit cards). Subject to GitHub Terms of Service. One user or organization site per account.
- **Educational exercise note:** using Pages for a learning exercise is permitted; code must be written by us and the site must not collect user data beyond the app's own auth flow (the hosted demo uses synthetic data and Clerk auth; no payment data).

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

## 6. Free-tier cost strategy ($0 target)

All hosted dependencies below are selected for $0 recurring cost. No paid service is chosen on the basis of a free trial. $0 is not guaranteed indefinitely; limits and provider terms can change. Assumptions and fallbacks are listed.

| Provider | Role | Free terms (verify current docs) | Key limits / risks | Fallback |
|---|---|---|---|---|
| GitHub Pages | Static frontend | Free for public repos | Static only; 1 GB published; 100 GB/mo bandwidth soft; 10 builds/hr (waived with Actions); not for commercial SaaS/sensitive txns | Render Static Sites (free) or Cloudflare Pages |
| GitHub Actions | CI/CD + Pages deploy | Unlimited minutes for public repos; 2,000 min/mo for private repos | If repo becomes private, minutes are capped | Reduce matrix; self-hosted runner (later) |
| Render Free (web service) | FastAPI API | $0 web service | Spins down after 15 min idle (cold start); 512 MB RAM; single instance; ephemeral filesystem; no persistent disks, SSH, one-off jobs, or inbound private network; monthly bandwidth/pipeline-minute caps; robots.txt auto-disallow when idle; restarts at any time | Fly.io (free allowance, card required), Koyeb (free tier), PythonAnywhere (free, limited) |
| Render Free (Postgres) | Not used | $0 but expires 30 days after creation, then 14-day grace, then deleted; 1 GB; no backups | Unsuitable for persistent data | Neon Free (preferred) |
| Neon Free | PostgreSQL (hosted) | $0/month; 100 projects; 10 branches/project; 100 CU-hours/project/month; up to 2 CU autoscaling; scale to zero after 5 min; 1 GB storage/project (20 GB account-wide); 5 GB public transfer/project/month; 6 h instant restore (capped 1 GB change history); 1 manual snapshot; no overage billing | Compute suspends when CU-hours exhausted; writes fail above 1 GB storage; no automated backups; community support | Supabase Free (500 MB, pauses after 1 week inactivity), Fly Postgres, self-hosted Postgres in a container |
| Clerk Hobby | Authentication | $0, no credit card; up to 50,000 MRU/app; unlimited apps; 3 dashboard seats; 5 impersonations/month; prebuilt UI; custom domain; fixed 7-day session; 1-day logs | MFA, satellite domains, custom session lifetime, SMS auth require Pro; MRU (not raw MAU) billing | Supabase Auth (100k MAU) or Firebase Auth if free MFA/SSO needed |
| Grafana Cloud Free | Optional hosted telemetry | $0 forever, no credit card; 14-day retention; all services with usage limits; community support; AI assistant allotment | Exact series/GB allowances must be confirmed in current docs; not required for MVP | Self-hosted Grafana stack in Compose (already local); skip hosted telemetry |

**Additional free-tier considerations:**
- **Sleep/cold start:** Render Free web services spin down after 15 min idle; first request after idle incurs a cold start. API calls from the GitHub Pages frontend will be slow on first hit; acceptable for a demo. Keep health checks lightweight.
- **Database persistence/backups:** Neon Free keeps data persistent (no expiry) with 6 h restore history and 1 manual snapshot; no automated backups. For a demo this is acceptable; document a manual export/backup procedure. Render Free Postgres is explicitly unsuitable (30-day expiry).
- **Filesystem ephemerality:** Render Free has no persistent disk; the backend must not rely on local files. This aligns with the plan: uploaded raw payloads are discarded after processing; only normalised records persist in Postgres.
- **Authentication quotas:** Clerk Hobby allows 50k MRU; sufficient for MVP/demo. MFA is not available free — if required, switch provider (see fallback).
- **CI minutes:** public repo gives unlimited Actions minutes. If the repo is ever made private, budget 2,000 min/month or reduce the matrix.
- **Payment card / billable risk:** Neon, Clerk, and Grafana Cloud Free require no credit card. Render's free tier terms/signup requirements must be verified at signup; if a card or billable upgrade is required, use the listed fallback. No provider is selected on the basis of a time-limited free trial.

## 7. Deployment and delivery workflow (documented, not implemented)

1. A pull request runs backend, frontend, and appropriate integration tests (GitHub Actions).
2. A successful build produces the static frontend artifact.
3. Merging to `main` deploys the frontend to GitHub Pages (GitHub Actions).
4. The backend is deployed separately to the selected free host (Render Free).
5. The hosted deployment receives a smoke test.
6. Deployment and rollback approach is documented and appropriate to the free tiers (Render supports rollback to previous deploys; Pages rolls back by redeploying a prior commit).

Distinguish: deploying the static frontend to GitHub Pages does **not** deploy the backend. The API is a separate service with its own deploy pipeline and environment variables.

## 8. Alternatives rejected (summary)

- **Django + server-rendered templates (Chorely pattern):** rejected because the plan calls for a React dashboard with charts and a maintained external auth provider; Django would discard the React/Vite preference and complicate the OTel/Prometheus observability alignment.
- **Next.js full-stack (Option 2):** rejected because serverless hosting conflicts with long-running benchmark subprocesses; would force containerised deploy anyway, losing Next's main advantage while keeping one less-familiar runtime boundary for Python benchmark integration.
- **.NET (Option 3):** rejected despite strong background-service primitives; lower familiarity and higher toolchain weight for an MVP, with no material benefit over FastAPI for this scope.
- **Go (Option 4):** rejected; weaker ecosystem for validation/charts and more manual auth wiring, for no meaningful MVP benefit.
- **Auth0 / Supabase Auth / FastAPI Users:** rejected in favour of Clerk (see §2.4).
- **Redis/Celery/Kubernetes:** rejected per plan non-goals; in-process single-flight runner suffices.
- **Fly.io (Option 1 hosting):** superseded by the GitHub Pages + Render Free + Neon Free decision for $0 recurring cost; Fly.io remains a documented fallback if Render/Neon terms change.
- **Render Free Postgres:** rejected for persistent data (30-day expiry, no backups); Neon Free preferred.
- **Sentry:** not added by default; Grafana/OpenTelemetry covers observability locally and Grafana Cloud Free optionally; add only if a concrete need arises.

## 9. Consequences

- The project is a Python (FastAPI) + TypeScript (React) monorepo with Postgres, Clerk, and Docker Compose, matching the owner's strongest existing skill set.
- The public frontend is a static Vite build on GitHub Pages; the API and database are separate free-tier services. Deploying the frontend does not deploy the backend.
- Local and hosted modes share one codebase and one auth mechanism; mode is an env switch, not a fork.
- Benchmark execution is intentionally simple and in-process, and disabled in hosted mode.
- Observability and CI/CD reuse proven patterns, reducing operational risk.
- The main remaining risk is the private benchmark interface, which gates runner and importer implementation (see §5). Free-tier limits (cold starts, storage caps, no automated backups) are a secondary risk for the hosted demo.

## 10. Open questions (to resolve during architecture planning)

1. Exact private benchmark command/API and result schema (§5).
2. Whether Render signup requires a payment method; if so, switch API host to the documented fallback.
3. Whether Clerk's free tier limits or terms require a fallback provider (Supabase Auth is the designated fallback if needed).
4. Whether hosted DB should be Neon Free or an alternative (Supabase Free) for cost/simplicity.
5. Final repository name and GitHub Pages base path (drives Vite `base`).
6. Whether frontend TS types are generated in CI via `openapi-typescript` or hand-maintained.
7. ~~Naming/convention for the local auth bypass and how it is guarded in production builds.~~ Resolved by issue #14: `LOCAL_AUTH_BYPASS=false` by default; enabling it requires `APP_ENV=development`, `APP_MODE=local`, and loopback bind.
8. Whether the anonymous demo dataset is seeded at deploy time or shipped as a fixture.
9. Whether hosted telemetry via Grafana Cloud Free is worth the added configuration.