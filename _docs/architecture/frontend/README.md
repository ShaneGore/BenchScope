# Frontend architecture (React + Vite)

## 1. Stack

React + Vite + TypeScript, `pnpm`. Hosted on GitHub Pages (static). Auth via Clerk (Hobby). Charts via a React-friendly library (choice deferred to implementation; must handle null metrics). Tests: Vitest + React Testing Library; e2e: Playwright.

## 2. Module layout (proposed)

```
frontend/
  src/
    main.tsx
    App.tsx
    routes/            # page components
    components/        # shared UI
    charts/            # comparison charts
    api/               # generated TS types + fetch client
    auth/              # Clerk integration, guards
    state/             # server-state (React Query) + local UI state
    config/            # env-driven config (base path, API URL, mode)
  public/
  index.html
  vite.config.ts
  package.json
  pnpm-lock.yaml
```

## 3. State management

- Server state via React Query (cache, refetch, mutations).
- Local UI state via React hooks/context; no global store unless needed.
- Optimistic updates only where safe; invalidate on mutation.

## 4. API client

- Base URL from `VITE_API_URL` (env, not hard-coded).
- Typed client generated from OpenAPI (`openapi-typescript`); regenerated in CI or dev.
- In hosted builds, Clerk provides sign-in/out and session tokens; an enabled personal API client attaches the current token as a bearer token. The Task 13 local-only API selection remains unchanged.

## 5. Auth gating

- Clerk provider wraps app. Signed-in state from Clerk.
- Route guards: protected routes redirect to sign-in; demo route public.
- Hosted mode: hide launch/profile-endpoint UI based on `VITE_APP_MODE`, but backend remains authoritative.

## 6. Data display rules

- Missing metrics render "unavailable", never `0`.
- Failed/interrupted runs visually distinct; excluded from success summaries unless failure view.
- Owner data never cached in a way that leaks between accounts (clear the app store on sign-out and remount the app on identity changes).

## 7. Observability

- OpenTelemetry browser SDK → OTLP (optional, local/hosted).
- Error boundary captures render errors; sends to console/OTel (no Sentry by default).

## 8. Build

- Multi-stage Dockerfile (Node build) for container parity; primary deploy via GitHub Actions to Pages.
- `base` path env-driven for repo project sites. See `routing.md`.