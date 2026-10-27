# BenchScope release-readiness audit

## Result and audit boundary

**Release conclusion: BLOCKED — not READY.** This is an evidence audit, not a
release approval. The product source audited is commit
`228081d5095c843bd4e7f3c60cf0025d8e01636b` (`2026-10-27`, “docs: restore
controlled alert test instructions”), on Windows PowerShell with Docker
Desktop’s local `desktop-linux` context (Docker Engine 28.4.0). Audit work is
on `task-24-release-audit`; this report and the narrowly supported README
correction are documentation changes after the audited source revision.
At audit time, GitHub issue #24 was open, assigned to ShaneGore, and labeled
`status: in-progress`; its PM comment marks the documentation scope READY while
explicitly retaining the BLOCKED release conclusion.

The local application stack was built and started from a temporary detached
checkout of that source revision using only synthetic settings. Host port 5432
was occupied before setup; it was not inspected or changed. All required fixed
ports were free, so the stack used verified-free `POSTGRES_PORT=15441`.
The unique Compose project and temporary checkout were removed with
project-scoped cleanup; no existing Compose project, worktree, hosted service,
personal/production data, benchmark, provider account, or external receiver
was used.

Hosted behavior was **not deployed or observed**. No GitHub Actions run was
started for this unpushed branch, branch-protection/ruleset settings were not
verified, and no provider terms, account, payment method, or $0 recurring-cost
approval was checked. Issue closure and documentation are not proof of those
outcomes.

## Clean-checkout walkthrough and observed results

The temporary checkout was at `228081d`; `.env` contained only random
synthetic PostgreSQL credentials and local-mode settings, was ignored by Git,
and was removed. The runbook in `README.md` documents the same Compose layout.
The exact project-scoped commands and results were:

| Command or observation | Result |
|---|---|
| `docker context show` | `desktop-linux` |
| `docker context inspect $context --format '{{.Endpoints.docker.Host}}'` | Local Docker named pipe; accepted by the README local-context guard. |
| `docker info --format 'Docker daemon: {{.ServerVersion}}'` | `Docker daemon: 28.4.0` |
| Port preflight using `Get-NetTCPConnection` / `IPGlobalProperties.GetActiveTcpListeners()` | Fixed ports `8000, 4318, 9090, 3100, 3200, 3000`: free. `5432`: occupied, untouched. `15441`: free and selected. |
| `docker compose --env-file .env -p benchscope-task24-6af4b91623ce44fd9aad0e5300ebc921 up --build --wait --detach` | Exit 0. |
| `docker compose --env-file .env -p benchscope-task24-6af4b91623ce44fd9aad0e5300ebc921 ps` | API and PostgreSQL healthy; Grafana, Loki, Prometheus, and Tempo healthy; OTEL Collector running. All published endpoints were loopback-only. |
| `Invoke-RestMethod http://127.0.0.1:8000/health` | `{"status":"ok"}` |
| `Invoke-RestMethod http://127.0.0.1:8000/ready` | `{"status":"ready"}` |
| `docker compose --env-file .env -p benchscope-task24-6af4b91623ce44fd9aad0e5300ebc921 config --quiet` | Exit 0. |
| `docker compose --env-file .env -p benchscope-task24-6af4b91623ce44fd9aad0e5300ebc921 down --volumes --remove-orphans --rmi local` | Exit 0; removed only this project's containers, volumes, network, and API image. |

After cleanup, this project's container, volume, and network counts were each
zero; `.env` and the temporary checkout were absent; ports `8000, 4318, 9090,
3100, 3200, 3000, 15441` were free. The original 5432 listener was not
altered. This verifies a clean-checkout **local startup**, not all documented
tests or application journeys.

The clean-checkout test walkthrough is **not verified** in this audit. Attempt
to start its backend test setup with `uv sync --locked --group dev` was blocked
before execution by the command tool: “Permission denied and could not request
permission from user. Copilot needed the user's approval and no one could
answer.” Therefore `uv lock --check`, `uv run ruff check .`, `uv run ruff
format --check .`, `uv run pytest`, frontend dependency installation/tests,
build, API drift check, and Playwright were not run in that checkout. This
permission to execute the local test setup is the unavailable prerequisite;
the prior issue QA results below are historical evidence, not a rerun here.

## Plan §9 success-criteria evidence matrix

