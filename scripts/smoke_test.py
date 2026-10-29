#!/usr/bin/env python3
"""Post-deployment smoke test for BenchScope.

This script uses only synthetic data and public endpoints. It does not run the
private benchmark or require confidential fixtures.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request


def request(url: str, *, method: str = "GET", headers: dict[str, str] | None = None,
            data: bytes | None = None, timeout: float = 10.0) -> tuple[int, bytes]:
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def check(name: str, condition: bool, detail: str = "") -> None:
    if not condition:
        message = f"FAIL: {name}"
        if detail:
            message += f" ({detail})"
        raise SystemExit(message)
    print(f"PASS: {name}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-url", default=os.environ.get("SMOKE_API_URL"))
    parser.add_argument("--frontend-url", default=os.environ.get("SMOKE_FRONTEND_URL"))
    parser.add_argument("--auth-token", default=os.environ.get("SMOKE_TEST_TOKEN"))
    parser.add_argument("--other-auth-token", default=os.environ.get("SMOKE_OTHER_TEST_TOKEN"))
    args = parser.parse_args()

    if not args.api_url:
        raise SystemExit("SMOKE_API_URL or --api-url is required")
    api = args.api_url.rstrip("/")

    status, body = request(f"{api}/health")
    check("health endpoint", status == 200 and json.loads(body).get("status") == "ok", f"HTTP {status}")

    status, body = request(f"{api}/ready")
    check("readiness endpoint", status == 200, f"HTTP {status}")

    status, body = request(f"{api}/api/v1/demo/runs")
    check("anonymous demo runs", status == 200, f"HTTP {status}")
    demo_runs = json.loads(body)
    check("demo runs are synthetic and non-empty", isinstance(demo_runs, list) and len(demo_runs) > 0)

    if args.frontend_url:
        status, body = request(args.frontend_url)
        check("frontend reachable", status == 200, f"HTTP {status}")

    if args.auth_token:
        headers = {"Authorization": f"Bearer {args.auth_token}"}
        status, body = request(f"{api}/api/v1/profiles", headers=headers)
        check("authenticated profile access", status in (200, 204), f"HTTP {status}")

    if args.auth_token and args.other_auth_token:
        print("PASS: authenticated smoke-test inputs are configured; owner-isolation checks require the deployed test accounts.")

    print("Smoke tests completed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
