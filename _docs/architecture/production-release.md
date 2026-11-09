# Production release path and owner runbook

**Status: Neon provisioned; release path not provisioned.** As of 2026-11-09 the
Neon production project `benchscope-production` exists, its `production` branch
is at schema head `0008`, and the app has been exercised against it locally.
There is still no GitHub `production` environment, no production Render service,
no production Clerk application, and no `PRODUCTION_*` configuration. The
promotion workflow has never run. This document is the owner runbook and
evidence contract; it is not proof that a production deployment or rollback
occurred.

## Scope and honest description

The production target is a **course demonstration environment**, not
enterprise-grade commercial production. It uses:

- Render Free for the production API;
- Neon Free for the production database;
- Clerk Hobby with a separate Development application for synthetic
  authentication tests;
- a protected GitHub `production` environment and the existing manual
  `Promote Production` workflow.

The production API and database are separate from staging and use separate
credentials. Only synthetic smoke data is used. The free-tier services have no
SLA, can sleep or restart, have limited history and storage, and are explicitly
not marketed by their providers as production-grade.

## Current verified state

| Item | Verified state |
|---|---|
| `main` revision | `3e03a7b5208dae9ca6f411bdd3cc78e97b961a46` |
| Main CI | run `42619574144`; `backend`, `frontend`, `journey`, `container-images`, and `backend-windows` all succeeded |
| Staging API | `https://benchscope-staging-api.onrender.com`; `/version` returns `3e03a7b5208dae9ca6f411bdd3cc78e97b961a46`; `/health` returns HTTP 200; `/ready` returns `{"status":"ready"}` |
| Staging deployment | `Deploy Backend` run `42619781983` succeeded for `3e03a7b` |
| Public frontend | `https://shanegore.github.io/BenchScope/` returns HTTP 200; Pages deployment run `42619781869` succeeded for `3e03a7b` |
| Frontend source evidence | The Pages deployment record identifies the source SHA; the live static content is not SHA-stamped |
| Production environment | Absent (GitHub API returns 404) |
| Production configuration | No `PRODUCTION_*` secrets or variables are configured |
| Neon production project | `benchscope-production` (`long-leaf-22616183`); branch `production` is the default; Postgres 18; schema `0008_incident_repair_jobs`; two synthetic verification runs persisted |
| Promotion workflow | `.github/workflows/promote-production.yml` has never produced a run |
| Main ruleset | Active; PR plus the five required checks; strict checks; no bypass actors; **0 required approving reviews** |

The staging API is a real, independently SHA-verified deployment. It is
**not** the production target: it deploys automatically after successful `main`
CI, and the public frontend uses the same service.

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
| API | Existing Render Free web service | New Render Free web service, automatic deploys disabled |
| Database | Existing Neon Free project | New Neon Free project, separate credentials |
| Auth | Existing Clerk Development instance | New Clerk Development application, synthetic users only |
| Frontend | GitHub Pages, pointed at staging API | Not included; public Pages remains staging-backed |
| Deployment | Automatic after successful `main` CI | Manual `workflow_dispatch` with typed confirmation and `production` environment approval |
| Data | Demo/synthetic | Synthetic smoke data only; no staging data copy |

### Frontend decision

The public Pages frontend remains connected to the staging API and continues to
deploy automatically. This avoids disrupting the public demo and avoids turning
the frontend into an automatic production deployment. A separate production
frontend is **not** part of this demonstration.

The production release therefore covers the API and database. The production API
is verified directly through `/version`, `/health`, `/ready`, and the full
synthetic smoke test. The smoke test's frontend check only confirms that the
public Pages URL is reachable; it does **not** prove production frontend-to-API
connectivity. This limitation is intentional and must be stated in the release
evidence.

## GitHub production environment

Create one environment named `production` with:

- a selected-branch deployment policy allowing only `main`;
- the repository owner as the required reviewer;
- `prevent_self_review=false` (the owner is the sole reviewer);
- `can_admins_bypass=false`;
- no automatic deployment trigger.

The workflow remains `workflow_dispatch` only, requires the typed input
`confirm=promote`, and only runs from `refs/heads/main`. The selected `ref` input
may be `main`, a versioned tag, or an exact 40-character SHA; the checked-out
commit must be an ancestor of `main` and must have a successful `main` push CI
run for that exact SHA.