`VERIFIED` means the cited test or runtime evidence covers the stated behavior
within its tested scope. It does not imply a hosted deployment. Every other
status has an owner and follow-up.

| # | Status | Evidence paths; exact executed command or observed result | Reason, owner, and follow-up for non-verified criteria |
|---:|---|---|---|
| 1 | VERIFIED | `compose.yaml`, `README.md`; clean temporary checkout: `docker compose --env-file .env -p benchscope-task24-6af4b91623ce44fd9aad0e5300ebc921 up --build --wait --detach` (exit 0), `/health` → `{"status":"ok"}`, `/ready` → `{"status":"ready"}`. | — |
| 2 | NOT VERIFIED | `backend/tests/test_postgres_storage.py`, `backend/tests/test_result_import.py` verify PostgreSQL persistence/readback and migrations, but do not demonstrate an imported result surviving an application restart. | ShaneGore: add/run a synthetic import → application restart → history read check in a disposable local PostgreSQL project; record the result. |
| 3 | VERIFIED | `backend/app/imports.py`, `backend/tests/test_import_validation.py`, `backend/tests/test_result_import.py`; historical #19 QA ran `uv run pytest` against PostgreSQL: **99 passed**, including invalid-schema/no-write, transaction rollback, and size-boundary cases. | — |
| 4 | VERIFIED | `backend/app/imports.py`, `backend/tests/test_import_validation.py`, `backend/tests/test_result_import.py`; test cases cover stable source ID and canonical-payload fingerprints, same-owner `409`, different-owner scope, and unique-index behavior. Covered by the historical `uv run pytest` result above. | — |
| 5 | BLOCKED | `backend/app/runner.py`, `backend/tests/test_runner.py`, `_docs/benchmark-interface.md`; `test_start_is_unavailable_without_adapter_and_does_not_create_run` expects `503` when no adapter is configured. #25 is open; the production adapter is not configured. | #25: private benchmark maintainer/operator is **not identified** in repository evidence and must confirm the callable/result contract; ShaneGore must resolve cancellation semantics and authorize the follow-up integration. |
| 6 | VERIFIED | `backend/tests/test_runner.py`, `backend/tests/test_result_import.py`, `frontend/src/pages/RunDetailPage.tsx`; #18 QA recorded `pnpm test:journey` passing the synthetic import → history/detail flow. The observed local runtime in this audit returned healthy/ready, but no benchmark was launched. | — |
| 7 | VERIFIED | `backend/tests/test_import_validation.py`, `backend/tests/test_result_import.py`, `backend/tests/test_run_history.py`, `frontend/src/components/ui/MetricValue.tsx`, `frontend/src/components/ui/MetricValue.test.tsx`; #18 QA verified null metrics remain null. | — |
| 8 | VERIFIED | `backend/app/runner.py`, `backend/tests/test_runner.py`; fake-adapter tests exercise sanitized failure, timeout, and startup reconciliation to `interrupted`. Historical #22 QA reported `pytest -q`: **107 passed**. | — |
| 9 | VERIFIED | `backend/app/runner.py`, `backend/tests/test_runner.py::test_adapter_failure_is_sanitized_and_retry_creates_linked_attempt`; test asserts a distinct linked retry and retained original failure. Historical #22 `pytest -q`: **107 passed**. | — |
| 10 | NOT VERIFIED | `backend/tests/test_run_history.py` verifies filtering and comparison API semantics; `frontend/src/pages/ComparePage.tsx` implements comparison display. The audited test evidence does not establish a browser-observed meaningful chart with filtered completed runs. | ShaneGore: add/run a synthetic browser check covering filter selection, completed-run comparison, chart values, and null metrics; record exact output. |
| 11 | VERIFIED | `backend/tests/test_import_validation.py`, `backend/tests/test_result_import.py`, `backend/tests/test_runner.py`, `backend/tests/test_run_history.py`; `frontend/src/` journey and component tests. Historical #19: `uv run pytest` **99 passed**, `corepack pnpm test` **36 passed**. Historical #22: `pytest -q` **107 passed**, `pnpm test:journey` **7 passed**. | — |
| 12 | BLOCKED | `.github/workflows/ci.yml` defines backend, frontend, journey, and image-build jobs. Historical #19 QA ran the local equivalents (`uv lock --check`, Ruff checks, PostgreSQL `uv run pytest` **99 passed**, frontend `pnpm test` **36 passed**, build, and `pnpm check:api`). | #26: ShaneGore must separately authorize push/PR, observe Actions for a candidate commit, and verify default-branch required checks. No remote pass or branch-protection result is claimed here. |
| 13 | BLOCKED | `compose.yaml`, `backend/Dockerfile`, `frontend/Dockerfile`, `.github/workflows/ci.yml`, `_docs/architecture/deployment.md`; #20 QA locally built both images and checked `/pages-preview/` static assets. This audit locally started the Compose app and verified health/readiness. | #21 and ShaneGore: choose/approve the hosted target and current provider terms, then exercise deployment and rollback in an approved non-production target. The deployment workflow/rollback remains documentation and build evidence only. |
| 14 | BLOCKED | `backend/app/demo.py`, `backend/tests/test_hosted_mode.py`, `frontend/src/hosted-routing.test.tsx`; #22 QA reported the synthetic hosted-anonymous journey passed locally. No hosted service was deployed or observed. | #21: ShaneGore must approve hosted target/account and run synthetic hosted smoke tests after provider terms and cost approval. |
| 15 | VERIFIED | `README.md`, `_docs/plan.md`, `_docs/tech-stack.md`, `_docs/architecture/`, `_docs/process.md`, `_docs/tasks.md`, `_docs/team/`, `AGENTS.md`, `_docs/benchmark-interface.md`, `_docs/incidents/task-23.md`; documentation review plus the Markdown audit and `git diff --check` recorded below. Stale statements are explicitly flagged in this audit. | — |
| 16 | NOT VERIFIED | `_docs/incidents/task-23.md` records an intentional local API stop, alert pending/firing/resolution, and recovery. The exact local command `docker compose --env-file .env.task23 -p benchscope-task23-f5ecf142d10e4cad873d5ad4299a1b4d run --rm --no-deps --entrypoint promtool prometheus test rules /etc/prometheus/api-alert-test.yml` returned `SUCCESS` (exit 0). The report explicitly says no application/alert-rule fix or genuine product root cause was established. | ShaneGore: decide and record a follow-up that demonstrates a genuine development failure, bounded fix, and verification; do not relabel the injected outage as a product fix. |
| 17 | BLOCKED | `backend/app/auth.py`, `backend/tests/test_auth.py`, `backend/tests/test_hosted_mode.py`, `frontend/src/auth/AuthBoundary.tsx`, `frontend/src/auth/AuthBoundary.test.tsx`; historical #14/#22 tests use synthetic JWT/JWKS and identity fixtures, not a deployed Clerk account. | #21 and ShaneGore: verify provider terms/cost, approve a synthetic hosted account, and test actual sign-in/out plus hosted profile/import paths. |
| 18 | VERIFIED | `backend/app/auth.py`, `backend/app/profiles.py`, `backend/app/run_history.py`, `backend/tests/test_auth.py`, `backend/tests/test_profiles_api.py`, `backend/tests/test_run_history.py`; #14 QA reports cross-owner read/update/delete and mixed-owner compare tests, and `pytest` passed in that QA run. | — |
| 19 | VERIFIED | `backend/app/demo.py`, `backend/tests/test_hosted_mode.py`, `frontend/src/hosted-routing.test.tsx`, `frontend/src/App.test.tsx`; tests assert anonymous GET-only deterministic synthetic records, no personal-data access, and no runner request in the anonymous hosted route. #22 QA reported the synthetic hosted-anonymous browser journey passed. | — |
| 20 | NOT VERIFIED | `backend/tests/test_result_import.py`, `backend/tests/test_observability.py`, `frontend/src/observability.test.ts`, `backend/Dockerfile`, `frontend/Dockerfile`, `.dockerignore` files, `.github/workflows/ci.yml`; #20 QA inspected local image contents/build contexts and reported no private material or secrets. No hosted public service was inspected; this audit did not run a full repository/history secret scanner. | ShaneGore: before any publication/deployment, run and record a repository/history and final-artifact secret/confidential-material review; #21 owns hosted observation. The private benchmark maintainer/operator remains unidentified for material inventory. |

