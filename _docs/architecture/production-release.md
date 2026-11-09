# Production release path and owner runbook

**Status: not provisioned.** As of 2026-11-09 there is no distinct production
target, no GitHub `production` environment, and no successful production
promotion. This document is an owner-approval runbook, not evidence that a
production release or rollback has occurred. Do not run the commands below
until the owner has approved the target, the environment protection rules, and
the release/rollback rehearsal.

## Current verified state

| Item | Verified state |
|---|---|
| `main` revision | `2be61f5cfc502a0425719f5f97705e716fb2061e` |
| Staging API | `https://benchscope-staging-api.onrender.com`; `/version` returns the exact `main` SHA and `/ready` returns `{"status":"ready"}` |
| Public frontend | `https://shanegore.github.io/BenchScope/` returns HTTP 200 |
| Staging deployment | `Deploy Backend` run at `2026-11-09T03:13:51Z` for `2be61f5`, completed successfully |
| Pages deployment | `Deploy GitHub Pages` run at `2026-11-09T03:13:51Z` for `2be61f5`, completed successfully |
| Promotion workflow | `.github/workflows/promote-production.yml` has never produced a run |
| GitHub environments | `staging` and `github-pages` allow only `main`; neither has required reviewers. `production` does not exist (API returns 404) |
| Production configuration | No `PRODUCTION_*` repository or environment variables/secrets are configured |
| Main branch rules | Active ruleset requires a pull request and the five CI checks, blocks deletion and non-fast-forward pushes, and has no bypass actors. Required approving reviews: 0 |
| Release tags | None |

The staging API is therefore a real, independently SHA-verified deployment.
It is **not** a production target: it deploys automatically after successful
`main` CI, and the public frontend uses the same service.

## Review findings

1. **Distinct production target:** No. The only live backend is the staging
   Render service. The promotion workflow names a `production` environment that
   does not exist and expects `PRODUCTION_*` settings that are not configured.
2. **Selected, tested revision:** The workflow is designed to do this. It
   accepts `main`, a versioned tag, or an exact SHA; requires the SHA to be an
   ancestor of `main`; requires the latest `main` push CI run for that exact SHA
   to be successful; runs a bounded identity preflight; applies migrations;
   triggers a Render deploy hook with `?ref=<sha>`; waits for `/version` to
   match; and runs smoke tests. None of this has been executed end to end.
3. **Explicit human action:** Partly. Promotion is a `workflow_dispatch` job
   with a typed `confirm=promote` input, but the `production` environment has no
   required reviewers. The workflow's environment gate is therefore not
   enforced and would fail or create an unprotected environment on first use.
4. **Independent source-SHA check:** Yes for the backend, via `/version` and the
   `wait_for_deployment.py` check. The frontend deployment record identifies the
   source SHA, but the live static content itself is not SHA-stamped or
   independently verified.
5. **Previous known-good revision:** The backend can be restored by re-running
   the promotion workflow with a known-good SHA, or by using Render's rollback.
   The frontend can be restored by re-running the Pages workflow with a
   known-good SHA. Neither rollback has been rehearsed. Database migrations are
   forward-only in the current workflow and are not automatically reversed.
6. **Environments and branch rules:** Main is protected by an active ruleset
   with the five CI checks and no bypass. Staging and Pages are main-only but
   have no required reviewers. A production environment with required reviewers
   and a main-only branch policy still has to be created.

## Smallest credible path

Use the already approved free providers, not a new platform:

- **Option A (recommended, distinct target):** add one free Render web service
  and one free Neon PostgreSQL database for production. Keep staging separate.
  Point the public Pages build at the production API. This is the clearest
  interpretation of a distinct production target and costs $0 at current free
  tiers, subject to provider terms.
- **Option B (absolute minimum, no new service):** treat the existing Render
  service and Pages site as production, disable automatic deploys, and require
  manual promotion. This uses existing infrastructure but removes the separate
  staging service and weakens the evidence that production was tested apart from
  staging.

