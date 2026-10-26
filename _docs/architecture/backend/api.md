# Backend API contract

FastAPI-generated OpenAPI is the source of truth; TS types generated via `openapi-typescript` (CI or dev). All paths prefixed `/api/v1`.

## Conventions

- JSON only. Errors: `{ "detail": string | {field: msg} }`.
- Auth: `Authorization: Bearer <Clerk JWT>` for personal endpoints. Anonymous demo endpoints require no auth.
- Pagination: `?limit=&cursor=` (cursor-based) where lists grow; default limit 50.
- Filtering: `?status=`, `?model=`, `?from=`, `?to=`.

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
- `GET /runs` — list/filter own.
- `GET /runs/{id}` — get (owner check).
- `DELETE /runs/{id}` — delete own.
- `POST /runs/import` — import a result JSON (multipart or JSON). Validates, normalises, dedups by fingerprint. Returns created run or `409` on duplicate.
- `POST /runs/{id}/retry` — create a new attempt linked to a failed run (local mode only; hosted returns 403/404).

### Benchmark (local mode only)
- `POST /benchmark/runs` — start a run with `{profile_id, config}`. Returns run id + status. 409 if a run is already active (single-flight).
- `GET /benchmark/runs/{id}` — status + events.
- `POST /benchmark/runs/{id}/cancel` — request cancellation.

In hosted mode these routes are not registered (404).

### Demo (anonymous, read-only)
- `GET /demo/runs` — synthetic dataset.
- `GET /demo/runs/{id}`.

### Comparison
- `GET /runs/compare?ids=...` — returns completed runs with metric series for charting (owner-scoped; rejects IDs not owned).

## Ownership rules

- `owner_id` is always taken from the verified JWT, never request body/path.
- Every `{id}` lookup includes `WHERE owner_id = current_owner`; mismatch → 404 (not 403, to avoid enumeration).
- Batch endpoints (compare) filter the provided IDs by owner; unowned IDs are silently dropped or rejected (decide at implementation; document).
- Hosted profile endpoint fields are validated/stripped of `endpoint_url` and credentials.

## Rate limiting

Basic per-user/per-IP limits on import and benchmark start to prevent abuse; specifics TBD. Render's own limits apply.

## Versioning

`/api/v1`. Breaking changes require `/api/v2` or coordinated frontend release. OpenAPI exported to frontend build for type generation.