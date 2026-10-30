import asyncio
import sys
from pathlib import Path
from uuid import uuid4

import pytest

from app.benchmark_adapter_subprocess import (
    SubprocessAdapter,
    SubprocessAdapterConfig,
)
from app.process_cleanup import process_exists
from app.runner import RunResult


def _config(
    tmp_path: Path, script: str, **overrides: object
) -> SubprocessAdapterConfig:
    values = {
        "executable": sys.executable,
        "model_alias": "test-model",
        "benchmark_id": "bench",
        "release": "1.0",
        "manifest_sha256": "a" * 64,
        "expected_task_ids": ("task-1",),
        "config_id": uuid4(),
        "args": ("-c", script),
        "working_root": tmp_path,
        "timeout_seconds": 5.0,
        "max_output_bytes": 10000,
    }
    values.update(overrides)
    return SubprocessAdapterConfig(**values)  # type: ignore[arg-type]


def _success_script() -> str:
    return (
        "import json, os\n"
        "path = os.environ['BENCHSCOPE_RESULT_PATH']\n"
        "result = {\n"
        "  'schema_version': 'benchscope.wrapper.result.v1',\n"
        "  'benchmark': {\n"
        "    'benchmark_id': os.environ['BENCHSCOPE_BENCHMARK_ID'],\n"
        "    'release': os.environ['BENCHSCOPE_RELEASE'],\n"
        "    'manifest_sha256': os.environ['BENCHSCOPE_MANIFEST_SHA256'],\n"
        "    'expected_task_ids': os.environ['BENCHSCOPE_EXPECTED_TASK_IDS'].split(','),\n"
        "  },\n"
        "  'task_results': [{'task_id': 'task-1', 'passed': True}],\n"
        "  'metrics': {'elapsed_ms': 1, 'prompt_tokens': 2, 'output_tokens': 3, 'generation_throughput_tps': 4.0},\n"
        "}\n"
        "with open(path, 'w', encoding='utf-8') as handle:\n"
        "    handle.write(__import__('json').dumps(result) + '\\n')\n"
        "print('adapter stdout')\n"
    )


@pytest.mark.anyio
async def test_subprocess_adapter_success(tmp_path: Path) -> None:
    config = _config(tmp_path, _success_script())
    adapter = SubprocessAdapter(config)
    result = await adapter.run({"name": "profile", "model_name": "m"}, config.config_id)
    assert isinstance(result, RunResult)
    assert result.quality_score is None
    assert result.pass_rate == 1.0
    assert result.prompt_tokens == 2
    assert result.output_tokens == 3
    assert result.task_results == [{"task_id": "task-1", "passed": True}]
    assert result.benchmark_details is not None


@pytest.mark.anyio
async def test_subprocess_adapter_partial_result_has_null_pass_rate(
    tmp_path: Path,
) -> None:
    script = _success_script().replace(
        "'task_results': [{'task_id': 'task-1', 'passed': True}],",
        "'task_results': [],",
    )
    config = _config(tmp_path, script, expected_task_ids=("task-1", "task-2"))
    adapter = SubprocessAdapter(config)
    result = await adapter.run({}, config.config_id)
    assert result.pass_rate is None
    assert result.task_results == []


@pytest.mark.anyio
async def test_subprocess_adapter_malformed_result(tmp_path: Path) -> None:
    script = (
        "import os\n"
        "with open(os.environ['BENCHSCOPE_RESULT_PATH'], 'w', encoding='utf-8') as handle:\n"
        "    handle.write('{bad json}\\n')\n"
    )
    config = _config(tmp_path, script)
    adapter = SubprocessAdapter(config)
    with pytest.raises(ValueError):
        await adapter.run({}, config.config_id)


@pytest.mark.anyio
async def test_subprocess_adapter_unknown_task(tmp_path: Path) -> None:
    script = _success_script().replace("'task-1'", "'task-2'")
    config = _config(tmp_path, script)
    adapter = SubprocessAdapter(config)
    with pytest.raises(ValueError):
        await adapter.run({}, config.config_id)


