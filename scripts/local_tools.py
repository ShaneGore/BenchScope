"""Shared, dependency-free helpers for local commands (never prints credentials)."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(
    *args: str,
    cwd: Path = ROOT,
    env: dict[str, str] | None = None,
    capture: bool = False,
) -> subprocess.CompletedProcess[str]:
    executable = shutil.which(args[0])
    if not executable:
        raise RuntimeError(f"Required command is unavailable: {args[0]}")
    command = [executable, *args[1:]]
    return subprocess.run(
        command, cwd=cwd, env=env, check=True, text=True, capture_output=capture
    )


def require_local_docker() -> None:
    if os.environ.get("DOCKER_HOST") or os.environ.get("DOCKER_CONTEXT"):
        raise RuntimeError(
            "Unset DOCKER_HOST/DOCKER_CONTEXT; these commands require the local Docker context."
        )
    endpoint = run(
        "docker",
        "context",
        "inspect",
        "--format",
        "{{.Endpoints.docker.Host}}",
        capture=True,
    ).stdout.strip()
    if not endpoint.startswith(("npipe:", "unix://")):
        raise RuntimeError("The selected Docker context is not a local socket.")
    try:
        run("docker", "info", "--format", "{{.ServerVersion}}", capture=True)
    except subprocess.CalledProcessError:
        raise RuntimeError(
            "Docker Engine is unavailable. Start Docker Desktop/Engine and retry."
        ) from None


def read_env(path: Path) -> dict[str, str]:
    values = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip("\"'")
    return values
