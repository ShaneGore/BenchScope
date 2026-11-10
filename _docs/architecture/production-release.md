# Production release path, promotion and rollback

**Status: provisioned and demonstrated (2026-11-10).** The production
demonstration API and database exist, the manual promotion workflow has run
successfully, and a rollback plus restoration rehearsal completed. This
document now records executed evidence as well as the owner runbook.

**Scope:** the production target is a **course demonstration environment**, not
enterprise-grade commercial production. It uses Render Free, Neon Free and a
Clerk **Development** application for synthetic smoke identities. The public
GitHub Pages frontend remains connected to **staging**; production is
backend/API-focused.

## Current verified state

Independently re-checked during Phase 4 on 2026-11-10:

| Item | Verified state |
|---|---|
| `main` revision | `dd8064ac6e3ebf505acb23fa01f5da051e07747f` |
| Main CI | run [`42714645314`](https://github.com/ShaneGore/BenchScope/actions/runs/42714645314) — `backend`, `frontend`, `journey`, `container-images`, `backend-windows` all successful |
| Staging API | `https://benchscope-staging-api.onrender.com`; `/version` returns `dd8064a…`; `/health` 200; `/ready` `{"status":"ready"}` |
| Staging deployment | `Deploy Backend` run [`42714879812`](https://github.com/ShaneGore/BenchScope/actions/runs/42714879812) succeeded at `dd8064a` |
| Public frontend | `https://shanegore.github.io/BenchScope/` returns HTTP 200; `Deploy GitHub Pages` run [`42714879726`](https://github.com/ShaneGore/BenchScope/actions/runs/42714879726) succeeded at `dd8064a`; the deployed JS references the staging API origin and contains no production API origin |
| Production API | `https://benchscope-production-api.onrender.com`; `/version` returns `dd8064a…`; `/health` 200; `/ready` `{"status":"ready"}` |
| Production database | Neon project `benchscope-production`; branch `production`; schema head `0008_incident_repair_jobs`; four synthetic runs with stable UUIDs (two `neon-verify-*`, two `smoke-test-run-*`) |
| Promotion | run [`42726216077`](https://github.com/ShaneGore/BenchScope/actions/runs/42726216077) succeeded for `dd8064a`; 13/13 smoke checks |
| Rollback rehearsal | rollback run [`42727553382`](https://github.com/ShaneGore/BenchScope/actions/runs/42727553382) to `ab6ea5d`; restore run [`42728234322`](https://github.com/ShaneGore/BenchScope/actions/runs/42728234322) to `dd8064a`; both 13/13 |
| Evidence record | <https://github.com/ShaneGore/BenchScope/issues/70#issuecomment-6755310213> |
| `production` environment | Present; custom branch policy; required reviewer `ShaneGore`; `prevent_self_review=false`; `can_admins_bypass=false` |
| Main ruleset | Active; pull request required; review-thread resolution; five required checks; strict policy; **0 required approving reviews** |
| Clerk production-demo app | `BenchScope Production` Development instance, issuer `https://closing-moray-6146.clerk.accounts.dev`; synthetic users only; no Production instance |

The staging and production APIs are separate Render services with separate
databases and separate credentials. Both currently report the same source
revision because production was restored to the approved `main` revision.

## Demonstration architecture

```
GitHub main (PR + five required CI checks)
   |
   +-- automatic after successful CI --> Render staging API --> Neon staging DB
   |                                          ^
   |                                          +-- GitHub Pages (staging API)
   |
   +-- manual workflow_dispatch (confirm=promote, production environment)
          --> Promote Production
                |-- selected SHA must be an ancestor of main and CI-green
                |-- alembic upgrade head --> Neon production DB
                |-- Render deploy hook ?ref=<SHA> --> Render production API
                +-- /version + /ready + full synthetic API smoke
```

| Component | Staging | Production demonstration |
|---|---|---|
| API | Render Free web service | Separate Render Free web service, automatic deploys disabled |
| Database | Neon Free project | Separate Neon Free project, separate credentials |
| Auth | Clerk Development instance | Separate Clerk Development application, synthetic users only |
| Frontend | GitHub Pages, pointed at staging API | Not included; public Pages remains staging-backed |
| Deployment | Automatic after successful `main` CI | Manual `workflow_dispatch` with typed confirmation and `production` environment approval |
| Data | Demo/synthetic | Synthetic smoke data only; no staging data copy |

### Frontend decision

The public Pages frontend remains connected to the staging API and continues to
deploy automatically. A separate production frontend is **not** part of this
demonstration. The production release covers the API and database, verified
through `/version`, `/health`, `/ready` and the authenticated synthetic smoke
suite. The smoke test's frontend check only confirms that the public Pages URL
is reachable; it does **not** prove production frontend-to-API connectivity.

## Promotion evidence (executed)

`Promote Production` is manual-only, requires `confirm=promote` and
`refs/heads/main`, and runs against the protected `production` environment.

| Field | Value |
|---|---|
| Workflow run | [`42726216077`](https://github.com/ShaneGore/BenchScope/actions/runs/42726216077) |
| Deployed revision | `dd8064ac6e3ebf505acb23fa01f5da051e07747f` |
| Trigger | `workflow_dispatch` from `main` |
| Approval | Protected `production` environment gate |
| Result | Success; 13/13 smoke checks |
| Side effects | Alembic `upgrade head` on the production database; SHA-targeted Render deploy |
| Staging | Unchanged and available |

Verification performed by the workflow: exact-SHA CI eligibility, main
ancestry, migration outcome, `/version` match, `/ready`, minted short-lived
Clerk tokens, full authenticated smoke test including cross-user owner
isolation.

### Earlier failed promotion attempts (historical)

These are preserved because they explain the hardening in PR #68 and the
configuration correction in PR #73:

- `42721658749` — failed on migration URL parsing.
- `42725097570` — failed because the Clerk secret key had been stored masked
  with a trailing `…` (U+2026) characters, so token minting failed.
- `42726216077` — succeeded after the corrected secret and workflow.

## Rollback and restoration evidence (executed)

The rollback path is re-running promotion with a previously verified,
schema-compatible SHA. It never runs `alembic downgrade`.

| Step | Revision | Run | Result |
|---|---|---|---|
| Rollback | `ab6ea5dc10d18059071f06696478edc0b1c46284` | [`42727553382`](https://github.com/ShaneGore/BenchScope/actions/runs/42727553382) | Success; 13/13 smoke |
| Restore | `dd8064ac6e3ebf505acb23fa01f5da051e07747f` | [`42728234322`](https://github.com/ShaneGore/BenchScope/actions/runs/42728234322) | Success; 13/13 smoke |

Both runs required `production` environment approval and both kept the schema at
`0008_incident_repair_jobs`. The four synthetic run UUIDs present before the
rehearsal were still present afterwards, and staging was unchanged.

Each run's `head_sha` is `dd8064a…` because that is the workflow definition
revision; the **deployed** revision is the `ref` input, which was `ab6ea5d` for
the rollback and `dd8064a` for the restore. Each run logged 13 `PASS:` smoke
lines and "Smoke tests completed successfully".

### Historical rollback candidate

`c47adc16aa3f4135a2cc1da81ff4cab16b6753b6` was the *proposed* rollback revision
in the original runbook. It is **not** the revision that was actually
demonstrated. It was superseded by `ab6ea5d` because `ab6ea5d` was the
immediately preceding approved `main` revision at rehearsal time and differed
from `dd8064a` only in documentation. Treat `c47adc1` as historical context
only.

### Limits of the rollback rehearsal

- This was an **application revision** rollback between schema-compatible
  revisions. No database downgrade, restore or data migration was performed.
- Render's free tier retains only a small number of recent deploys; the
  rehearsal relied on a SHA-pinned deploy hook, not a dashboard rollback.
- Neon Free history and its single manual snapshot are **not** a backup or a
  point-in-time-recovery substitute.
- The workflow runs `alembic upgrade head` before every deploy, including a
  rollback. A rollback target must therefore have an Alembic head compatible
  with the current database schema.

## Workflow behaviour

`.github/workflows/promote-production.yml`:

- triggers only through `workflow_dispatch`;
- requires `confirm=promote` and `github.ref == refs/heads/main`;
- accepts `main`, a versioned tag, or a full lowercase 40-character SHA, and
  requires the checked-out commit to be an ancestor of `main`;
- requires the latest `main` **push** CI run for that exact SHA to be
  successful (pull-request CI does not qualify);
- uses deployment concurrency `production-release` with
  `cancel-in-progress: false` and a 30-minute job timeout;
- runs a bounded identity/deployment-verifier preflight;
- runs `alembic upgrade head` against `PRODUCTION_DATABASE_URL`;
- triggers the Render deploy hook with `?ref=<selected-sha>`;
- waits for `/version` to match the selected SHA and `/ready` to be ready;
- mints fresh synthetic Clerk tokens at runtime;
- runs `scripts/smoke_test.py --mode full`, covering health, readiness,
  anonymous demo, authenticated access, synthetic import, persistence, run
  detail, comparison and owner isolation.

The workflow fails closed before the deploy hook on configuration, ancestry,
CI, preflight or migration errors. A failure after the hook leaves the new
revision live, so the owner must roll back and record the failed release.

## Required environment settings (configured)

| Name | Kind | Purpose |
|---|---|---|
| `PRODUCTION_DATABASE_URL` | secret | Neon production **direct** URL for Alembic migrations |
| `PRODUCTION_RENDER_DEPLOY_HOOK_URL` | secret | Production Render deploy hook |
| `PRODUCTION_CLERK_SECRET_KEY` | secret | Mints short-lived synthetic smoke tokens |
| `PRODUCTION_SMOKE_API_URL` | variable | Production API origin, HTTPS |
| `PRODUCTION_SMOKE_FRONTEND_URL` | variable | Public Pages URL checked for reachability |
| `PRODUCTION_SMOKE_TEST_USER_A_ID` | variable | Synthetic Clerk user A |
| `PRODUCTION_SMOKE_TEST_USER_B_ID` | variable | Synthetic Clerk user B, distinct from A |

The obsolete `PRODUCTION_SMOKE_TEST_TOKEN` and
`PRODUCTION_SMOKE_OTHER_TEST_TOKEN` secrets are unused. Tokens are minted at
runtime with `scripts/generate_smoke_tokens.py`. That Clerk API is
testing-only and requires a Development instance.

Render's runtime variables (names only): `APP_MODE=hosted`, `APP_ENV=production`,
`HOST`, `DATABASE_URL` (pooled Neon URL), `CORS_ORIGINS`,
`CLERK_JWKS_URL`, `CLERK_ISSUER`, `CLERK_AUTHORIZED_PARTIES`,
`BENCHMARK_ENABLED=false`. `CORS_ORIGINS` and `CLERK_AUTHORIZED_PARTIES` must be
JSON arrays of origins, for example `["https://shanegore.github.io"]`; comma
strings and origins with paths are rejected. Never set `LOCAL_AUTH_BYPASS`.
Never configure the AI repair worker, GitHub credentials, OpenRouter
credentials or private benchmark paths on the production service.

## Release procedure (reusable)

1. Confirm the selected full SHA is on `main` with all five required CI checks
   green.
2. Confirm automatic staging deployment succeeded for the same SHA and record
   staging `/version`, `/ready` and smoke evidence.
3. Trigger the promotion from `main`:

   ```powershell
   gh workflow run promote-production.yml --ref main -f confirm=promote -f ref=<40-char-sha>
   ```

4. Approve the `production` environment deployment in GitHub.
5. Wait for the run to pass.
6. Independently verify and record: production `/version` matches, `/health` and
   `/ready` succeed, migrations completed, 13/13 smoke passed, the deployment
   record shows the same SHA, staging is unchanged, and no secret appears in
   logs.

## Rollback procedure (reusable)

1. Record the current production `/version` and deployment record.
2. Choose a previously verified revision whose Alembic head is compatible with
   the live schema.
3. Trigger promotion with that SHA and approve the `production` environment.
4. Verify `/version` returns the rollback SHA, `/ready` succeeds, the full smoke
   test passes, and previously imported synthetic runs still exist.
5. Restore the approved revision through the same workflow and verify again.
6. Do **not** run `alembic downgrade` or any destructive database operation. If
   the schema is incompatible, stop and keep the current revision.

## Approval model — honest description

GitHub technically enforces the `production` environment reviewer gate: the job
pauses until approved. Because the repository owner is also the sole reviewer,
this is a **self-approval gate**, not independent second-person review. The main
ruleset requires zero approving reviews, so independent code review is
procedural rather than enforced.

## Cost and free-tier limits

Limits reviewed on 2026-11-09; recheck current provider terms before relying on
them.

| Provider | Resource | Relevant limits | Cost |
|---|---|---|---|
| Render | Free Web Service | 0.1 CPU / 512 MB; sleeps after 15 minutes idle; 750 instance-hours per workspace per month shared across free services; few retained deploys | $0 within limits |
| Neon | Free project | 100 CU-hours/project/month; 1 GB/project; 5 GB egress; scale-to-zero; 6-hour history; 1 manual snapshot | $0 within limits |
| Clerk | Hobby, Development application | 50,000 MRU per app; no card | $0 within limits |
| GitHub | Public repository | Actions, Pages, environments, required reviewers | $0 |

Two always-awake Render Free services can exhaust the shared 750-hour monthly
allowance. This project relies on free-tier sleep and does not keep both awake
continuously.

## Security and privacy

- Production secrets are environment-scoped and only available after the
  `production` environment gate is approved.
- The workflow uses read-only `actions` and `contents` permissions.
- `generate_smoke_tokens.py` writes tokens only to `GITHUB_ENV` and does not
  print them.
- The production database URL, Render deploy hook and Clerk secret key are never
  placed in frontend variables, committed files or logs.
- Production CORS is an explicit HTTPS origin, never a wildcard.
- The smoke test verifies owner isolation by confirming that user B cannot read
  user A's run.
- Only synthetic smoke data is created. No customer, private or benchmark data
  is copied or exposed.
- `BENCHMARK_ENABLED=false`; the AI repair worker is not hosted, not configured
  and holds no production credentials.

## Abort criteria

Stop before any side effect if:

- the target, environment or promotion is not authorised;
- the `production` environment has no required reviewer;
- the selected SHA is not an ancestor of `main` or lacks exact-SHA `main` CI;
- any required production setting is missing;
- a smoke URL is not HTTPS or points at the staging API;
- the smoke users are not distinct;
- the identity preflight, migrations or deploy hook fail;
- `/version` does not match within the verifier timeout or `/ready` is not ready;
- any smoke check fails;
- a secret or credential would be printed;
- Render or Neon reports a payment requirement or quota exhaustion.

## What this does not prove

- The production demonstration is a **course environment**, not an
  enterprise-grade system; free tiers have no SLA.
- The public frontend remains staging-backed; production frontend-to-API
  connectivity is not exercised.
- The environment reviewer gate is a **self-approval** gate.
- The main ruleset requires zero approving reviews.
- Migrations are forward-only; rollback is safe only between schema-compatible
  revisions, and no database rollback was performed.
- Neon Free history and its manual snapshot are not a production backup.
- Hosted AI repair is disabled; the demonstrated repair/recovery was supervised
  in a disposable environment.
