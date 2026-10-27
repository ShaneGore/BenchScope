# Backend data model

Canonical entities. Types are indicative; final schema via Alembic. All personal entities carry `owner_id` (Clerk `sub`), indexed, and are queried with an owner filter derived from the verified JWT.

## User (logical, not stored)

Identity lives in Clerk. The backend does not store passwords. `owner_id = Clerk sub` is the foreign key used on owned rows. A local dev bypass uses a fixed id.

## ModelProfile

Represents a named model/configuration. Owned.

- `id` (uuid, pk)
- `owner_id` (string, indexed)
- `name` (string)
- `model_name` (string)
- `model_version` (string, nullable)
- `quantisation` (string, nullable)
- `endpoint_url` (string, nullable; local mode only; stripped/rejected in hosted mode)
- `hardware_notes` (text, nullable)
- `inference_config` (json, nullable) — optional benchmark-supported settings
- `created_at`, `updated_at`

## BenchmarkRun

One attempt (imported or launched). Owned.

- `id` (uuid, pk)
- `owner_id` (string, indexed)
- `source` (enum: `imported` | `launched`)
- `status` (enum: `running` | `completed` | `failed` | `interrupted`)
- `profile_id` (fk → ModelProfile, nullable) — snapshot taken at run time
- `profile_snapshot` (json) — model/hardware/config captured to preserve historical meaning
- `benchmark_config` (json, nullable) — allowlisted summary config for imported runs
- `source_run_id` (string, nullable) — benchmark's own run id
- `import_fingerprint` (string, nullable, unique per owner where present) — duplicate detection
- `benchmark_version` (string, nullable)
- `started_at`, `completed_at` (nullable), `elapsed_ms` (nullable)
- `quality_score` (numeric, nullable)
- `pass_rate` (numeric, nullable)
- `ttft_ms` (numeric, nullable)
- `prompt_tokens` (int, nullable)
- `output_tokens` (int, nullable)
- `prompt_throughput_tps` (numeric, nullable)
- `generation_throughput_tps` (numeric, nullable)
- `hardware_snapshot` (json, nullable) — CPU/GPU/RAM/VRAM/OS
- `error_category` (string, nullable)
- `error_message_sanitised` (text, nullable)
- `process_exit_code` (int, nullable)
- `artifact_ref` (string, nullable) — opaque reference to private local artifact; never served
- `related_run_id` (fk → BenchmarkRun, nullable) — retry lineage
- `created_at`, `updated_at`

## RunEvent (optional, for launched runs)

Timeline events for a launched run (status transitions, timeout). Owned via run.

- `id`, `run_id` (fk), `event_type`, `occurred_at`, `payload` (json, sanitised)

## DemoDataset (read-only, sentinel owner)

Synthetic runs stored with `owner_id = 'demo'` (or a separate table). Read-only endpoints; no writes from API.

## Metric nullability

All metric fields are nullable. Missing is distinct from zero; UI renders "unavailable". Aggregations exclude nulls and never coerce to 0.

## Indexes

- `(owner_id, created_at desc)` on BenchmarkRun
- `(owner_id, status)` on BenchmarkRun
- `(owner_id, import_fingerprint)` unique partial where not null
- `(owner_id, model_name)` for filtering

## Migrations

Alembic; one migration per change; reviewed. No destructive changes without a rollback migration. Integration tests run against Postgres to avoid dialect drift.

## PostgreSQL baseline

The initial SQLAlchemy 2 schema stores `ModelProfile` and `BenchmarkRun` only.
`RunEvent` remains optional and is not part of this baseline. The database uses
UUID primary keys, timezone-aware timestamps, JSON columns for the documented
snapshots/configuration, checked strings for run source/status, and the partial
unique `(owner_id, import_fingerprint)` index. `started_at` is required;
`completed_at` and every listed metric are nullable. Numeric precision and
metric semantics remain unspecified; no additional benchmark-derived columns
are introduced.

The v1 result importer stores only the normalized allowlist, optional
`source_run_id`, and a SHA-256 import fingerprint. It does not store raw request
bytes, prompts, generated code, private task identifiers, raw outputs,
credentials, events, artifacts, or error data.

The verified Clerk `sub` is the production owner key. Local development may use
the fixed owner `local` (`LOCAL_OWNER_ID`) only under the documented
development/local/loopback bypass guard; callers never supply ownership.
`endpoint_url` is the documented local-only endpoint reference; credentials are
not stored as separate fields or embedded in its value.