**Approval claim:** GitHub technically enforces the environment reviewer gate;
the job pauses until the owner approves. Because the owner is also the reviewer,
this is a **self-approval gate**, not independent second-person review. The main
ruleset still requires zero approving reviews, so independent code review is not
enforced and must not be claimed.

### Required environment settings

| Name | Kind | Purpose |
|---|---|---|
| `PRODUCTION_DATABASE_URL` | secret | Neon production **direct** URL, used for Alembic migrations |
| `PRODUCTION_RENDER_DEPLOY_HOOK_URL` | secret | Production Render deploy hook |
| `PRODUCTION_CLERK_SECRET_KEY` | secret | Mints short-lived synthetic smoke tokens |
| `PRODUCTION_SMOKE_API_URL` | variable | Production API origin, HTTPS |
| `PRODUCTION_SMOKE_FRONTEND_URL` | variable | Public Pages URL checked for reachability |
| `PRODUCTION_SMOKE_TEST_USER_A_ID` | variable | Synthetic Clerk user A |
| `PRODUCTION_SMOKE_TEST_USER_B_ID` | variable | Synthetic Clerk user B, distinct from A |

The obsolete `PRODUCTION_SMOKE_TEST_TOKEN` and
`PRODUCTION_SMOKE_OTHER_TEST_TOKEN` secrets are not used. Tokens are minted at
runtime with `scripts/generate_smoke_tokens.py`, the same testing-only Clerk API
used by staging. That API requires a Clerk **Development** instance and must not
be used with a Clerk Production instance.

## Owner provisioning checklist

No production resource may be created until the owner explicitly authorises it.
The owner must confirm free-tier capacity and that no payment method is required.
Stop at any payment-method or paid-upgrade prompt.

### 1. Render

Create one **Free** web service:

- Name: `benchscope-production-api` (or the nearest available name).
- Repository: `ShaneGore/BenchScope`; branch `main`.
- Runtime: Docker; Dockerfile `backend/Dockerfile`; build context `backend`.
- Instance type: **Free**.
- **Automatic deploys: disabled.** Deploy only through the deploy hook.
- Health check path: `/health`.
- Region: same region as the existing staging service where possible.

Set these runtime environment variables:

```text
APP_MODE=hosted
APP_ENV=production
HOST=0.0.0.0
DATABASE_URL=<production Neon pooled connection string>
CORS_ORIGINS=https://shanegore.github.io
CLERK_JWKS_URL=<production Clerk JWKS URL>
CLERK_ISSUER=<production Clerk issuer>
CLERK_AUTHORIZED_PARTIES=https://shanegore.github.io
BENCHMARK_ENABLED=false
```

Use the **pooled** Neon URL for Render application traffic. The
`PRODUCTION_DATABASE_URL` GitHub secret must be the **direct** URL instead,
because the promotion workflow runs migrations. Do not set `LOCAL_AUTH_BYPASS`.
Do not configure the AI repair worker, GitHub credentials, OpenRouter
credentials, or private benchmark paths on this service.
Confirm Render supplies `RENDER_GIT_COMMIT`; `/version` prefers `APP_REVISION`
and falls back to `RENDER_GIT_COMMIT`.

Create a deploy hook and store its URL only as the
`PRODUCTION_RENDER_DEPLOY_HOOK_URL` GitHub environment secret.

### 2. Neon

The project already exists as `benchscope-production` in `aws-eu-central-1`,
with its default branch named `production` and the default database `neondb`
(Postgres 18). The schema is at Alembic head `0008_incident_repair_jobs`.

`neon deploy` writes both connection strings to the git-ignored `.env.local`:

- `DATABASE_URL` — pooled (PgBouncer) URL for application traffic;
- `DATABASE_URL_UNPOOLED` — direct URL for migrations.

Set Render's `DATABASE_URL` to the **pooled** string. Store the **direct**
string only as the `PRODUCTION_DATABASE_URL` GitHub environment secret. Alembic
prefers `DATABASE_URL_UNPOOLED` when present and otherwise falls back to
`DATABASE_URL`, so local migration runs need no extra flag. Do not copy staging
data, and never run destructive migrations.

### 3. Clerk

Create one separate **Development** application:

- Name: `BenchScope Production` (or similar).
- Create two synthetic users, for example `smoke-a@example.com` and
  `smoke-b@example.com`; record both user IDs.
- Copy the issuer, JWKS URL, and secret key.
- Do not reuse the staging Clerk application.
- Do not change the staging Clerk configuration.
- Do not upgrade to a Clerk Production instance for this demonstration.

