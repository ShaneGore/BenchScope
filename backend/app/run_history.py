from datetime import UTC, datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import AwareDatetime, BaseModel, Field
from sqlalchemy import and_, or_, select, update
from sqlalchemy.orm import Session

from app.auth import current_owner
from app.database import get_session
from app.models import BenchmarkRun
from app.run_serialization import run_history_response

RunStatus = Literal["running", "completed", "failed", "interrupted"]
router = APIRouter()


class RunMetricsResponse(BaseModel):
    quality_score: float | int | None
    pass_rate: float | int | None
    ttft_ms: float | int | None
    prompt_tokens: int | None
    output_tokens: int | None
    prompt_throughput_tps: float | int | None
    generation_throughput_tps: float | int | None
    elapsed_ms: int | None


class BenchmarkRunResponse(BaseModel):
    id: UUID
    owner_id: str
    status: RunStatus
    profile_snapshot: dict[str, Any]
    benchmark_config: dict[str, Any]
    started_at: datetime
    ended_at: datetime | None
    related_run_id: UUID | None = None
    source: Literal["imported", "launched"] | None = None
    fingerprint: str | None = None
    artifact_ref: str | None = None
    events: list[dict[str, Any]] = Field(default_factory=list)
    metrics: RunMetricsResponse
    error_category: str | None = None
    error_message_sanitised: str | None = None
    process_exit_code: int | None = None
    hardware_snapshot: dict[str, Any] | None = None


class PaginatedRunsResponse(BaseModel):
    items: list[BenchmarkRunResponse]
    next_cursor: UUID | None = None
    has_more: bool


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="Run not found")


def _invalid_cursor() -> HTTPException:
    return HTTPException(status_code=422, detail="Invalid cursor")


def _filters(
    owner_id: str,
    model: str | None,
    run_status: RunStatus | None,
    date_from: datetime | None,
    date_to: datetime | None,
) -> list[Any]:
    filters: list[Any] = [BenchmarkRun.owner_id == owner_id]
    if model is not None:
        filters.append(BenchmarkRun.profile_snapshot["model_name"].as_string() == model)
    if run_status is not None:
        filters.append(BenchmarkRun.status == run_status)
    if date_from is not None:
        filters.append(BenchmarkRun.started_at >= date_from.astimezone(UTC))
    if date_to is not None:
        filters.append(BenchmarkRun.started_at < date_to.astimezone(UTC))
    return filters


@router.get("/runs", response_model=PaginatedRunsResponse)
def list_runs(
    owner_id: Annotated[str, Depends(current_owner)],
    session: Annotated[Session, Depends(get_session)],
    model: str | None = None,
    status: RunStatus | None = None,
    date_from: Annotated[AwareDatetime | None, Query(alias="from")] = None,
    date_to: Annotated[AwareDatetime | None, Query(alias="to")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: str | None = None,
) -> dict[str, Any]:
    if date_from is not None and date_to is not None and date_from >= date_to:
        raise HTTPException(status_code=422, detail="Invalid date range")

    filters = _filters(owner_id, model, status, date_from, date_to)
    cursor_run: BenchmarkRun | None = None
    if cursor is not None:
        try:
            cursor_id = UUID(cursor)
        except ValueError:
            raise _invalid_cursor() from None
        cursor_run = session.scalar(
            select(BenchmarkRun).where(
                *filters,
                BenchmarkRun.id == cursor_id,
            )
        )
        if cursor_run is None:
            raise _invalid_cursor()
        filters.append(
            or_(
                BenchmarkRun.started_at < cursor_run.started_at,
                and_(
                    BenchmarkRun.started_at == cursor_run.started_at,
                    BenchmarkRun.id < cursor_run.id,
                ),
            )
        )

    runs = list(
        session.scalars(
            select(BenchmarkRun)
            .where(*filters)
            .order_by(BenchmarkRun.started_at.desc(), BenchmarkRun.id.desc())
            .limit(limit + 1)
        )
    )
    has_more = len(runs) > limit
    page = runs[:limit]
    return {
        "items": [run_history_response(run) for run in page],
        "next_cursor": page[-1].id if has_more and page else None,
        "has_more": has_more,
    }


@router.get("/runs/compare", response_model=list[BenchmarkRunResponse])
def compare_runs(
    owner_id: Annotated[str, Depends(current_owner)],
    session: Annotated[Session, Depends(get_session)],
    ids: str = Query(
        description="At least two distinct run UUIDs, comma-delimited in input order."
    ),
) -> list[dict[str, Any]]:
    try:
        run_ids = [UUID(value) for value in ids.split(",")]
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid run IDs") from None
    if len(run_ids) < 2 or len(set(run_ids)) != len(run_ids):
        raise HTTPException(status_code=422, detail="Invalid run IDs")

    runs = list(
        session.scalars(
            select(BenchmarkRun).where(
                BenchmarkRun.owner_id == owner_id,
                BenchmarkRun.id.in_(run_ids),
            )
        )
    )
    by_id = {run.id: run for run in runs}
    if len(by_id) != len(run_ids):
        raise _not_found()

    completed = [
        by_id[run_id] for run_id in run_ids if by_id[run_id].status == "completed"
    ]
    if len(completed) < 2:
        raise HTTPException(
            status_code=422,
            detail="At least two completed runs are required",
        )
    return [run_history_response(run) for run in completed]


@router.get("/runs/{id}", response_model=BenchmarkRunResponse)
def get_run(
    id: UUID,
    owner_id: Annotated[str, Depends(current_owner)],
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, Any]:
    run = session.scalar(
        select(BenchmarkRun).where(
            BenchmarkRun.id == id,
            BenchmarkRun.owner_id == owner_id,
        )
    )
    if run is None:
        raise _not_found()
    return run_history_response(run)


@router.delete("/runs/{id}", status_code=204)
def delete_run(
    id: UUID,
    owner_id: Annotated[str, Depends(current_owner)],
    session: Annotated[Session, Depends(get_session)],
) -> Response:
    run = session.scalar(
        select(BenchmarkRun).where(
            BenchmarkRun.id == id,
            BenchmarkRun.owner_id == owner_id,
        )
    )
    if run is None:
        raise _not_found()
    session.execute(
        update(BenchmarkRun)
        .where(
            BenchmarkRun.owner_id == owner_id,
            BenchmarkRun.related_run_id == run.id,
        )
        .values(related_run_id=None)
    )
    session.delete(run)
    session.commit()
    return Response(status_code=204)
