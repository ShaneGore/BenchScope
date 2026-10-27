from functools import lru_cache
from typing import Annotated, cast

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient, PyJWKClientError, PyJWTError

from app.database import LOCAL_OWNER_ID

_bearer = HTTPBearer(auto_error=False)


@lru_cache(maxsize=4)
def _jwks_client(url: str) -> PyJWKClient:
    return PyJWKClient(url)


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


def current_owner(
    request: Request,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(_bearer)
    ] = None,
) -> str:
    settings = request.app.state.settings
    if settings.local_auth_bypass:
        return LOCAL_OWNER_ID
    if (
        credentials is None
        or credentials.scheme.casefold() != "bearer"
        or not settings.clerk_jwks_url
        or not settings.clerk_issuer
        or not settings.clerk_audience
    ):
        raise _unauthorized()

    try:
        key = _jwks_client(settings.clerk_jwks_url).get_signing_key_from_jwt(
            credentials.credentials
        )
        claims = jwt.decode(
            credentials.credentials,
            key.key,
            algorithms=["RS256"],
            issuer=settings.clerk_issuer,
            audience=settings.clerk_audience,
            options={"require": ["exp", "iss", "aud", "sub"]},
        )
        owner_id = claims.get("sub")
        if not isinstance(owner_id, str) or not owner_id.strip():
            raise _unauthorized()
        return cast(str, owner_id)
    except (PyJWTError, PyJWKClientError, OSError, TypeError, ValueError):
        raise _unauthorized() from None
