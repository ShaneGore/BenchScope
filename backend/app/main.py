import logging
import sqlite3
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import unquote
from uuid import UUID, uuid4

import psycopg
import uvicorn
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import sessionmaker
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.config import Settings, load_settings
from app.database import create_database_engine
from app.imports import router as imports_router
from app.profiles import router as profiles_router
from app.run_history import router as run_history_router

logger = logging.getLogger("app.request")
CORRELATION_HEADER = "X-Correlation-ID"
API_PREFIX = "/api/v1"


def database_is_ready(database_url: str | None) -> bool:
    if database_url is None:
        return False
    if database_url.startswith("sqlite:///"):
        path = unquote(database_url[len("sqlite:///") :].split("?", 1)[0])
        if not path or (path != ":memory:" and not Path(path).is_file()):
            return False
        try:
            with sqlite3.connect(path, timeout=2) as connection:
                return connection.execute("SELECT 1").fetchone() == (1,)
        except sqlite3.Error:
            return False
    try:
        with psycopg.connect(database_url, connect_timeout=2) as connection:
            return connection.execute("SELECT 1").fetchone() == (1,)
    except (psycopg.Error, ValueError):
        return False


class CorrelationIdMiddleware:
    """Returns X-Correlation-ID and includes it in each request log record."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        try:
            supplied = headers.get(CORRELATION_HEADER.lower().encode(), b"").decode(
                "ascii"
            )
            correlation_id = str(UUID(supplied))
        except (UnicodeDecodeError, ValueError):
            correlation_id = str(uuid4())

        response_started = False

        async def send_with_correlation(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
                message["headers"] = [
                    (name, value)
                    for name, value in message["headers"]
                    if name.lower() != CORRELATION_HEADER.lower().encode()
                ]
                message["headers"].append(
                    (CORRELATION_HEADER.lower().encode(), correlation_id.encode())
                )
                logger.info(
                    "request completed correlation_id=%s",
                    correlation_id,
                    extra={
                        "correlation_id": correlation_id,
                        "status_code": message["status"],
                    },
                )
            await send(message)

        try:
            await self.app(scope, receive, send_with_correlation)
        except Exception as error:
            if response_started:
                raise
            logger.error(
                "unhandled request error correlation_id=%s",
                correlation_id,
                extra={
                    "correlation_id": correlation_id,
                    "error_type": type(error).__name__,
                },
            )
            await JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"},
            )(scope, receive, send_with_correlation)


def create_app(
    settings: Settings | None = None,
    readiness_probe: Callable[[str | None], bool] | None = None,
) -> FastAPI:
    config = settings or load_settings()
    database_url = (
        config.database_url.get_secret_value() if config.database_url else None
    )
    engine = create_database_engine(database_url)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            if engine is not None:
                engine.dispose()

    app = FastAPI(
        title="BenchScope",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.state.settings = config
    app.state.readiness_probe = readiness_probe or database_is_ready
    app.state.engine = engine
    app.state.session_factory = (
        sessionmaker(bind=engine, expire_on_commit=False)
        if engine is not None
        else None
    )
    app.include_router(profiles_router, prefix=API_PREFIX)
    app.include_router(imports_router, prefix=API_PREFIX)
    app.include_router(run_history_router, prefix=API_PREFIX)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready")
    def ready(request: Request) -> JSONResponse:
        url = config.database_url.get_secret_value() if config.database_url else None
        is_ready = request.app.state.readiness_probe(url)
        return JSONResponse(
            status_code=200 if is_ready else 503,
            content={"status": "ready" if is_ready else "not_ready"},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        _request: Request, error: RequestValidationError
    ) -> JSONResponse:
        details = {
            ".".join(
                str(part)
                for part in issue["loc"]
                if part not in {"body", "query", "path"}
            )
            or "request": issue["msg"]
            for issue in error.errors()
        }
        return JSONResponse(status_code=422, content={"detail": details})

    # CORS sits inside correlation middleware so preflight responses also get an ID.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_allow_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(CorrelationIdMiddleware)
    return app


settings = load_settings()
app = create_app(settings)

if __name__ == "__main__":
    uvicorn.run(app, host=settings.bind_host, port=settings.port)
