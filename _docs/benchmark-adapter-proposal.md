# Proposed Local Benchmark Adapter Contract

**Status:** Contract direction approved; implementation is blocked until the
real runner's callable entry point, configuration, result delivery, and
cancellation behavior are verified. No private benchmark material belongs in
BenchScope.

## Recommendation

Build a local-only adapter and a versioned normalized result contract; do not
add a new frontend page. The existing
[`BenchmarkPage`](../frontend/src/pages/BenchmarkPage.tsx) already starts and
polls local runs, and [`ImportPage`](../frontend/src/pages/ImportPage.tsx)
accepts supported JSON summaries. Extend those surfaces only to expose
cancellation and, if desired, per-task outcomes.

Treat one run as one model profile, one approved configuration, one benchmark
release, and one seed. Repeated seeds remain separate runs; do not aggregate
across repeats in this MVP.

## Proposed result contract

Introduce `benchscope.run.v2`; keep the strict `benchscope.run.v1` contract
unchanged. A v2 result should retain the existing profile, configuration,
timestamps, and allowlisted aggregate metrics, and add:

- `benchmark`: stable benchmark ID, release version, canonical manifest
  SHA-256, and expected task count.
- `task_coverage`: expected and completed task counts.
- `task_results`: one canonical task ID and `pass` or `fail` outcome per
  completed task.

Use the same validated result type for imported summaries and adapter output;
the launched adapter should return it to the run lifecycle, not make an HTTP
request back into BenchScope.

Reject unknown or duplicate task IDs, outcomes other than `pass`/`fail`, and
coverage inconsistent with the task results. Missing tasks remain missing; do
not turn them into failures. Never include prompts, references, test contents,
generated code, raw responses, raw test output, machine paths, or exception
text.

Recommended aggregate semantics:

- Preserve a separate passed-task count. Map it to `quality_score` only if an
  authoritative benchmark scoring definition confirms that mapping; otherwise
  leave `quality_score` null.
- `pass_rate` is passing tasks divided by expected tasks, and is only populated
  for complete coverage. Never infer an aggregate pass rate from partial
  coverage.
- `elapsed_ms` is measured for the whole run. Token metrics are retained only
  when the source provides them reliably; TTFT and throughput must not be
  inferred.
- Compare scores only when benchmark ID, release, manifest hash, and coverage
  match.

The current database already has a nullable `benchmark_version` column, but
v1 import does not accept or populate it. The strict v1 request also has no
benchmark identity, coverage, or task outcomes, and its `quality_score` has no
denominator. Store the new benchmark identity, coverage, and task outcomes in
one sanitized run-detail JSON field for the MVP; normalize to a child table
only if cross-run per-task queries become a requirement. Populate and return
`benchmark_version` in v2. Use a v2-specific fingerprint namespace.

The launched-run seam is also provisional: it passes an owner-validated
profile snapshot and an opaque config UUID to an injected adapter, returns only
generic metrics, and has no production adapter or config catalog. The backend
must resolve both IDs through server-owned configuration before it can select
the benchmark release, model alias, and allowed settings.

## Proposed local invocation and cleanup

- Enable the adapter only in local mode, bound to loopback, and leave hosted
  execution hard-disabled. The current Compose API image is Linux-based while
  the inspected benchmark runner requires Windows `llama-server.exe` and local
  GPU/model files. For this benchmark, run the benchmark-enabled API natively
  on Windows with the database still local, or design a separate host worker;
  do not mount private benchmark/model files into the Linux API container.
- Keep the API request limited to owner-scoped profile/config IDs. Resolve
  those IDs through a server-controlled allowlist for the executable, model
  alias/path, benchmark root/version, and arguments. Reject unknown IDs; never
  accept a command, filesystem path, or arbitrary environment from the
  browser.
- Launch with `asyncio.create_subprocess_exec` (no shell), one active run at a
  time, a configured overall timeout, bounded output capture, and a private
  temporary run directory outside the repository. Parse only the result
  allowlist; do not persist or serve raw runner output or artifacts.
- The inspected `run47.py` is not a stable callable interface: it has
  machine-specific paths and output locations. Add a small configured wrapper
  or supported entry point before connecting it to BenchScope; do not treat
  its model-server HTTP protocol as the adapter contract.

## Cancellation recommendation

Represent a user-requested cancellation as a distinct terminal `cancelled`
status rather than `failed` or `interrupted`. Add an owner-scoped,
local-only cancel operation for a running run. It should be idempotent, request
graceful shutdown, then terminate and reap the complete Windows process tree
(prefer a kill-on-close Job Object or an equivalently verified mechanism)
after a bounded grace period. Mark the run `cancelled` only after cleanup
finishes. Keep timeout as `failed` with a timeout category, and reserve
`interrupted` for an application/process loss discovered during recovery.

If sanitized checkpoints are available, keep completed task outcomes and
accurate coverage for cancelled, timed-out, or interrupted runs; do not assign
them a comparable aggregate score unless coverage is complete. Never release
the single-flight lock while the child process may still be alive.

## Implementation gate

The v2 direction, v1 compatibility, distinct `cancelled` status, timeout and
interrupted mappings, native Windows loopback-only local execution, and
server-controlled configuration are approved. Before implementing the real
adapter, verify and document the callable entry point, required configuration,
result delivery format, and cancellation/process-tree behavior in
[`benchmark-interface.md`](./benchmark-interface.md). The currently inspected
runner has no callable cancel API or verified process-tree termination
guarantee, so the real adapter remains blocked. Only sanitized result fields
may cross into BenchScope.

Relevant constraints are in
[`backend runner architecture`](./architecture/backend/runner.md),
[`backend data model`](./architecture/backend/data-model.md), and
[`plan.md`](./plan.md). The benchmark release's scoring and privacy rules are
described in the local, owner-provided benchmark package; no private paths or
benchmark materials are copied into this proposal.
