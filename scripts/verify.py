#!/usr/bin/env python3
"""Run all quality gates and restart-persistence checks in an isolated local stack."""

from __future__ import annotations

import json
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import urllib.request
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

from local_tools import ROOT, require_local_docker, run
from smoke_test import smoke_import_payload
from wait_for_deployment import wait_for_revision


def verify_backend_report(path: Path) -> None:
    for case in ET.parse(path).findall(".//testcase"):
        skipped = case.find("skipped")
        if skipped is None:
            continue
        reason = skipped.get("message", "") + " " + (skipped.text or "")
        if os.name != "nt" and "Windows" in reason:
            continue
        raise RuntimeError(f"Unexpected backend skip: {case.get('name')}")


def free_ports(count: int) -> list[str]:
    # Hold all reservations together so selected ports are distinct. Binding to
    # an ephemeral loopback port never stops/reuses another application's socket.
    listeners = []
    try:
        for _ in range(count):
            listener = socket.socket()
            listener.bind(("127.0.0.1", 0))
            listeners.append(listener)
        return [str(listener.getsockname()[1]) for listener in listeners]
    finally:
        for listener in listeners:
            listener.close()


def request_json(url: str, payload: dict | None = None) -> object:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode() if payload else None,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.load(response)


def verify_persistence(compose: list[str], env: dict[str, str]) -> None:
    api = f"http://127.0.0.1:{env['API_PORT']}"
    wait_for_revision(api, env["APP_REVISION"], timeout=120)
    payload = smoke_import_payload("verification-" + uuid.uuid4().hex)
    imported = request_json(api + "/api/v1/runs/import", payload)
    run_id = imported["run"]["id"]
    before = request_json(api + "/api/v1/runs/" + run_id)
    if before.get("metrics", {}).get("pass_rate") != 0.75:
        raise RuntimeError("Imported synthetic result did not read back correctly.")
    run(*compose, "restart", "api", env=env)
    wait_for_revision(api, env["APP_REVISION"], timeout=120)
    after = request_json(api + "/api/v1/runs/" + run_id)
    history = request_json(api + "/api/v1/runs")
    if after != before or not any(item["id"] == run_id for item in history["items"]):
        raise RuntimeError("Imported result did not survive the API restart.")
    frontend = f"http://127.0.0.1:{env['FRONTEND_PORT']}"
    with urllib.request.urlopen(frontend, timeout=10) as response:
        if response.status != 200:
            raise RuntimeError("Containerized frontend is not reachable.")
    print(
        "PASS: containerized frontend/API, import/history/detail, and persistence after API restart."
    )


