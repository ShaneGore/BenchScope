#!/usr/bin/env python3
"""Export an allowlisted BenchScope v2 summary from private trial JSONL."""

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

SAFE_ID = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._ -]{0,126}[A-Za-z0-9._-])?$")
SAFE_LABEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,254}$")


class ExportError(ValueError):
    pass


def _reject_constant(_value: str) -> None:
    raise ExportError("invalid JSON number")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ExportError("duplicate JSON key")
        result[key] = value
    return result


def _aware_timestamp(value: str) -> str:
    try:
        timestamp = datetime.fromisoformat(value)
    except ValueError:
        raise ExportError("start and end must be ISO timestamps") from None
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ExportError("start and end must include a timezone")
    return timestamp.isoformat()


def _manifest_task_ids(manifest: Any) -> tuple[str, list[str], dict[str, str]]:
    if not isinstance(manifest, dict) or not isinstance(manifest.get("tasks"), list):
        raise ExportError("manifest must contain a tasks array")
    release = manifest.get("release")
    if not isinstance(release, str) or not SAFE_LABEL.fullmatch(release):
        raise ExportError("manifest release is invalid")
    task_ids: list[str] = []
    aliases_by_task: list[tuple[str, list[str]]] = []
    for task in manifest["tasks"]:
        if not isinstance(task, dict):
            raise ExportError("manifest task record is invalid")
        release_id = task.get("release_id")
        if not isinstance(release_id, str) or not SAFE_ID.fullmatch(release_id):
            raise ExportError("manifest release_id is invalid")
        if release_id in task_ids:
            raise ExportError("manifest release_id is duplicated")
        task_ids.append(release_id)
        task_aliases = task.get("aliases", [])
        if isinstance(task_aliases, str):
            task_aliases = [task_aliases]
        elif not isinstance(task_aliases, list):
            raise ExportError("manifest aliases are invalid")
        if any(not isinstance(alias, str) or not alias for alias in task_aliases):
            raise ExportError("manifest alias is invalid")
        aliases_by_task.append((release_id, task_aliases))
    if not task_ids:
        raise ExportError("manifest has no release_id task IDs")

    canonical_ids = set(task_ids)
    aliases: dict[str, str] = {}
    for release_id, task_aliases in aliases_by_task:
        for alias in task_aliases:
            if alias in canonical_ids and alias != release_id:
                raise ExportError(
                    "manifest alias conflicts with a canonical release_id"
                )
            if alias in aliases:
                raise ExportError("manifest alias is ambiguous")
            aliases[alias] = release_id
    return release, sorted(task_ids), aliases


def export_run(
    manifest_bytes: bytes,
    jsonl: str,
    *,
    benchmark_id: str,
    model_name: str,
    profile_name: str,
    started_at: str,
    ended_at: str,
    seed: int,
    repeat_index: int,
) -> dict[str, Any]:
    try:
        manifest = json.loads(
            manifest_bytes,
            parse_constant=_reject_constant,
            object_pairs_hook=_unique_object,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError):
        raise ExportError("manifest is not valid JSON") from None
    release, expected_ids, aliases = _manifest_task_ids(manifest)
    if (
        not SAFE_LABEL.fullmatch(benchmark_id)
        or not model_name
        or len(model_name) > 255
        or not profile_name
        or len(profile_name) > 255
    ):
        raise ExportError("benchmark and profile labels are required")
    start = _aware_timestamp(started_at)
    end = _aware_timestamp(ended_at)
    start_datetime = datetime.fromisoformat(start)
    end_datetime = datetime.fromisoformat(end)
    if end_datetime < start_datetime:
        raise ExportError("end must be at or after start")
    elapsed_ms = (end_datetime - start_datetime) // timedelta(milliseconds=1)
    if (
        type(seed) is not int
        or seed < 0
        or type(repeat_index) is not int
        or repeat_index < 0
    ):
        raise ExportError("seed and repeat index must be non-negative integers")

    outcomes: dict[str, bool] = {}
    token_totals = {"prompt_tokens": 0, "output_tokens": 0}
    complete_token_totals = {"prompt_tokens": True, "output_tokens": True}
    for line_number, line in enumerate(jsonl.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(
                line,
                parse_constant=_reject_constant,
                object_pairs_hook=_unique_object,
            )
        except (json.JSONDecodeError, RecursionError, ExportError):
            raise ExportError(f"JSONL record {line_number} is invalid") from None
        if not isinstance(record, dict):
            raise ExportError(f"JSONL record {line_number} is invalid")
        task_id = record.get("task_id")
        record_seed = record.get("seed")
        record_repeat = record.get("repeat_index")
        passed = record.get("pass")
        if (
            not isinstance(task_id, str)
            or type(record_seed) is not int
            or record_seed < 0
            or type(record_repeat) is not int
            or record_repeat < 0
            or type(passed) is not bool
        ):
            raise ExportError(f"JSONL record {line_number} is invalid")
        if (record_seed, record_repeat) != (seed, repeat_index):
            continue
        canonical_id = aliases.get(task_id, task_id)
        if canonical_id not in expected_ids:
            raise ExportError(f"JSONL record {line_number} has an unknown task ID")
        if canonical_id in outcomes:
            raise ExportError(f"duplicate task outcome for {canonical_id}")
        outcomes[canonical_id] = passed
        for metric in token_totals:
            value = record.get(metric)
            if value is None:
                complete_token_totals[metric] = False
            elif type(value) is not int or value < 0:
                raise ExportError(f"JSONL record {line_number} has invalid {metric}")
            else:
                token_totals[metric] += value

    if not outcomes:
        raise ExportError("selected seed/repeat group has no records")

    return {
        "format_version": "benchscope.run.v2",
        "profile_snapshot": {
            "name": profile_name,
            "model_name": model_name,
        },
        "benchmark_config": {
            "name": benchmark_id,
            "seed": seed,
            "repeat_index": repeat_index,
        },
        "started_at": start,
        "ended_at": end,
        "metrics": {
            metric: token_totals[metric] if complete_token_totals[metric] else None
            for metric in token_totals
        }
        | {"elapsed_ms": elapsed_ms},
        "benchmark_details": {
            "benchmark_id": benchmark_id,
            "release": release,
            "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
            "expected_task_ids": expected_ids,
        },
        "task_results": [
            {"task_id": task_id, "passed": outcomes[task_id]}
            for task_id in expected_ids
            if task_id in outcomes
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--jsonl", required=True, type=Path)
    parser.add_argument("--benchmark-id", required=True)
    parser.add_argument("--model-name", required=True)
    parser.add_argument("--profile-name", required=True)
    parser.add_argument("--started-at", required=True)
    parser.add_argument("--ended-at", required=True)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--repeat-index", required=True, type=int)
    args = parser.parse_args(argv)
    try:
        exported = export_run(
            args.manifest.read_bytes(),
            args.jsonl.read_text(encoding="utf-8"),
            benchmark_id=args.benchmark_id,
            model_name=args.model_name,
            profile_name=args.profile_name,
            started_at=args.started_at,
            ended_at=args.ended_at,
            seed=args.seed,
            repeat_index=args.repeat_index,
        )
    except (OSError, UnicodeError, ExportError):
        print("Export failed: input is invalid or unreadable.", file=sys.stderr)
        return 2
    json.dump(exported, sys.stdout, sort_keys=True, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