The runbook below uses **Option A**. If the owner chooses Option B, substitute
the existing service URLs and record that staging is no longer separate.

## Owner decisions required

1. Approve Option A or Option B in writing.
2. Approve creating the `production` GitHub environment with a required
   reviewer. If a second trusted reviewer is available, set
   `prevent_self_review=true`; otherwise document owner self-review as a
   limitation.
3. Approve the production provider resources. Stop if Render, Neon, or Clerk
   requests payment details or a paid upgrade.
4. Decide whether the public Pages site should point at the production API. If
   yes, changing `VITE_API_URL` and redeploying Pages is a live setting change.
5. Decide how the production smoke token is refreshed. The current workflow
   expects a pre-minted read-only `PRODUCTION_SMOKE_TEST_TOKEN`; a short-lived
   token must be refreshed before each run. Runtime generation would require a
   Clerk Development instance and a workflow change.

## One-time setup (owner-approved)

### 1. Create and protect the `production` environment

Run from the repository root after confirming the owner decision. The reviewer
ID is the GitHub user ID, not the login.

```powershell
$ownerId = gh api user --jq .id
@"
{
  "prevent_self_review": false,
  "reviewers": [{"type": "User", "id": $ownerId}],
  "deployment_branch_policy": {
    "protected_branches": false,
    "custom_branch_policies": true
  }
}
"@ | Set-Content -Encoding utf8 production-environment.json
gh api --method PUT repos/ShaneGore/BenchScope/environments/production --input production-environment.json
gh api --method POST repos/ShaneGore/BenchScope/environments/production/deployment-branch-policies -f name=main
Remove-Item production-environment.json
gh api repos/ShaneGore/BenchScope/environments/production --jq '{name, protection_rules}'
```

The final command must show a required-reviewer rule. If it does not, stop;
do not promote.

### 2. Provision the production backend and database

Use the owner-approved free Render and Neon accounts. Record every URL and
resource name in the release evidence, never in a public issue.

- Create a Neon PostgreSQL database named for production. Keep it separate from
  staging. Store its pooled connection string as `PRODUCTION_DATABASE_URL`.
- Create a Render web service from this repository with **auto-deploy disabled**
  and deploy only through its deploy hook. Set:
  - `APP_MODE=hosted`
  - `APP_ENV=production`
  - `DATABASE_URL=<production Neon URL>`
  - `CORS_ORIGINS=https://shanegore.github.io`
  - `CLERK_JWKS_URL`, `CLERK_ISSUER`, `CLERK_AUTHORIZED_PARTIES` from the
    separate Clerk test application
  - `BENCHMARK_ENABLED=false`
- Confirm Render supplies `RENDER_GIT_COMMIT` so `/version` reports the deployed
  SHA.
- Store the deploy hook URL as `PRODUCTION_RENDER_DEPLOY_HOOK_URL`.
- Do not reuse the staging database, deploy hook, or Clerk application.

### 3. Configure GitHub production settings

```powershell
gh variable set PRODUCTION_SMOKE_API_URL --env production --body "https://<production-api-host>"
gh variable set PRODUCTION_SMOKE_FRONTEND_URL --env production --body "https://shanegore.github.io/BenchScope/"
gh secret set PRODUCTION_DATABASE_URL --env production
gh secret set PRODUCTION_RENDER_DEPLOY_HOOK_URL --env production
gh secret set PRODUCTION_SMOKE_TEST_TOKEN --env production
```

`PRODUCTION_SMOKE_TEST_TOKEN` is a read-only Clerk session token for one
synthetic test user. Refresh it immediately before each promotion. The workflow
does not currently generate it at runtime.

### 4. Point the public frontend at production (if approved)

The public Pages site is currently built with `VITE_API_URL` pointing at the
staging API. If the owner approves using Pages as the production frontend:

```powershell
gh variable set VITE_API_URL --body "https://<production-api-host>"
gh workflow run deploy-frontend.yml --ref main -f ref=main
```

