#!/usr/bin/env python3
"""Wait for a healthy API running the exact intended Git commit."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable


class DeploymentVerificationError(RuntimeError):
    """A deployment did not reach the intended healthy revision."""


def fetch_json(url: str) -> object:
    with urllib.request.urlopen(url, timeout=10) as response:
        data = response.read(65537)
        if len(data) > 65536:
            raise ValueError("Oversized deployment metadata")
        return json.loads(data)


def wait_for_revision(
    api_url: str,
    expected: str,
    *,
    timeout: float = 300,
    interval: float = 5,
    fetch: Callable[[str], object] = fetch_json,
    clock: Callable[[], float] = time.monotonic,
    pause: Callable[[float], None] = time.sleep,
) -> None:
    if re.fullmatch(r"[0-9a-f]{40}", expected) is None:
        raise ValueError("Expected revision must be an exact 40-character commit SHA.")
    parsed = urllib.parse.urlsplit(api_url)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        raise ValueError("API URL must be an HTTP(S) origin without credentials.")
    if timeout <= 0 or interval <= 0:
        raise ValueError("Timeout and poll interval must be positive.")
    deadline = clock() + timeout
    api = api_url.rstrip("/")
    while clock() < deadline:
        try:
            version = fetch(f"{api}/version")
            readiness = fetch(f"{api}/ready")
            if (
                isinstance(version, dict)
                and version.get("revision") == expected
                and isinstance(readiness, dict)
                and readiness.get("status") == "ready"
            ):
                return
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            pass
        remaining = deadline - clock()
        if remaining > 0:
            pause(min(interval, remaining))
    raise DeploymentVerificationError(
        "API did not become ready at the expected commit before the deadline."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default=os.environ.get("SMOKE_API_URL"))
    parser.add_argument("--revision", default=os.environ.get("EXPECTED_REVISION"))
    parser.add_argument("--timeout", type=float, default=300)
    args = parser.parse_args()
    if not args.api_url or not args.revision:
        parser.error(
            "SMOKE_API_URL and EXPECTED_REVISION (or explicit arguments) are required"
        )
    try:
        wait_for_revision(args.api_url, args.revision, timeout=args.timeout)
    except (DeploymentVerificationError, ValueError) as error:
        print(f"::error::{error}", file=sys.stderr)
        return 1
    print(f"Backend is ready at intended revision {args.revision}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
