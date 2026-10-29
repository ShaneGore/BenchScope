# Benchmark Adapter Contract Assessment

This document records the repository-side assessment for Issue #25. It contains
only sanitized, non-confidential facts. It does not include benchmark prompts,
reference solutions, generated code, raw model responses, credentials, or
machine-specific private paths.

## Status

No real private benchmark adapter has been implemented.

The BenchScope runner lifecycle, cancellation status decision, import schemas,
and persistence model are implemented. The real adapter remains blocked because
the private runner does not expose a stable, supported BenchScope-callable
contract or a verified cancellation/timeout cleanup guarantee.

## Verified runner contract

Source of record: `_docs/benchmark-interface.md`.

- Official scoring runner: standalone CLI `tools/run47.py`.
- Invocation shape:
  `python tools/run47.py --model <configured-model-key> [--tasks <comma-separated-task-ids>] [--seed <integer>] [--repeat <integer>]`
- `--model` is required and resolves through a source-defined model table.
- Executable paths, model paths, repository paths, and output locations are
  environment-specific source configuration, not CLI arguments.
- The runner starts a local `llama.cpp` server on `127.0.0.1:8090`.
- It sends one OpenAI-compatible chat completion request per task/seed.
- It evaluates generated Python code in a temporary directory.
- Defaults are seed `1234` and one repeat.
- Selected tasks and repeats are configurable.
- Model failures are not retried.
- The runner is Windows-specific and depends on a Windows executable, Windows
  absolute paths, and NVIDIA GPU tooling.

## Verified output behavior

- The runner emits per-task/seed JSONL records.
- It does not emit a native BenchScope run-level import document.
- Completed task/seed pairs are checkpointed in JSONL and skipped on rerun.
- Successful, failed, timeout, and model-error states are represented in the
  per-task record fields.
- Aggregate metrics are not emitted as a run-level object.
- `prompt_tokens` and `output_tokens` are present only when usage metadata is
  returned by the endpoint.
- `served_model_path` may be empty.

## Verified cancellation and cleanup behavior

- There is no runner cancellation command, signal protocol, or callable cancel
  API.
- The runner starts `llama-server` with `CREATE_NEW_PROCESS_GROUP`.
- Cleanup terminates, waits for, and may kill the single server child PID.
- There is no verified process-tree cleanup guarantee.
- Existing PowerShell matrix/watch scripts target an older evaluation path and
  are not a safe cancellation wrapper.
- BenchScope's approved status mapping is:
  - cancellation -> `cancelled`
  - timeout -> `failed`
  - unexpected process loss -> `interrupted`

These mappings are implemented in BenchScope. They do not imply that the
## BenchScope import compatibility

BenchScope supports two import contracts:

- `benchscope.run.v1`: one run-level record with profile snapshot, benchmark
  configuration, metrics, and optional hardware snapshot.
- `benchscope.run.v2`: one run-level record with benchmark details, task
  results, and a subset of metrics.

A runner JSONL stream is not directly either contract. A safe adapter would
need to:

1. Run the runner with an allowlisted server-side configuration.
2. Parse and validate each JSONL record.
3. Aggregate or otherwise derive run-level metrics using an approved
   definition.
4. Construct a `benchscope.run.v1` or `benchscope.run.v2` document.
5. Persist only allowlisted, sanitized fields.
6. Preserve missing metrics as `null`; do not infer unverified metrics.
7. Handle partial JSONL output without claiming a complete run.

The existing import code already enforces:

- owner scoping
- duplicate detection
- strict schema validation
- task-result uniqueness and expected-task coverage for v2
- allowlisted metrics only
- sanitized persistence

## Implementation decision

Do not implement a real adapter now.

The invocation is documented but not a stable BenchScope-callable contract. The
runner requires source-level path edits, emits per-task JSONL rather than a
run-level document, and has no verified cancellation or process-tree cleanup
guarantee. Implementing it now would require inventing adapter behavior and
would risk unsafe process handling.

## Verified BenchScope behavior

- `RunStatus` supports `running`, `completed`, `failed`, `interrupted`, and
  `cancelled`.
- Cancelled runs are persisted as `cancelled` with null metrics.
- Timeouts are persisted as `failed` with category `timeout`.
- Unexpected process loss is reconciled to `interrupted`.
- Run cancellation is owner-scoped and only applies to launched runs.
- The benchmark lock is released after cancellation.
- Synthetic adapter tests cover cancellation and owner scoping.

These tests validate BenchScope's lifecycle. They are not proof that the real
runner supports cancellation or cleanup.

## Evidence references

- Private runner contract: `_docs/benchmark-interface.md`
- Runner lifecycle and cancellation mapping: `backend/app/runner.py`
  (`RunStatus`, `_execute`, `_finish_run`, `reconcile_interrupted_runs`,
  `cancel_run`)
- Import schema and validation: `backend/app/imports.py`
  (`RunImportRequest`, `RunImportV2Request`, `_fingerprint`,
  `_fingerprint_v2`, `_import_v2`)
- Persistence and status model: `backend/app/models.py` (`BenchmarkRun`)
- Cancellation and owner-scope tests: `backend/tests/test_runner.py`
- Approved cancellation mapping: `_docs/benchmark-interface.md`

## Remaining blocker

The exact missing evidence is:

- A stable, server-side invocation contract for `tools/run47.py` that does not
  require source edits or browser-supplied paths.
- A documented result-to-run mapping, including aggregation semantics.
- A verified cancellation protocol or process-tree cleanup guarantee.
- Evidence that partial output can be safely distinguished from a complete run.

## Acceptance test plan once unblocked

1. Invoke the runner with a synthetic or approved model configuration in an
   isolated environment.
2. Capture and validate the JSONL schema without exposing private task content.
3. Transform one complete run into a valid BenchScope import document.
4. Verify all required metrics are either present or explicitly null.
5. Test cancellation before start, during parent execution, during child
   execution, timeout, forced termination, and wrapper exit.
6. Verify no orphaned `llama-server` process remains.
7. Verify partial output is rejected or marked incomplete.
8. Run owner-scoped import, history, detail, and comparison tests with
   synthetic data.
9. Run migration and concurrency tests.

Until these are available, Issue #25 remains blocked.
