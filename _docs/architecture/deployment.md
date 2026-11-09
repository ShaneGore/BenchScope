# Deployment design and readiness

This document describes the hosted layout and the manual production-release
path. As of 2026-11-09 the Pages frontend and the Render staging API are
deployed and SHA-verified from `main`. The production demonstration is
**prepared but not provisioned**: there is no GitHub `production` environment,
no production Render service, no production Neon database, no production Clerk
application, and no production promotion or rollback. See
[production-release.md](./production-release.md) for the simplified architecture,
owner checklist, and exact release/rollback runbook.

The production target is a **course demonstration environment**, not
enterprise-grade production. It uses Render Free, Neon Free, and a Clerk
Development application, and it hosts only synthetic smoke data. The public
GitHub Pages frontend remains connected to staging.

On 2026-10-27 the owner approved GitHub Pages for the public static frontend,
Render Free for the API, Neon Free for a disposable database, and Clerk Hobby
only if provisioning remains $0 and requires no payment method. Use synthetic
data and test identities only. Stop if a provider requests payment details or a
paid upgrade. Do not create production resources without explicit owner
approval.

## Hosted layout

| Component | Staging | Production demonstration |
|---|---|---|
| Static frontend | GitHub Pages, pointing at the staging API | Not included; public Pages remains staging-backed |
| API | Existing Render Free web service | New Render Free web service, automatic deploys disabled |
| Database | Existing Neon Free project | New Neon Free project, separate credentials |
| Authentication | Existing Clerk Development instance | New Clerk Development application, synthetic users only |
| Deployment | Automatic after successful `main` CI | Manual `workflow_dispatch` with typed confirmation and `production` environment approval |

GitHub Pages cannot run the backend, database, or benchmark runner. The
browser's `VITE_API_URL` must point to the approved API origin. The API's
`CORS_ORIGINS` must be an explicit allowlist of the deployed Pages origin(s),
without wildcards. Local development continues to use the root Vite path and
local API. Do not publish a frontend build until its API URL and hosted auth
configuration are available; an unusable or misconfigured public site is not
a successful deployment.

## Build and configuration boundaries

- `frontend/Dockerfile` builds from `frontend/` using `pnpm-lock.yaml` and
  serves only the generated static files with nginx. It contains no API server.
- `backend/Dockerfile` builds from `backend/` and copies the FastAPI runtime,
  Alembic files, and production dependencies only. The build context excludes
  tests, local environments, secrets, and private benchmark artifacts.
- CI builds both images for pull requests and pushes to `main`; it does not log
  in to a registry, push images, or upload artifacts.
- GitHub Pages needs a static build, not the frontend container. Set
  `VITE_BASE_PATH` from repository/deployment configuration to the approved
  Pages path (for a project site, a path such as `/<repo>/`). No repository
  name is hard-coded. The local default is `/`. The API endpoint is supplied
  separately as `VITE_API_URL`; both values are public build-time
  configuration. Changing either requires rebuilding the static output.
- Public frontend configuration can include `VITE_APP_MODE=hosted`,
  `VITE_CLERK_PUBLISHABLE_KEY`, `VITE_BASE_PATH`, and `VITE_API_URL`.
  `VITE_API_URL` and Clerk publishable keys are not secrets. Never put API
  credentials, Clerk secret keys, database URLs, private endpoints, or other
  secrets in `VITE_*` variables, static files, or frontend build logs.
- `.github/workflows/pages-deploy.yml` is manual-only and deploys only from
  `main`. It requires repository variables `VITE_API_URL` (a public HTTPS API
  URL) and `VITE_CLERK_PUBLISHABLE_KEY`; the workflow checks these before
  building. It publishes only the static frontend and does not provision or
  deploy the API.
- `.github/workflows/deploy-frontend.yml` supports automatic `workflow_run`
  deployments from successful CI and manual deployments. A manual run accepts
  `ref=main` or a full 40-character commit SHA from `main` history; the
  workflow verifies the SHA with GitHub's compare API before checkout. It
  preserves HTTPS API validation, the repository Pages base path, Clerk
  public-key configuration, environment protection, and Pages deployment
  permissions.
- Hosted backend configuration currently requires `APP_MODE=hosted`, `HOST`,
  `DATABASE_URL`, `CORS_ORIGINS`, `CLERK_JWKS_URL`, `CLERK_ISSUER`, and
  `CLERK_AUTHORIZED_PARTIES`. Configure `HOST` as the provider-required public bind
  address (commonly `0.0.0.0`) and set the service port using the name the
  selected provider supports; the application setting is `PORT` (default
  `8000`). `DATABASE_URL` and any provider credentials belong only in the
  backend host's secret configuration. Clerk issuer, JWKS URL, and authorized
  parties are backend-only configuration. `CLERK_AUDIENCE` is not used. Set
  `BENCHMARK_ENABLED=false`; the application only enables its runner when
  `APP_MODE=local`, regardless of this flag.
