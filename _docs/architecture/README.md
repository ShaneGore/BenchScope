# BenchScope — Architecture

**Status:** Draft (MVP). Companion to `_docs/plan.md` (product) and `_docs/tech-stack.md` (stack decision). This document set covers system architecture only; backlog, agent roles, and task tracking are out of scope here.

## Scope

This architecture set defines:

- System boundaries and trust zones (private benchmark, local vs hosted).
- Component layout for frontend and backend.
- Data model and API surface.
- Free-tier deployment design and operational constraints.
- Observability, CI/CD, and rollback.

It does **not** prescribe implementation details that are deferred (benchmark command/API, exact result schema, final repo name/base path) — those remain open questions in `tech-stack.md` §10 and `plan.md` §11.

## Documents

- [`boundaries.md`](boundaries.md) — private benchmark boundary, local vs hosted separation, data isolation.
- [`deployment.md`](deployment.md) — free-tier deployment design, environments, CI/CD, rollback.
- [`backend/README.md`](backend/README.md) — backend architecture (modules, auth, runner, storage).
- [`backend/data-model.md`](backend/data-model.md) — canonical entities and persistence.
- [`backend/api.md`](backend/api.md) — HTTP API contract and ownership rules.
- [`backend/runner.md`](backend/runner.md) — benchmark runner lifecycle and safety.
- [`frontend/README.md`](frontend/README.md) — frontend architecture (components, state, API client).
- [`frontend/routing.md`](frontend/routing.md) — routing, GitHub Pages base path, auth gating.

## High-level shape

```
┌─────────────────────────────────────────────────────────────┐
│  Browser (SPA)                                              │
│  React + Vite + TS, hosted on GitHub Pages (static)         │
│  • Clerk (auth)  • reads/writes via HTTPS API               │
└──────────────┬──────────────────────────────────────────────┘
               │ HTTPS (CORS-restricted to Pages origin)
               ▼
┌─────────────────────────────────────────────────────────────┐
│  FastAPI (Render Free / local uvicorn)                      │
│  • Pydantic v2  • SQLAlchemy 2  • Alembic migrations        │
│  • Clerk JWT verify via JWKS; `sub` = owner key             │
│  • Local mode: benchmark runner (in-process, single-flight)  │
│  • Hosted mode: import/compare only; runner disabled        │
└──────────────┬──────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│  PostgreSQL (Neon Free / local Docker Compose)              │
│  Owner-scoped rows; synthetic demo dataset (read-only)      │
└─────────────────────────────────────────────────────────────┘

Private benchmark (local disk, outside repo) ──► runner subprocess
Local model endpoint (localhost) ──► benchmark process
```

## Core principles

1. **One codebase, two modes.** Mode is an env switch (`APP_MODE=local|hosted`), not a fork. The same image runs in both contexts; only capability flags and config differ.
2. **Backend is the authority.** Ownership, validation, normalisation, and access control are enforced server-side. The frontend never trusts client state for authorization.
3. **Private benchmark stays out.** The benchmark binary, prompts, reference answers, hidden tests, and raw artifacts live on the developer's machine outside the repo and are never committed, served, or logged.
4. **Failed attempts are first-class.** Runs have a status lifecycle; failures are persisted with sanitised diagnostics and never masquerade as successes.
5. **Missing ≠ zero.** Nullable metrics; UI renders "unavailable", never `0`.
6. **$0 recurring cost.** All hosted dependencies are free tiers; no paid service is assumed on a trial basis. Limits are documented and accepted (see `deployment.md`).

## Trust zones

| Zone | Contents | Exposure |
|---|---|---|
| Z0 Public repo / Pages | SPA bundle, docs, tests, synthetic fixtures | Public |
| Z1 Hosted API (Render) | FastAPI, import/compare/profile endpoints, Clerk verification | Public HTTPS |
| Z2 Hosted DB (Neon) | Owner-scoped run/profile rows, synthetic demo dataset | Private (API only) |
| Z3 Local machine | Private benchmark, model endpoints, raw artifacts, local DB | Loopback / developer only |
| Z4 Telemetry (local or Grafana Cloud) | Metrics/logs/traces | Operator only |

No data flows from Z3 to Z1/Z2 except allowlisted, normalised, non-confidential metrics via explicit import. No raw benchmark output, prompts, generated code, or secrets leave Z3. See `boundaries.md`.