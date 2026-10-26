from typing import Annotated

from fastapi import Depends
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy.orm import Session

from app.config import Settings
from app.database import create_database_engine, get_session
from app.main import create_app


def test_postgres_urls_use_the_installed_psycopg_driver() -> None:
    engine = create_database_engine("postgresql://localhost/db")

    assert engine is not None
    assert engine.url.drivername == "postgresql+psycopg"
    engine.dispose()


def test_invalid_database_url_does_not_break_health() -> None:
    app = create_app(Settings(database_url=SecretStr("not-a-database-url")))

    client = TestClient(app)
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/ready").status_code == 503


def test_request_session_is_entered_and_closed() -> None:
    class SessionContext:
        entered = False
        exited = False

        def __call__(self) -> "SessionContext":
            return self

        def __enter__(self) -> object:
            self.entered = True
            return object()

        def __exit__(self, *_: object) -> None:
            self.exited = True

    factory = SessionContext()
    app = create_app()
    app.state.session_factory = factory

    def session_check(
        session: Annotated[Session, Depends(get_session)],
    ) -> dict[str, bool]:
        return {"opened": session is not None}

    app.add_api_route("/test-session", session_check)

    with TestClient(app) as client:
        response = client.get("/test-session")

    assert response.status_code == 200
    assert response.json() == {"opened": True}
    assert factory.entered is True
    assert factory.exited is True
