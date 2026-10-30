import asyncio
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Annotated, Literal, Protocol
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker

from app.auth import current_owner
from app.database import get_session
from app.models import BenchmarkRun, ModelProfile
from app.run_history import RunMetricsResponse

RunStatus = Literal["running", "completed", "failed", "interrupted", "cancelled"]
router = APIRouter()


@dataclass(frozen=True)
class RunResult:
    """Provisional normalized run-level result; not the private adapter schema."""

    quality_score: float | None = None
    pass_rate: float | None = None
    ttft_ms: float | None = None
    prompt_tokens: int | None = None
    output_tokens: int | None = None
    prompt_throughput_tps: float | None = None
    generation_throughput_tps: float | None = None
    benchmark_details: dict[str, object] | None = None
    task_results: list[dict[str, object]] | None = None


class BenchmarkAdapter(Protocol):
    async def run(
        self, profile: dict[str, str | None], config_id: UUID
    ) -> RunResult: ...


class BenchmarkStartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_id: UUID
    config_id: UUID


class RunStartResponse(BaseModel):
    id: UUID
    status: Literal["running"]


class RunStatusResponse(BaseModel):
    id: UUID
    status: RunStatus
    related_run_id: UUID | None
    started_at: datetime
    completed_at: datetime | None
    elapsed_ms: int | None
    metrics: RunMetricsResponse
    error_category: str | None
    error_message_sanitised: str | None


def _unavailable() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Benchmark runner is unavailable because no adapter is configured",
    )


def _snapshot(profile: ModelProfile) -> dict[str, str | None]:
    # Endpoint URLs and free-form inference settings are intentionally not snapshotted.
    return {
        "name": profile.name,
        "model_name": profile.model_name,
        "model_version": profile.model_version,
        "quantisation": profile.quantisation,
    }


def _consume_task_exception(task: asyncio.Task[None]) -> None:
    if not task.cancelled():
        task.exception()


def _run_task_finished(
    request: Request, run_id: UUID, task: asyncio.Task[None]
) -> None:
    if request.app.state.benchmark_tasks.get(run_id) is task:
        del request.app.state.benchmark_tasks[run_id]
    _consume_task_exception(task)
    request.app.state.benchmark_lock.release()


async def _launch(
    request: Request,
    owner_id: str,
    session: Session,
    profile_id: UUID,
    profile_snapshot: dict[str, str | None],
    config_id: UUID,
    related_run_id: UUID | None = None,
) -> BenchmarkRun:
    adapter: BenchmarkAdapter | None = request.app.state.benchmark_adapter
    if adapter is None:
        raise _unavailable()

    lock: asyncio.Lock = request.app.state.benchmark_lock
    if lock.locked():
        # A rejected request creates no row; only accepted work is persisted as running.
        raise HTTPException(status_code=409, detail="A benchmark run is already active")
    await lock.acquire()
    task: asyncio.Task[None] | None = None
    try:
        run = BenchmarkRun(
            id=uuid4(),
            owner_id=owner_id,
            source="launched",
            status="running",
            profile_id=profile_id,
            profile_snapshot=profile_snapshot,
            benchmark_config={"config_id": str(config_id)},
            related_run_id=related_run_id,
            started_at=datetime.now(UTC),
        )
        task = asyncio.create_task(
            _execute(request, adapter, run.id, owner_id, profile_snapshot, config_id)
        )
        request.app.state.benchmark_tasks[run.id] = task
        task.add_done_callback(
            lambda completed: _run_task_finished(request, run.id, completed)
        )
        session.add(run)
        session.commit()
        await asyncio.sleep(0)
        return run
    except Exception:
        session.rollback()
        if task is None:
            lock.release()
        else:
            task.cancel()
        raise


async def _execute(
    request: Request,
    adapter: BenchmarkAdapter,
    run_id: UUID,
    owner_id: str,
    profile_snapshot: dict[str, str | None],
    config_id: UUID,
) -> None:
    started = asyncio.get_running_loop().time()
    try:
        result = await asyncio.wait_for(
            adapter.run(profile_snapshot, config_id),
            timeout=request.app.state.settings.benchmark_timeout_seconds,
        )
        if not isinstance(result, RunResult):
            raise TypeError
    except asyncio.CancelledError:
        _finish_run(
            request.app.state.session_factory,
            run_id,
            owner_id,
            "cancelled",
            None,
            None,
            started,
        )
    except TimeoutError:
        _finish_run(
            request.app.state.session_factory,
            run_id,
            owner_id,
            "failed",
            "timeout",
            "Benchmark execution timed out.",
            started,
        )
    except Exception:  # noqa: BLE001 - adapter failures must stay sanitized
        _finish_run(
            request.app.state.session_factory,
            run_id,
            owner_id,
            "failed",
            "adapter_error",
            "Benchmark adapter failed.",
            started,
        )
    else:
        _finish_run(
            request.app.state.session_factory,
            run_id,
            owner_id,
            "completed",
            None,
            None,
            started,
            asdict(result),
        )


