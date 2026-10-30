"""Server-controlled subprocess adapter foundation for Issue #25.

This module connects the verified process-tree cleanup and wrapper result
foundations to BenchScope's provisional runner seam.  It does not invoke the
private benchmark and does not accept commands, paths, or arguments from API
requests.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID

from app.benchmark_wrapper import (
    parse_wrapper_result,
    validate_wrapper_result,
)
from app.process_cleanup import (
    assign_process,
    create_job,
    is_windows,
)
from app.runner import RunResult


@dataclass(frozen=True)
class SubprocessAdapterConfig:
    """Server-side configuration only; never constructed from request input."""

    executable: str
    model_alias: str
    benchmark_id: str
    release: str
    manifest_sha256: str
    expected_task_ids: tuple[str, ...]
    config_id: UUID
    seed: int = 1234
    repeat: int = 1
    args: tuple[str, ...] = field(default_factory=tuple)
    working_root: Path = Path(tempfile.gettempdir()) / "benchscope-runs"
    timeout_seconds: float = 3600.0
    max_output_bytes: int = 1_048_576
    environment: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.executable or not Path(self.executable).is_absolute():
            raise ValueError("executable must be an absolute server-configured path")
        if not self.model_alias.strip():
            raise ValueError("model_alias is required")
        if not self.benchmark_id.strip() or not self.release.strip():
            raise ValueError("benchmark identity is required")
        if len(self.manifest_sha256) != 64 or any(
            char not in "0123456789abcdef" for char in self.manifest_sha256
        ):
            raise ValueError("manifest_sha256 must be lowercase hexadecimal")
        if not self.expected_task_ids or len(set(self.expected_task_ids)) != len(
            self.expected_task_ids
        ):
            raise ValueError("expected_task_ids must be non-empty and unique")
        if self.seed < 0:
            raise ValueError("seed must be non-negative")
        if self.repeat < 1:
            raise ValueError("repeat must be positive")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.max_output_bytes <= 0:
            raise ValueError("max_output_bytes must be positive")
        if not self.working_root.is_absolute():
            raise ValueError("working_root must be an absolute path")
        for key, value in self.environment.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise TypeError("environment values must be strings")


class SubprocessAdapter:
    """A cancellation-aware adapter that runs one configured wrapper process."""

    def __init__(self, config: SubprocessAdapterConfig) -> None:
        self.config = config
        self.last_process_id: int | None = None

    async def run(self, profile: dict[str, str | None], config_id: UUID) -> RunResult:
        if config_id != self.config.config_id:
            raise ValueError("config_id is not allowed for this adapter")

        working_directory = self.config.working_root / f"run-{config_id}"
        working_directory.mkdir(parents=True, exist_ok=True)
        result_path = working_directory / "result.jsonl"
        result_path.unlink(missing_ok=True)

        environment = {
            "PATH": os.environ.get("PATH", ""),
            "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
            "TEMP": os.environ.get("TEMP", ""),
            "TMP": os.environ.get("TMP", ""),
        }
        environment.update(self.config.environment)
        environment.update(
            {
                "BENCHSCOPE_RESULT_PATH": str(result_path),
                "BENCHSCOPE_MODEL_ALIAS": self.config.model_alias,
                "BENCHSCOPE_BENCHMARK_ID": self.config.benchmark_id,
                "BENCHSCOPE_RELEASE": self.config.release,
                "BENCHSCOPE_MANIFEST_SHA256": self.config.manifest_sha256,
                "BENCHSCOPE_EXPECTED_TASK_IDS": ",".join(self.config.expected_task_ids),
                "BENCHSCOPE_SEED": str(self.config.seed),
                "BENCHSCOPE_REPEAT": str(self.config.repeat),
                "BENCHSCOPE_CONFIG_ID": str(config_id),
                "BENCHSCOPE_PROFILE_JSON": _sanitized_profile(profile),
            }
        )

        process: asyncio.subprocess.Process | None = None
        job_handle: int | None = None
        try:
            process = await asyncio.create_subprocess_exec(
                self.config.executable,
                *self.config.args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(working_directory),
                env=environment,
            )
            self.last_process_id = process.pid
            if is_windows():
                try:
                    job_handle = create_job()
                    assign_process(job_handle, process.pid)
                except OSError:
                    job_handle = None

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=self.config.timeout_seconds
                )
            except TimeoutError as exc:
                await _terminate(process, job_handle)
                raise RuntimeError("Benchmark adapter timed out.") from exc
            except asyncio.CancelledError:
                await _terminate(process, job_handle)
                raise

            if (
                len(stdout) > self.config.max_output_bytes
                or len(stderr) > self.config.max_output_bytes
            ):
                await _terminate(process, job_handle)
                raise RuntimeError(
                    "Benchmark adapter output exceeded the configured bound."
                )

            if process.returncode != 0:
                raise RuntimeError(
                    f"Benchmark adapter exited with code {process.returncode}."
                )

            if not result_path.is_file():
                raise RuntimeError("Benchmark adapter did not produce a result file.")

            result_text = result_path.read_text(encoding="utf-8")
            if len(result_text.encode("utf-8")) > self.config.max_output_bytes:
                raise RuntimeError(
                    "Benchmark result file exceeded the configured bound."
                )

            wrapper_result = parse_wrapper_result(
                result_text, max_bytes=self.config.max_output_bytes
            )
            validate_wrapper_result(
                wrapper_result, expected_task_ids=list(self.config.expected_task_ids)
            )
            _validate_benchmark_identity(wrapper_result.benchmark, self.config)

            task_results = [item.model_dump() for item in wrapper_result.task_results]
            expected_count = len(self.config.expected_task_ids)
            completed_count = len(task_results)
            pass_count = sum(item.passed for item in wrapper_result.task_results)
            pass_rate = (
                pass_count / expected_count
                if completed_count == expected_count
                else None
            )
            metrics = wrapper_result.metrics
            return RunResult(
                quality_score=None,
                pass_rate=pass_rate,
                ttft_ms=None,
                prompt_tokens=metrics.prompt_tokens,
                output_tokens=metrics.output_tokens,
                prompt_throughput_tps=None,
                generation_throughput_tps=metrics.generation_throughput_tps,
                benchmark_details=wrapper_result.benchmark.model_dump(mode="json"),
                task_results=task_results,
            )
        finally:
            if job_handle is not None:
                try:
                    if is_windows():
                        from app.process_cleanup import kernel32

                        kernel32.TerminateJobObject(job_handle, 1)
                except OSError:
                    pass
                try:
                    from app.process_cleanup import kernel32 as _kernel32

                    _kernel32.CloseHandle(job_handle)
                except OSError:
                    pass
                job_handle = None
            if process is not None and process.returncode is None:
                await _terminate(process, None)
            shutil.rmtree(working_directory, ignore_errors=True)


def _sanitized_profile(profile: dict[str, str | None]) -> str:
    allowed = {"name", "model_name", "model_version", "quantisation"}
    return json.dumps(
        {key: profile.get(key) for key in allowed if profile.get(key) is not None},
        sort_keys=True,
    )


def _validate_benchmark_identity(actual: Any, config: SubprocessAdapterConfig) -> None:
    if actual.benchmark_id != config.benchmark_id:
        raise RuntimeError("Benchmark adapter returned an unexpected benchmark ID.")
    if actual.release != config.release:
        raise RuntimeError("Benchmark adapter returned an unexpected release.")
    if actual.manifest_sha256 != config.manifest_sha256:
        raise RuntimeError("Benchmark adapter returned an unexpected manifest hash.")
    if actual.expected_task_ids != list(config.expected_task_ids):
        raise RuntimeError("Benchmark adapter returned an unexpected task set.")


async def _terminate(
    process: asyncio.subprocess.Process, job_handle: int | None
) -> None:
    if job_handle is not None and is_windows():
        try:
            from app.process_cleanup import kernel32

            kernel32.TerminateJobObject(job_handle, 1)
        except OSError:
            pass
    if process.returncode is None:
        try:
            process.kill()
        except ProcessLookupError:
            pass
        await process.wait()
