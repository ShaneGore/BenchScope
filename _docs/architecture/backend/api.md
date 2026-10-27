# Backend API contract

FastAPI-generated OpenAPI is the source of truth; TS types generated via `openapi-typescript` (CI or dev). All paths prefixed `/api/v1`.

## Conventions

- JSON only. Errors: `{ "detail": string | {field: msg} }`.
- Personal endpoints require a Clerk JWT verified through JWKS (signature,
  issuer, audience, and expiry); invalid credentials return a generic 401.
  Ownership comes only from the verified `sub`, except for the guarded fixed
  local-development identity.
- Auth: `Authorization: Bearer <Clerk JWT>` for personal endpoints. Anonymous demo endpoints require no auth.
- Pagination: `GET /runs?limit=&cursor=`; default limit 50, range 1–100.
  Run history is ordered by `started_at DESC, id DESC`; `next_cursor` is the UUID
  of the last returned run when another page exists. A cursor must resolve within
  the current owner and filter scope or the request returns a generic 422.
- Filtering: `?status=`, `?model=`, `?from=`, `?to=`.
  Run model matches `profile_snapshot.model_name` exactly. Status values are
  `running`, `completed`, `failed`, and `interrupted`. `from` and `to` require
  timezone-aware instants, normalize to UTC, and apply to `started_at`; `from` is
  inclusive, `to` is exclusive, and `from` must precede `to`.

## Endpoints

### Health
- `GET /health` — liveness (no auth).
- `GET /ready` — readiness (DB reachable).

### Profiles (auth required)
- `GET /profiles` — list own.
- `POST /profiles` — create.
- `GET /profiles/{id}` — get (owner check).
- `PATCH /profiles/{id}` — update (owner check).
- `DELETE /profiles/{id}` — delete (owner check; cascades? runs keep snapshot).

### Runs (auth required)
- `GET /runs` — list/filter runs for the authenticated owner.
- `GET /runs/{id}` — get own run; missing and other-owner IDs both return generic 404.
- `DELETE /runs/{id}` — delete own run; missing and other-owner IDs both return
  generic 404. Same-owner child runs have `related_run_id` cleared before deletion.
- `POST /runs/import` — import one strict `benchscope.run.v1` JSON run summary.
  A trusted exporter must normalize completed-run data before upload; private
  per-trial JSONL is not accepted and aggregate metrics are never derived here.
  The request requires a profile snapshot, named benchmark config, and
  timezone-aware start/end timestamps. Only `temperature`, `max_tokens`,
  `reasoning`, `mtp`, `ctx`, and `seed` are accepted as config settings.
  Canonical metrics may be omitted or null; values are passed through, never
  derived, and missing values remain null. Unknown fields are rejected at every
  level. The server assigns the authenticated owner, `source=imported`, and
  `status=completed`; imports have no profile foreign key, events, or artifacts.
  A provided `source_run_id` is hashed with a versioned namespace; otherwise a
  SHA-256 fingerprint is calculated from canonical JSON for the validated
  allowlisted request. Fingerprint uniqueness is scoped to the owner. Raw
  request bytes are not retained, logged, or echoed. JSON uploads are streamed
  up to `MAX_UPLOAD_BYTES` (default 1 MiB, configurable via Pydantic settings).
  Returns the existing `ImportResult` success shape (`201`) or errors (`409`
  duplicate, `413` too large, `422` malformed/unsupported/invalid request).
- `POST /runs/{id}/retry` — create a new attempt linked to a failed run (local mode only; hosted returns 403/404).

### Benchmark (local mode only)
- `GET /benchmark/capabilities` — anonymous, read-only response containing only
  `{ "enabled": boolean }`. It is true only when `APP_MODE=local` and
  `BENCHMARK_ENABLED=true`; it neither probes nor starts the runner and is not
  an authorization check.
- `POST /benchmark/runs` — start a run with UUID `{profile_id, config_id}`. Returns run id + `running`; 409 if a run is already active (the rejected request creates no row), 503 if no adapter is configured.
- `GET /benchmark/runs/{id}` — owner-scoped status and sanitized diagnostics.
- `POST /runs/{id}/retry` — retry an owned failed launched run, creating a distinct linked attempt.

Runner start/status/retry routes are not registered unless the server is local
and benchmarks are enabled (404 otherwise). The capability endpoint remains
available in every mode; frontend gating is presentation only.
The interim config UUID is opaque; no config catalog or private adapter mapping is claimed. Cancellation is not implemented or exposed; its semantics are deferred to #25.

### Demo (anonymous, read-only)
- `GET /demo/runs` — deterministic synthetic fixture records; no authentication,
  database seed, or write path.
- `GET /demo/runs/{id}` — one fixture record; unknown IDs return 404.
- Demo responses contain only synthetic profile/configuration metadata,
  timestamps, nullable metrics, and synthetic hardware values. They exclude
  personal owners, endpoints, credentials, artifacts, prompts, and diagnostics.

### Comparison
- `GET /runs/compare?ids=...` — requires at least two distinct comma-delimited UUIDs.
  The whole batch returns generic 404 if any ID is missing or not owned by
  the authenticated owner. Otherwise it returns only completed runs in input order;
  failed, interrupted, and running runs are excluded. Fewer than two completed
  runs returns 422. Null metrics remain null; no aggregation or zero coercion occurs.

## Ownership rules

- `owner_id` is derived only from the verified JWT subject, or the fixed
  `LOCAL_OWNER_ID` under the guarded local development bypass; never from
  request body/path/query.
- Import v1 assigns the authenticated owner; owner, source, status, profile FK,
  fingerprint, event and artifact fields are never accepted from the request.
- Every `{id}` lookup includes `WHERE owner_id = authenticated owner`; mismatch → 404
  (not 403, to avoid enumeration).
- Batch endpoints (compare) reject the complete request with a generic 404 if any
  ID is missing or not owned; no partial results are returned.
- Hosted profile endpoint fields are validated/stripped of `endpoint_url` and credentials.

## Rate limiting

Basic per-user/per-IP limits on import and benchmark start to prevent abuse; specifics TBD. Render's own limits apply.

## Versioning

`/api/v1`. Breaking changes require `/api/v2` or coordinated frontend release. OpenAPI exported to frontend build for type generation.
## Contract authority and drift

- Initial committed artifact: repository-root `openapi.yaml`, derived from the frontend service interface.
- Maintenance command: `cd frontend && pnpm gen:api` regenerates `frontend/src/types/api.generated.ts`.
- Drift check: `cd frontend && pnpm check:api` fails if generated types differ from the committed contract.
- FastAPI-generated OpenAPI becomes the authoritative source of truth after backend feature tasks land; reconcile `openapi.yaml` against it before #13 integrates the real API client.
