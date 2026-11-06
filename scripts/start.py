#!/usr/bin/env python3
"""Start the full local app; optional telemetry uses a separate Compose overlay."""

from __future__ import annotations

import argparse
import hashlib
import os
import secrets
import subprocess
import sys
from pathlib import Path

from local_tools import ROOT, read_env, require_local_docker, run


def prepare_environment(*, observability: bool = False) -> dict[str, str]:
    path = ROOT / ".env"
    if not path.exists():
        content = (ROOT / ".env.example").read_text(encoding="utf-8-sig")
        content = content.replace(
            "replace-with-a-local-url-safe-password", secrets.token_hex(24)
        )
        content = content.replace("LOCAL_AUTH_BYPASS=false", "LOCAL_AUTH_BYPASS=true")
        # Exclusive creation preserves another shell's configuration if it races us.
        try:
            with path.open("x", encoding="utf-8") as output:
                output.write(content)
            print("Created ignored .env with a random local database password.")
        except FileExistsError:
            pass
    values = read_env(path)
    env = {**values, **os.environ}
    if env.get("POSTGRES_PASSWORD") in (
        None,
        "",
        "replace-with-a-local-url-safe-password",
    ):
        raise RuntimeError(
            "Set POSTGRES_PASSWORD in your existing .env; it was not overwritten."
        )
    if (
        env.get("APP_MODE"),
        env.get("APP_ENV"),
        env.get("LOCAL_AUTH_BYPASS", "").lower(),
    ) != ("local", "development", "true"):
        raise RuntimeError(
            "Local startup needs APP_MODE=local, APP_ENV=development and LOCAL_AUTH_BYPASS=true in .env; existing configuration was preserved."
        )
    if observability:
        secret_path = Path(
            env.get("ALERT_RECEIVER_SECRET_FILE") or "./secrets/alert-receiver-bearer"
        )
        secret_path = (ROOT / secret_path).resolve()
        if not secret_path.is_relative_to(ROOT.resolve()):
            raise RuntimeError(
                "Keep ALERT_RECEIVER_SECRET_FILE inside this checkout's ignored secrets/ directory."
            )
        if not secret_path.is_relative_to((ROOT / "secrets").resolve()):
            raise RuntimeError(
                "ALERT_RECEIVER_SECRET_FILE must be inside the ignored secrets/ directory."
            )
        existing = secret_path.read_text().strip() if secret_path.exists() else ""
        configured = env.get("ALERT_RECEIVER_BEARER", "")
        if existing and configured and existing != configured:
            raise RuntimeError(
                "Receiver bearer and existing secret file differ; neither was changed."
            )
        bearer = configured or existing or secrets.token_hex(32)
        if not existing:
            secret_path.parent.mkdir(exist_ok=True)
            with secret_path.open("x", encoding="utf-8") as output:
                output.write(bearer)
        env["ALERT_RECEIVER_BEARER"] = bearer
        env["ALERT_RECEIVER_SECRET_FILE"] = str(secret_path)
    try:
        env["APP_REVISION"] = run(
            "git", "rev-parse", "HEAD", capture=True
        ).stdout.strip()
    except (RuntimeError, subprocess.CalledProcessError):
        env["APP_REVISION"] = "unknown"
    return env


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--observability",
        action="store_true",
        help="also start local metrics/logs/traces/Grafana and alert intake",
    )
    args = parser.parse_args()
    try:
        require_local_docker()
        env = prepare_environment(observability=args.observability)
        project = (
            "benchscope-" + hashlib.sha256(str(ROOT.resolve()).encode()).hexdigest()[:8]
        )
        compose = [
            "docker",
            "compose",
            "--project-name",
            project,
            "--env-file",
            str(ROOT / ".env"),
            "-f",
            "compose.yaml",
        ]
        if args.observability:
            compose.extend(["-f", "compose.observability.yaml"])
        run(*compose, "up", "--build", "--wait", "--detach", env=env)
        print(f"BenchScope: http://127.0.0.1:{env.get('FRONTEND_PORT', '5173')}")
        print(f"API readiness: http://127.0.0.1:{env.get('API_PORT', '8000')}/ready")
        print(f"Compose project: {project}; data persists in its PostgreSQL volume.")
        print("Stop while retaining data: " + " ".join(compose) + " down")
        return 0
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        # CalledProcessError may contain environment-derived arguments; do not echo it.
        print(
            f"Startup failed: {error if not isinstance(error, subprocess.CalledProcessError) else 'a required command failed; see its output above.'}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
