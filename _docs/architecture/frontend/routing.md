# Frontend routing & GitHub Pages

## 1. Base path

- GitHub Pages repository project sites are served under `/<repo-name>/`, not the domain root.
- Vite `base` is set from env (`VITE_BASE_PATH`), defaulting to `/` for local dev and `/<repo-name>/` for Pages builds. Never hard-code the final repo name in source; inject via CI env.
- All asset/router paths derive from `import.meta.env.BASE_URL`.

## 2. Router

- Prefer hash-based routing (`HashRouter`) for Pages to avoid 404s on deep links and refresh; alternatively configure a 404 fallback. Decision: hash router for MVP simplicity; revisit if clean URLs needed.
- Routes:
  - `/` — dashboard (auth required in hosted mode; local may allow)
  - `/runs` — history + filters
  - `/runs/:id` — detail
  - `/compare` — comparison chart
  - `/profiles` — model profiles
  - `/import` — import result
  - `/benchmark` — launch (local mode only; hidden in hosted)
  - `/demo` — anonymous read-only synthetic dataset
  - `/sign-in`, `/sign-up` — Clerk

  The local frontend queries `GET /api/v1/benchmark/capabilities` before exposing
  benchmark launch controls. A false or failed check hides the controls; backend
  route mounting remains authoritative. Hosted mode never queries capability or
  runner endpoints. The demo uses only the anonymous read-only demo run endpoints.

## 3. Auth gating

- Protected routes check Clerk auth state; unauthenticated users redirect to sign-in (except `/demo`).
- In hosted mode, anonymous visitors land on `/demo` by default.

## 4. Build/deploy

- Dev: `pnpm dev` with base `/`.
- Prod (Pages): `VITE_BASE_PATH=/<repo-name>/ VITE_API_URL=... pnpm build`.
- CI sets these from repository variables/secrets. No secrets in bundle.