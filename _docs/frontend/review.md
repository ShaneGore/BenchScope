# Frontend prototype review

## Environment

- Browser: local Chromium via Vite dev server (`corepack pnpm dev`) on Windows.
- Build tooling: Vite 7, React 19, TypeScript, Tailwind CSS 3.
- Test command: `corepack pnpm test` (Vitest + jsdom + React Testing Library).
- Build command: `corepack pnpm build`.
- Mode under review: `VITE_APP_MODE=local` (default).

## Workflows exercised

- Dashboard: renders synthetic runs and profile summary; loading/empty states visible.
- Runs list: filtering by status/model/date and pagination cursor.
- Run detail: events, metrics, failure/interrupted rendering, unavailable metrics.
- Compare: selection of completed runs; null metrics remain unavailable in charts/tables.
- Profiles: create/update/delete validation; hosted/demo gating flags.
- Import: validation errors, duplicate 409 handling, successful import rendering.
- Benchmark launch/retry: local-only actions and status polling. Run cancellation
  is not part of the interim scope; defer it to #25.
- Demo route: read-only synthetic data.

## Issues found and disposition

1. `window.scrollTo` is not implemented in jsdom and emitted an unhandled runtime error during tests.
   - Fix: guarded `useScrollTopOnRoute` with a jsdom/user-agent check and try/catch.
2. The original skeleton test expected a "BenchScope" heading that the migrated App shell does not render.
   - Fix: replaced with a smoke render test.
3. The prototype initially lived in `frontend/frontend_mock` outside the tracked `frontend/` pnpm project.
   - Fix: migrated source, styles, Tailwind/PostCSS config, and dependencies into `frontend/`; removed reliance on the untracked mock directory for acceptance commands.
4. Null metrics could be mistaken for zero in UI comparisons.
   - Verified `metricAvailable` rejects `null`, `undefined`, and `NaN` while accepting `0`; `MetricValue` renders "Unavailable".

## Test coverage added

- `src/App.test.tsx`: application renders.
- `src/lib/metrics.test.ts`: null/zero metric handling.
- `src/components/ui/MetricValue.test.tsx`: unavailable and available rendering.
- `src/mock/store.test.ts`: synthetic profiles/runs and completed-run availability.

## Result

- `pnpm build` passes.
- `pnpm test` passes (7 tests).
- No direct HTTP calls in presentation components; data access remains through `mock/store`.
- Missing metrics render as "Unavailable" and are not coerced to zero.
