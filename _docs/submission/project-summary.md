# BenchScope Project Summary

BenchScope is a local-first web application for recording, comparing, and understanding the performance of local language models on an independent coding benchmark. It turns isolated benchmark results into a durable, inspectable history while keeping the proprietary benchmark itself out of the repository.

## Problem

Developers running local language models often produce one-off benchmark results that are hard to compare across model versions, quantisations, inference settings, hardware configurations, and time. BenchScope provides a persistent observatory for those results: import an existing result, inspect it, and compare it with earlier results.

## Solution

BenchScope imports supported JSON result files, validates required fields, normalises metrics, detects duplicates, persists results, and supports history, detail, filtering, and comparison. It distinguishes missing metrics from zero values and keeps incomplete coverage from being presented as a complete score.

## Main features

- Import v1 and v2 benchmark result contracts.
- Persisted run history with owner isolation.
- Run detail and comparison views.
- Synthetic read-only demo for unauthenticated visitors.
- Model profiles with hardware and benchmark settings.
- Local/private mode with loopback binding.
- Hosted multi-user mode with Clerk authentication.
- Observability with OpenTelemetry, Prometheus, Grafana, Loki, and Tempo.
- Authenticated alert intake and supervised recovery.
- Windows process-tree safety foundation for future local benchmark execution.
- Bounded output capture and result-file reads.
- Docker Compose local stack.
- CI/CD with five required checks, including Windows.

## Technology stack

- Frontend: React, Vite, TypeScript, pnpm, Vitest, Playwright
- Backend: Python 3.12, FastAPI, Pydantic v2, SQLAlchemy, Alembic
- Database: PostgreSQL
- Authentication: Clerk
- Observability: OpenTelemetry, Prometheus, Grafana, Loki, Tempo
- Deployment: GitHub Pages, Render Free, Neon Free
- CI/CD: GitHub Actions

## Hosted demo

- Frontend: https://shanegore.github.io/BenchScope/
- Backend: https://benchscope-staging-api.onrender.com

## Privacy and safety

BenchScope never stores private prompts, reference answers, hidden tests, generated code, raw model responses, or confidential benchmark paths. Hosted import processing stores only allowlisted, non-confidential metrics and metadata and discards the uploaded raw payload. Hosted mode cannot run the private benchmark.

## Known limitations

- Real benchmark launch and cancellation are not yet fully integrated; Issue #25 remains open.
- The local subprocess adapter is implemented and tested with synthetic runners.
- Observability and alerting are verified in local Docker Compose.
- `quality_score` remains null until an authoritative scoring definition exists.
PY