#!/usr/bin/env python3
"""Generate short-lived Clerk session tokens for staging smoke tests.

The generated tokens are written only to the requested destination. They are
never printed, because Clerk session tokens are sensitive and expire quickly.

The session-creation API used here is a testing-only Clerk API and requires a
Development instance. Do not use it with a Production instance.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

CLERK_API_BASE = "https://api.clerk.com"
MIN_EXPIRES_IN_SECONDS = 30
MAX_EXPIRES_IN_SECONDS = 315360000


class SmokeCredentialError(RuntimeError):
    """Raised when Clerk smoke credentials cannot be generated safely."""


def _validate_base_url(base_url: str) -> str:
    parsed = urllib.parse.urlsplit(base_url.rstrip("/"))
    if parsed.scheme != "https" or not parsed.netloc or parsed.path not in ("", "/"):
        raise SmokeCredentialError("Clerk API base URL must be an HTTPS origin")
    return f"{parsed.scheme}://{parsed.netloc}"


def _request(
    method: str,
    url: str,
    secret_key: str,
    payload: dict[str, Any] | None = None,
    *,
    timeout: float = 10.0,
) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {secret_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "BenchScope smoke-token generator",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = response.getcode()
            body = response.read()
    except urllib.error.HTTPError as exc:
        raise SmokeCredentialError(
            f"Clerk credential request failed with HTTP {exc.code}"
        ) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise SmokeCredentialError("Clerk credential request failed") from exc

    if status != 200:
        raise SmokeCredentialError(
            f"Clerk credential request failed with HTTP {status}"
        )

    try:
        parsed = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SmokeCredentialError("Clerk returned an invalid JSON response") from exc
    if not isinstance(parsed, dict):
        raise SmokeCredentialError("Clerk returned an unexpected response")
    return parsed


def create_session(
    secret_key: str,
    user_id: str,
    *,
    base_url: str = CLERK_API_BASE,
    timeout: float = 10.0,
) -> str:
    """Create a Clerk session for a synthetic smoke-test user."""
    if not secret_key.strip():
        raise SmokeCredentialError("CLERK_SECRET_KEY is required")
    if not user_id.strip():
        raise SmokeCredentialError("a Clerk user ID is required")

    origin = _validate_base_url(base_url)
    url = f"{origin}/v1/sessions"
    response = _request(
        "POST",
        url,
        secret_key,
        {"user_id": user_id.strip()},
        timeout=timeout,
    )
    session_id = response.get("id")
    if not isinstance(session_id, str) or not session_id.strip():
        raise SmokeCredentialError("Clerk did not return a session ID")
    return session_id.strip()


def create_session_token(
    secret_key: str,
    session_id: str,
    *,
    expires_in_seconds: int = 60,
    base_url: str = CLERK_API_BASE,
    timeout: float = 10.0,
) -> str:
    """Create a short-lived session JWT for an existing Clerk session."""
    if not secret_key.strip():
        raise SmokeCredentialError("CLERK_SECRET_KEY is required")
    if not session_id.strip():
        raise SmokeCredentialError("a Clerk session ID is required")
    if not MIN_EXPIRES_IN_SECONDS <= expires_in_seconds <= MAX_EXPIRES_IN_SECONDS:
        raise SmokeCredentialError(
            "expires_in_seconds is outside Clerk's allowed range"
        )

    origin = _validate_base_url(base_url)
    quoted_session_id = urllib.parse.quote(session_id.strip(), safe="")
    url = f"{origin}/v1/sessions/{quoted_session_id}/tokens"
    response = _request(
        "POST",
        url,
        secret_key,
        {"expires_in_seconds": expires_in_seconds},
        timeout=timeout,
    )
    jwt = response.get("jwt")
    if not isinstance(jwt, str) or not jwt.strip():
        raise SmokeCredentialError("Clerk did not return a session token")
    return jwt.strip()


def generate_tokens(
    secret_key: str,
    user_a_id: str,
    user_b_id: str,
    *,
    expires_in_seconds: int = 60,
    base_url: str = CLERK_API_BASE,
    timeout: float = 10.0,
) -> dict[str, str]:
    """Generate tokens for the two designated synthetic smoke-test users."""
    session_a = create_session(
        secret_key, user_a_id, base_url=base_url, timeout=timeout
    )
    session_b = create_session(
        secret_key, user_b_id, base_url=base_url, timeout=timeout
    )
    token_a = create_session_token(
        secret_key,
        session_a,
        expires_in_seconds=expires_in_seconds,
        base_url=base_url,
        timeout=timeout,
    )
    token_b = create_session_token(
        secret_key,
        session_b,
        expires_in_seconds=expires_in_seconds,
        base_url=base_url,
        timeout=timeout,
    )
    return {
        "SMOKE_TEST_TOKEN": token_a,
        "SMOKE_OTHER_TEST_TOKEN": token_b,
    }


def write_env_file(
    tokens: dict[str, str], path: str | Path, *, append: bool = False
) -> None:
    """Write tokens to an environment file without printing them."""
    destination = Path(path)
    mode = "a" if append else "w"
    with destination.open(mode, encoding="utf-8") as handle:
        for name, value in tokens.items():
            handle.write(f"{name}={value}\n")
    try:
        os.chmod(destination, 0o600)
    except OSError:
        # chmod is best-effort on platforms that do not support POSIX modes.
        pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--secret-key", default=os.environ.get("CLERK_SECRET_KEY"))
    parser.add_argument("--user-a-id", default=os.environ.get("SMOKE_TEST_USER_A_ID"))
    parser.add_argument("--user-b-id", default=os.environ.get("SMOKE_TEST_USER_B_ID"))
    parser.add_argument("--base-url", default=CLERK_API_BASE)
    parser.add_argument("--expires-in", type=int, default=60)
    parser.add_argument("--write-github-env", action="store_true")
    parser.add_argument("--env-file")
    args = parser.parse_args()

    if not args.secret_key:
        print("::error::CLERK_SECRET_KEY is required", file=sys.stderr)
        return 2
    if not args.user_a_id:
        print("::error::SMOKE_TEST_USER_A_ID is required", file=sys.stderr)
        return 2
    if not args.user_b_id:
        print("::error::SMOKE_TEST_USER_B_ID is required", file=sys.stderr)
        return 2
    if args.user_a_id == args.user_b_id:
        print("::error::smoke-test users must be distinct", file=sys.stderr)
        return 2

    try:
        tokens = generate_tokens(
            args.secret_key,
            args.user_a_id,
            args.user_b_id,
            expires_in_seconds=args.expires_in,
            base_url=args.base_url,
        )
    except SmokeCredentialError as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 1

    if args.write_github_env:
        destination = os.environ.get("GITHUB_ENV")
        if not destination:
            print("::error::GITHUB_ENV is not available", file=sys.stderr)
            return 2
        write_env_file(tokens, destination, append=True)
    elif args.env_file:
        write_env_file(tokens, args.env_file)
    else:
        print(
            "::error::an output destination is required (--write-github-env or --env-file)",
            file=sys.stderr,
        )
        return 2

    print("Generated smoke credentials.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