## Privacy and security checklist

| Area | Evidence and finding | Audit status / limit |
|---|---|---|
| Repository secrets and confidential benchmark materials | `_docs/benchmark-interface.md` enumerates safe-to-retain and prohibited material and states the investigation occurred outside the repository. `backend/tests/test_result_import.py` rejects private/import-only fields without echo or log; `backend/Dockerfile`, `frontend/Dockerfile`, `.dockerignore` files, and `.github/workflows/ci.yml` constrain build contexts and CI. #20 QA reports image inspection found no secret/private benchmark material. A targeted scan of tracked paths and credential-pattern matches returned no matching file paths; this is not a full history scanner. No values, personal paths, benchmark prompts, or raw result data are included in this report. | No full current git-history secret scan or deployed-artifact/public-service inspection was run. **NOT VERIFIED** as a complete release claim; ShaneGore owns pre-publication scan and #21 hosted review. |
| Owner scope and IDOR | `backend/app/auth.py` derives owners from verified JWT `sub` or guarded local identity; `backend/app/profiles.py`, `backend/app/imports.py`, and `backend/app/run_history.py` scope personal queries to owner. `backend/tests/test_auth.py`, `backend/tests/test_profiles_api.py`, and `backend/tests/test_run_history.py` cover forged owners and cross-owner reads/writes/deletes/compare; #14 QA reports these checks passed. | Verified by historical tests; not an observation against a hosted provider/service. |
| Import schema, size boundaries, and transaction behavior | `backend/app/imports.py` validates `application/json`, parses streamed bytes up to `MAX_UPLOAD_BYTES`, rejects oversize with 413, validates strict Pydantic schema before adding a row, and rolls back integrity/general failures. `backend/tests/test_import_validation.py` and `backend/tests/test_result_import.py` include exact-limit/over-limit, invalid/no-write, and injected rollback cases. | Historical PostgreSQL suite evidence exists; suite not rerun in this audit because the local test command was blocked before execution. |
| Logs and telemetry | `backend/app/observability.py` uses route templates and bounded attributes; `backend/app/imports.py` logs generic transaction errors. `backend/tests/test_observability.py` checks synthetic prompt/code/output/token sentinels are absent from spans, logs, and metrics and that export failures do not break responses; `frontend/src/observability.test.ts` checks token/owner sentinels. #18 QA reports local correlated telemetry and privacy-sentinel checks passed. | Local-only observability evidence. Hosted telemetry was not deployed or observed. |
| Nullable metrics | Nullable DB columns are tested in `backend/tests/test_postgres_storage.py`; import and run-history tests preserve `None` distinctly from zero; `frontend/src/components/ui/MetricValue.tsx` renders `Unavailable`, with `MetricValue.test.tsx` coverage. | Verified by historical tests and code; benchmark-specific metric semantics/aggregation are still unresolved under #25. |
| Local-only benchmark and hosted restrictions | `backend/app/main.py` mounts runner routes only when `APP_MODE=local` and `BENCHMARK_ENABLED=true`; `backend/tests/test_runner.py` and `test_hosted_mode.py` test disabled/hosted behavior. `frontend/src/App.tsx`, `frontend/src/hosted-routing.test.tsx`, and `compose.yaml` retain the presentation/backend boundary. #22 QA reports hosted anonymous E2E used the demo, runner routes returned 404, and no JWKS request occurred. | Hosted restriction behavior has synthetic tests, not hosted deployment evidence. A real adapter/cancellation lifecycle remains blocked by #25. |

