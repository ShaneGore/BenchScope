# Frontend Implementation Handoff

This handoff translates the product plan, technology stack, and architecture into an
implementable frontend contract. It is written for the React/Vite/TypeScript
implementation in issue #4 and the review in issue #5. It references the
authoritative documents rather than copying them wholesale.

Authoritative sources: `_docs/plan.md`, `_docs/tech-stack.md`,
`_docs/architecture/README.md`, `_docs/architecture/boundaries.md`,
`_docs/architecture/deployment.md`, `_docs/architecture/frontend/README.md`,
`_docs/architecture/frontend/routing.md`, `_docs/architecture/backend/README.md`,
`_docs/architecture/backend/api.md`, `_docs/architecture/backend/data-model.md`,
`_docs/architecture/backend/runner.md`, and `_docs/benchmark-interface.md`.

## 1. Purpose and scope

The frontend is a static single-page application (SPA) that lets developers
record, compare, and understand local model benchmark runs. It has two
operating contexts: local/private use, where benchmark launching is available,
and hosted use, where users import, manage, and compare their own results. An
anonymous read-only demo uses synthetic data.

This document does **not**:

- Build or implement the frontend (issue #4).
- Resolve the private benchmark result schema beyond the sanitised facts in
  `_docs/benchmark-interface.md`.
- Change backend API design (issue #6).
- Present any unapproved UI decision as final product behaviour.

## 2. Product purpose and target users

- Product: Local AI Benchmark Observatory.
- Purpose: turn scattered benchmark runs into a persistent, comparable history,
  including failed and interrupted attempts.
- Target users: developers and data scientists running different local language
  models and comparing coding performance, speed, and hardware requirements.
- A user may vary model versions, quantisations, inference settings, and
  hardware configurations.
- MVP excludes teams, shared private workspaces, public submissions, public
  leaderboards, hosted benchmark execution, model downloads, and model-server
  lifecycle management.

## 3. Operating contexts

| Context | Auth | Benchmark launch | Profiles with endpoints | Data | Notes |
|---|---|---|---|---|---|
| Local/private | Optional dev bypass | Yes | Yes | Local Postgres/SQLite | Full workflow |
| Hosted | Clerk required for personal data | No | Metadata only | Neon Free | Import/compare/profile management |
| Demo | None | No | No | Read-only synthetic dataset | Anonymous visitor |

Mode is an environment switch (`VITE_APP_MODE=local|hosted`), not a fork. The
backend is authoritative: hiding UI in hosted mode is not access control, and
backend runner endpoints return 404 in hosted mode.

## 4. Core workflows and frontend behaviour

### Workflow A - Import an existing result

1. User selects a benchmark result file in the supported JSON format.
2. Frontend sends the file to `POST /api/v1/runs/import`.
3. Backend validates and normalises; frontend shows validation errors clearly.
4. On success, frontend confirms import and displays available metrics.
5. User can find the run in history and compare it.

Frontend rules:
- Invalid import must not create a partial run or change existing records; the
  backend enforces this, but the UI must not optimistically add a run.
- Re-importing the same result returns `409` when a stable source ID or
  fingerprint is available; UI shows a duplicate message and links to the
  existing run if the response identifies it.
- Missing metrics render "unavailable", never `0`.

### Workflow B - Launch a benchmark (local mode only)

1. User selects a configured model profile and benchmark configuration.
2. User starts the run; frontend calls `POST /api/v1/benchmark/runs`.
3. Backend creates a unique run record with status `running`; frontend shows
   running state without blocking the UI.
4. Frontend polls `GET /api/v1/benchmark/runs/{id}` for status/events.
5. On completion/failure, frontend shows result or sanitised diagnostic.

Frontend rules:
- Only one benchmark runs at a time; a `409` from start means a run is already
  active and the UI must show that state.
- Failed/interrupted attempts remain visible and distinct from completed runs.

### Workflow C - Investigate and recover from a failure

- Failed, interrupted, and cancelled runs are first-class history entries.
- Previously completed results remain available and unchanged.
- A new attempt or imported corrected result is recorded separately.
- The UI never presents a failed/interrupted run as a successful result.

### Workflow D - Compare results

- User filters history by model, status, and date.
- User selects completed runs for comparison.
- UI uses `GET /api/v1/runs/compare?ids=...` and renders only metrics available
  for those runs.
- Missing metrics are not coerced to zero and no unsupported statistical
  significance is implied.

### Workflow E - Personal hosted workspace

- Sign-in via Clerk; unauthenticated visitors can explore `/demo`.
- Signed-in users import supported JSON and maintain private history.
- Users can view, filter, compare, and delete their own records.
- Backend verifies ownership; frontend must not assume client state is
  authoritative.
- Hosted workspace never launches benchmarks.

## 5. Navigation and routes

Routing follows `_docs/architecture/frontend/routing.md`: hash router, base path
from `VITE_BASE_PATH`, default `/` in dev and `/<repo-name>/` in Pages builds.

| Route | Purpose | Auth (hosted) | Local/hosted notes |
|---|---|---|---|
| `/` | Dashboard | Required (except local may allow) | Summary and recent runs |
| `/runs` | History + filters | Required | Filterable list |
| `/runs/:id` | Run detail | Required | Includes events for launched runs |
| `/compare` | Comparison chart | Required | Completed runs only |
| `/profiles` | Model profiles | Required | Endpoint fields local only |
| `/import` | Import result | Required | File upload |
| `/benchmark` | Launch benchmark | N/A hidden in hosted | Local mode only |
| `/demo` | Anonymous synthetic dataset | None | Read-only |
| `/sign-in`, `/sign-up` | Clerk auth | None | Hosted primarily |

Hosted anonymous visitors land on `/demo` by default. Protected routes redirect
unauthenticated users to sign-in, except `/demo`.

## 6. Screens

Each screen lists purpose, primary actions, data, and state handling. States not
relevant to a screen are marked `N/A` rather than omitted.

### 6.1 Dashboard (`/`)

- Purpose: high-level overview of completed/failed runs and recent activity.
- Primary actions: navigate to history, import, compare, launch (local), demo.
- Data: counts of completed and failed runs, most recent run and status, model
  and configuration per run, quality score, TTFT, prompt/output tokens,
  prompt-processing/generation throughput, total duration.
- Loading: skeleton/placeholder for counts and recent run; disable actions that
  require loaded data.
- Empty: show zero-state guidance and primary calls to action (import or launch
  in local mode; import in hosted mode).
- Validation: N/A (no form input on this screen).
- Running: show active run indicator and link to its detail when a benchmark is
  running; this is a status display, not a page-level running state.
- Completed: normal dashboard rendering.
- Failed: show failed-run count and link to failed history filter; do not merge
  failed runs into success summaries.
- Interrupted: show interrupted-run count and link; treat as non-success.

### 6.2 Run history (`/runs`)

- Purpose: browse, filter, and select runs.
- Primary actions: filter by model/status/date, open detail, delete own run,
  compare selected completed runs.
- Data: paginated list (cursor-based, default limit 50), status, model/profile,
  timestamps, available metrics.
- Loading: list skeleton and disabled filters until first page loads.
- Empty: explain no runs match filters; offer clear-filter and import actions.
- Validation: validate filter inputs (date range, selected status) before
  requesting; show field-level errors.
- Running: rows with `running` status are visually distinct and may poll for
  updates.
- Completed: normal rows with metrics where available.
- Failed: visually distinct; show sanitised category/message summary.
- Interrupted: visually distinct; show interruption diagnostic.

### 6.3 Run detail (`/runs/:id`)

- Purpose: inspect one run, its metrics, diagnostics, and retry lineage.
- Primary actions: delete run; retry (local mode only); navigate to compare.
- Data: full run record, profile snapshot, events timeline for launched runs,
  metrics, error category/message, artifact reference (opaque text only).
- Loading: detail skeleton; avoid showing partial metric values.
- Empty: N/A (a missing run returns 404, handled as not found).
- Validation: N/A for read view; retry action validates local-mode availability.
- Running: show running status, elapsed time, and event timeline updates.
- Completed: show available metrics and comparison action.
- Failed: show sanitised diagnostic and retry/import recovery actions.
- Interrupted: show interruption diagnostic and recovery actions.

### 6.4 Compare (`/compare`)

- Purpose: chart completed runs side by side.
- Primary actions: select run IDs, choose metric, view chart.
- Data: `GET /api/v1/runs/compare?ids=...`, completed runs only, metric series.
- Loading: chart skeleton while request resolves.
- Empty: prompt to select at least two completed runs; no chart rendered.
- Validation: reject non-completed or unowned IDs in the selection flow; backend
  filters unowned IDs.
- Running: N/A (comparison is for completed runs only).
- Completed: render chart with null-aware metric handling.
- Failed: N/A as comparison inputs.
- Interrupted: N/A as comparison inputs.

### 6.5 Model profiles (`/profiles`)

- Purpose: manage named model/configuration profiles.
- Primary actions: create, edit, delete profiles.
- Data: profile list and detail; endpoint/credential fields only in local mode.
- Loading: list/form skeleton.
- Empty: explain no profiles and prompt creation.
- Validation: required fields (`name`, `model_name`), field-level errors from
  422 responses.
- Running: N/A.
- Completed: N/A.
- Failed: N/A.
- Interrupted: N/A.

Hosted mode: endpoint URL and credential fields are rejected or stripped by the
backend; the UI hides them but does not rely on hiding for security.

### 6.6 Import result (`/import`)

- Purpose: upload and validate a supported result JSON file.
- Primary actions: select file, submit, view result or errors.
- Data: upload response with created run or validation errors; duplicate 409.
- Loading: upload progress/disabled submit state.
- Empty: no file selected.
- Validation: client-side basic file checks plus backend validation; show all
  backend field errors.
- Running: N/A.
- Completed: show imported run summary and link to detail/history.
- Failed: show validation/import failure without creating a run.
- Interrupted: N/A.

### 6.7 Launch benchmark (`/benchmark`, local mode only)

- Purpose: start a benchmark run against a selected profile/config.
- Primary actions: select profile and config, start, cancel, view status.
- Data: `POST /api/v1/benchmark/runs`, `GET /api/v1/benchmark/runs/{id}`,
  `POST /api/v1/benchmark/runs/{id}/cancel`.
- Loading: starting state and disabled submit while request resolves.
- Empty: no profiles available; prompt to create one.
- Validation: require profile and config selection; show backend errors.
- Running: poll status/events; show elapsed time and cancellation action.
- Completed: show result summary and link to detail.
- Failed: show sanitised diagnostic and retry action.
- Interrupted: show interruption diagnostic after restart/reconciliation.

In hosted mode this route is not registered (backend 404) and the UI hides it.

### 6.8 Demo (`/demo`)

- Purpose: anonymous read-only exploration of synthetic data.
- Primary actions: browse synthetic runs, open detail, compare.
- Data: `GET /api/v1/demo/runs`, `GET /api/v1/demo/runs/{id}`.
- Loading: skeleton for synthetic list/detail.
- Empty: N/A (synthetic dataset is seeded).
- Validation: N/A.
- Running: N/A.
- Completed: N/A (synthetic runs have statuses, but no live running state).
- Failed: synthetic failed runs displayed as data only.
- Interrupted: synthetic interrupted runs displayed as data only.

### 6.9 Sign-in / sign-up (Clerk)

- Purpose: authenticate hosted users.
- Primary actions: sign in, sign up, sign out.
- Data: Clerk user/session state.
- Loading: Clerk loading state.
- Empty: N/A.
- Validation: Clerk-managed validation/errors.
- Running: N/A.
- Completed: redirect to requested protected route or dashboard.
- Failed: show Clerk error state.
- Interrupted: N/A.

## 7. Layout and information hierarchy

- Top-level navigation exposes Dashboard, History, Compare, Profiles, Import,
  and, in local mode, Benchmark; Demo is available anonymously.
- Primary content area shows the selected screen; secondary panels show filters,
  selected comparison items, or run events.
- Metric values are displayed with labels and units where defined; missing
  values show "unavailable".
- Failed and interrupted runs are visually separated from completed runs in all
  summaries.
- Destructive actions (delete) require confirmation.

Specific spacing, colour palette, and component library choices are not yet
approved (see unresolved items).

## 8. Visual consistency

- Use a single shared component set for buttons, forms, tables, cards, alerts,
  and status badges.
- Status badges use distinct visual treatment for `running`, `completed`,
  `failed`, `interrupted`, and `cancelled`.
- Charts must handle null metrics without rendering zero.
- Error states use sanitised messages only; no raw benchmark output, prompts, or
  code.
- The final visual design system is not specified in the source documents and
  must be approved before implementation (see unresolved items).

## 9. Interactions and feedback

- Server state via React Query; local UI state via hooks/context.
- Mutations invalidate affected queries on success.
- Optimistic updates only where safe; delete/import flows should refetch or
  invalidate rather than assume success.
- Attach Clerk token to requests; refresh handled by Clerk.
- Show loading, success, and error feedback for all mutations.
- Clear server-state cache on sign-out to prevent cross-account leakage.
- Cancel actions are explicit and reversible only before completion.

## 10. Responsive and accessibility expectations

- Responsive layout supports desktop and tablet widths at minimum; mobile
  support should not break core read/import/compare flows.
- Keyboard navigation for all interactive controls and filters.
- Form fields have labels and accessible error text.
- Status and metric changes are announced appropriately (ARIA live regions
  where useful).
- Colour is not the only indicator for run status.
- Charts provide text/table alternatives or tooltips for null values.
- Focus management on route changes and modal dialogs.

Exact breakpoints and WCAG target level are not specified in the source docs and
require product approval (see unresolved items).

## 11. Local/hosted/demo behaviour matrix

| Capability | Local | Hosted | Demo |
|---|---|---|---|
| View dashboard/history/detail | Yes | Own data | Synthetic |
| Import result | Yes | Yes | No |
| Create/edit/delete profiles | Yes | Yes (metadata only) | No |
| Endpoint/credential fields | Yes | Rejected/stripped | No |
| Launch benchmark | Yes | No | No |
| Cancel run | Yes | N/A | No |
| Compare | Yes | Own completed runs | Synthetic completed runs |
| Sign in/out | Optional bypass | Required for personal data | None |

## 12. Frontend service operations

### 12.1 Client configuration

- Base URL from `VITE_API_URL` (env, not hard-coded).
- Base path from `VITE_BASE_PATH`.
- Mode from `VITE_APP_MODE` (`local` or `hosted`) for UI gating only.
- Typed client generated from FastAPI OpenAPI via `openapi-typescript`; types
  are regenerated in CI or dev.
- All paths prefixed `/api/v1`.

### 12.2 Auth

- Hosted: Clerk JWT in `Authorization: Bearer <token>`.
- Local dev: optional bypass resolves a fixed local user id; must not be
  enabled in production builds.
- Anonymous demo endpoints require no auth.
- Token refresh is handled by Clerk.

### 12.3 Endpoints and expected behaviour

| Method | Path | Auth | Purpose | Key responses |
|---|---|---|---|---|
| GET | `/health` | None | Liveness | 200 |
| GET | `/ready` | None | Readiness (DB reachable) | 200/503 |
| GET | `/profiles` | Required | List own profiles | 200, paginated |
| POST | `/profiles` | Required | Create profile | 201, 422 |
| GET | `/profiles/{id}` | Required | Get own profile | 200, 404 |
| PATCH | `/profiles/{id}` | Required | Update own profile | 200, 404, 422 |
| DELETE | `/profiles/{id}` | Required | Delete own profile | 204, 404 |
| GET | `/runs` | Required | List/filter own runs | 200, paginated; filters `status`, `model`, `from`, `to` |
| GET | `/runs/{id}` | Required | Get own run | 200, 404 |
| DELETE | `/runs/{id}` | Required | Delete own run | 204, 404 |
| POST | `/runs/import` | Required | Import result JSON | 201 created, 409 duplicate, 422 validation |
| POST | `/runs/{id}/retry` | Required (local only) | Create linked attempt | 201, 403/404 hosted |
| POST | `/benchmark/runs` | Required (local only) | Start run | 201, 409 active run, 403/404 hosted |
| GET | `/benchmark/runs/{id}` | Required (local only) | Status/events | 200, 404 |
| POST | `/benchmark/runs/{id}/cancel` | Required (local only) | Cancel run | 202/200, 404 |
| GET | `/demo/runs` | None | Synthetic runs | 200 |
| GET | `/demo/runs/{id}` | None | Synthetic run | 200, 404 |
| GET | `/runs/compare?ids=...` | Required | Compare completed runs | 200, 404/422 |

Pagination uses `?limit=&cursor=` (default limit 50). Errors use
`{ "detail": string | {field: msg} }`. Ownership mismatches return 404, not 403,
 to avoid enumeration. Unowned IDs in batch compare are dropped or rejected;
 implementation must document the chosen behaviour.

### 12.4 Nullable metrics

All metric fields are nullable. Missing is distinct from zero. The frontend
must render "unavailable" and must not coerce null to 0 in charts, sums,
averages, or comparisons. Affected fields include:

- `quality_score`
- `pass_rate`
- `ttft_ms`
- `prompt_tokens`
- `output_tokens`
- `prompt_throughput_tps`
- `generation_throughput_tps`
- `elapsed_ms`
- `hardware_snapshot`
- `error_category`, `error_message_sanitised`, `process_exit_code`

### 12.5 Hosted mode API restrictions

- Benchmark routes are not registered in hosted mode (404).
- Profile endpoint/credential fields are validated or stripped server-side.
- Personal endpoints require a verified Clerk JWT; `owner_id` comes from JWT
  `sub`, never request body/path.

## 13. Synthetic data and mock-service expectations

- CI and frontend tests run without the private benchmark, GPU, or model
  weights.
- Frontend tests use synthetic fixtures and a mock API service.
- Mock service must reproduce the API contract, including nullable metrics,
  404 ownership behaviour, 409 duplicates/active runs, and 422 validation
  errors.
- Demo data uses a sentinel owner (`demo`) and is read-only.
- No confidential benchmark prompts, reference solutions, tests, generated code,
  or raw artifacts may be used as fixtures.

## 14. Privacy constraints

- Private benchmark binary, prompts, reference answers, hidden tests, generated
  code, raw artifacts, model endpoints, and credentials stay local (Z3) and are
  never committed, served, or logged.
- Only sanitised, normalised result records cross into the application.
- Logs must not contain prompts, generated code, secrets, credentials, or
  complete benchmark output.
- Hosted import processing extracts only allowlisted metrics/metadata, discards
  the uploaded raw payload after processing, and never stores prompts, reference
  answers, generated code, secrets, or private raw artifacts.
- Upload size is capped and all input validated before persistence.
- The frontend must not display or cache raw benchmark output.

## 15. Sign-in/out and cache behaviour

- Hosted personal data requires Clerk sign-in.
- Unauthenticated visitors use `/demo` only.
- On sign-out, clear React Query cache and any local UI state containing
  owner data to prevent cross-account leakage.
- Local dev may use a guarded auth bypass; it must be impossible to enable in
  production builds.
- Anonymous demo has no write path and no owner context.

## 16. Hosted mode restrictions

- No benchmark launching, cancellation, or retry.
- No localhost model endpoint access.
- No private artifact serving.
- Profile endpoint fields are metadata-only.
- Hosted API binds publicly over HTTPS; CORS restricted to Pages origin(s).
- Render free service may cold-start after idle; UI should tolerate transient
  failures and allow retry.

## 17. Unresolved items requiring approval

The following are left open by the source documents and must not be guessed or
presented as approved behaviour:

1. Exact private benchmark command/API and result schema (`plan.md` section 11.1,
   `_docs/benchmark-interface.md`).
2. Exact supported result JSON fields and a sanitised sample fixture
   (`plan.md` section 11.2).
3. Model endpoint protocol details beyond the local OpenAI-compatible
   llama.cpp endpoint verified for the pilot runner; whether all profiles use
   that protocol is unverified (`plan.md` section 11.3).
4. Metric definitions for quality score, pass rate, TTFT, and throughput; which
   metrics the benchmark can reliably supply (`plan.md` section 11.4,
   `_docs/benchmark-interface.md`).
5. Authentication provider final terms/limits; Clerk Hobby preferred, Supabase
   Auth fallback (`tech-stack.md` section 10.3).
6. Hosting final terms and fallbacks (Render/Neon/Clerk) (`tech-stack.md`
   section 10.2-4).
7. Final repository name and GitHub Pages base path (`tech-stack.md` section 10.5).
8. Whether frontend TS types are generated in CI or maintained by hand
   (`tech-stack.md` section 10.6).
9. Naming/convention for local auth bypass and production guard
   (`tech-stack.md` section 10.7).
10. Whether anonymous demo data is seeded at deploy time or shipped as a fixture
    (`tech-stack.md` section 10.8).
11. Whether hosted telemetry via Grafana Cloud Free is used (`tech-stack.md`
    section 10.9).
12. Chart library choice; must handle null metrics (`frontend/README.md` section 1).
13. Final visual design system, colour palette, spacing, and component library.
14. Responsive breakpoints and WCAG target level.
15. Batch compare behaviour for unowned IDs (drop vs reject).
16. Rate-limit specifics for import and benchmark start.
17. Whether `DELETE /profiles/{id}` cascades to runs or runs retain a snapshot.
18. Whether retry creates a new run linked via `related_run_id` and how much
    profile state is snapshotted.
19. Exact run-event payload schema and polling interval for launched runs.
20. Whether local mode allows unauthenticated dashboard access.

No item above should be resolved in the handoff or implementation without
product approval.

## 18. Out of scope

- Building the frontend (issue #4) and reviewing it (issue #5).
- Resolving benchmark result schema (issue #2) or changing API design (issue #6).
- Team workspaces, organisation accounts, shared private results, roles beyond
  individual ownership, public leaderboard.
- Public benchmark-result submissions or hosted execution of the private
  benchmark.
- Model downloads or model-server lifecycle management.
- Multiple inference-framework or cloud-provider integrations.
- Distributed job queues, Kubernetes, or complex orchestration.
- Advanced analytics or statistical-significance claims unsupported by the
  benchmark.

## 19. Traceability

| Handoff section | Authoritative source |
|---|---|
| Product purpose/users/workflows | `_docs/plan.md` sections 1-5, 7 |
| Operating contexts/mode gating | `_docs/architecture/boundaries.md`, `_docs/architecture/frontend/README.md` |
| Routes | `_docs/architecture/frontend/routing.md` |
| Layout/state/API client | `_docs/architecture/frontend/README.md` |
| API operations/errors | `_docs/architecture/backend/api.md` |
| Data/nullability | `_docs/architecture/backend/data-model.md` |
| Runner lifecycle/safety | `_docs/architecture/backend/runner.md` |
| Deployment/hosted limits | `_docs/architecture/deployment.md`, `_docs/tech-stack.md` |
| Benchmark interface | `_docs/benchmark-interface.md` |
| Tech decisions | `_docs/tech-stack.md` |