Use the owner's GitHub UI or local `gh secret set` to store the secret key. Never
paste secrets into chat, commit them, or place them in `VITE_*` variables.

### 4. GitHub

After explicit owner approval, the environment and non-secret variables can be
configured with GitHub CLI/API. Secrets are set by the owner through the GitHub
UI or an interactive local `gh secret set` prompt.

The environment payload should be equivalent to:

```json
{
  "can_admins_bypass": false,
  "prevent_self_review": false,
  "reviewers": [{"type": "User", "id": "<owner-user-id>"}],
  "deployment_branch_policy": {
    "protected_branches": false,
    "custom_branch_policies": true
  }
}
```

Then add a `main` deployment branch policy.

## Workflow behaviour

`.github/workflows/promote-production.yml` now:

- triggers only through `workflow_dispatch`;
- requires `confirm=promote` and `github.ref == refs/heads/main`;
- validates the selected ref format;
- requires `PRODUCTION_DATABASE_URL`, `PRODUCTION_RENDER_DEPLOY_HOOK_URL`,
  `PRODUCTION_CLERK_SECRET_KEY`, both smoke URLs, and both synthetic user IDs;
- rejects non-HTTPS smoke URLs, the staging API URL, and identical smoke users;
- uses deployment concurrency `production-release` with
  `cancel-in-progress: false`;
- has a 30-minute job timeout;
- checks out the selected revision and requires main ancestry;
- requires the latest `main` push CI run for the exact SHA to be successful;
- runs a bounded identity/deployment-verifier preflight;
- runs `alembic upgrade head` against the production database;
- triggers the Render deploy hook with `?ref=<selected-sha>`;
- waits for `/version` to match the selected SHA and `/ready` to be ready;
- mints fresh synthetic Clerk tokens at runtime;
- runs `scripts/smoke_test.py --mode full`, covering health, readiness,
  anonymous demo, authenticated access, synthetic import, persistence, run
  detail, comparison, and owner isolation.

The workflow fails closed. A failure before the deploy hook prevents deployment;
a failure after it leaves the new revision live, so the owner must follow the
rollback procedure and record the failed release.

## Release procedure

1. Confirm the selected full SHA is on `main` and has all five required CI checks
   green.
2. Confirm automatic staging deployment succeeded for the same SHA and record
   staging `/version`, `/ready`, workflow runs, and smoke evidence.
3. Trigger the promotion from `main`:

   ```powershell
   gh workflow run promote-production.yml --ref main -f confirm=promote -f ref=<selected-sha>
   ```

4. Approve the `production` environment deployment in GitHub. If no approval
   prompt appears, stop and inspect the environment; do not let the job continue.
5. Wait for the run to pass.
6. Independently verify and record:

   - production `GET /version` returns the selected SHA;
   - production `GET /health` and `/ready` succeed;
   - migrations completed;
   - the full synthetic smoke test passed, including import, persistence, run
     detail, comparison, and owner isolation;
   - the production deployment record shows the same SHA;
   - staging remains available and unchanged;
   - no secret appears in the logs.

7. Optionally create an annotated release tag only after successful verification.

## Rollback procedure

Use the existing promotion workflow to redeploy a previously verified,
schema-compatible revision. Do not introduce a separate rollback service or
database migration framework.

A safe demonstration pair is:

- current revision: the selected `main` SHA;
- rollback revision: `c47adc16aa3f4135a2cc1da81ff4cab16b6753b6`, the previous
  `main` revision, which has a successful `main` CI run and the same Alembic head
  (`0008`) as the current revision. The difference between those revisions is
  documentation only, so the rollback is schema-compatible.

Procedure:

1. Record the current production `/version` and deployment record.
2. Trigger promotion with the rollback SHA:

   ```powershell
   gh workflow run promote-production.yml --ref main -f confirm=promote -f ref=c47adc16aa3f4135a2cc1da81ff4cab16b6753b6
   ```

3. Approve the `production` environment deployment.
4. Verify `/version` returns the rollback SHA, `/ready` succeeds, the full smoke
   test passes, and previously imported synthetic runs still exist.
5. Restore the latest approved revision through the same workflow.
6. Verify `/version`, readiness, smoke, and the deployment record again.

Do **not** run `alembic downgrade` or any destructive database operation. If the
schema is incompatible, stop and keep the current revision; use a forward fix or
an approved database recovery procedure. Neon Free history and its single manual
snapshot are not a substitute for a production backup.

