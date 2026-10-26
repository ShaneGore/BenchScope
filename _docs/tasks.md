# BenchScope - MVP Backlog (Proposed)

**Status:** Proposed for review. Planning only; no application code, dependencies, issues, or repository settings are created by this document.

**Sources:** `_docs/plan.md`, `_docs/tech-stack.md`, `_docs/architecture/`.

**Scope guardrails (must remain true throughout):** $0 recurring-cost target; individual ownership only; no team workspaces, public benchmark submissions, hosted benchmark execution, public remote execution, Kubernetes, distributed queues, model downloads or server lifecycle management, or confidential benchmark material in the public repository. Missing metrics remain null or 'unavailable', never zero.

## How to use this backlog

- Tasks are ordered by recommended implementation sequence.
- Each task should be implementable and verifiable in one coding-agent session.
- Acceptance criteria are intentionally observable and testable.
- Dependencies lists prerequisite tasks by number. 'None' means it can start immediately.
- A task is not complete until its acceptance criteria and relevant tests pass.

## Phase 0 - Foundation and feasibility

### Task 1 - Initialise empty project skeleton and baseline test

**Goal:** Establish the agreed repository structure and one passing automated test without implementing application features.

**Description:** Create top-level `frontend/` and `backend/` directories with minimal manifests, test directories, and shared ignore rules. Add one trivial automated test (for example, a backend pytest smoke test) that proves the test harness works. Do not add endpoints, UI features, database models, or benchmark logic.

**Acceptance criteria:**
- [ ] `frontend/` and `backend/` directories exist with documented test commands.
- [ ] At least one automated test passes locally with no external services.
- [ ] No feature code, API routes, UI workflows, or database schema are implemented.
- [ ] Repository remains free of secrets and confidential benchmark material.

**Dependencies:** None.

### Task 2 - Investigate private benchmark invocation and compatibility

**Goal:** Determine whether and how the private benchmark can be invoked safely before designing the runner.

**Description:** In a private environment outside the public repository, inspect the benchmark's supported command, API, adapter, runtime dependencies, model endpoint protocol, result schema, timeout/cancellation behaviour, exit codes, and OS/container compatibility. Record only sanitised findings in a new `_docs/benchmark-interface.md`. Explicitly decide whether the benchmark can run in a Linux container; do not assume it can. Keep confidential benchmark code, prompts, reference answers, hidden tests, generated code, and raw output outside version control.

**Acceptance criteria:**
- [ ] A sanitised benchmark interface document is committed.
- [ ] Supported invocation mechanism and required arguments/environment are documented.
- [ ] Result schema and metric definitions are documented, including nullable/missing fields.
- [ ] Container feasibility decision is recorded with rationale.
- [ ] No confidential benchmark material is committed; ignore rules are verified.

**Dependencies:** None (may run in parallel with Task 1).
## Phase 1 - Design handoff and frontend prototype

### Task 3 - Create frontend design handoff document

**Goal:** Produce a comprehensive, self-contained design handoff for a specialised frontend coding agent or generation tool.

**Description:** Create `_docs/frontend/handoff.md` from the product plan, technology stack, and architecture documents. It should stand alone when supplied to a frontend specialist without duplicating the entire architecture documentation. Cover product purpose, target users, and core workflows; navigation, routes, and screen-by-screen specifications; layout, information hierarchy, key components, and user interactions; loading, empty, validation, running, completed, failed, and interrupted states; nullable metrics and comparison rules; synthetic data requirements; expected frontend service operations and the mock requirement; visual consistency, responsive design, and accessibility; local versus hosted/demo behaviour; and privacy constraints. Flag missing information rather than inventing requirements.

**Acceptance criteria:**
- [ ] `_docs/frontend/handoff.md` exists and is self-contained enough for a specialised frontend implementation.
- [ ] It covers every required handoff section listed in the backlog.
- [ ] Each screen specifies purpose, primary actions, displayed data, states, validation, and empty/loading behaviour.
- [ ] Service operations are listed with request/response expectations and nullable metric handling.
- [ ] Local, hosted, and demo restrictions and privacy constraints are explicit.
- [ ] Unresolved or missing information is listed separately instead of being invented.
- [ ] No confidential benchmark material or unsupported backend assumptions are included.