def main() -> int:
    name = "benchscope-verify-" + uuid.uuid4().hex[:12]
    started = False
    env = dict(os.environ)
    for key in list(env):
        if key.startswith(("CLERK_", "VITE_", "E2E_", "OTEL_")) or key in {
            "DATABASE_URL",
            "TEST_DATABASE_URL",
            "APP_MODE",
            "APP_ENV",
            "APP_REVISION",
            "RENDER_GIT_COMMIT",
            "HOST",
            "PORT",
            "LOCAL_AUTH_BYPASS",
            "BENCHMARK_ENABLED",
            "CORS_ORIGINS",
        }:
            env.pop(key)
    env["VITE_API_URL"] = ""
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    with tempfile.TemporaryDirectory(prefix="benchscope-verification-") as temporary:
        # Explicit empty env file prevents Compose loading a developer's .env.
        empty_env = Path(temporary) / ".env"
        empty_env.touch()
        compose = [
            "docker",
            "compose",
            "--project-name",
            name,
            "--env-file",
            str(empty_env),
            "-f",
            str(ROOT / "compose.yaml"),
        ]
        try:
            require_local_docker()
            ports = free_ports(8)
            env.update(
                dict(
                    zip(
                        (
                            "POSTGRES_PORT",
                            "API_PORT",
                            "FRONTEND_PORT",
                            "E2E_API_PORT",
                            "E2E_JWKS_PORT",
                            "E2E_FRONTEND_PORT",
                            "E2E_DEMO_PORT",
                            "E2E_PREVIEW_PORT",
                        ),
                        ports,
                    )
                )
            )
            env.update(
                POSTGRES_PASSWORD=secrets.token_hex(24),
                POSTGRES_USER="benchscope_test",
                POSTGRES_DB="benchscope_test",
                APP_MODE="local",
                APP_ENV="development",
                LOCAL_AUTH_BYPASS="true",
            )
            revision = run(
                "git", "rev-parse", "HEAD", capture=True
            ).stdout.strip()
            # Only the app containers see development bypass. Unit/E2E harnesses
            # use their own explicit auth settings below.
            stack_env = dict(env)
            stack_env["APP_REVISION"] = revision
            started = True  # cleanup also covers partial Compose startup failures
            run(*compose, "up", "--build", "--wait", "--detach", env=stack_env)
            verify_persistence(compose, stack_env)
            for key in ("APP_ENV", "APP_MODE", "LOCAL_AUTH_BYPASS"):
                env.pop(key, None)
            env["TEST_DATABASE_URL"] = (
                f"postgresql+psycopg://benchscope_test:{stack_env['POSTGRES_PASSWORD']}@127.0.0.1:{ports[0]}/benchscope_test"
            )
            run(
                "uv",
                "sync",
                "--locked",
                "--group",
                "dev",
                cwd=ROOT / "backend",
                env=env,
            )
            run("uv", "lock", "--check", cwd=ROOT / "backend", env=env)
            run("uv", "run", "ruff", "check", ".", cwd=ROOT / "backend", env=env)
            run(
                "uv",
                "run",
                "ruff",
                "format",
                "--check",
                ".",
                cwd=ROOT / "backend",
                env=env,
            )
            report = Path(temporary) / "backend.xml"
            run(
                "uv",
                "run",
                "pytest",
                "-p",
                "anyio.pytest_plugin",
                "--junitxml",
                str(report),
                cwd=ROOT / "backend",
                env=env,
            )
            verify_backend_report(report)
            run(
                "corepack",
                "pnpm",
                "install",
                "--frozen-lockfile",
                cwd=ROOT / "frontend",
                env=env,
            )
            run("corepack", "pnpm", "test", cwd=ROOT / "frontend", env=env)
            run("corepack", "pnpm", "build", cwd=ROOT / "frontend", env=env)
            run("corepack", "pnpm", "check:api", cwd=ROOT / "frontend", env=env)
            run(
                "corepack",
                "pnpm",
                "exec",
                "playwright",
                "install",
                "chromium",
                cwd=ROOT / "frontend",
                env=env,
            )
            container_browser_env = {
                **env,
                "VERIFY_FRONTEND_URL": f"http://127.0.0.1:{stack_env['FRONTEND_PORT']}",
                "VERIFY_API_URL": f"http://127.0.0.1:{stack_env['API_PORT']}",
            }
            run("node", "scripts/verify-container.mjs", env=container_browser_env)
            run("corepack", "pnpm", "test:journey", cwd=ROOT / "frontend", env=env)
            print(
                "PASS: backend unit/integration, frontend tests/build/contract, and browser journeys."
            )
            return 0
        except (
            OSError,
            RuntimeError,
            subprocess.CalledProcessError,
            ValueError,
        ) as error:
            print(
                f"Verification failed: {error if not isinstance(error, subprocess.CalledProcessError) else 'a required check failed; see its output above.'}",
                file=sys.stderr,
            )
            return 1
        finally:
            if started:
                try:
                    # Unique project name scopes removal to this run. No image
                    # removal or global prune can affect another user's stack.
                    run(
                        *compose, "down", "--volumes", "--remove-orphans", env=stack_env
                    )
                except (RuntimeError, subprocess.CalledProcessError):
                    print(
                        f"Cleanup needs attention: verification project {name} was retained.",
                        file=sys.stderr,
                    )
                    raise SystemExit(1) from None


if __name__ == "__main__":
    sys.exit(main())
