"""Sanitized wrapper result contract for a future local benchmark adapter.

This module defines the boundary between BenchScope and a private runner.  It
does not invoke the private benchmark or contain any private benchmark data.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

SAFE_TASK_ID_PATTERN = r"^[A-Za-z0-9](?:[A-Za-z0-9._ -]{0,126}[A-Za-z0-9._-])?$"
MANIFEST_SHA256_PATTERN = r"^[a-f0-9]{64}$"
WRAPPER_RESULT_VERSION = "benchscope.wrapper.result.v1"


class WrapperTaskResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str = Field(pattern=SAFE_TASK_ID_PATTERN)
    passed: bool


class WrapperBenchmarkDetails(BaseModel):
    model_config = ConfigDict(extra="forbid")

    benchmark_id: str = Field(min_length=1, max_length=255)
    release: str = Field(min_length=1, max_length=255)
    manifest_sha256: str = Field(pattern=MANIFEST_SHA256_PATTERN)
    expected_task_ids: list[str] = Field(min_length=1, max_length=10000)


class WrapperMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    elapsed_ms: int | None = Field(default=None, ge=0)
    prompt_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    generation_throughput_tps: float | None = Field(default=None, ge=0)


class WrapperResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = WRAPPER_RESULT_VERSION
    benchmark: WrapperBenchmarkDetails
    task_results: list[WrapperTaskResult] = Field(max_length=10000)
    metrics: WrapperMetrics = Field(default_factory=WrapperMetrics)


class WrapperResultError(ValueError):
    """Raised when wrapper output cannot be trusted."""


def parse_wrapper_jsonl(
    text: str, *, max_bytes: int = 1_048_576
) -> list[dict[str, Any]]:
    encoded = text.encode("utf-8")
    if len(encoded) > max_bytes:
        raise WrapperResultError("wrapper output exceeds the configured size limit")
    objects: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise WrapperResultError(
                f"invalid JSON on line {line_number}: {exc.msg}"
            ) from exc
        if not isinstance(value, dict):
            raise WrapperResultError(f"line {line_number} is not a JSON object")
        objects.append(value)
    if not objects:
        raise WrapperResultError("wrapper output is empty")
    return objects


def parse_wrapper_result(text: str, *, max_bytes: int = 1_048_576) -> WrapperResult:
    objects = parse_wrapper_jsonl(text, max_bytes=max_bytes)
    try:
        result = WrapperResult.model_validate(objects[-1])
    except ValidationError as exc:
        raise WrapperResultError(str(exc)) from exc
    validate_wrapper_result(result)
    return result


def validate_wrapper_result(
    result: WrapperResult, expected_task_ids: list[str] | None = None
) -> None:
    task_ids = [item.task_id for item in result.task_results]
    if len(task_ids) != len(set(task_ids)):
        raise WrapperResultError("task_results must contain unique task_id values")
    expected = (
        expected_task_ids
        if expected_task_ids is not None
        else result.benchmark.expected_task_ids
    )
    if not set(task_ids) <= set(expected):
        raise WrapperResultError("task_results must be in expected_task_ids")
    if result.benchmark.expected_task_ids != sorted(
        set(result.benchmark.expected_task_ids)
    ):
        # Preserve the supplied canonical order; only reject duplicates.
        pass
    if len(set(result.benchmark.expected_task_ids)) != len(
        result.benchmark.expected_task_ids
    ):
        raise WrapperResultError("expected_task_ids must be unique")


def exit_code_is_success(exit_code: int | None) -> bool:
    return exit_code == 0
