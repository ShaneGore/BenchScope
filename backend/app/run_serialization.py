from typing import Any

from app.models import BenchmarkRun


def run_metrics(run: BenchmarkRun) -> dict[str, Any]:
    return {
        "quality_score": run.quality_score,
        "pass_rate": run.pass_rate,
        "ttft_ms": run.ttft_ms,
        "prompt_tokens": run.prompt_tokens,
        "output_tokens": run.output_tokens,
        "prompt_throughput_tps": run.prompt_throughput_tps,
        "generation_throughput_tps": run.generation_throughput_tps,
        "elapsed_ms": run.elapsed_ms,
    }


def run_history_response(run: BenchmarkRun) -> dict[str, Any]:
    return {
        "id": run.id,
        "owner_id": run.owner_id,
        "status": run.status,
        "profile_snapshot": run.profile_snapshot,
        "benchmark_config": run.benchmark_config,
        "started_at": run.started_at,
        "ended_at": run.completed_at,
        "related_run_id": run.related_run_id,
        "source": run.source,
        "fingerprint": run.import_fingerprint,
        "artifact_ref": run.artifact_ref,
        "events": [],
        "metrics": run_metrics(run),
        "error_category": run.error_category,
        "error_message_sanitised": run.error_message_sanitised,
        "process_exit_code": run.process_exit_code,
        "hardware_snapshot": run.hardware_snapshot,
    }
