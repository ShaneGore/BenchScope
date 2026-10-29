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
from datetime import datetime, timedelta, timezone


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


def load_json(body: bytes) -> object:
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return None


def smoke_import_payload(source_run_id: str) -> dict[str, object]:
    started_at = datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat()
    ended_at = (datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=1)).isoformat()
    return {
        "format_version": "benchscope.run.v1",
        "source_run_id": source_run_id,
        "profile_snapshot": {
            "name": "Smoke Test Model",
            "model_name": "smoke-test-model",
            "model_version": "1.0",
            "quantisation": "Q4",
        },
        "benchmark_config": {
            "name": "smoke-test",
            "temperature": 0.2,
            "max_tokens": 128,
        },
        "started_at": started_at,
        "ended_at": ended_at,
        "metrics": {
            "quality_score": 0.8,
            "pass_rate": 0.75,
            "elapsed_ms": 60000,
        },
        "hardware_snapshot": {
            "cpu": "Smoke CPU",
            "gpu": "Smoke GPU",
            "ram_gb": 16,
            "gpu_vram_gb": 8,
            "os": "Smoke OS",
        },
    }


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
    check("health endpoint", status == 200 and load_json(body) == {"status": "ok"}, f"HTTP {status}")

    status, body = request(f"{api}/ready")
    check("readiness endpoint", status == 200, f"HTTP {status}")

    status, body = request(f"{api}/api/v1/demo/runs")
    check("anonymous demo runs", status == 200, f"HTTP {status}")
    demo_runs = load_json(body)
    check("demo runs are synthetic and non-empty", isinstance(demo_runs, list) and len(demo_runs) > 0)

    status, _ = request(f"{api}/api/v1/demo/runs", method="POST")
    check("anonymous demo records are immutable", status in (401, 403, 404, 405), f"HTTP {status}")

    if args.frontend_url:
        status, _ = request(args.frontend_url)
        check("frontend reachable", status == 200, f"HTTP {status}")

    if not args.auth_token:
        print("SKIP: authenticated import/history/comparison checks require SMOKE_TEST_TOKEN")
        print("Smoke tests completed successfully.")
        return 0

    headers = {"Authorization": f"Bearer {args.auth_token}"}
    status, body = request(f"{api}/api/v1/profiles", headers=headers)
    check("authenticated access", status in (200, 204), f"HTTP {status}")

    status, body = request(f"{api}/api/v1/runs", headers=headers)
    check("run history accessible", status == 200, f"HTTP {status}")
    history = load_json(body)
    smoke_runs = [
        item for item in history.get("items", [])
        if item.get("profile_snapshot", {}).get("model_name") == "smoke-test-model"
    ] if isinstance(history, dict) else []

    for source_run_id in ("smoke-test-run-a", "smoke-test-run-b"):
        if len(smoke_runs) >= 2:
            break
        payload = smoke_import_payload(source_run_id)
        status, body = request(
            f"{api}/api/v1/runs/import",
            method="POST",
            headers={**headers, "Content-Type": "application/json"},
            data=json.dumps(payload).encode("utf-8"),
        )
        check(f"import synthetic run {source_run_id}", status in (201, 409), f"HTTP {status}")
        if status == 201:
            imported = load_json(body)
            if isinstance(imported, dict) and isinstance(imported.get("run"), dict):
                smoke_runs.append(imported["run"])

    status, body = request(f"{api}/api/v1/runs", headers=headers)
    check("run history after import", status == 200, f"HTTP {status}")
    history = load_json(body)
    smoke_runs = [
        item for item in history.get("items", [])
        if item.get("profile_snapshot", {}).get("model_name") == "smoke-test-model"
    ] if isinstance(history, dict) else []
    check("at least two smoke-test runs exist", len(smoke_runs) >= 2, f"found {len(smoke_runs)}")

    first_id = smoke_runs[0]["id"]
    second_id = smoke_runs[1]["id"]

    status, body = request(f"{api}/api/v1/runs/{first_id}", headers=headers)
    check("run detail retrievable", status == 200 and load_json(body).get("id") == first_id, f"HTTP {status}")

    status, body = request(f"{api}/api/v1/runs/compare?ids={first_id},{second_id}", headers=headers)
    check("run comparison works", status == 200 and isinstance(load_json(body), list) and len(load_json(body)) >= 2, f"HTTP {status}")

    if args.other_auth_token:
        other_headers = {"Authorization": f"Bearer {args.other_auth_token}"}
        status, _ = request(f"{api}/api/v1/runs/{first_id}", headers=other_headers)
        check("owner isolation enforced", status == 404, f"HTTP {status}")
    else:
        print("SKIP: owner-isolation check requires SMOKE_OTHER_TEST_TOKEN")

    print("Smoke tests completed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