def _finish_run(
    factory: sessionmaker[Session] | None,
    run_id: UUID,
    owner_id: str,
    run_status: Literal["completed", "failed", "cancelled"],
    error_category: str | None,
    error_message: str | None,
    started: float,
    metrics: dict[str, float | int | None] | None = None,
) -> None:
    if factory is None:
        return
    values: dict[str, object] = {
        "status": run_status,
        "completed_at": datetime.now(UTC),
        "error_category": error_category,
        "error_message_sanitised": error_message,
    }
    if run_status != "cancelled":
        values["elapsed_ms"] = round(
            (asyncio.get_running_loop().time() - started) * 1000
        )
    if metrics is not None:
        values.update(metrics)
    with factory() as session:
        session.execute(
            update(BenchmarkRun)
            .where(
                BenchmarkRun.id == run_id,
                BenchmarkRun.owner_id == owner_id,
                BenchmarkRun.status == "running",
            )
            .values(**values)
        )
        session.commit()


def reconcile_interrupted_runs(factory: sessionmaker[Session]) -> None:
    with factory() as session:
        session.execute(
            update(BenchmarkRun)
            .where(BenchmarkRun.status == "running")
            .values(
                status="interrupted",
                completed_at=datetime.now(UTC),
                error_category="interrupted",
                error_message_sanitised="Run interrupted by application restart.",
            )
        )
        session.commit()


def _status_response(run: BenchmarkRun) -> RunStatusResponse:
    return RunStatusResponse(
        id=run.id,
        status=run.status,
        related_run_id=run.related_run_id,
        started_at=run.started_at,
        completed_at=run.completed_at,
        elapsed_ms=run.elapsed_ms,
        metrics={
            "quality_score": run.quality_score,
            "pass_rate": run.pass_rate,
            "ttft_ms": run.ttft_ms,
            "prompt_tokens": run.prompt_tokens,
            "output_tokens": run.output_tokens,
            "prompt_throughput_tps": run.prompt_throughput_tps,
            "generation_throughput_tps": run.generation_throughput_tps,
            "elapsed_ms": run.elapsed_ms,
        },
        error_category=run.error_category,
        error_message_sanitised=run.error_message_sanitised,
    )


@router.post(
    "/benchmark/runs",
    response_model=RunStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_run(
    body: BenchmarkStartRequest,
    request: Request,
    owner_id: Annotated[str, Depends(current_owner)],
    session: Annotated[Session, Depends(get_session)],
) -> BenchmarkRun:
    profile = session.scalar(
        select(ModelProfile).where(
            ModelProfile.id == body.profile_id,
            ModelProfile.owner_id == owner_id,
        )
    )
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return await _launch(
        request,
        owner_id,
        session,
        profile.id,
        _snapshot(profile),
        body.config_id,
    )


@router.get("/benchmark/runs/{id}", response_model=RunStatusResponse)
def get_run_status(
    id: UUID,
    owner_id: Annotated[str, Depends(current_owner)],
    session: Annotated[Session, Depends(get_session)],
) -> RunStatusResponse:
    run = session.scalar(
        select(BenchmarkRun).where(
            BenchmarkRun.id == id,
            BenchmarkRun.owner_id == owner_id,
            BenchmarkRun.source == "launched",
        )
    )
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return _status_response(run)


@router.post("/benchmark/runs/{id}/cancel", response_model=RunStatusResponse)
async def cancel_run(
    id: UUID,
    request: Request,
    owner_id: Annotated[str, Depends(current_owner)],
    session: Annotated[Session, Depends(get_session)],
) -> RunStatusResponse:
    run = session.scalar(
        select(BenchmarkRun).where(
            BenchmarkRun.id == id,
            BenchmarkRun.owner_id == owner_id,
            BenchmarkRun.source == "launched",
        )
    )
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.status == "running":
        task: asyncio.Task[None] | None = request.app.state.benchmark_tasks.get(id)
        if task is not None and not task.done():
            if not task.cancelling():
                task.cancel()
            await asyncio.shield(task)
        session.refresh(run)
    return _status_response(run)


@router.post(
    "/runs/{id}/retry",
    response_model=RunStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def retry_run(
    id: UUID,
    request: Request,
    owner_id: Annotated[str, Depends(current_owner)],
    session: Annotated[Session, Depends(get_session)],
) -> BenchmarkRun:
    previous = session.scalar(
        select(BenchmarkRun).where(
            BenchmarkRun.id == id,
            BenchmarkRun.owner_id == owner_id,
        )
    )
    if (
        previous is None
        or previous.source != "launched"
        or previous.status != "failed"
        or previous.profile_id is None
    ):
        raise HTTPException(status_code=409, detail="Run cannot be retried")
    profile = session.scalar(
        select(ModelProfile).where(
            ModelProfile.id == previous.profile_id,
            ModelProfile.owner_id == owner_id,
        )
    )
    try:
        config_id = UUID(previous.benchmark_config["config_id"])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(status_code=409, detail="Run cannot be retried") from None
    if profile is None:
        raise HTTPException(status_code=409, detail="Run cannot be retried")
    return await _launch(
        request,
        owner_id,
        session,
        profile.id,
        previous.profile_snapshot,
        config_id,
        related_run_id=previous.id,
    )
