# Private benchmark boundary & local-vs-hosted separation

## 1. Private benchmark boundary

The existing benchmark is a **private dependency**. Its implementation, prompts, reference answers, hidden test identifiers, generated code, confidential evaluation logic, and raw artifacts must never enter the public repository or be served by the dashboard.

### What stays local (Z3)

- Benchmark executable / source and its evaluation data.
- Model endpoints (localhost URLs, ports, auth tokens).
- Raw benchmark stdout/stderr, generated code, prompts, reference answers.
- Private artifacts referenced by runs (kept on disk, never uploaded).

### What may cross into the application

Only a **sanitised, normalised result record**:

- Run identity (optional source run ID), status, timestamps, elapsed time.
- Model name/version/quantisation and selected configuration (as recorded by the benchmark).
- Benchmark version or non-confidential identifier.
- Quality score / aggregate pass rate as defined by the benchmark.
- TTFT, prompt/output token counts, prompt-processing and generation throughput.
- Hardware/OS snapshot (CPU, GPU, RAM, VRAM) where available.
- Sanitised error category + diagnostic message (no raw stdout, no code, no prompts).
- Import fingerprint / source identifier.
- Optional opaque reference to a private local artifact (path/URI stored as text; never served).

### Enforcement

- The runner accepts **only** a validated profile ID + benchmark config ID from the API; it never accepts arbitrary commands, paths, or shell input from the browser.
- Benchmark paths and private config live in env vars / local config files outside version control (e.g. `.env.local`, `config/local.toml` gitignored).
- CI runs without the private benchmark, GPU, or model weights. Tests use synthetic fixtures only.
- Logs must not contain prompts, generated code, secrets, credentials, or complete benchmark output. Error diagnostics are allowlisted fields.
- Hosted import processing extracts only allowlisted metrics/metadata, discards the uploaded raw payload after processing, and never stores prompts, reference answers, generated code, secrets, or private raw artifacts.
- Upload size is capped and all input validated before persistence.

### Integration seam (open)

The exact command/API/adapter that launches the private benchmark is unresolved (`plan.md` §11.1). Architecture assumes a **single adapter interface**:

```
BenchmarkAdapter.run(profile, config) -> AsyncIterator[RunEvent] | RunResult
```

implemented locally and registered only when `APP_MODE=local` and `BENCHMARK_ENABLED=true`. The adapter is not shipped in hosted images (or is shipped but inert/disabled). Until the interface is confirmed, the runner module is scaffolded behind this seam and exercised with a fake adapter in tests.

## 2. Local vs hosted separation

### Local/private mode (`APP_MODE=local`)

- Service binds to loopback by default (`127.0.0.1`).
- Full workflow: import + launch benchmark + compare.
- Local DB (Postgres via Compose) or SQLite override.
- Auth bypass available for dev only, guarded so it cannot be enabled in production builds (see `tech-stack.md` §10.7).
- Benchmark runner enabled (single-flight, in-process).
- Model endpoints and private benchmark paths available.
- Observability stack (Prometheus/Loki/Tempo/Grafana) via Compose.

### Hosted mode (`APP_MODE=hosted`)

- Public HTTPS API (Render Free).
- Auth required (Clerk JWT) for all personal data; anonymous read-only demo available.
- The anonymous demo is an immutable sanitized application fixture served by
  GET only; it has no database seed or mutation path.
- Import + compare + profile management only. **Runner disabled**; no localhost endpoint access.
- DB: Neon Free (or configured `DATABASE_URL`).
- CORS restricted to the GitHub Pages origin(s).
- No benchmark paths, no model endpoints, no local artifacts.
- Telemetry optional via Grafana Cloud Free.

### Capability matrix

| Capability | Local | Hosted |
|---|---|---|
| Sign in / out | Optional (bypass in dev) | Required for personal data |
| Import result JSON | Yes | Yes |
| Launch benchmark | Yes | No |
| Model profiles with endpoints | Yes | Metadata only (no endpoints) |
| Compare runs | Yes | Yes (own data) |
| Anonymous demo | Optional | Yes (read-only synthetic) |
| Benchmark runner | Enabled (single-flight) | Disabled |
| Local artifact references | Yes (local paths) | Stored as opaque text only |

### Mode enforcement

- `APP_MODE` is set at deploy time, not by request. The frontend may read a public `VITE_APP_MODE` for UI gating, but the backend never trusts it for authorization.
- Runner endpoints return `404`/`403` in hosted mode (not merely hidden in UI).
- Profile fields containing endpoints/credentials are rejected or stripped in hosted mode.
- A single codebase is used; mode is an env switch, not a fork.

## 3. Data isolation (hosted)

- Every personal row carries `owner_id` (Clerk `sub`), indexed.
- All queries filter by `owner_id` derived from the verified JWT, never from request body/path.
- Authorization tests prove IDOR resistance (changing record IDs cannot cross owners).
- Anonymous demo uses a separate read-only dataset with a sentinel owner (e.g. `demo`) and no write path.
- No cross-user sharing, teams, or public submissions in MVP.

## 4. Future extension (not MVP)

A securely connected local runner for hosted users is a possible future extension; it is not required and must not delay MVP. It would be a separate authenticated channel from a local agent to the hosted API, out of scope for this architecture.