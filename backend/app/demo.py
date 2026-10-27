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


# Frozen response models and a tuple keep the approved, synthetic fixture read-only.
_DEMO_RUNS = (
    DemoRun(
        id="demo-run-01",
        status="completed",
        profile_snapshot=DemoProfile(
            name="Sample Model A",
            model_name="sample-model-a",
            model_version="1.0",
            quantisation="Q4",
        ),
        benchmark_config=DemoConfig(
            name="synthetic-demo", temperature=0.2, max_tokens=128
        ),
        started_at=datetime(2026, 10, 26, 10, 0, tzinfo=UTC),
        ended_at=datetime(2026, 10, 26, 10, 1, tzinfo=UTC),
        metrics=DemoMetrics(
            quality_score=0.82,
            pass_rate=0.78,
            ttft_ms=215,
            prompt_tokens=400,
            output_tokens=190,
            prompt_throughput_tps=125.0,
            generation_throughput_tps=42.5,
            elapsed_ms=60_000,
        ),
        hardware_snapshot=DemoHardware(
            cpu="Demo CPU",
            gpu="Demo GPU",
            ram_gb=16,
            gpu_vram_gb=8,
            os="Demo OS",
        ),
    ),
    DemoRun(
        id="demo-run-02",
        status="completed",
        profile_snapshot=DemoProfile(
            name="Sample Model B",
            model_name="sample-model-b",
            model_version=None,
            quantisation="Q5",
        ),
        benchmark_config=DemoConfig(
            name="synthetic-demo", temperature=0.0, max_tokens=128
        ),
        started_at=datetime(2026, 10, 26, 11, 0, tzinfo=UTC),
        ended_at=datetime(2026, 10, 26, 11, 1, tzinfo=UTC),
        metrics=DemoMetrics(quality_score=0.74, pass_rate=0.69, elapsed_ms=60_000),
        hardware_snapshot=DemoHardware(
            cpu="Demo CPU",
            gpu="Demo GPU",
            ram_gb=16,
            gpu_vram_gb=8,
            os="Demo OS",
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