**Dependencies:** Task 1.

### Task 4 - Implement React/Vite/TypeScript frontend from the approved handoff

**Goal:** Build the working frontend prototype using the approved handoff and synthetic data.

**Description:** Implement the routes, screens, components, and interactions specified in `_docs/frontend/handoff.md`. All data access must go through a central frontend service interface with a mock implementation that works without a backend. Add tests for service behaviour and important UI states. Presentation components must not make direct HTTP calls.

**Acceptance criteria:**
- [ ] `pnpm build` and `pnpm test` pass.
- [ ] The prototype implements the workflows and screens defined in the handoff.
- [ ] All backend calls are centralised in a service layer.
- [ ] A mock service implementation allows the prototype to run without a backend.
- [ ] Tests cover service behaviour and important UI states.
- [ ] No presentation component contains direct HTTP calls.
- [ ] Missing metrics render as unavailable, never zero.

**Dependencies:** Task 3.

### Task 5 - Review and refine the frontend prototype in the browser

**Goal:** Validate and refine the prototype before implementing the real backend.

**Description:** Exercise the prototype in a browser, record issues, and refine the interface. Update fixtures and tests to reflect changes. Resolve issues where practical or track them explicitly.

**Acceptance criteria:**
- [ ] A short review record is committed (for example, `_docs/frontend/review.md`) listing checked workflows, issues found, and changes made.
- [ ] All handoff workflows are demonstrable in the prototype.
- [ ] Issues are either resolved or explicitly tracked.
- [ ] Frontend tests pass after refinement.

**Dependencies:** Task 4.

### Task 6 - Derive the OpenAPI contract from the frontend service interface

**Goal:** Establish the API contract after the frontend has demonstrated what it needs.

**Description:** Derive `openapi.yaml` from the actual frontend service interface rather than from an assumed backend design. Generate TypeScript types and add contract tests. The contract must cover authentication, ownership, validation, errors, nullable metrics, and mode-gated benchmark endpoints.

**Acceptance criteria:**
- [ ] An OpenAPI contract file is committed.
- [ ] TypeScript types generated from the contract compile successfully.
- [ ] Contract tests pass for representative request and response payloads.
- [ ] The contract covers authentication, ownership, validation, errors, and nullable metrics.
- [ ] Mode-gated benchmark endpoints are represented accurately.

**Dependencies:** Task 5.

## Phase 2 - Backend core

### Task 7 - Create FastAPI skeleton and configuration

**Goal:** Implement the backend application shell without business logic.

**Description:** Create the FastAPI app factory, Pydantic settings, CORS configuration, health/readiness endpoints, error handling, and request correlation hooks. Add initial backend tests using FastAPI's test client.

**Acceptance criteria:**
- [ ] `GET /health` and `GET /ready` pass.
- [ ] Configuration is loaded from environment variables; invalid required configuration fails startup.
- [ ] CORS is restricted to configured origins.
- [ ] Backend tests pass without a database.

**Dependencies:** Tasks 1 and 6.

### Task 8 - Add Docker Compose for reproducible local development

**Goal:** Provide a repeatable local stack for backend and database.

**Description:** Add Docker Compose for PostgreSQL and the backend, with environment examples and documented startup commands. Include health checks. Keep the private benchmark on the host unless Task 2 explicitly proves container support; do not containerise the benchmark by default.

**Acceptance criteria:**
- [ ] `docker compose up` starts PostgreSQL and the backend.
- [ ] Health checks pass.
- [ ] Setup documentation allows a clean machine to start the stack.
- [ ] No confidential benchmark material or secrets are included in the Compose configuration.

**Dependencies:** Task 7.
### Task 9 - Replace temporary storage with PostgreSQL and Alembic migrations

