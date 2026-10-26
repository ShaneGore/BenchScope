# BenchScope Copilot Instructions

BenchScope is a FastAPI backend + React/Vite/TypeScript frontend monorepo for tracking, importing, and comparing private benchmark results.

## Stack

- Frontend: React + Vite + TypeScript; package manager `pnpm`
- Backend: FastAPI on Python 3.12; dependencies and lockfile via `uv`
- Database: PostgreSQL; migrations with Alembic
- Local orchestration: Docker Compose
- Auth: Clerk in hosted mode; local mode has its own bypass
- Benchmark execution is local-only and must never run in hosted mode

## Commands

Frontend (run in `frontend/`):
- `pnpm install`
- `pnpm test`
- `pnpm build`

Backend:
- `uv sync`
- `uv run pytest`
- `uv run pytest path/to/test_file.py`
- `uv run ruff check .`
- `uv run ruff format .`
- `uv run alembic upgrade head`

Local stack:
- `docker compose up`

## Workflow

- Read `_docs/tasks.md` and the relevant architecture docs before implementing.
- Follow `_docs/process.md`: PM grooms, Engineer implements, QA verifies.
- Run relevant checks or tests after changing code.
- Create migrations with Alembic and apply them with `alembic upgrade head`.
- Keep benchmark execution local-only; hosted mode must not run benchmarks.
- Keep user data owner-scoped and treat metrics as nullable.

## Roles

- PM: `_docs/team/pm.md`
- Software Engineer: `_docs/team/software-engineer.md`
- QA Engineer: `_docs/team/qa-engineer.md`
- Custom Copilot agents are available in `.github/agents/`.

## Rules

- Backend dependencies go in `pyproject.toml` and `uv.lock`.
- Frontend dependencies go in `package.json` and `pnpm-lock.yaml`.
- Do not add dependencies without asking.
- Do not invent missing requirements; flag gaps in docs or task notes.
