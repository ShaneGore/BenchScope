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
    started_at: datetime | None
    ended_at: datetime | None
    metrics: DemoMetrics
    hardware_snapshot: DemoHardware


# Each tuple is an allowlisted summary, independently reconciled with the private
# trial files. The first two timestamps come from driver START/END logs; null
# means no verified whole-run boundary. No private trial material is served.
_SUMMARY_ROWS = (
    # label, model, quantisation, mode, MTP, passed, throughput, errors, start, end
    (
        "Qwen3.8 27B GSQ-RCO (MTP on)",
        "Qwen3.8-27B-GSQ-RCO-IQ3_XXS-MTP",
        "IQ3_XXS",
        "off",
        "on",
        31,
        27.4,
        0,
        datetime(2026, 10, 14, 9, 55, 33, 57603, tzinfo=UTC),
        datetime(2026, 10, 14, 10, 17, 31, 87900, tzinfo=UTC),
    ),
    (
        "Qwen3.8 27B AP (MTP off)",
        "Qwen3.8-27B-AP-IQ3_XXS",
        "IQ3_XXS",
        "off",
        "off",
        30,
        33.9,
        0,
        datetime(2026, 10, 14, 14, 10, 48, 455124, tzinfo=UTC),
        datetime(2026, 10, 14, 14, 28, 55, 145489, tzinfo=UTC),
    ),
    (
        "AtomicChat AD (MTP off)",
        "AtomicChat-AD-IQ2_S",
        "IQ2_S",
        "off",
        "off",
        28,
        27.2,
        0,
        None,
        None,
    ),
    (
        "AtomicChat AD (MTP off)",
        "AtomicChat-AD-IQ2_S",
        "IQ2_S",
        "on",
        "off",
        30,
        27.8,
        0,
        None,
        None,
    ),
    (
        "Ornith 1.5 35B (MTP off)",
        "Ornith-1.5-35B-Q4_K_M",
        "Q4_K_M",
        "off",
        "off",
        21,
        55.9,
        0,
        None,
        None,
    ),
    (
        "Ornith 1.5 35B (MTP off)",
        "Ornith-1.5-35B-Q4_K_M",
        "Q4_K_M",
        "on",
        "off",
        25,
        67.3,
        0,
        None,
        None,
    ),
    (
        "Qwen3.8 27B AP (MTP off)",
        "Qwen3.8-27B-AP-IQ3_XXS",
        "IQ3_XXS",
        "on",
        "off",
        31,
        34.5,
        0,
        None,
        None,
    ),
    (
        "Qwen3.8 27B GSQ-RCO (MTP on)",
        "Qwen3.8-27B-GSQ-RCO-IQ3_XXS-MTP",
        "IQ3_XXS",
        "on",
        "on",
        33,
        26.8,
        0,
        None,
        None,
    ),
    (
        "Strata Qwen3.8 Flash Next Coder (MTP on, context 16384)",
        "Strata-Qwen3.8-Flash-Next-Coder-IQ1_M",
        "IQ1_M",
        "off",
        "on",
        31,
        15.6,
        0,
        None,
        None,
    ),
    (
        "Ternary Bonsai 2 27B (MTP off)",
        "Ternary-Bonsai-2-27B-PQ2_0-MTP",
        "PQ2_0",
        "off",
        "off",
        26,
        49.1,
        0,
        None,
        None,
    ),
    (
        "Ternary Bonsai 2 27B (MTP off)",
        "Ternary-Bonsai-2-27B-PQ2_0-MTP",
        "PQ2_0",
        "on",
        "off",
        29,
        50.6,
        1,
        None,
        None,
    ),
    (
        "Underdog Saluki 27B (MTP on)",
        "Underdog-Saluki-27B-1.0-IQ2-mix-MTP",
        "IQ2-mix",
        "off",
        "on",
        22,
        87.8,
        0,
        None,
        None,
    ),
    (
        "Underdog Saluki 27B (MTP on)",
        "Underdog-Saluki-27B-1.0-IQ2-mix-MTP",
        "IQ2-mix",
        "on",
        "on",
        32,
        87.6,
        0,
        None,
        None,
    ),
    (
        "Qwen3.8 27B OpenRouter (hosted)",
        "Qwen3.8-27B-OR-paid-off",
        None,
        "disabled",
        None,
        34,
        None,
        0,
        None,
        None,
    ),
    (
        "Qwen3.8 27B OpenRouter (hosted)",
        "Qwen3.8-27B-OR-paid-med2047",
        None,
        "medium, budget 2047",
        None,
        31,
        None,
        0,
        None,
        None,
    ),
)


def _make_demo_run(index: int, row: tuple) -> DemoRun:
    (
        name,
        model,
        quantisation,
        reasoning,
        _mtp,
        passed,
        throughput,
        errors,
        start,
        end,
    ) = row
    coverage = f"{passed}/47 passed · 47/47 recorded"
    if errors:
        coverage += f" · {errors} provider error"
    return DemoRun(
        id=f"demo-run-{index:02d}",
        status="completed",
        profile_snapshot=DemoProfile(
            name=name, model_name=model, model_version=None, quantisation=quantisation
        ),
        benchmark_config=DemoConfig(
            name=f"Reasoning {reasoning} · {coverage}", temperature=0.0, max_tokens=6000
        ),
        started_at=start,
        ended_at=end,
        metrics=DemoMetrics(
            pass_rate=passed / 47, generation_throughput_tps=throughput
        ),
        hardware_snapshot=DemoHardware(
            cpu=None, gpu=None, ram_gb=None, gpu_vram_gb=None, os=None
        ),
    )


_DEMO_RUNS = tuple(_make_demo_run(i, row) for i, row in enumerate(_SUMMARY_ROWS, 1))


@router.get("/demo/runs", response_model=list[DemoRun])
def list_demo_runs() -> tuple[DemoRun, ...]:
    return _DEMO_RUNS


@router.get("/demo/runs/{id}", response_model=DemoRun)
def get_demo_run(id: str) -> DemoRun:
    for run in _DEMO_RUNS:
        if run.id == id:
            return run
    raise HTTPException(status_code=404, detail="Demo run not found")