**Goal:** Implement canonical persistence for profiles and runs.

**Description:** Add SQLAlchemy 2 models, Alembic baseline migration, request-scoped sessions, and integration tests against PostgreSQL. Store all metrics as nullable fields. Include owner fields even before authentication is enforced, using a local owner placeholder.

**Acceptance criteria:**
- [ ] Baseline migration applies cleanly to an empty PostgreSQL database.
- [ ] Integration tests pass against PostgreSQL (Docker Compose or CI service).
- [ ] No test relies on SQLite-specific behaviour.
- [ ] Metric fields are nullable and missing values remain distinct from zero.

**Dependencies:** Task 8.

### Task 10 - Implement model profile API

**Goal:** Provide CRUD operations for model profiles.

**Description:** Implement profile endpoints with validation, local owner scoping, and OpenAPI updates. In hosted mode, reject or strip local endpoint URLs and credentials.

**Acceptance criteria:**
- [ ] Create, read, update, and delete profile tests pass.
- [ ] Invalid input returns clear validation errors.
- [ ] Hosted-mode profile fields containing endpoints or credentials are rejected or stripped.
- [ ] OpenAPI matches the frontend contract for profiles.

**Dependencies:** Tasks 9 and 6.

### Task 11 - Implement result import and normalisation API

**Goal:** Deliver Workflow A on the backend.

**Description:** Implement the import endpoint with strict validation, normalisation, transactional persistence, duplicate detection by stable fingerprint/source ID, and clear errors. Discard raw uploaded payloads after processing. Store only allowlisted metrics and metadata.

**Acceptance criteria:**
- [ ] Valid import creates one run and returns its metrics.
- [ ] Invalid import returns an error and creates no partial records.
- [ ] Re-importing the same fingerprint does not create a duplicate.
- [ ] Missing metrics remain null, not zero.
- [ ] Upload size is limited and enforced.

**Dependencies:** Task 9.

### Task 12 - Implement run history, filtering, and comparison API

**Goal:** Deliver backend support for Workflows C and D.

**Description:** Implement list/filter endpoints by model, status, and date; detail and delete; and a comparison endpoint returning completed runs with metric series. Exclude non-completed runs from successful-performance summaries unless explicitly requested.

**Acceptance criteria:**
- [ ] Filtering by model, status, and date works and is tested.
- [ ] Comparison endpoint returns only owned, completed runs.
- [ ] Failed/interrupted runs are inspectable but excluded from success summaries.
- [ ] Missing metrics remain null in responses.

**Dependencies:** Task 11.
### Task 13 - Connect frontend to the real backend

**Goal:** Replace the mock service with an API-backed implementation.

**Description:** Implement `ApiBenchmarkService` using generated TypeScript types from FastAPI OpenAPI. Keep `MockBenchmarkService` available for tests and local development. Configure the API base URL through environment variables.

**Acceptance criteria:**
- [ ] Frontend works against the local backend for profiles, import, history, and comparison.
- [ ] Mock service remains usable for tests.
- [ ] End-to-end smoke tests pass against the local stack.
- [ ] No backend URL is hard-coded in frontend source.

**Dependencies:** Tasks 12 and 6.

## Phase 3 - Security and benchmark execution

### Task 14 - Add authentication and per-user ownership

**Goal:** Implement Clerk-based authentication and enforce ownership.

**Description:** Verify Clerk JWTs via JWKS in FastAPI; use `sub` as the owner key. Add sign-in/sign-out to the frontend. Filter every personal query by the authenticated owner. Add a guarded local development auth bypass. Implement IDOR tests.

**Acceptance criteria:**
- [ ] Authenticated users can manage their own profiles, imports, runs, and comparisons.
- [ ] Unauthenticated requests to personal endpoints return 401.
- [ ] Changing a record ID cannot access another user's data.
- [ ] Local auth bypass cannot be enabled in a production configuration.
- [ ] Frontend clears cached user data on sign-out.

**Dependencies:** Task 13.

### Task 15 - Implement controlled benchmark runner, failure handling, and recovery

