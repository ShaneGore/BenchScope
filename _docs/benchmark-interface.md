# Private Benchmark Interface (Sanitised)

This document records only sanitised, verified facts from the private benchmark
investigation. It does not contain benchmark prompts, reference solutions,
tests, generated code, raw model responses, credentials, or other confidential
material.

## Scope

- Benchmark: Local LLM Coding Benchmark v1, 47 tasks (33 legacy tasks plus 14
  additions).
- Frozen instrument: prompts, references, tests, and scoring rules must not be
  silently altered.
- Inspection and execution were performed outside the public repository.
- This file is the only repository artifact added by this task.

## Verified invocation type

- The pilot runner starts a local `llama.cpp` server (`llama-server`) on
  `127.0.0.1:8090`.
- It sends an OpenAI-compatible `POST /v1/chat/completions` request with
  `model: "local"`, a single user message containing the task prompt, and
  `stream: false`.
- It captures `/props` to record the served model path for verification.
- It extracts candidate Python code from the response and evaluates it in a
  temporary directory.
- One scored attempt is made per task/seed. Model failures are not retried.
- The runner is not self-contained and requires environment-specific absolute
  path edits before use.

## Verified configuration

| Setting | Value |
|---|---|
| Context size | 8192 |
| Temperature | 0.0 |
| Seed | 1234 (repeat seeds use seed + 1000) |
| Max tokens | 6000 |
| Reasoning | Off (`reasoning: false`, `chat_template_kwargs.enable_thinking: false`) |
| MTP | Off |
| GPU layers | 99 |
| Jinja chat templates | Enabled |
| Flash attention | On |
| KV cache type | q8_0 |
| Parallel slots | 1 |
| `--fit` | on |
| Server readiness timeout | 240 seconds |
| Model request timeout | 900 seconds |
| Verifier timeout | 30 seconds per import/public/hidden check |

## Working directory behaviour

- Automated evaluation creates a temporary directory, writes the extracted code
  as `solution.py`, copies the public and hidden tests into that directory, and
  runs each test with that directory as the working directory.
- Manual evaluation requires placing a candidate `solution.py` in the task
  folder and running `import solution`, then the public and hidden test scripts
  from that folder.
- The runner itself depends on absolute source-repository paths and is not
  portable without edits.

## Model endpoint protocol

- Endpoint: local HTTP service on `127.0.0.1:8090`.
- Readiness check: `GET /health`.
- Model identity check: `GET /props`, using `model_path` or `model`.
- Inference request: `POST /v1/chat/completions`.
- Response text is read from `choices[0].message.content`.
- Usage metadata is read from `usage` when present.

## Result delivery and record schema

The runner writes one JSONL record per trial. Sanitised field names include:

- `model`
- `task_id`
- `source`
- `seed`
- `repeat_index`
- `prompt_sha256_16` (prompt hash prefix only)
- `served_model_path`
- `served_matches`
- `response_chars`
- `extraction_note`
- `import_ok`
- `public_rc`
- `hidden_rc`
- `pass`
- `category`
- `wall_s`
- `prompt_tokens`
- `output_tokens`
- `error`
- `temperature`
- `max_tokens`
- `reasoning`
- `mtp`
- `ctx`
- `timestamp_utc`

It also writes raw response text, extracted code, and evidence JSON under a
local output directory. Those artifacts are confidential and must not be
committed.

## Exit and failure behaviour

- Binary outcome only: PASS requires all of:
  1. `import solution` succeeds.
  2. `tests/public_test.py` exits 0 within 30 seconds.
  3. `tests/hidden_test.py` exits 0 within 30 seconds.
- FAIL is returned for any other result.
- No partial credit, test weakening, or per-task exception is allowed.
- The exact evaluated string is the extracted code, without reformatting.
- Diagnostic categories are recorded for analysis only and never convert a FAIL
  into a PASS:
  - `provider-empty`
  - `capture`
  - `extraction`
  - `import`
  - `genuine`
  - `pass`
  - `provider-error`
- If the server fails to start, the runner exits with status 3.

## Cancellation and timeout behaviour

- Model request timeout: 900 seconds.
- Import check timeout: 30 seconds.
- Public and hidden test timeout: 30 seconds each.
- Server readiness timeout: 240 seconds.
- GPU free-memory check timeout: 20 seconds.
- The server process is terminated in a `finally` block.
- Completed task/seed pairs are checkpointed in JSONL and skipped on rerun.
- No retry is performed for model failures.

## Dependencies

Verified dependencies include:

- Windows `llama-server.exe`.
- Local GGUF model files.
- NVIDIA GPU and `nvidia-smi`.
- Python runtime for verification.
- Absolute-path configuration edits for repository root, server executable,
  and model paths.

## OS and container compatibility

- The verified runner is Windows-specific.
- It depends on a Windows executable, Windows-style absolute paths, and NVIDIA
  GPU tooling.
- Linux-container feasibility is not established by the available evidence.
- Containerising the benchmark remains out of scope unless feasibility is
  established and approval is given.

## Safe-to-retain fields

The following are safe to retain in sanitized form:

- Task metadata fields such as id, category, capability tags, interface,
  language, standard-library-only flag, network flag, timeout, and scoring type.
- Task-card identity, aliases, source revision, file hashes, and disposition.
- Aggregate scores and diagnostic categories.
- Invocation configuration and timeout values.
- Integrity and provenance hashes.

## Fields that must be discarded

Do not commit or publish:

- `prompt.txt`
- `reference.py` or `reference_solution.py`
- `tests/public_test.py`
- `tests/hidden_test.py`
- Candidate or generated `solution.py`
- Raw model responses
- Extracted code
- Raw test output containing hidden-test details
- Credentials or model files
- Machine-specific absolute paths in committed artifacts

## Recorded metric names and definitions

- `pass`: boolean, true only when import and both tests pass.
- `import_ok`: boolean.
- `public_rc`: process exit code.
- `hidden_rc`: process exit code.
- `wall_s`: model request wall time in seconds.
- `response_chars`: response length.
- `extraction_note`: `closed-fence`, `unclosed-fence`, or `full-text`.
- `category`: diagnostic classification.
- `prompt_tokens` and `output_tokens`: present only when the endpoint returns
  usage metadata.
- Comparison gap interpretation: 0-2 points is a tie, 3-4 points is marginal,
  and 5 or more points is separation.

## Values that may be absent

- `served_model_path` may be empty.
- `prompt_tokens` and `output_tokens` may be absent.
- `error` is null on successful requests.
- `response_chars` may be 0 for empty responses.
- Task metadata fields such as timeout or network behaviour are task-specific
  and must not be generalised without verification.

## Unknowns

- Hosted per-call spend telemetry is unknown.
- Linux-container feasibility is unknown.
- The exact Python version required by every task is not uniformly stated.
- Network requirements are task-specific and not fully enumerated here.
- Whether all endpoints support the same request fields is not verified.
- Any fact not listed above must be marked unknown rather than inferred.
