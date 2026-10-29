# Hosted deployment readiness and provider constraints

Date checked: 2026-10-29.

This document prepares repository-side deployment work for Issue #21. It does not
create, activate, upgrade, or configure any external service.

## Proposed architecture

- Static frontend: GitHub Pages
- Backend: Render Free web service
- Database: Neon Free PostgreSQL
- Authentication: Clerk Hobby, only if hosted authentication is enabled
- CI/CD: GitHub Actions workflows already in `.github/workflows/`

## Provider findings

### Render Free
Source: https://render.com/docs/free and https://render.com/docs/faq

- Free web services are available.
- Free web services spin down after 15 consecutive minutes without incoming
  traffic and take about one minute to spin back up.
- Free web services do not support persistent disks, scaling beyond one
  instance, edge caching, one-off jobs, SSH/shell access, or private inbound
  network traffic.
- Free Render Postgres databases have a 1 GB storage limit.
- Free Render Postgres databases expire 30 days after creation.
- Expired Free Postgres databases have a 14-day upgrade grace period before
  deletion.
- Free Render Postgres databases do not support backups or managed connection
  pooling.
- Render may restart or maintain Free services at any time.
- The checked documentation does not explicitly state whether a payment card is
  required to create a Free service. Confirm this during account setup and stop
  if payment details are requested.

### Neon Free
Source: https://neon.com/pricing

- Free plan is advertised as `$0` with no time limits and no credit card
  required.
- Free plan includes 100 projects and 100 CU-hours per project per month.
- Free plan includes 1 GB storage per project.
- Compute scales to zero after inactivity; the checked page lists 5 minutes for
  the Free plan.
- Free plan includes up to 10 branches per project.
- Free plan includes Managed Better Auth for up to 60,000 monthly active users
  per project.
- Autoscaling limits can cap compute cost.
- Storage beyond the free allowance or paid features would incur charges; keep
  the deployment within free allowances.

### Clerk Hobby
Source: https://clerk.com/pricing

- Hobby plan is free and states "No credit card required".
- Hobby plan includes up to 50,000 monthly retained users per app.
- Hobby plan has a fixed 7-day session lifetime.
- Application logs are retained for 1 day.
- Only 3 dashboard seats are included.
- Clerk is optional for BenchScope. Hosted authentication should remain disabled
  unless its current terms continue to satisfy the no-card/no-paid constraint.

### GitHub Pages
Source: https://docs.github.com/en/pages/getting-started-with-github-pages/about-github-pages

- GitHub Pages is available for public repositories with GitHub Free.
- It hosts static HTML, CSS, and JavaScript only.
- It cannot run the FastAPI backend, PostgreSQL, or benchmark runner.
- The frontend must be built with a public HTTPS `VITE_API_URL`.
### GitHub Actions environments
Source: https://docs.github.com/en/actions/deployment/targeting-different-environments/using-environments-for-deployment

- Environment protection rules must be configured in repository settings.
- Required reviewers, wait timers, and branch policies are not created by
  workflow YAML alone.
- Environment secrets and variables are only available to jobs that reference
  the environment.
- The repository currently has `copilot`, `github-pages`, and `staging`
  environments. `production` does not yet exist.

## Required GitHub configuration

### Repository variables
- `VITE_API_URL`
- `VITE_CLERK_PUBLISHABLE_KEY`
- `SMOKE_API_URL`
- `SMOKE_FRONTEND_URL`
- `PRODUCTION_SMOKE_API_URL`
- `PRODUCTION_SMOKE_FRONTEND_URL`

### Repository secrets
- `DATABASE_URL`
- `RENDER_DEPLOY_HOOK_URL`
- `SMOKE_TEST_TOKEN`
- `SMOKE_OTHER_TEST_TOKEN`
- `PRODUCTION_DATABASE_URL`
- `PRODUCTION_RENDER_DEPLOY_HOOK_URL`
- `PRODUCTION_SMOKE_TEST_TOKEN`
- `PRODUCTION_SMOKE_OTHER_TEST_TOKEN`

### Backend environment variables
- `APP_MODE=hosted`
- `DATABASE_URL`
- `CORS_ORIGINS`
- `HOST`
- `PORT`
- `BENCHMARK_ENABLED=false`
- Clerk variables only if authentication is enabled:
  - `CLERK_JWKS_URL`
  - `CLERK_ISSUER`
  - `CLERK_AUDIENCE`

## Pre-deployment checklist
- Confirm provider terms still satisfy the $0, no-card, no-paid-upgrade policy.
- Confirm no payment details are requested.
- Confirm Render Free database expiration is acceptable for a non-production
  staging environment.
- Create GitHub `production` environment and configure required reviewers.
- Set all required variables and secrets.
- Keep benchmark execution disabled in hosted mode.
- Use synthetic data only in smoke tests.

## Staging deployment sequence
1. Configure GitHub Pages and frontend variables.
2. Create Render Free web service and Neon Free database.
3. Configure GitHub `staging` secrets and variables.
4. Run `deploy-backend.yml`.
5. Verify `/health`, `/ready`, migrations, and smoke tests.
6. Run `deploy-frontend.yml`.
7. Verify frontend reachability and anonymous demo access.

## Success criteria
- Frontend is reachable at the GitHub Pages URL.
- Backend `/ready` returns HTTP 200.
- Prometheus reports `up{job="api"} == 1`.
- Synthetic import, history, detail, comparison, and owner isolation pass.
- No secrets or private benchmark data appear in logs or telemetry.

## Failure handling and rollback
- If migrations fail, stop before triggering the Render deploy hook.
- If readiness or smoke tests fail, fail the workflow.
- Roll back frontend and backend to the previous deployment.
- Do not downgrade or delete the database automatically.
- Preserve the database and investigate the failed deployment.

## Agent-tested versus owner-required
- Agent-tested locally:
  - backend tests
  - frontend tests and build
  - Render deploy-hook URL helper
  - smoke-test argument and failure behavior
- Owner-required:
  - provider account/resource creation
  - GitHub variable/secret configuration
  - Environment reviewer configuration
  - hosted deployment
  - hosted smoke tests
  - rollback rehearsal

## Cost and card confirmation
- Neon Free and Clerk Hobby are documented as no credit card required.
- Render Free documentation does not explicitly state whether a card is required
  for signup or service creation. Stop and report if payment details are requested.
- All selected providers must remain within free allowances. No paid upgrade is
  authorised by this document.

- GitHub Pages is suitable for the frontend only.