## `_docs/tasks.md` item 24 unresolved-decision reconciliation

Statuses below describe the decision itself, not issue closure. “Resolved with
evidence”, “partly resolved”, and “still unresolved” are the only decision
labels used.

| Item 24 bullet / related issues | Decision status and current evidence | Approval or follow-up |
|---|---|---|
| Private benchmark invocation, result schema, endpoint protocol, and container feasibility (#2; #25) | **partly resolved.** #2 and `_docs/benchmark-interface.md` document sanitized pilot invocation/protocol and trial-level fields. This is not an authoritative BenchScope-callable adapter/result contract; #25 remains open and cancellation documents disagree. Linux/container feasibility is explicitly unknown; current code has only a fake async adapter seam. | Identify the private benchmark maintainer/operator (not identified in repo evidence); ShaneGore to confirm contract and cancellation in #25. Keep benchmark/materials on host and out of images. |
| Initial OpenAPI contract from #6; backend-generated contract and #13 integration | **partly resolved.** Routes are integrated and implemented in `backend/app/main.py`; `backend/tests/test_contract.py`, `frontend/src/contract/`, and CI `pnpm check:api` verify the committed contract/types. The source-of-truth transition is not demonstrated: `backend/app/main.py` sets `openapi_url=None`, while README and `_docs/architecture/backend/api.md` still describe reconciliation “before #13” or future FastAPI authority. | ShaneGore: reconcile contract authority and update the stale statements; no issue closure alone resolves drift. |
| Repository name and Pages base path injected by environment (#20) | **partly resolved.** The current remote is `ShaneGore/BenchScope`; `VITE_BASE_PATH` is environment-driven and no repository name is embedded. #20 QA recorded `/pages-preview/` static build verification. Final Pages visibility, deployment path, and activation have not been approved/observed. | ShaneGore to approve final public target/path and deployment under #21; no Pages publication was performed. |
| Render/Neon/Clerk/GitHub terms, payment method, and $0 recurring cost (#20/#21) | **still unresolved.** `_docs/tech-stack.md` and `_docs/architecture/deployment.md` correctly list candidates and require current terms checks before provisioning; no terms/account/cost review was performed here. | ShaneGore must verify current official terms and payment requirements, confirm $0 recurring cost, and approve provisioning. |
| Hosted-profile endpoint/credential and inference-config policy (#10; explicitly reused by #16) | **resolved with evidence.** Explicit #10 decisions: [endpoint/credential fields return 422 before persistence](https://github.com/ShaneGore/BenchScope/issues/10#issuecomment-6429849395); [non-null unsupported `inference_config` also returns 422](https://github.com/ShaneGore/BenchScope/issues/10#issuecomment-6429898364). #16 explicitly approved reuse of this policy ([decision](https://github.com/ShaneGore/BenchScope/issues/16#issuecomment-6432785215)); #10 QA records the approved policy passing ([QA](https://github.com/ShaneGore/BenchScope/issues/10#issuecomment-6430184549)). `backend/app/profiles.py::_validate_mode_fields`, `create_profile`, and `update_profile` reject any supplied `endpoint_url` (including null) and non-null `inference_config` with 422; strict `ProfileFields` rejects extra credential fields. `backend/tests/test_hosted_mode.py::test_hosted_profiles_reject_endpoint_credentials_and_unsupported_config_without_writes` exercises POST and PATCH, verifies 422/no secret echo, and confirms no partial profile mutation. | No remaining policy decision for #10. ShaneGore still owns provider terms/account approval and hosted observation under #21; this decision is not approval to provision or deploy. |
| Run-history date filters, pagination/cursors, and comparison behavior (#12) | **partly resolved.** The explicit #12 decision in [the issue comment](https://github.com/ShaneGore/BenchScope/issues/12#issuecomment-6430631541) approves timezone-aware `from`/`to` normalized to UTC, inclusive `from` and exclusive `to` with `from < to`, deterministic `started_at DESC, id DESC` ordering, default/capped page size of 50/100, and UUID cursors resolved within the owner/filter scope or generic 422. For comparison, it approves generic all-or-nothing 404 for missing/non-owned IDs, completed runs only in input order, at least two completed runs, and preserving null metrics without aggregation/coercion. **That approval does not specify that comparison UUIDs must be distinct.** Distinctness is observed current behavior, not an approved product decision: [implementation comment](https://github.com/ShaneGore/BenchScope/issues/12#issuecomment-6430728108) reports it; `backend/app/run_history.py::compare_runs` documents/rejects repeated UUIDs; and `backend/tests/test_run_history.py::test_compare_rejects_invalid_batches_and_returns_only_owned_completed_runs` verifies a repeated UUID returns 422. | ShaneGore/PM must confirm whether distinct UUIDs are a product requirement and record the decision on #12. Until then, do not treat the current uniqueness behavior as approved. Hosted operation is still unobserved under #21; remote Actions/required-check verification remains #26, separate from approval of these API semantics. |
| Hosted-mode, immutable demo, anonymous read-only access, and no DB seeding (#16; policy reuse from #10) | **resolved with evidence.** The explicit #16 approval says to reuse #10's 422 profile policy and serve an immutable sanitized synthetic fixture through anonymous GET-only endpoints, with no DB seed or startup/deploy write side effect ([approval](https://github.com/ShaneGore/BenchScope/issues/16#issuecomment-6432785215)). Independent QA records hosted runner routes absent even when enabled, fake adapter uncalled, deterministic demo list/detail, rejected writes, unchanged DB row counts, and profile policy passing ([QA](https://github.com/ShaneGore/BenchScope/issues/16#issuecomment-6432949114)). `backend/app/demo.py` defines frozen response models in a tuple and exposes only GET routes; `backend/app/main.py` mounts runner routes only in local mode with `BENCHMARK_ENABLED=true`. `backend/tests/test_hosted_mode.py::test_anonymous_demo_reads_are_deterministic_sanitized_and_personal_data_stays_protected`, `::test_demo_is_get_only_and_has_no_startup_or_read_database_side_effects`, `::test_hosted_runner_routes_are_absent_when_enabled_and_adapter_is_never_called`, and `::test_hosted_profiles_reject_endpoint_credentials_and_unsupported_config_without_writes` cover these decisions. `frontend/src/hosted-routing.test.tsx` verifies the anonymous hosted route uses demo GET only. | No remaining #16 policy decision. ShaneGore still owns actual hosted target/account, provider terms, and live smoke/rollback under #21; these tests are synthetic and do not claim hosted deployment. |
| Local auth bypass policy (#14) | **resolved with evidence.** The explicit #14 decision is `LOCAL_AUTH_BYPASS=false` by default, permitted only with `APP_ENV=development`, `APP_MODE=local`, and loopback-only effective host. `backend/app/config.py`, `backend/tests/test_auth.py`, and settings tests enforce the guard. | No new approval inferred. Clerk account/terms remain separately unresolved and are not approved by the local bypass decision. |
| Benchmark must remain on host unless container feasibility is proven (#2/#8/#20/#25) | **resolved with evidence** for the current boundary: `compose.yaml` does not mount benchmark assets; Docker contexts exclude private material; `_docs/benchmark-interface.md` states Windows-specific dependencies and unknown Linux compatibility. No benchmark was containerized or executed. | Keep host-only boundary. ShaneGore/private maintainer must revisit only through #25 with evidence and explicit approval. |
| Loopback host service vs container bind (#8/#14/#22) | **resolved with evidence.** `compose.yaml` publishes API/DB/observability on `127.0.0.1`; API container binds internally on `0.0.0.0`; local auth bypass remains guarded by effective host resolution. #22 records the synthetic E2E process binding directly to loopback rather than weakening the Compose guard. | No deployment approval inferred. Preserve the loopback publication and bypass guard. |
| Explicit MVP non-goals (#1–#23) | **resolved with evidence** as a scope boundary: no team sharing, public submissions, hosted benchmark execution, or distributed runner is added. `backend/app/main.py`, `backend/tests/test_hosted_mode.py`, `_docs/plan.md`, and #16/#17 evidence keep the hosted runner disabled. | Do not expand scope without a separately groomed decision. |

### Other documented TBD decisions

| Open item | Evidence and owner/follow-up |
|---|---|
| Cancellation status/mapping and private adapter cleanup | Still unresolved in `_docs/architecture/backend/data-model.md`, `_docs/architecture/backend/runner.md`, `_docs/benchmark-interface.md`, and #25. ShaneGore and the unidentified private maintainer/operator must resolve in #25 before real integration. |
| Metric score/pass-rate definitions and safe trial-to-run aggregation | `_docs/plan.md` §11 and `_docs/benchmark-interface.md` list unknown semantics. Do not infer aggregation; ShaneGore/private maintainer to approve definitions through #25. |
| Import/history rate-limit specifics | `_docs/architecture/backend/api.md` says “specifics TBD.” ShaneGore to decide and groom follow-up if required before public exposure; no rate-limit behavior was claimed in this audit. |
| Hosted migration ordering, backups, restore, persistence, cold starts, quotas, and rollback procedure | `_docs/architecture/deployment.md` says these are provider-dependent and unverified. ShaneGore to review current provider documentation and rehearse an approved non-production rollback under #21 before promotion. |
| Hosted target/account, CORS, authentication, and actual smoke/rollback | #21 remains open and explicitly requires owner-approved non-production target/account and rehearsal. ShaneGore owns approval and execution; do not use personal/production data. |
| Remote Actions and default-branch required checks | #26 remains open. ShaneGore must separately authorize push/PR and record remote run plus backend/frontend required-check settings; this task did not push. |
| Provider provisioning / payment / cost | `tech-stack.md` §6/§10 and `deployment.md` explicitly defer current terms and billing checks. ShaneGore must make and record the $0-cost/payment/provisioning decision before any provider is created. |
| Hosted telemetry provider | `tech-stack.md` lists Grafana Cloud as optional and unverified. ShaneGore must decide whether it is needed and approve terms/cost before enabling; local observability is the only observed mode. |

## Documentation consistency review

| Document set checked | Audit finding |
|---|---|
| `README.md` | The claim “Backend domain routes are not yet implemented” was stale versus `backend/app/main.py` and route tests; corrected in this audit to name the implemented route groups. The CI paragraph now states jobs block each workflow run and explicitly says repository required-check settings are unverified pending #26. The API-contract paragraph still says FastAPI OpenAPI will become authoritative and needs reconciliation after #13; see the stale contract finding above. |
| `_docs/tech-stack.md` | Candidate provider terms/$0 cost remain accurately unverified. Its selection table describes a subprocess benchmark runner, but current #15 code is only an in-process fake-adapter seam and does not launch a subprocess; treat that as a target design, not current implementation. Its TS generation open question is stale versus CI `pnpm check:api` / `pnpm gen:api`. |
| `_docs/architecture/README.md`, `deployment.md`, `boundaries.md` | Deployment document clearly says proposed/not active and blocks provisioning pending current terms/owner approval. Boundaries correctly state local-only benchmark and synthetic, read-only hosted demo. No hosted claim was verified. |
| `_docs/architecture/backend/README.md`, `api.md`, `data-model.md`, `runner.md` | API route/ownership statements generally match code/tests. `api.md` retains the obsolete “before #13 integrates” contract paragraph; FastAPI OpenAPI is disabled in `main.py`, so contract authority still needs a decision. Its rate-limit specifics remain TBD. Runner docs distinguish the interim fake seam, no production adapter, no subprocess, and deferred cancellation; keep those as limitations rather than release proof. |
| `_docs/architecture/frontend/README.md`, `routing.md` | Local/hosted/demo behavior and env-injected base path match frontend tests and CI static build. `README.md`/CI document test and build steps. Clerk plan/terms remain candidates, not verified account configuration. |
| `_docs/process.md`, `_docs/task-template.md`, `_docs/team/pm.md`, `_docs/team/software-engineer.md`, `_docs/team/qa-engineer.md`, `.github/agents/pm.agent.md`, `.github/agents/software-engineer.agent.md`, `.github/agents/qa-engineer.agent.md`, `AGENTS.md` | Role/process instructions align on groomed scope, QA independence, test reporting, commit, and leaving closure to the orchestrator. This audit is committed without closing #24; independent QA remains outstanding. |
| `_docs/benchmark-interface.md` | Sanitized pilot facts and explicit unknowns are retained. The verified pilot protocol is not the confirmed callable BenchScope adapter contract; #25 remains authoritative for that blocker. |
| `_docs/incidents/task-23.md` | Accurately records a local injected API outage, firing/resolution, `promtool` success, cleanup, and no application/alert-rule fix. It does not prove a genuine product incident with bounded fix as plan criterion 16 requires. |

## Checks and execution record

Checks are separated by source and location. “Historical QA” refers to the
named issue comment and its checked revision, not this audit checkout.

| Check | Source / exact command | Result and boundary |
|---|---|---|
| Clean-checkout Compose configuration | Current audit checkout at source revision `228081d`: `docker compose --env-file .env -p benchscope-task24-6af4b91623ce44fd9aad0e5300ebc921 config --quiet` | Exit 0; local synthetic config only. |
| Clean-checkout Compose build/start | `docker compose --env-file .env -p benchscope-task24-6af4b91623ce44fd9aad0e5300ebc921 up --build --wait --detach` | Exit 0; local stack only. |
| Clean-checkout health/readiness | `Invoke-RestMethod http://127.0.0.1:8000/health`; `Invoke-RestMethod http://127.0.0.1:8000/ready` | `{"status":"ok"}` and `{"status":"ready"}`. No hosted service. |
| Backend dependency/test checks for this audit checkout | Attempted `uv sync --locked --group dev`; command tool refused before execution and required unavailable user approval. Follow-on commands were not run. | No current-audit `uv` or pytest result. |
| #19 backend CI-equivalent checks | Historical issue #19 QA: `uv sync --locked --group dev`, `uv lock --check`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run pytest` | Reported passed; PostgreSQL-backed suite **99 passed**. Local QA only; not a remote Actions run. |
| #19 frontend CI-equivalent checks | Historical issue #19 QA: `corepack pnpm install --frozen-lockfile`, `corepack pnpm test`, `corepack pnpm build`, `corepack pnpm check:api` | Reported passed; **36 tests passed**. Local QA only. |
| #20 image and Pages static checks | Historical #20 QA: `docker build --tag benchscope-backend:ci ./backend`; `docker build --tag benchscope-frontend:ci --build-arg VITE_BASE_PATH=/ --build-arg VITE_API_URL= ./frontend`; `pnpm exec vite build --outDir dist-pages`; `node scripts/check-static-build.mjs dist-pages` | QA reported both images built without publishing and `/pages-preview/` static assets verified. Local QA only; no deploy. |
| #22 backend/frontend/journey checks | Historical #22 QA: backend `pytest -q` **107 passed**; frontend `pnpm test` **36 passed**, `pnpm build`, `pnpm check:api`; `pnpm test:journey` **7 passed** | Synthetic local and hosted-mode test configurations. QA explicitly did not run a live Prometheus/Loki/Tempo-backed E2E stack for that check. |
| #23 incident alert rule | Historical #23 local project command: `docker compose --env-file .env.task23 -p benchscope-task23-f5ecf142d10e4cad873d5ad4299a1b4d run --rm --no-deps --entrypoint promtool prometheus test rules /etc/prometheus/api-alert-test.yml` | `SUCCESS` (exit 0); local synthetic alert-rule fixture. Not a hosted or genuine product-fix test. |
| #23 injected outage and recovery | `_docs/incidents/task-23.md` timestamps and sanitized observation: API health/readiness no response; Prometheus `up=0`; alert pending then firing after 173.3 seconds; API restart restored health/`up=1` and resolved alert. | Observed in a disposable local project. No application/rule fix or root cause claimed. |
| Markdown/documentation validation for this audit | PowerShell piped a Node standard-library check (`node -`) over the report and 23 named Markdown docs; checked balanced fences, no trailing whitespace, valid local links, cited path existence, and plan matrix 1–20 exactly once with allowed statuses. | `Markdown audit passed: 24 documents have balanced fences/no trailing whitespace; criteria 1–20 occur once with allowed statuses; 53 cited repository paths exist; Markdown links resolve.` |
| Whitespace / patch validation | `git diff --check`; `git diff --cached --check` | Both exit 0. |
| Targeted tracked-file privacy scan | PowerShell: `$pattern='-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----|github_pat_[A-Za-z0-9_]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|sk_live_[A-Za-z0-9]+'`; `git grep -I -l -E -- $pattern -- .`; `git ls-files` filtered for prompt/reference/hidden-test/solution and model/key file suffixes. | No matching credential-pattern file paths or tracked private-material filenames. This targeted scan is not a full history scanner and does not establish hosted/public-serving state. |
| Remote GitHub Actions | No workflow was triggered for `task-24-release-audit`; branch was not pushed. | Not run / not verified. Do not infer branch protection or required-check enforcement; #26 owns it. |
| Hosted service, credentials, terms, payment, rollback | None provisioned or accessed. | Not run / not verified; owner approval and #21 remain required. |

## Blockers and release owners

| Blocker | Owner and required follow-up |
|---|---|
| Real private benchmark adapter/result contract and cancellation semantics (#25) | Private benchmark maintainer/operator is not identified in repo evidence. ShaneGore must identify the authoritative maintainer, confirm the contract and cancellation decision, and approve any implementation. |
| Hosted target/account and rollback rehearsal (#21) | ShaneGore must approve a synthetic non-production target/account, current provider terms and $0-cost constraints, then run hosted smoke tests and exercise rollback. |
| Remote Actions and required checks (#26) | ShaneGore must separately authorize push/PR, observe the candidate Actions run, and verify required backend/frontend checks on the default branch. No push/PR was performed. |
| Provider terms, payment method, recurring cost, and provisioning | ShaneGore must verify current official GitHub Pages, Render, Neon, and Clerk terms as applicable, confirm payment-method requirements and $0 recurring cost, and explicitly approve provisioning. |
| Documentation/API contract authority, restart persistence, chart browser proof, and genuine incident fix | ShaneGore owns decisions/follow-ups; no new issue was created or scope silently expanded in this audit. |

**Disposition:** retain BLOCKED. Independent QA should review this audit and
the documentation correction. Do not close #24, deploy, publish, provision,
push, or claim remote CI/branch protection until the named approvals and
follow-ups are completed.
