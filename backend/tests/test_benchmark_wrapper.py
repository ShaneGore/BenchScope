import pytest

from app.benchmark_wrapper import (
    WrapperResultError,
    exit_code_is_success,
    parse_wrapper_jsonl,
    parse_wrapper_result,
    validate_wrapper_result,
)


def test_parse_single_json_object() -> None:
    result = parse_wrapper_result(
        '{"schema_version":"benchscope.wrapper.result.v1",'
        '"benchmark":{"benchmark_id":"b","release":"r","manifest_sha256":"'
        + "a"
        * 64
        + '","expected_task_ids":["t1"]},'
        '"task_results":[{"task_id":"t1","passed":true}],'
        '"metrics":{"elapsed_ms":10}}'
    )
    assert result.benchmark.benchmark_id == "b"
    assert result.task_results[0].passed is True


def test_parse_jsonl_uses_final_object() -> None:
    objects = parse_wrapper_jsonl('{"a":1}\n{"a":2}\n')
    assert objects == [{"a": 1}, {"a": 2}]


def test_malformed_jsonl_rejected() -> None:
    with pytest.raises(WrapperResultError):
        parse_wrapper_jsonl('{"a":1}\n{bad}\n')


def test_incomplete_output_rejected() -> None:
    with pytest.raises(WrapperResultError):
        parse_wrapper_result("")


def test_duplicate_task_ids_rejected() -> None:
    text = (
        '{"schema_version":"benchscope.wrapper.result.v1",'
        '"benchmark":{"benchmark_id":"b","release":"r","manifest_sha256":"'
        + "a"
        * 64
        + '","expected_task_ids":["t1"]},'
        '"task_results":[{"task_id":"t1","passed":true},{"task_id":"t1","passed":false}],'
        '"metrics":{}}'
    )
    with pytest.raises(WrapperResultError):
        parse_wrapper_result(text)


def test_unknown_task_ids_rejected() -> None:
    text = (
        '{"schema_version":"benchscope.wrapper.result.v1",'
        '"benchmark":{"benchmark_id":"b","release":"r","manifest_sha256":"'
        + "a"
        * 64
        + '","expected_task_ids":["t1"]},'
        '"task_results":[{"task_id":"t2","passed":true}],'
        '"metrics":{}}'
    )
    with pytest.raises(WrapperResultError):
        parse_wrapper_result(text)


def test_unexpected_exit_code_helper() -> None:
    assert exit_code_is_success(0) is True
    assert exit_code_is_success(1) is False
    assert exit_code_is_success(None) is False


def test_missing_usage_metadata_stays_null() -> None:
    result = parse_wrapper_result(
        '{"schema_version":"benchscope.wrapper.result.v1",'
        '"benchmark":{"benchmark_id":"b","release":"r","manifest_sha256":"'
        + "a"
        * 64
        + '","expected_task_ids":["t1"]},'
        '"task_results":[{"task_id":"t1","passed":true}],'
        '"metrics":{}}'
    )
    assert result.metrics.prompt_tokens is None
    assert result.metrics.output_tokens is None
    assert result.metrics.generation_throughput_tps is None


def test_output_size_limit() -> None:
    with pytest.raises(WrapperResultError):
        parse_wrapper_jsonl('{"a":1}\n', max_bytes=1)


def test_coverage_can_be_partial() -> None:
    result = parse_wrapper_result(
        '{"schema_version":"benchscope.wrapper.result.v1",'
        '"benchmark":{"benchmark_id":"b","release":"r","manifest_sha256":"'
        + "a"
        * 64
        + '","expected_task_ids":["t1","t2"]},'
        '"task_results":[{"task_id":"t1","passed":true}],'
        '"metrics":{}}'
    )
    validate_wrapper_result(result)
    assert len(result.task_results) == 1