**Goal:** Add local-only benchmark execution with safe failure handling.

**Description:** Implement the adapter seam using Task 2 findings. Run benchmarks in-process with single-flight execution, subprocess execution without a shell, configurable timeout, DB-backed status, startup reconciliation of interrupted runs, sanitised diagnostics, and retry lineage. Keep the runner disabled outside local mode.

**Acceptance criteria:**
- [ ] A successful run stores available metrics and appears in history.
- [ ] Failed, timed-out, cancelled, and interrupted runs are recorded with categories and do not appear as successes.
- [ ] A second concurrent run request returns 409.
- [ ] Restarting the application marks a previously running run as interrupted.
- [ ] No arbitrary command, path, or shell input is accepted from the browser.
- [ ] Tests use a fake adapter and do not require the private benchmark.

**Dependencies:** Tasks 2 and 14.

### Task 16 - Implement hosted mode and anonymous demo

**Goal:** Enforce hosted restrictions and provide read-only demo data.

**Description:** Add `APP_MODE=hosted` behaviour: disable benchmark endpoints, reject profile endpoint/credential fields, and expose a read-only synthetic demo dataset. Ensure hosted imports extract only allowlisted metrics and discard raw payloads.

**Acceptance criteria:**
- [ ] Benchmark endpoints are unavailable in hosted mode.
- [ ] Hosted profile fields containing endpoints or credentials are rejected.
- [ ] Anonymous visitors can browse the synthetic demo without an account.
- [ ] Demo data is read-only and cannot be modified through the API.
- [ ] Mode-gating tests pass.

**Dependencies:** Task 15.

### Task 17 - Finalise frontend mode gating and demo flows

**Goal:** Align the frontend with hosted restrictions.

**Description:** Hide benchmark launch UI in hosted mode, default anonymous visitors to the demo, and ensure cached user data is cleared on sign-out. Keep mock and API services selectable by environment.

**Acceptance criteria:**
- [ ] Hosted frontend cannot invoke benchmark execution.
- [ ] Anonymous demo flow passes end-to-end tests.
- [ ] Sign-out clears cached personal data.
- [ ] Hosted build passes lint, typecheck, and tests.

**Dependencies:** Tasks 16 and 13.
## Phase 4 - Observability, CI/CD, and deployment

### Task 18 - Add OpenTelemetry instrumentation and local observability stack

**Goal:** Provide correlated metrics, logs, and traces with dashboards and an alert.

**Description:** Instrument FastAPI and the React app with OpenTelemetry. Configure local Prometheus, Loki, Tempo, and Grafana in Docker Compose. Create a dashboard for the import/run journey and at least one actionable alert for a meaningful failure.

**Acceptance criteria:**
- [ ] A key user journey produces correlated traces, metrics, and logs.
- [ ] Trace IDs can be used to move between traces, logs, and metrics.
- [ ] At least one alert fires in a controlled test scenario.
- [ ] Observability services start via Docker Compose.

**Dependencies:** Tasks 8 and 12.

### Task 19 - Establish CI pipeline

**Goal:** Automate quality checks and tests.

**Description:** Add GitHub Actions for linting, type checking, backend tests against PostgreSQL, frontend tests, contract checks, and image builds. Ensure CI does not require the private benchmark, GPU, model weights, or paid services.

**Acceptance criteria:**
- [ ] CI passes on a clean repository.
- [ ] Backend integration tests run against PostgreSQL in CI.
- [ ] Frontend tests and contract checks run in CI.
- [ ] No CI step requires confidential benchmark material.

**Dependencies:** Tasks 17 and 18.

### Task 20 - Build container images and deployment workflows

**Goal:** Deploy the frontend to GitHub Pages and backend to the selected free host.

**Description:** Create backend and frontend Dockerfiles. Add workflows for GitHub Pages deployment and backend deployment using free-tier services. Configure environment variables, health checks, CORS origins, and Vite base path without hard-coding the final repository name in source.

