# Benchmark runner (local mode only)

## 1. Goals

Launch the private benchmark against a configured local model endpoint without blocking the web UI, record status/metrics/diagnostics, survive restarts, and enforce single-flight. No arbitrary commands from the browser.

## 2. Lifecycle

States: `running` → `completed` | `failed` | `interrupted` | `cancelled`.

1. `POST /benchmark/runs` creates a `BenchmarkRun` row (status `running`) with profile snapshot, returns immediately.
2. Runner acquires the single-flight lock; if busy, returns 409.
3. Adapter is invoked with validated profile + config (never raw input).
4. Subprocess runs via `asyncio.create_subprocess_exec` (no shell). stdout/stderr captured to a bounded buffer (not logged in full).
5. `asyncio.wait_for` enforces a configurable timeout; on expiry, terminate process group, mark `failed` with `timeout` category.
6. On completion, parse allowlisted metrics, normalise, persist; mark `completed` or `failed`.
7. On application startup, reconcile any row still `running` → `interrupted` (with diagnostic).

## 3. Safety

- No shell (`create_subprocess_exec`, args as list). No user-supplied command/path.
- Only allowlisted env/config passed to subprocess; private paths from server config, not request.
- Bounded output capture; truncate + flag if exceeded; never store raw prompts/code.
- Process group termination on timeout/cancel (avoid orphans).
- Single-flight lock prevents concurrent runs (MVP only needs one at a time).

## 4. Metrics capture

- TTFT measured by runner/streaming client when possible; never inferred from prompt-processing duration.
- Only metrics the benchmark provides are stored; missing stays null.
- Hardware/OS snapshot captured at run start (best-effort).

## 5. Diagnostics

- Sanitised error category (enum: `timeout`, `process_exit`, `parse_error`, `endpoint_unavailable`, `adapter_error`, `cancelled`, `interrupted`).
- Short sanitised message; no raw stdout/stderr, no code, no prompts.
- Process exit code stored when available.

## 6. Observability

- Span per run with attributes: run id, profile id, status, elapsed. No prompts/code.
- Metrics: run count by status, duration histogram, timeout count.
- Alert on repeated failures / stuck runs.

## 7. Mode gating

- Runner module imported only when `APP_MODE=local` and `BENCHMARK_ENABLED=true`.
- Endpoints absent otherwise. Frontend hides launch UI in hosted mode but backend is authoritative.

## 8. Open dependency

Exact adapter interface and result schema are unresolved (`plan.md` §11.1–4). Until confirmed, implement adapter seam + a fake adapter for tests. Do not block other work.