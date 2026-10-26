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

Pipeline stages:
1. Lint + typecheck (Python ruff/pyright; TS ESLint/tsc).
2. Tests (pytest against Postgres service container; Vitest; Playwright).
3. Build images (backend; frontend).
4. Deploy frontend to Pages.
5. Deploy backend to Render (trigger deploy hook or Render auto-deploy).
6. Smoke test hosted endpoints.
7. Promote (manual) from dev to prod where applicable.

Runs on public repo = unlimited minutes. Private benchmark not available in CI; tests use fakes/fixtures.

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