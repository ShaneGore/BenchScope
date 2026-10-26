# Agent Instructions

- `_docs/process.md` - how work is organized

## Roles

- PM - grooms a task before anyone implements it, follows _docs/team/pm.md
- Engineer - implements one groomed task, follows _docs/team/software-engineer.md
- QA - checks the result against the acceptance criteria, follows _docs/team/qa-engineer.md

## Commands

- `pnpm install` - install frontend dependencies (run in `frontend/`)
- `pnpm test` - frontend tests
- `pnpm build` - frontend production build
- `uv sync` - install backend dependencies
- `uv run pytest` - backend tests
- `uv run pytest path/to/test_file.py` - one backend test file
- `uv run ruff check .` - Python lint
- `uv run ruff format .` - Python format
- `uv run alembic upgrade head` - apply database migrations
- `docker compose up` - local app + Postgres stack

## Project

- This is a FastAPI backend + React/Vite/TypeScript frontend monorepo.
- Backend code lives in `backend/`; frontend code lives in `frontend/`.
- Use `uv` for Python dependencies and `pnpm` for frontend dependencies.

## Workflow

- Run the relevant frontend/backend checks or tests after changing code.
- Create migrations with Alembic and apply them with `alembic upgrade head`.
- Keep benchmark execution local-only; hosted mode must not run benchmarks.

## Rules

- Backend dependencies are added in `pyproject.toml` and locked with `uv.lock`; frontend dependencies are added in `package.json` and locked with `pnpm-lock.yaml`. Do not add one without asking.
