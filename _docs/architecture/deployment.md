# Deployment design and readiness

This document describes a possible hosted layout, not an active deployment.
Issue #20 adds local image builds and a Pages-ready Vite build only. No account,
service, repository environment, provider terms, or paid option has been
configured or accepted. Before any provisioning, the owner must verify the
current official terms below against the $0 recurring-cost constraint and
approve the provider choice and configuration. Do not provision a provider or
fallback before both checks.

## Hosted layout

| Component | Candidate | What it serves |
|---|---|---|
| Static frontend | GitHub Pages | Public Vite build only; never the FastAPI API |
| API | Render web service | Separately hosted FastAPI container |
| Database | Neon PostgreSQL | Persistent application records through `DATABASE_URL` |
| Authentication | Clerk, if enabled | Frontend sign-in; API verifies Clerk JWTs |

These are candidates, not verified or provisioned services. GitHub Pages cannot
run the backend, database, or benchmark runner. The browser's `VITE_API_URL`
must point to the separately approved API origin. The API's `CORS_ORIGINS` must
be an explicit allowlist of the deployed Pages origin(s), without wildcards.
Local development continues to use the root Vite path and local API.

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
- Hosted backend configuration currently requires `APP_MODE=hosted`, `HOST`,
  `DATABASE_URL`, `CORS_ORIGINS`, `CLERK_JWKS_URL`, `CLERK_ISSUER`, and
  `CLERK_AUDIENCE`. Configure `HOST` as the provider-required public bind
  address (commonly `0.0.0.0`) and set the service port using the name the
  selected provider supports; the application setting is `PORT` (default
  `8000`). `DATABASE_URL` and any provider credentials belong only in the
  backend host's secret configuration. Clerk issuer, audience, and JWKS URL
  are backend-only configuration and must be provided together. Set
  `BENCHMARK_ENABLED=false`; the application only enables its runner when
  `APP_MODE=local`, regardless of this flag.
- `APP_ENV` defaults to `production`; `MAX_UPLOAD_BYTES` defaults to 1 MiB.
  These may be explicitly set on the backend if their defaults are unsuitable.
  No frontend or backend secret is needed by CI.

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

## Staged promotion and rollback

1. Keep development local; review a pull request and require its backend,
   frontend, and container image build jobs to pass.
2. After owner approval and current terms checks, configure an isolated hosted
   development environment with synthetic data and separate credentials.
3. Use issue #21 for owner-approved hosted health/readiness, CORS, and smoke
   verification. Promote to production only after that review and explicit
   owner approval; use distinct production secrets and database configuration.
4. For a frontend rollback, redeploy the last known-good Pages artifact from
   its source commit (or revert the change and rebuild). For an API rollback,
   redeploy the last known-good image/commit using the selected host's reviewed
   procedure. For a database migration issue, stop promotion and follow a
   previously verified backup/restore or forward-fix procedure; do not assume
   migrations are reversible.

This is a documented procedure only. Deployment, health/readiness, production
CORS, promotion, and rollback have not been exercised; those require approved
owner-controlled configuration and belong to #21.

## Provider terms to recheck before provisioning

Current requirements, eligibility, limits, and payment-method rules have not
been verified for this task. Check the official sources immediately before
provisioning; confirm $0 recurring cost, payment-method requirements, and
owner approval. No provider or fallback may be provisioned until those checks
are complete.

- GitHub Pages eligibility, terms, and usage restrictions:
  [GitHub Pages documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages)
  and [GitHub Pages limits](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits).
- Render free-tier pricing, service behavior, and payment-method requirements:
  [Render pricing](https://render.com/pricing).
- Neon limits, usage billing, and payment requirements:
  [Neon pricing](https://neon.tech/pricing).
- Clerk terms and plan limits if authentication is deployed:
  [Clerk pricing](https://clerk.com/pricing).

Do not treat earlier free-tier descriptions or numbers elsewhere in the
repository as verified current terms.