This changes the public demo and removes the separate staging frontend. If the
owner wants to keep a staging frontend, do not change the variable; scope
production to the backend and record the frontend limitation.

## Release procedure

1. Select a full 40-character SHA from `main` with a successful `main` push CI
   run. Prefer a versioned tag created after the previous successful release.
2. Refresh `PRODUCTION_SMOKE_TEST_TOKEN` if it has expired.
3. Start the promotion from `main`:

   ```powershell
   gh workflow run promote-production.yml --ref main -f confirm=promote -f ref=<sha-or-tag>
   ```

4. Open the run and approve the `production` environment deployment. If GitHub
   does not show an approval prompt, stop and inspect the environment; do not
   let the job continue.
5. Wait for the workflow. It must pass:
   - selected ref validation and `main` ancestry;
   - successful `main` CI for the exact SHA;
   - deployment identity compatibility preflight;
   - production migrations;
   - SHA-pinned Render deploy;
   - `/version` and `/ready` verification;
   - production smoke tests.
6. Deploy the frontend from the same SHA if it is part of the release:

   ```powershell
   gh workflow run deploy-frontend.yml --ref main -f ref=<sha>
   ```

7. Verify independently and record:
   - `GET <production-api>/version` returns the exact SHA;
   - `GET <production-api>/ready` returns `{"status":"ready"}`;
   - the smoke output and run URL;
   - `gh api "repos/ShaneGore/BenchScope/deployments?environment=production&per_page=5"` shows the SHA;
   - the Pages deployment record shows the same SHA and the site returns HTTP 200.
8. Only after all checks pass, create and push an annotated release tag for the
   SHA, and record the tag, URLs, run IDs, and SHAs in the release evidence.

## Rollback procedure

1. Identify the last-known-good tagged SHA and its recorded successful
   deployment evidence.
2. Refresh the production smoke token if needed.
3. Re-run the promotion with the known-good SHA:

   ```powershell
   gh workflow run promote-production.yml --ref main -f confirm=promote -f ref=<known-good-sha>
   ```

4. Approve the `production` environment deployment.
5. Redeploy the frontend from the same known-good SHA:

   ```powershell
   gh workflow run deploy-frontend.yml --ref main -f ref=<known-good-sha>
   ```

6. Verify `/version`, `/ready`, smoke tests, the production deployment record,
   and the Pages record against the known-good SHA.
7. Database rollback: the workflow runs `alembic upgrade head` before deploying,
   so code rollback does not reverse schema changes. Take a logical backup before
   every promotion. If the failed release introduced an incompatible migration,
   stop and use a forward fix or the approved database recovery procedure. Do not
   rely on Neon Free history as a backup.
8. Record the rollback as a separate incident/release entry with its own run URL
   and verification output.

## Abort criteria

Stop before any side effect if any of these is true:

- the owner has not approved the target, environment, or promotion;
- the `production` environment has no required reviewer;
- the selected SHA is not an ancestor of `main`;
- the exact SHA has no successful `main` push CI run;
- the identity preflight fails;
- production secrets or variables are missing;
- the migration step fails or the pre-migration backup is absent;
- the deploy hook rejects the SHA;
- `/version` does not match within 300 seconds;
- `/ready` is not ready;
- any smoke test fails;
- the frontend deployment record does not match the promoted SHA;
- any secret or credential would be printed.

## What this does not prove

- No production target, environment, promotion, or rollback exists or has been
  executed.
- The workflow definition and its unit tests are not evidence of a working
  production release.
- The frontend's live content is not SHA-stamped; the deployment record is the
  current source-SHA evidence.
- The main ruleset requires zero approving reviews. Production approval is
  provided by the environment reviewer, not by a second code reviewer.
- Render Free is not a production-grade service; free-tier sleep, limits, and
  provider terms apply.
- Database migrations are forward-only here; rollback safety depends on a backup
  and backward-compatible schema changes.
