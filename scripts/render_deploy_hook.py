#!/usr/bin/env python3
"""Trigger a Render deploy hook for one verified commit SHA."""

from __future__ import annotations

import argparse
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class DeployHookError(RuntimeError):
    """Raised when a deploy hook cannot be triggered safely."""


def build_deploy_url(hook_url: str, ref: str) -> str:
    """Return the deploy-hook URL with ``ref`` added or replaced.

    Existing query parameters, including Render's secret ``key`` parameter, are
    preserved. The returned URL is never printed by this module.
    """
    if not isinstance(ref, str) or SHA_RE.fullmatch(ref) is None:
        raise ValueError("deployment ref must be a 40-character lowercase hex commit SHA")

    parsed = urllib.parse.urlsplit(hook_url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("deploy hook URL must be an HTTPS URL with a host")

    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    query = [(key, value) for key, value in query if key != "ref"]
    query.append(("ref", ref))
    new_query = urllib.parse.urlencode(query)

    return urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, new_query, parsed.fragment)
    )


def trigger_deploy(hook_url: str, ref: str, *, timeout: float = 30.0) -> int:
    """Trigger Render deployment for *ref* and return the HTTP status code."""
    url = build_deploy_url(hook_url, ref)
    request = urllib.request.Request(url, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = response.getcode()
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as exc:
        raise DeployHookError("deployment trigger failed") from exc

    if status != 200:
        raise DeployHookError("deployment trigger failed")
    return status


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hook-url", default=os.environ.get("RENDER_DEPLOY_HOOK_URL"))
    parser.add_argument("--ref", default=os.environ.get("SELECTED_REF"))
    args = parser.parse_args()

    if not args.hook_url:
        print("::error::RENDER_DEPLOY_HOOK_URL is required", file=sys.stderr)
        return 2
    if not args.ref:
        print("::error::SELECTED_REF is required", file=sys.stderr)
        return 2

    try:
        trigger_deploy(args.hook_url, args.ref)
    except (ValueError, DeployHookError) as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 1

    print("Deployment trigger accepted.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