**Acceptance criteria:**
- [ ] Container images build successfully in CI.
- [ ] Frontend deploys to GitHub Pages.
- [ ] Backend deploys and passes health checks.
- [ ] Rollback approach is documented.

**Dependencies:** Task 19.

### Task 21 - Verify hosted smoke tests and rollback

**Goal:** Prove the hosted demonstration and recovery path.

**Description:** Add post-deployment smoke tests for health, demo access, authentication, import, and comparison. Document and rehearse rollback for both frontend and backend.

**Acceptance criteria:**
- [ ] Smoke tests pass against the hosted deployment.
- [ ] Anonymous demo is reachable and read-only.
- [ ] Authenticated import/comparison works in hosted mode.
- [ ] Rollback steps are documented and verified.

**Dependencies:** Task 20.

### Task 22 - Complete end-to-end tests

**Goal:** Cover principal user journeys across the full stack.

**Description:** Add Playwright tests against the local stack for import, benchmark launch using a fake adapter, failure recovery, comparison, authentication, and hosted demo behaviour. Include IDOR checks where feasible.

**Acceptance criteria:**
- [ ] End-to-end suite passes in CI.
- [ ] Success, validation failure, benchmark failure, timeout, and interruption paths are covered.
- [ ] Hosted mode restrictions are covered.
- [ ] No test requires the private benchmark or GPU.

**Dependencies:** Tasks 17 and 15.
## Phase 5 - Incident response and release

### Task 23 - Bounded incident responder and fault/fix demonstration

**Goal:** Demonstrate alert-driven investigation and a bounded fix.

**Description:** Create a reproducible development-environment fault, trigger an actionable alert, investigate using correlated telemetry, apply a bounded fix, and record the outcome. Add runbook documentation for the responder.

**Acceptance criteria:**
- [ ] A fault scenario is documented and reproducible.
- [ ] An alert fires and includes enough context to investigate.
- [ ] A bounded fix is applied and verified by tests.
- [ ] A post-incident note is committed.

**Dependencies:** Tasks 22 and 18.

### Task 24 - Documentation and release verification

**Goal:** Finalise documentation and verify release readiness.

**Description:** Complete setup, architecture, deployment, rollback, and troubleshooting documentation. Run a privacy/security audit for secrets, confidential material, ownership checks, upload limits, and hosted-mode restrictions. Verify all MVP success criteria from the product plan.

**Acceptance criteria:**
- [ ] A new contributor can set up and run the project from documentation.
- [ ] Privacy/security audit checklist is completed and committed.
- [ ] All automated tests pass in CI.
- [ ] MVP success criteria are mapped to evidence or explicitly marked unresolved.

**Dependencies:** Task 23.

## Recommended implementation order

1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24.

Task 2 may run in parallel with Task 1. Tasks 18 and 11 can overlap only where Docker Compose is already available; otherwise keep the listed order.

## Unresolved decisions and potential contradictions to review

- The private benchmark interface, result schema, endpoint protocol, and container feasibility are unresolved until Task 2. The runner design must not be finalised before then.
- The initial OpenAPI contract in Task 6 is a reconciliation target; FastAPI's generated OpenAPI becomes authoritative in Tasks 7-14. Any drift must be reconciled before Task 13.
- The final GitHub repository name and Pages base path are unresolved; Task 20 must inject them through environment variables rather than hard-coding.
- Render signup/payment-method requirements and current free-tier terms for Render, Neon, Clerk, and GitHub are unresolved and must be verified before Task 20.
- Local auth bypass naming and production guards are unresolved and must be settled in Task 14.
- Docker Compose should keep the benchmark on the host by default because container feasibility is unproven; this slightly conflicts with a fully containerised local experience until Task 2 confirms support.
- The product plan requires local service binding to loopback by default; containerised deployments may bind 0.0.0.0 inside the container while publishing only to localhost on the host. This should be documented in Task 8.
- The backlog intentionally does not include team workspaces, public submissions, hosted benchmark execution, Kubernetes, distributed queues, or other MVP non-goals.

