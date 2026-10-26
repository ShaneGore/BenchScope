from collections.abc import Iterator

from fastapi import Request
from sqlalchemy import Engine, create_engine
from sqlalchemy.exc import ArgumentError
from sqlalchemy.orm import Session, sessionmaker

LOCAL_OWNER_ID = "local"


def sqlalchemy_database_url(database_url: str) -> str:
    if database_url.startswith("postgres://"):
        return "postgresql+psycopg://" + database_url.removeprefix("postgres://")
    if database_url.startswith("postgresql://"):
        return "postgresql+psycopg://" + database_url.removeprefix("postgresql://")
    return database_url


def create_database_engine(database_url: str | None) -> Engine | None:
    if not database_url:
        return None
    try:
        return create_engine(sqlalchemy_database_url(database_url))
    except ArgumentError:
        return None


def get_session(request: Request) -> Iterator[Session]:
    factory: sessionmaker[Session] | None = request.app.state.session_factory
    if factory is None:
        raise RuntimeError("Database is not configured")
    with factory() as session:
        yield session
