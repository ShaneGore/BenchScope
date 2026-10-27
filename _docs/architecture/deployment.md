# Free-tier deployment design

## 1. Environments

| Env | Frontend | Backend | DB | Purpose |
|---|---|---|---|---|
| local | `pnpm dev` / Docker | uvicorn / Docker | Postgres (Compose) | Full workflow incl. benchmark |
| dev (hosted) | GitHub Pages (preview/branch) | Render Free (dev service) | Neon Free (dev branch/db) | Integration/smoke |
| prod (hosted) | GitHub Pages (main) | Render Free (prod service) | Neon Free (prod db) | Public demo |

Local and hosted share one codebase; mode via `APP_MODE`.

## 2. Frontend (GitHub Pages)

- Static Vite build deployed by GitHub Actions on push to `main` (and PR previews optional).
- Public repo required for free Pages; repo must not contain secrets.
- Base path env-driven; hash router.
- Rollback: redeploy prior commit / revert.

## 3. Backend (Render Free)

- Docker image built in CI, pushed to registry (GHCR) or built by Render.
- Free web service spins down after 15 min idle; cold start ~30-60s. Acceptable for demo; document.
- Ephemeral filesystem: no persistent local files; DB on Neon.
- Env vars configured in Render dashboard (not in repo): `DATABASE_URL`, Clerk settings, `CORS_ORIGINS`, `APP_MODE=hosted`, etc.
- Health checks on `/health`/`/ready`.

## 4. Database (Neon Free)

- Persistent, 1 GB storage, 100 CU-hr/month, no expiry (verify terms).
- Alembic migrations run as part of deploy (release command) or manual.
- Backups: Neon's provided backup/branching; document restore.
- Connection pooling via Neon pooler endpoint for serverless-ish usage.

## 5. Auth (Clerk Hobby)

- Free, no card, 50k MRU. Verify current limits/terms.
- JWKS URL/issuer/audience configured via env.
- Fallback: Supabase Auth if terms change.

## 6. CI/CD (GitHub Actions)

`.github/workflows/ci.yml` runs on pull requests and pushes to `main`. The
`backend` and `frontend` jobs are the required quality, test, and contract
gates; configure both job checks as required in the repository ruleset to block
merges when either fails. No optional jobs are defined.

- Backend: Python 3.12, locked `uv` development dependencies, Ruff lint and
  format checks, and the full pytest suite against a health-checked,
  ephemeral PostgreSQL service.
- Frontend: Node 22, pnpm selected from `frontend/package.json`, frozen-lock
  install, Vitest, production build (`tsc --noEmit`), and generated API drift
  check.
- The workflow uses read-only repository permissions and does not need secrets,
  private benchmark materials, model weights, a GPU, or paid services.
- Dockerfiles and image-build checks are deferred to #20. Hosted deploy,
  smoke-test, and promotion steps are not part of this workflow. Python
  type-checker and frontend lint scripts are not currently configured.
- The separate Playwright `test:journey` script is not a required CI check.

See the repository README for exact local commands. The tests use synthetic
fixtures and fake adapters; private benchmark assets remain local-only.

## 7. Rollback

- Frontend: redeploy previous commit via Actions (or revert).
- Backend: Render supports rollback to previous deploy.
- DB: restore from Neon backup/branch; migrations are forward-only with rollback migrations.

## 8. Observability (hosted)

- Optional Grafana Cloud Free for API telemetry (14-day retention, no card). Not required for MVP; local stack covers dev.
- Sentry not included by default.

## 9. Risks / limits (accepted)

- Render cold starts; Neon compute quotas; Pages 1 GB/100 GB/mo soft; Clerk MRU cap.
- No automated backups guarantee beyond provider offerings.
- Free terms may change → fallbacks documented in `tech-stack.md` §7.

## 10. Security checklist

- No secrets in frontend bundle or repo.
- CORS restricted to Pages origins.
- Upload size caps; input validation.
- Owner checks server-side; IDOR tests.
- Private benchmark paths never in hosted env.