from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

router = APIRouter()


class DemoProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    model_name: str
    model_version: str | None
    quantisation: str | None


class DemoConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    temperature: float | None
    max_tokens: int | None


class DemoMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    quality_score: float | None = None
    pass_rate: float | None = None
    ttft_ms: float | None = None
    prompt_tokens: int | None = None
    output_tokens: int | None = None
    prompt_throughput_tps: float | None = None
    generation_throughput_tps: float | None = None
    elapsed_ms: int | None = None


class DemoHardware(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    cpu: str | None
    gpu: str | None
    ram_gb: float | None
    gpu_vram_gb: float | None
    os: str | None


class DemoRun(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    status: Literal["completed"]
    profile_snapshot: DemoProfile
    benchmark_config: DemoConfig
    started_at: datetime
    ended_at: datetime
    metrics: DemoMetrics
    hardware_snapshot: DemoHardware


# Allowlisted summaries of two complete reasoning-off runs; see README provenance.
_DEMO_RUNS = (
    DemoRun(
        id="demo-run-01",
        status="completed",
        profile_snapshot=DemoProfile(
            name="Qwen3.8 27B GSQ-RCO (MTP on)",
            model_name="Qwen3.8-27B-GSQ-RCO-IQ3_XXS-MTP",
            model_version=None,
            quantisation="IQ3_XXS",
        ),
        benchmark_config=DemoConfig(
            name="Local coding v2 · reasoning off", temperature=0.0, max_tokens=6000
        ),
        started_at=datetime(2026, 10, 14, 9, 55, 33, 57603, tzinfo=UTC),
        ended_at=datetime(2026, 10, 14, 10, 17, 31, 87900, tzinfo=UTC),
        metrics=DemoMetrics(
            pass_rate=31 / 47,
            generation_throughput_tps=27.4,
        ),
        hardware_snapshot=DemoHardware(
            cpu=None,
            gpu=None,
            ram_gb=None,
            gpu_vram_gb=None,
            os=None,
        ),
    ),
    DemoRun(
        id="demo-run-02",
        status="completed",
        profile_snapshot=DemoProfile(
            name="Qwen3.8 27B AP (MTP off)",
            model_name="Qwen3.8-27B-AP-IQ3_XXS",
            model_version=None,
            quantisation="IQ3_XXS",
        ),
        benchmark_config=DemoConfig(
            name="Local coding v2 · reasoning off", temperature=0.0, max_tokens=6000
        ),
        started_at=datetime(2026, 10, 14, 14, 10, 48, 455124, tzinfo=UTC),
        ended_at=datetime(2026, 10, 14, 14, 28, 55, 145489, tzinfo=UTC),
        metrics=DemoMetrics(pass_rate=30 / 47, generation_throughput_tps=33.9),
        hardware_snapshot=DemoHardware(
            cpu=None,
            gpu=None,
            ram_gb=None,
            gpu_vram_gb=None,
            os=None,
        ),
    ),
)


@router.get("/demo/runs", response_model=list[DemoRun])
def list_demo_runs() -> tuple[DemoRun, ...]:
    return _DEMO_RUNS


@router.get("/demo/runs/{id}", response_model=DemoRun)
def get_demo_run(id: str) -> DemoRun:
    for run in _DEMO_RUNS:
        if run.id == id:
            return run
    raise HTTPException(status_code=404, detail="Demo run not found")
