import json

import pytest

from app.imports import RunImportV2Request
from scripts.export_private_jsonl import ExportError, export_run

MANIFEST = {
    "release": "release-1",
    "tasks": [
        {"release_id": "release-task-a", "aliases": ["legacy-a"]},
        {"release_id": "release-task-b", "aliases": ["legacy-b"]},
    ],
}
MANIFEST_BYTES = json.dumps(MANIFEST).encode()


def row(task_id: str, passed: bool, **extra: object) -> str:
    return json.dumps(
        {
            "task_id": task_id,
            "seed": 1234,
            "repeat_index": 0,
            "pass": passed,
            "prompt": "private prompt",
            "served_model_path": "private path",
            "error": "private error",
            "generated_code": "private output",
            "api_key": "private credential",
            "prompt_sha256_16": "private hash",
            "prompt_tokens": 17,
            "output_tokens": 9,
            "timestamp_utc": "private trial time",
            **extra,
        }
    )


def export(jsonl: str, **overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "benchmark_id": "local-coding",
        "model_name": "example/model",
        "profile_name": "Local model",
        "started_at": "2026-10-26T10:00:00Z",
        "ended_at": "2026-10-26T10:10:00+00:00",
        "seed": 1234,
        "repeat_index": 0,
    }
    values.update(overrides)
    return export_run(MANIFEST_BYTES, jsonl, **values)  # type: ignore[arg-type]


def test_export_maps_aliases_and_excludes_private_fields() -> None:
    result = export(row("legacy-a", True) + "\n" + row("release-task-b", False))
    result_text = json.dumps(result)

    assert result["format_version"] == "benchscope.run.v2"
    assert result["benchmark_config"] == {
        "name": "local-coding",
        "seed": 1234,
        "repeat_index": 0,
    }
    assert result["benchmark_details"]["expected_task_ids"] == [
        "release-task-a",
        "release-task-b",
    ]
    assert result["task_results"] == [
        {"task_id": "release-task-a", "passed": True},
        {"task_id": "release-task-b", "passed": False},
    ]
    assert (
        RunImportV2Request.model_validate(result).task_results[0].task_id
        == "release-task-a"
    )
    assert result["benchmark_details"]["manifest_sha256"]
    for private in (
        "private prompt",
        "private path",
        "private error",
        "private output",
        "private credential",
    ):
        assert private not in result_text
    for private_key in (
        "prompt",
        "prompt_sha256_16",
        "served_model_path",
        "error",
        "generated_code",
        "api_key",
        "prompt_tokens",
        "output_tokens",
        "timestamp_utc",
    ):
        assert private_key not in result_text


@pytest.mark.parametrize(
    "jsonl",
    [
        "{",
        "[]",
        row("release-task-a", "yes"),  # type: ignore[arg-type]
        row("release-task-a", True, seed="1234"),
    ],
)
def test_rejects_malformed_records(jsonl: str) -> None:
    with pytest.raises(ExportError):
        export(jsonl)


def test_rejects_duplicate_canonical_outcomes_after_alias_mapping() -> None:
    with pytest.raises(ExportError, match="duplicate task outcome"):
        export(row("legacy-a", True) + "\n" + row("release-task-a", False))


def test_selects_one_seed_repeat_group_and_requires_explicit_zoned_times() -> None:
    selected = row("legacy-a", True)
    other_group = row("release-task-b", False, repeat_index=1)
    result = export(selected + "\n" + other_group)
    assert result["task_results"] == [{"task_id": "release-task-a", "passed": True}]

    with pytest.raises(ExportError, match="timezone"):
        export(selected, started_at="2026-10-26T10:00:00")
    with pytest.raises(ExportError, match="no records"):
        export(row("release-task-a", True), repeat_index=2)
    repeat_one = export(row("release-task-a", True, repeat_index=1), repeat_index=1)
    assert repeat_one["benchmark_config"]["repeat_index"] == 1


def test_rejects_alias_that_shadows_another_canonical_release_id() -> None:
    conflicting = json.dumps(
        {
            "release": "release-1",
            "tasks": [
                {"release_id": "task-a"},
                {"release_id": "task-b", "aliases": ["task-a"]},
            ],
        }
    ).encode()

    with pytest.raises(ExportError, match="conflicts with a canonical release_id"):
        export_run(
            conflicting,
            row("task-a", True),
            benchmark_id="id",
            model_name="model",
            profile_name="profile",
            started_at="2026-10-26T10:00:00Z",
            ended_at="2026-10-26T10:00:01Z",
            seed=1,
            repeat_index=0,
        )


def test_rejects_unsafe_release_ids_and_ambiguous_aliases() -> None:
    unsafe = json.dumps(
        {"release": "release-1", "tasks": [{"release_id": "../private"}]}
    ).encode()
    with pytest.raises(ExportError):
        export_run(
            unsafe,
            "",
            benchmark_id="id",
            model_name="model",
            profile_name="profile",
            started_at="2026-10-26T10:00:00Z",
            ended_at="2026-10-26T10:00:01Z",
            seed=1,
            repeat_index=0,
        )
    ambiguous = json.dumps(
        {
            "release": "release-1",
            "tasks": [
                {"release_id": "task-a", "aliases": ["same"]},
                {"release_id": "task-b", "aliases": ["same"]},
            ],
        }
    ).encode()
    with pytest.raises(ExportError, match="ambiguous"):
        export_run(
            ambiguous,
            "",
            benchmark_id="id",
            model_name="model",
            profile_name="profile",
            started_at="2026-10-26T10:00:00Z",
            ended_at="2026-10-26T10:00:01Z",
            seed=1,
            repeat_index=0,
        )