- `APP_ENV` defaults to `production`; `MAX_UPLOAD_BYTES` defaults to 1 MiB.
  These may be explicitly set on the backend if their defaults are unsuitable.
  Backend deployment CI requires `DATABASE_URL`, `RENDER_DEPLOY_HOOK_URL`, and
  `CLERK_SECRET_KEY` as GitHub Actions secrets, plus the smoke-test user IDs and
  public frontend variables listed above. No secret belongs in frontend build
  configuration.
## Smoke-test credentials

- Staging uses the GitHub Actions secret `CLERK_SECRET_KEY` and the variables
  `SMOKE_TEST_USER_A_ID` and `SMOKE_TEST_USER_B_ID`.
- The production environment uses the secret `PRODUCTION_CLERK_SECRET_KEY` and
  the variables `PRODUCTION_SMOKE_TEST_USER_A_ID` and
  `PRODUCTION_SMOKE_TEST_USER_B_ID`.
- Both `.github/workflows/deploy-backend.yml` and
  `.github/workflows/promote-production.yml` mint fresh, short-lived Clerk
  session tokens at runtime with `scripts/generate_smoke_tokens.py`. The
  obsolete pre-minted `SMOKE_TEST_TOKEN`, `SMOKE_OTHER_TEST_TOKEN`,
  `PRODUCTION_SMOKE_TEST_TOKEN`, and `PRODUCTION_SMOKE_OTHER_TEST_TOKEN` secrets
  are not required.
- The token-generation API is testing-only and requires a Clerk Development
  instance; it must not be used with a Production instance. The production
  demonstration therefore uses a separate Clerk Development application.
- `VITE_CLERK_PUBLISHABLE_KEY` remains a public frontend build-time variable
  for GitHub Pages.
- Render's runtime Clerk settings (`CLERK_JWKS_URL`, `CLERK_ISSUER`, and
  `CLERK_AUTHORIZED_PARTIES`) are configured separately in the Render service
  and are not GitHub Actions secrets. `CLERK_AUDIENCE` is not used.


## Runtime, persistence, and migrations

Current code behavior is limited to the following known facts:

- `/health` reports process health; `/ready` checks whether the configured
  database is reachable. Both are live-verified on staging. They have not yet
  been exercised against the production demonstration service.
- The hosted settings validator requires a PostgreSQL `DATABASE_URL`, a
  non-empty CORS allowlist, a public bind host, and all three Clerk settings.
  Wildcard CORS origins are rejected in hosted mode.
- The hosted migration procedure is now selected: the manual promotion workflow
  runs `alembic upgrade head` against `PRODUCTION_DATABASE_URL` before triggering
  the deploy hook. It has not yet been exercised against a production database.
  Migrations are forward-only in this workflow; rollback is safe only between
  schema-compatible revisions.
- Application records are stored through the configured database. The selected
  API host's filesystem persistence, restart behavior, cold starts, quotas, and
  database plan limits are provider-dependent. Render Free may sleep or restart;
  do not rely on API-local files for durable user data.
- Provider limits were checked against current official documentation on
  2026-11-09, but the owner's account capacity has not been verified. Confirm
  Render's shared monthly instance-hour usage, Neon project limits, and Clerk
  Hobby eligibility before provisioning.

## Automatic staging and manual production promotion

1. Keep development local; review a pull request and require its `backend`,
   `frontend`, `journey`, `container-images`, and `backend-windows` checks to
   pass.
2. Staging deploys automatically after a successful `main` CI run. The public
   Pages frontend remains connected to the staging API and continues to deploy
   automatically.
3. Production is a separate Render Free API and Neon Free database. The public
   Pages frontend is not part of the production release, so production
   frontend-to-API connectivity is not exercised. The production API is verified
   directly.
4. The manual promotion workflow requires the `production` GitHub environment,
   typed `confirm=promote`, a selected `main`-ancestor SHA or tag with a
   successful exact-SHA `main` CI run, and the environment-scoped settings below.
5. The workflow uses `concurrency: production-release` (no cancellation), a
   30-minute timeout, and fails closed on missing configuration, a staging API
   URL, non-HTTPS smoke URLs, identical smoke users, failed identity preflight,
   failed migrations, a failed deploy hook, a `/version` mismatch, or failed
   smoke tests.
6. After deployment it mints fresh synthetic Clerk tokens and runs
   `scripts/smoke_test.py --mode full`, covering health, readiness, anonymous
   demo, authenticated access, synthetic import, persistence, run detail,
   comparison, and owner isolation.

### Production environment settings

- Secrets: `PRODUCTION_DATABASE_URL`,
  `PRODUCTION_RENDER_DEPLOY_HOOK_URL`, `PRODUCTION_CLERK_SECRET_KEY`.
- Variables: `PRODUCTION_SMOKE_API_URL`, `PRODUCTION_SMOKE_FRONTEND_URL`,
  `PRODUCTION_SMOKE_TEST_USER_A_ID`, `PRODUCTION_SMOKE_TEST_USER_B_ID`.
- The `production` environment should allow only `main`, require the owner as
  reviewer, allow self-review (sole owner), disallow admin bypass, and have no
  automatic deployment trigger.

