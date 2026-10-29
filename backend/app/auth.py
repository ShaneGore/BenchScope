import http.client
import json
import time
from functools import lru_cache
from typing import Annotated, cast
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, build_opener
from urllib.request import Request as UrlRequest

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import (
    PyJWKClient,
    PyJWKClientConnectionError,
    PyJWKClientError,
    PyJWTError,
)

from app.config import resolved_loopback_addresses
from app.database import LOCAL_OWNER_ID

_bearer = HTTPBearer(auto_error=False)


class _RejectRedirects(HTTPRedirectHandler):
    def redirect_request(self, *args: object, **kwargs: object) -> None:
        return None


class _LoopbackHTTPJWKClient(PyJWKClient):
    """HTTP JWKS fetcher used only by the validated local test profile."""

    def fetch_data(self) -> dict[str, object]:
        parsed = urlsplit(self.uri)
        if not parsed.hostname:
            raise PyJWKClientConnectionError("JWKS host is unavailable")
        addresses = resolved_loopback_addresses(parsed.hostname)
        if not addresses:
            raise PyJWKClientConnectionError("JWKS host is not loopback-only")

        address = min(addresses, key=lambda item: (item.version, item.packed))
        authority = (
            f"[{address.compressed}]" if address.version == 6 else address.compressed
        )
        if parsed.port is not None:
            authority = f"{authority}:{parsed.port}"
        pinned_url = parsed._replace(netloc=authority).geturl()
        headers = {**self.headers, "Host": parsed.netloc}
        request = UrlRequest(pinned_url, headers=headers)
        opener = build_opener(ProxyHandler({}), _RejectRedirects())
        try:
            with opener.open(request, timeout=self.timeout) as response:
                jwk_set = self._as_jwk_set_payload(json.load(response))
        except (
            URLError,
            TimeoutError,
            http.client.HTTPException,
            OSError,
            ValueError,
        ) as error:
            raise PyJWKClientConnectionError(
                "Failed to fetch local test JWKS"
            ) from error

        if self.jwk_set_cache is not None:
            self.jwk_set_cache.put(jwk_set)
        self._last_successful_fetch = time.monotonic()
        return jwk_set


@lru_cache(maxsize=4)
def _jwks_client(url: str, allow_test_http: bool = False) -> PyJWKClient:
    scheme = urlsplit(url).scheme
    if scheme == "http":
        if not allow_test_http:
            raise PyJWKClientError("HTTP JWKS is disabled")
        return _LoopbackHTTPJWKClient(url)
    if scheme != "https":
        raise PyJWKClientError("Unsupported JWKS scheme")
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
        or not settings.clerk_authorized_parties
    ):
        raise _unauthorized()

    try:
        key = _jwks_client(
            settings.clerk_jwks_url,
            allow_test_http=settings.test_local_http_jwks,
        ).get_signing_key_from_jwt(credentials.credentials)
        claims = jwt.decode(
            credentials.credentials,
            key.key,
            algorithms=["RS256"],
            issuer=settings.clerk_issuer,
            options={"require": ["exp", "nbf", "iat", "iss", "sub"]},
        )
        owner_id = claims.get("sub")
        if not isinstance(owner_id, str) or not owner_id.strip():
            raise _unauthorized()
        authorized_parties = settings.clerk_authorized_parties or []
        if "azp" in claims:
            authorized_party = claims.get("azp")
            if (
                not isinstance(authorized_party, str)
                or not authorized_party
                or authorized_party not in authorized_parties
            ):
                raise _unauthorized()
        return cast(str, owner_id)
    except (PyJWTError, PyJWKClientError, OSError, TypeError, ValueError):
        raise _unauthorized() from None
