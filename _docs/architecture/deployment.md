# Deployment design and readiness

This document describes an owner-approved non-production test layout, not an
active deployment. Issue #20 adds local image builds and a Pages-ready Vite
build only. On 2026-10-27 the owner approved GitHub Pages for the public static
frontend, Render Free for the API, Neon Free for a disposable database, and
Clerk Hobby only if provisioning remains $0 and requires no payment method.
Use synthetic data and test identities only. Stop if a provider requests
payment details or a paid upgrade. No service is provisioned yet.

## Hosted layout

| Component | Candidate | What it serves |
|---|---|---|
| Static frontend | GitHub Pages | Public Vite build only; never the FastAPI API |
| API | Render web service | Separately hosted FastAPI container |
| Database | Neon PostgreSQL | Persistent application records through `DATABASE_URL` |
| Authentication | Clerk, if enabled | Frontend sign-in; API verifies Clerk JWTs |

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

- `CLERK_SECRET_KEY` is a GitHub Actions secret used only by the backend
  deployment workflow to mint fresh smoke-test credentials.
- `SMOKE_TEST_USER_A_ID` and `SMOKE_TEST_USER_B_ID` are GitHub Actions
  variables identifying the two synthetic Clerk test users.
- `.github/workflows/deploy-backend.yml` generates fresh, short-lived Clerk
  session tokens during deployment. The obsolete `SMOKE_TEST_TOKEN` and
  `SMOKE_OTHER_TEST_TOKEN` secrets are no longer required.
- The token-generation API is testing-only and requires a Clerk Development
  instance; it must not be used with a Production instance.
- `VITE_CLERK_PUBLISHABLE_KEY` remains a public frontend build-time variable
  for GitHub Pages.
- Render's runtime Clerk settings (`CLERK_JWKS_URL`, `CLERK_ISSUER`, and
  `CLERK_AUDIENCE`) are configured separately in the Render service and are
  not GitHub Actions secrets.


## Runtime, persistence, and migrations

Current code behavior is limited to the following known facts:

- `/health` reports process health; `/ready` checks whether the configured
  database is reachable. These endpoints have not been tested against a hosted
  service.
- The hosted settings validator requires a PostgreSQL `DATABASE_URL`, a
  non-empty CORS allowlist, a public bind host, and all three Clerk settings.
  Wildcard CORS origins are rejected in hosted mode.
- The local Compose API command runs `alembic upgrade head` before starting
  Uvicorn. A hosted release/migration command and its ordering, locking,
  recovery, and backward-compatibility policy are not selected or verified.
  Review migrations and choose an explicit migration procedure before a
  hosted database is provisioned.
- Application records are stored through the configured database. The
  selected API host's filesystem persistence, restart behavior, cold starts,
  quotas, and database plan limits are provider-dependent and unverified.
  Do not rely on API-local files for durable user data.
- The code and CI do not establish provider backup guarantees, restore
  procedures, free-tier sleep timing, cold-start duration, or service limits.
  Verify each against current official provider documentation before use.

## Staged promotion, rollback, and recreation

1. Keep development local; review a pull request and require its backend,
   frontend, and container image build jobs to pass.
2. The owner has authorized this isolated hosted development environment.
   Provision only the services in the table above, with synthetic fixtures,
   separate test credentials, no payment method, and no paid upgrade.
3. Before smoke tests, configure GitHub Pages with a Vite build containing the
   public API URL and Pages base path; configure the API with hosted mode,
   explicit Pages CORS origin, test Clerk issuer/audience/JWKS values, and
   `BENCHMARK_ENABLED=false`. Keep all backend secrets outside GitHub Pages and
   the repository.
4. Use issue #21 to record health/readiness, anonymous demo, auth, import,
   comparison, owner-isolation, and rollback results. Promote to production
   only after that review and separate explicit owner approval.
5. **Frontend rollback:** redeploy the Pages site from the last-known-good
   source commit using the Pages deployment workflow, or revert through a PR
   and redeploy. Keep the source commit and successful deployment URL in
   issue #21.
6. **API rollback:** use Render's rollback to a known-good deploy when it is
   available; otherwise redeploy the last-known-good source commit. Free
   service rollback history is limited, so do not depend on old deployment
   entries remaining available.
7. **Database recovery:** Neon Free is disposable test storage, not a backup
   target. For a failed migration or contaminated test data, stop smoke tests,
   discard the test branch/database, create a fresh disposable database, run
   the reviewed Alembic migrations, and seed synthetic fixtures again. Do not
   rely on point-in-time restore or assume migrations are reversible.
8. **Auth recreation:** use only the separate Clerk test application and
   synthetic identities. If its test state is unusable, recreate the test
   identities in that application; never copy production identities or
   credentials.

No deployment, hosted health/readiness check, CORS check, migration, smoke test,
rollback, or recreation has been exercised yet. Record actual deployment URLs
and rehearsal results in #21; do not mark its acceptance criteria complete
until verified.

## Provider terms to recheck before provisioning

Current documented free-tier limits were checked on 2026-10-27; they do not
guarantee that account onboarding will avoid a payment-method prompt. Stop at
any such prompt. Do not add a provider or fallback outside the approved list.

- Render Free web services sleep after 15 minutes without inbound traffic and
  take about a minute to start again. Free web services have a 750
  instance-hour monthly workspace allowance and are explicitly not for
  production. Free Render Postgres expires after 30 days and has no backups;
  do not use it.
- Neon Free is permanent and does not require a credit card according to its
  pricing page. Limits include 100 CU-hours/project, 1 GB/project, scale-to-
  zero after five minutes, and a six-hour history window; Instant Restore is
  not included. Do not treat this as backup/PITR.
- Clerk Hobby is free and does not require a credit card according to its
  pricing page; the current allowance is 50,000 MRUs per app. Use a separate
  test application.

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