Missing values are identified by name without printing their contents. The
environment gate is technically enforced by GitHub, but because the owner is the
sole reviewer it is a self-approval gate, not independent second-person review.
The main ruleset still requires zero approving reviews.

As of 2026-11-09 none of those settings exists and the `production` environment
has not been created, so the workflow has never run. Creating the environment
and the production target requires the owner approval described in
[production-release.md](./production-release.md).

### Promotion guards

Promotion accepts `main`, `refs/heads/main`, a versioned `v...` tag (optionally
prefixed with `refs/tags/`), or a full lowercase 40-character commit SHA.
The checked-out commit must exist and be in main's history before any code
from it is executed. The workflow also requires the latest run of the
repository's `.github/workflows/ci.yml` for that exact SHA to be a completed,
successful `push` run on `main`; pull-request CI does not qualify. It uses
read-only Actions access, rejects missing, pending, unsuccessful, malformed,
unavailable, or more than 100 matching runs, and fails closed on API errors.
A successful run reflects the CI definition at that revision, not an
independent guarantee that its checks were adequate; protecting main and
reviewing changes to CI remain necessary.

After these checks, the workflow installs the selected revision's locked
development dependencies. Before migration or deployment, a bounded local check
starts the actual app in isolated local test configuration with no database URL,
benchmark execution disabled and socket connections blocked. It sends in-process
HTTP requests to `/version` with synthetic revision values, and exercises the
deployment verifier against synthetic ready, wrong-revision and not-ready
responses. A failed or unsupported preflight fails closed. The checked-out SHA
is used for the deploy hook, the readiness/revision check, and the smoke test.
These guards do not constitute owner approval or evidence that production
deployment has been exercised.

### Rollback

1. Identify the current production SHA and a previously verified,
   schema-compatible SHA. A safe demonstration pair is the current `main` SHA
   and `c47adc16aa3f4135a2cc1da81ff4cab16b6753b6`, which has a successful `main`
   CI run and the same Alembic head (`0008`); the difference is documentation
   only.
2. Re-run the promotion workflow with the rollback SHA and approve the
   `production` environment.
3. Verify `/version`, `/ready`, the full smoke test, and that previously
   imported synthetic data still exists.
4. Restore the latest approved revision through the same workflow and verify
   again.
5. Do not run `alembic downgrade` or a destructive database operation. If the
   schema is incompatible, stop and keep the current revision; use a forward fix
   or an approved database recovery procedure.
6. Neon Free history and its single manual snapshot are not a production backup.

The staging API and Pages frontend have been deployed from `main`, and the
staging `/version` endpoint matched the source SHA on 2026-11-09. No production
promotion, production health/readiness check, production migration, production
smoke test, production rollback, or recreation has been exercised. Record
production URLs and rehearsal results in the release evidence; do not mark them
complete until verified.

## Provider terms to recheck before provisioning

Current documented free-tier limits were checked on 2026-11-09; they do not
guarantee that account onboarding will avoid a payment-method prompt. Stop at
any such prompt. Do not add a provider or fallback outside the approved list.

- Render Free web services sleep after 15 minutes without inbound traffic and
  take about a minute to start again. Free web services share a 750
  instance-hour monthly workspace allowance. One always-awake service consumes
  about 720 hours in a 30-day month; two always-awake services can exhaust the
  allowance around mid-month. Check the Render dashboard's monthly included
  usage before creating the production service. Free Render Postgres expires
  after 30 days and has no backups; do not use it.
- Neon Free is permanent and does not require a credit card according to its
  pricing page. Limits include 100 CU-hours/project, 1 GB/project, 20 GB account
  total, 5 GB egress/project, scale-to-zero after five minutes, a six-hour
  history window, and one manual snapshot; Instant Restore is not included. Do
  not treat this as backup/PITR.
- Clerk Hobby is free and does not require a credit card according to its
  pricing page; the current allowance is 50,000 MRUs per app. Use a separate
  Development application for the production demonstration. The testing-only
  session-token API requires a Development instance and must not be used with a
  Production instance.

- GitHub Pages eligibility, terms, and usage restrictions:
  [GitHub Pages documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages)
  and [GitHub Pages limits](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits).
- Render free-tier service behavior:
  [Render free instances](https://render.com/docs/free) and
  [Render deploys and rollbacks](https://render.com/docs/deploys#rollback-a-deploy).
- Neon plan limits:
  [Neon pricing](https://neon.com/pricing).
- Clerk plan limits:
  [Clerk pricing](https://clerk.com/pricing).

Do not treat earlier free-tier descriptions or numbers elsewhere in the
repository as verified current terms.

## Render deploy-hook revision control

When triggering a Render deploy hook from GitHub Actions, append `?ref=<commit-sha>` to the hook URL. Render supports deploying a specific commit with this parameter. Configure the Render service so automatic deploys from the linked branch cannot overwrite a deliberately pinned release; use the deploy hook as the controlled deployment trigger.
