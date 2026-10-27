from copy import deepcopy

import pytest
from pydantic import ValidationError

from app.imports import RunImportRequest, _fingerprint, _validation_failures


def valid_request() -> dict[str, object]:
    return {
        "format_version": "benchscope.run.v1",
        "profile_snapshot": {"name": "Local", "model_name": "example/model"},
        "benchmark_config": {"name": "short", "temperature": 0},
        "started_at": "2026-10-26T10:00:00Z",
        "ended_at": "2026-10-26T10:00:01Z",
    }


def test_missing_metrics_normalize_to_null_without_changing_zero() -> None:
    request = RunImportRequest.model_validate(valid_request())
    metrics = request.metrics.model_dump()

    assert set(metrics) == {
        "quality_score",
        "pass_rate",
        "ttft_ms",
        "prompt_tokens",
        "output_tokens",
        "prompt_throughput_tps",
        "generation_throughput_tps",
        "elapsed_ms",
    }
    assert all(value is None for value in metrics.values())

    with_zero = valid_request()
    with_zero["metrics"] = {"quality_score": 0, "prompt_tokens": 0}
    zero_metrics = RunImportRequest.model_validate(with_zero).metrics
    assert zero_metrics.quality_score == 0
    assert zero_metrics.prompt_tokens == 0
    assert zero_metrics.pass_rate is None


@pytest.mark.parametrize(
    "change",
    [
        lambda value: value.update(owner_id="private-owner"),
        lambda value: value["profile_snapshot"].update(profile_id="private-profile"),
        lambda value: value["benchmark_config"].update(prompt_set="private prompt"),
        lambda value: value.update(ended_at="2026-10-26T10:00:00"),
        lambda value: value.update(metrics={"elapsed_ms": 1.5}),
        lambda value: value.update(metrics={"pass_rate": 1.01}),
        lambda value: value["benchmark_config"].update(reasoning="yes"),
        lambda value: value["benchmark_config"].update(max_tokens=None),
    ],
)
def test_strict_schema_rejects_unknown_nullable_or_invalid_values(change) -> None:
    payload = valid_request()
    change(payload)

    with pytest.raises(ValidationError) as error:
        RunImportRequest.model_validate(payload)

    safe_errors = _validation_failures(error.value)
    assert safe_errors
    assert all("private" not in item["field"] for item in safe_errors)


def test_time_order_and_format_version_are_validated() -> None:
    payload = valid_request()
    payload["ended_at"] = "2026-10-26T09:59:59Z"
    with pytest.raises(ValidationError) as error:
        RunImportRequest.model_validate(payload)
    assert "ended_at must be greater than or equal to started_at" in str(
        _validation_failures(error.value)
    )

    payload = valid_request()
    payload["format_version"] = "benchscope.run.v2"
    with pytest.raises(ValidationError) as error:
        RunImportRequest.model_validate(payload)
    assert "benchscope.run.v1" in str(_validation_failures(error.value))


def test_fingerprints_use_source_id_or_canonical_allowlisted_payload() -> None:
    request = RunImportRequest.model_validate(valid_request())
    reordered = RunImportRequest.model_validate(
        dict(reversed(list(valid_request().items())))
    )
    assert _fingerprint(request) == _fingerprint(reordered)

    with_source_id = valid_request()
    with_source_id["source_run_id"] = "stable-source"
    original = RunImportRequest.model_validate(with_source_id)
    changed = deepcopy(with_source_id)
    changed["metrics"] = {"quality_score": 0.5}
    assert _fingerprint(original) == _fingerprint(
        RunImportRequest.model_validate(changed)
    )

    without_id = valid_request()
    with_idless_metrics = deepcopy(without_id)
    with_idless_metrics["metrics"] = {"quality_score": 0.5}
    assert _fingerprint(RunImportRequest.model_validate(without_id)) != _fingerprint(
        RunImportRequest.model_validate(with_idless_metrics)
    )
