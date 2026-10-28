# Benchmark runner (local mode only)

## 1. Goals

Provide a local-only runner lifecycle boundary that can later launch the private benchmark, record sanitized run status/results, survive restarts, and enforce single-flight. The real private benchmark adapter is deferred to #25.

## 2. Target lifecycle (real integration deferred)

Persisted states: `running` -> `completed` | `failed` | `interrupted` | `cancelled`.

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
- Process group termination on timeout (avoid orphans); user cancellation is distinct from failure and is persisted only after the cooperative coroutine cleanup completes; it does not terminate processes.
- Single-flight lock prevents concurrent runs (MVP only needs one at a time).

## 4. Metrics capture

- TTFT measured by runner/streaming client when possible; never inferred from prompt-processing duration.
- Only metrics the benchmark provides are stored; missing stays null.
- Hardware/OS snapshot captured at run start (best-effort).

## 5. Diagnostics

- Sanitised error category (enum: `timeout`, `process_exit`, `parse_error`, `endpoint_unavailable`, `adapter_error`, `interrupted`).
- Short sanitised message; no raw stdout/stderr, no code, no prompts.
- Process exit code stored when available.

## 6. Observability

- Span per run with attributes: run id, profile id, status, elapsed. No prompts/code.
- Metrics: run count by status, duration histogram, timeout count.
- Alert on repeated failures / stuck runs.

## 7. Mode gating

- Runner routes are registered only when `APP_MODE=local` and `BENCHMARK_ENABLED=true`.
- `BENCHMARK_TIMEOUT_SECONDS` bounds the interim adapter coroutine; its default is 3600 seconds.
- Endpoints absent otherwise. Frontend hides launch UI in hosted mode but backend is authoritative.

## 8. Open dependency

Exact adapter interface and result schema are unresolved (`plan.md` §11.1–4). Until confirmed, implement adapter seam + a fake adapter for tests. Do not block other work.

### Interim seam implemented by #15

- The internal adapter protocol accepts only an owner-validated profile snapshot and a UUID config identifier and returns a normalized run-level result. This is provisional, not the private benchmark's confirmed interface or schema.
- The test suite injects its synthetic fake. Production app creation does not select or register a fake adapter; with no real adapter configured, launch and retry return 503 without creating a run.
- This interim seam does not launch subprocesses, invoke `llama-server`, parse output, aggregate trials, derive missing metrics, or terminate processes. Owner-scoped cancellation awaits the cooperative adapter coroutine cleanup before persisting `cancelled`; timeouts remain `failed` and startup/process loss remains `interrupted`. The adapter may not detach child tasks. No child process is launched by this seam.
- Only the metric allowlist is persisted. The profile snapshot contains `name`, `model_name`, `model_version`, and `quantisation`; endpoint URLs and free-form inference settings are excluded. The config identifier is validated as a UUID and stored opaquely; no config catalog or mapping is claimed.
- A concurrent start returns 409 and creates no row. Accepted work is persisted as `running`; startup changes stale `running` rows to `interrupted`. Retry accepts an owned failed launched run and creates a new row linked by `related_run_id`.
- Cancellation does not create a new run or metrics. Only failed launched runs are retryable.