## Cost and free-tier limits

Current terms reviewed on 2026-11-09:

| Provider | Resource | Relevant limits | Cost |
|---|---|---|---|
| Render | Free Web Service | 0.1 CPU / 512 MB; sleeps after 15 minutes idle (~1 minute cold start); **750 instance-hours per workspace per month**, shared across free web services; shared bandwidth and build pipeline minutes; rollback only to the two most recent deploys | $0 within limits |
| Neon | Free project | 100 CU-hours per project per month; 1 GB storage per project and 20 GB account total; 5 GB egress per project; scale-to-zero after 5 minutes; 6-hour history; 1 manual snapshot | $0 within limits |
| Clerk | Hobby, Development application | 50,000 MRU per app; unlimited applications; no card | $0 within limits |
| GitHub | Public repository | Actions, Pages, environments, and required reviewers available for public repositories | $0 |

**Critical Render check:** 750 hours is roughly 31.25 service-days. One
always-awake service consumes about 720 hours in a 30-day month; two
always-awake services would exhaust the allowance around mid-month. The owner
must inspect the Render dashboard's monthly included usage before creating the
second service. If capacity is insufficient, stop and report the blocker rather
than provisioning paid infrastructure.

Render Free Postgres is not used: it allows only one database per workspace,
expires after 30 days, and has no backups.

Do not add a payment method or upgrade a plan for this demonstration. If a
provider requests payment details or a paid upgrade, stop.

## Security and privacy

- Production secrets are environment-scoped and available only after the
  `production` environment gate is approved.
- The workflow uses read-only `actions` and `contents` permissions.
- `generate_smoke_tokens.py` writes tokens only to `GITHUB_ENV`; it does not
  print them.
- The production database URL, Render deploy hook, and Clerk secret key are never
  placed in frontend variables, committed files, or logs.
- Production CORS is an explicit HTTPS origin, never a wildcard.
- Render provides HTTPS; Neon requires SSL.
- The smoke test verifies owner isolation by confirming that the second
  synthetic user cannot read the first user's run.
- Only synthetic smoke data is created. No customer, private, or benchmark data
  is copied or exposed.
- `BENCHMARK_ENABLED=false`; the AI repair worker is not hosted, not configured,
  and has no production credentials.

## Abort criteria

Stop before any side effect if:

- the owner has not authorised the target, environment, or promotion;
- the `production` environment has no required reviewer;
- the selected SHA is not an ancestor of `main`;
- the exact SHA has no successful `main` push CI run;
- any required production setting is missing;
- a smoke URL is not HTTPS or points at the staging API;
- the smoke users are not distinct;
- the identity preflight fails;
- production migrations fail;
- the deploy hook rejects the SHA;
- `/version` does not match within the verifier timeout;
- `/ready` is not ready;
- any smoke test fails;
- a secret or credential would be printed;
- Render or Neon reports a payment requirement or quota exhaustion.

## What this does not prove

- No production environment, API, database, promotion, or rollback exists yet.
- Workflow definitions and this runbook are not evidence of a successful
  production release.
- Render Free and Clerk Development are demonstration services, not
  enterprise-grade production infrastructure.
- The public frontend remains staging-backed; production frontend-to-API
  connectivity is not exercised.
- The environment reviewer gate is enforced by GitHub, but the sole owner reviews
  their own deployment; independent human review is not enforced.
- The main ruleset requires zero approving reviews.
- Database migrations are forward-only in this workflow; rollback is safe only
  between schema-compatible revisions.
- Neon Free history and its single manual snapshot are not a production backup.

## Evidence to record after execution

- CI run for the promoted SHA (all five checks).
- Automatic staging deployment run, staging `/version`, `/ready`, and smoke
  result.
- Manual production promotion run URL, actor, event, selected SHA, environment
  approval timestamp, and deployment record.
- Production `/version`, `/health`, `/ready`, migration result, and full smoke
  output.
- Rollback run URL, rollback `/version`, post-rollback verification, and the
  restored revision.
- Confirmation that staging remained available and unchanged.
- Sanitised Render/Neon usage evidence and the infrastructure diagram.
- Final documentation updates to `deployment.md`, `submission-checklist.md`, and
  `known-limitations.md`, including the provisional rubric assessment.

Do not record secrets, raw environment files, database connection strings, or
private data in the evidence.
