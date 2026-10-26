# BenchScope

BenchScope is a React/Vite frontend and FastAPI backend. This repository currently
contains only the project skeleton; it has no product API routes or benchmark
execution.

## Frontend

From `frontend/`, run `pnpm install`, `pnpm dev`, `pnpm test`, or `pnpm build`.

## Backend

From `backend/`, run `uv sync`, `uv run uvicorn app.main:app --reload`,
`uv run pytest`, or `uv run ruff check .`.

## Offline smoke test

From `backend/`, run `uv run pytest tests/test_smoke.py`. This imports the empty
FastAPI application and verifies that it has no product routes. It needs no
database, network service, GPU, or private benchmark.