@pytest.mark.anyio
async def test_subprocess_adapter_duplicate_task(tmp_path: Path) -> None:
    script = _success_script().replace(
        "'task_results': [{'task_id': 'task-1', 'passed': True}],",
        "'task_results': [{'task_id': 'task-1', 'passed': True}, {'task_id': 'task-1', 'passed': False}],",
    )
    config = _config(tmp_path, script)
    adapter = SubprocessAdapter(config)
    with pytest.raises(ValueError):
        await adapter.run({}, config.config_id)


@pytest.mark.anyio
async def test_subprocess_adapter_unexpected_exit_code(tmp_path: Path) -> None:
    script = "import sys\nprint('failing')\nsys.exit(3)\n"
    config = _config(tmp_path, script)
    adapter = SubprocessAdapter(config)
    with pytest.raises(RuntimeError, match="exited with code 3"):
        await adapter.run({}, config.config_id)


@pytest.mark.anyio
async def test_subprocess_adapter_timeout(tmp_path: Path) -> None:
    script = "import time\ntime.sleep(5)\n"
    config = _config(tmp_path, script, timeout_seconds=0.1)
    adapter = SubprocessAdapter(config)
    with pytest.raises(RuntimeError, match="timed out"):
        await adapter.run({}, config.config_id)


@pytest.mark.anyio
async def test_subprocess_adapter_output_limit(tmp_path: Path) -> None:
    script = "print('x' * 1000)\n"
    config = _config(tmp_path, script, max_output_bytes=10)
    adapter = SubprocessAdapter(config)
    with pytest.raises(RuntimeError, match="output exceeded"):
        await adapter.run({}, config.config_id)


@pytest.mark.anyio
async def test_subprocess_adapter_missing_usage_metadata(tmp_path: Path) -> None:
    script = _success_script().replace(
        "  'metrics': {'elapsed_ms': 1, 'prompt_tokens': 2, 'output_tokens': 3, 'generation_throughput_tps': 4.0},",
        "  'metrics': {},",
    )
    config = _config(tmp_path, script)
    adapter = SubprocessAdapter(config)
    result = await adapter.run({}, config.config_id)
    assert result.prompt_tokens is None
    assert result.output_tokens is None
    assert result.generation_throughput_tps is None


@pytest.mark.anyio
async def test_subprocess_adapter_identity_mismatch(tmp_path: Path) -> None:
    script = _success_script().replace(
        "os.environ['BENCHSCOPE_BENCHMARK_ID']",
        "'wrong-benchmark'",
    )
    config = _config(tmp_path, script)
    adapter = SubprocessAdapter(config)
    with pytest.raises(RuntimeError, match="unexpected benchmark ID"):
        await adapter.run({}, config.config_id)


@pytest.mark.anyio
async def test_subprocess_adapter_cancellation(tmp_path: Path) -> None:
    script = "import time\ntime.sleep(5)\n"
    config = _config(tmp_path, script, timeout_seconds=5.0)
    adapter = SubprocessAdapter(config)
    task = asyncio.create_task(adapter.run({}, config.config_id))
    await asyncio.sleep(0.2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    if adapter.last_process_id is not None:
        deadline = asyncio.get_event_loop().time() + 2
        while (
            process_exists(adapter.last_process_id)
            and asyncio.get_event_loop().time() < deadline
        ):
            await asyncio.sleep(0.05)
        assert not process_exists(adapter.last_process_id)


def test_subprocess_adapter_config_rejects_user_controlled_paths() -> None:
    with pytest.raises(ValueError):
        SubprocessAdapterConfig(
            executable="python",
            model_alias="m",
            benchmark_id="b",
            release="r",
            manifest_sha256="a" * 64,
            expected_task_ids=("task-1",),
            config_id=uuid4(),
        )
    with pytest.raises(ValueError):
        SubprocessAdapterConfig(
            executable=sys.executable,
            model_alias="m",
            benchmark_id="b",
            release="r",
            manifest_sha256="a" * 64,
            expected_task_ids=("task-1",),
            config_id=uuid4(),
            args=("--evil",),
            working_root=Path("relative"),
        )


def test_subprocess_adapter_sanitized_profile_excludes_paths() -> None:
    from app.benchmark_adapter_subprocess import _sanitized_profile

    profile = {
        "name": "profile",
        "model_name": "model",
        "endpoint_url": "http://secret",
        "inference_config": {"token": "secret"},
    }
    serialized = _sanitized_profile(profile)
    assert "endpoint_url" not in serialized
    assert "inference_config" not in serialized
