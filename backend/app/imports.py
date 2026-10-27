import hashlib
import json
import logging
from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    ValidationError,
    model_validator,
)
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import LOCAL_OWNER_ID, get_session
from app.models import BenchmarkRun
from app.run_serialization import run_metrics

logger = logging.getLogger("app.imports")
router = APIRouter()

NonNegativeNumber = Annotated[StrictInt | StrictFloat, Field(ge=0, allow_inf_nan=False)]
PositiveInteger = Annotated[StrictInt, Field(ge=1)]
NonNegativeInteger = Annotated[StrictInt, Field(ge=0)]


class StrictObject(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ImportedProfile(StrictObject):
    name: Annotated[StrictStr, Field(min_length=1, max_length=255)]
    model_name: Annotated[StrictStr, Field(min_length=1, max_length=255)]
    model_version: Annotated[StrictStr, Field(max_length=255)] | None = None
    quantisation: Annotated[StrictStr, Field(max_length=100)] | None = None


class ImportedBenchmarkConfig(StrictObject):
    name: Annotated[StrictStr, Field(min_length=1, max_length=255)]
    temperature: NonNegativeNumber = None
    max_tokens: PositiveInteger = None
    reasoning: StrictBool = None
    mtp: StrictBool = None
    ctx: PositiveInteger = None
    seed: NonNegativeInteger = None


class ImportedMetrics(StrictObject):
    quality_score: NonNegativeNumber | None = None
    pass_rate: (
        Annotated[StrictInt | StrictFloat, Field(ge=0, le=1, allow_inf_nan=False)]
        | None
    ) = None
    ttft_ms: NonNegativeNumber | None = None
    prompt_tokens: NonNegativeInteger | None = None
    output_tokens: NonNegativeInteger | None = None
    prompt_throughput_tps: NonNegativeNumber | None = None
    generation_throughput_tps: NonNegativeNumber | None = None
    elapsed_ms: NonNegativeInteger | None = None


class ImportedHardware(StrictObject):
    cpu: StrictStr | None = None
    gpu: StrictStr | None = None
    ram_gb: NonNegativeNumber | None = None
    gpu_vram_gb: NonNegativeNumber | None = None
    os: StrictStr | None = None


class RunImportRequest(StrictObject):
    format_version: Literal["benchscope.run.v1"]
    source_run_id: Annotated[StrictStr, Field(min_length=1, max_length=255)] | None = (
        None
    )
    profile_snapshot: ImportedProfile
    benchmark_config: ImportedBenchmarkConfig
    started_at: AwareDatetime
    ended_at: AwareDatetime
    metrics: ImportedMetrics = Field(default_factory=ImportedMetrics)
    hardware_snapshot: ImportedHardware | None = None

    @model_validator(mode="after")
    def end_must_not_precede_start(self) -> "RunImportRequest":
        if self.ended_at < self.started_at:
            raise ValueError("ended_at must be greater than or equal to started_at")
        return self


class ProfileSnapshotResponse(StrictObject):
    name: str
    model_name: str
    model_version: str | None
    quantisation: str | None


class BenchmarkConfigResponse(StrictObject):
    name: str
    temperature: float | int | None = None
    max_tokens: int | None = None
    reasoning: bool | None = None
    mtp: bool | None = None
    ctx: int | None = None
    seed: int | None = None


class MetricsResponse(StrictObject):
    quality_score: float | int | None
    pass_rate: float | int | None
    ttft_ms: float | int | None
    prompt_tokens: int | None
    output_tokens: int | None
    prompt_throughput_tps: float | int | None
    generation_throughput_tps: float | int | None
    elapsed_ms: int | None


class HardwareResponse(StrictObject):
    cpu: str | None
    gpu: str | None
    ram_gb: float | int | None
    gpu_vram_gb: float | int | None
    os: str | None


class ImportedRunResponse(StrictObject):
    id: UUID
    owner_id: str
    status: Literal["completed"]
    profile_snapshot: ProfileSnapshotResponse
    benchmark_config: BenchmarkConfigResponse
    started_at: datetime
    ended_at: datetime
    source: Literal["imported"]
    fingerprint: str
    metrics: MetricsResponse
    hardware_snapshot: HardwareResponse | None


class ImportErrorItem(StrictObject):
    field: str
    message: str


class ImportFailure(StrictObject):
    ok: Literal[False]
    status: int
    errors: list[ImportErrorItem]


class ImportSuccess(StrictObject):
    ok: Literal[True]
    run: ImportedRunResponse


ImportResult = ImportSuccess | ImportFailure


def _failure(status_code: int, field: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "ok": False,
            "status": status_code,
            "errors": [{"field": field, "message": message}],
        },
    )


def _validation_failures(error: ValidationError) -> list[dict[str, str]]:
    allowed_fields = {
        "format_version",
        "source_run_id",
        "profile_snapshot",
        "name",
        "model_name",
        "model_version",
        "quantisation",
        "benchmark_config",
        "temperature",
        "max_tokens",
        "reasoning",
        "mtp",
        "ctx",
        "seed",
        "started_at",
        "ended_at",
        "metrics",
        "quality_score",
        "pass_rate",
        "ttft_ms",
        "prompt_tokens",
        "output_tokens",
        "prompt_throughput_tps",
        "generation_throughput_tps",
        "elapsed_ms",
        "hardware_snapshot",
        "cpu",
        "gpu",
        "ram_gb",
        "gpu_vram_gb",
        "os",
    }
    messages = {
        "missing": "Field is required.",
        "extra_forbidden": "Field is not allowed.",
        "literal_error": "format_version must be benchscope.run.v1.",
        "greater_than_equal": "Value is below the allowed minimum.",
        "greater_than": "Value is below the allowed minimum.",
        "less_than_equal": "Value exceeds the allowed maximum.",
        "less_than": "Value exceeds the allowed maximum.",
        "value_error": "ended_at must be greater than or equal to started_at.",
    }
    return [
        {
            "field": ".".join(
                str(part)
                for part in issue["loc"]
                if part in allowed_fields or isinstance(part, int)
            )
            or "request",
            "message": messages.get(
                issue["type"],
                "Field has an invalid type or value.",
            ),
        }
        for issue in error.errors(include_input=False, include_context=False)
    ]


def _parse_constant(_value: str) -> None:
    raise ValueError("Non-standard JSON number")


def _object_without_duplicate_keys(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON object key")
        result[key] = value
    return result


async def _read_json(request: Request, maximum: int) -> bytes | JSONResponse:
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip()
    if content_type.casefold() != "application/json":
        return _failure(422, "content-type", "Content-Type must be application/json.")

    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            length = int(content_length)
            if length < 0:
                return _failure(422, "content-length", "Invalid Content-Length header.")
            if length > maximum:
                return _failure(413, "request", "Upload exceeds MAX_UPLOAD_BYTES.")
        except ValueError:
            return _failure(422, "content-length", "Invalid Content-Length header.")

    parts: list[bytes] = []
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > maximum:
            return _failure(413, "request", "Upload exceeds MAX_UPLOAD_BYTES.")
        parts.append(chunk)
    return b"".join(parts)


def _fingerprint(imported: RunImportRequest) -> str:
    if imported.source_run_id is not None:
        value = f"benchscope.run.v1\0source_run_id\0{imported.source_run_id}"
    else:
        canonical = json.dumps(
            imported.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        value = f"benchscope.run.v1\0payload\0{canonical}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _run_response(run: BenchmarkRun) -> dict[str, Any]:
    return {
        "id": run.id,
        "owner_id": run.owner_id,
        "status": "completed",
        "profile_snapshot": run.profile_snapshot,
        "benchmark_config": run.benchmark_config,
        "started_at": run.started_at,
        "ended_at": run.completed_at,
        "source": "imported",
        "fingerprint": run.import_fingerprint,
        "metrics": run_metrics(run),
        "hardware_snapshot": run.hardware_snapshot,
    }


def _duplicate(field: str) -> JSONResponse:
    return _failure(
        409,
        field,
        "This run has already been imported for this owner.",
    )


@router.post(
    "/runs/import",
    response_model=ImportSuccess,
    response_model_exclude_unset=True,
    status_code=201,
    responses={
        409: {"model": ImportFailure, "description": "Duplicate import"},
        413: {"model": ImportFailure, "description": "Upload is too large"},
        422: {"model": ImportFailure, "description": "Invalid import request"},
    },
)
async def import_run(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> ImportResult:
    body = await _read_json(request, request.app.state.settings.max_upload_bytes)
    if isinstance(body, JSONResponse):
        return body
    try:
        payload = json.loads(
            body,
            parse_constant=_parse_constant,
            object_pairs_hook=_object_without_duplicate_keys,
        )
    except (ValueError, RecursionError):
        return _failure(422, "request", "Request body must be valid JSON.")
    try:
        imported = RunImportRequest.model_validate(payload)
    except ValidationError as error:
        return JSONResponse(
            status_code=422,
            content={
                "ok": False,
                "status": 422,
                "errors": _validation_failures(error),
            },
        )

    fingerprint = _fingerprint(imported)
    profile_snapshot = imported.profile_snapshot.model_dump()
    benchmark_config = imported.benchmark_config.model_dump(exclude_unset=True)
    metrics = imported.metrics
    run = BenchmarkRun(
        owner_id=LOCAL_OWNER_ID,
        source="imported",
        status="completed",
        profile_id=None,
        profile_snapshot=profile_snapshot,
        benchmark_config=benchmark_config,
        source_run_id=imported.source_run_id,
        import_fingerprint=fingerprint,
        started_at=imported.started_at,
        completed_at=imported.ended_at,
        elapsed_ms=metrics.elapsed_ms,
        quality_score=metrics.quality_score,
        pass_rate=metrics.pass_rate,
        ttft_ms=metrics.ttft_ms,
        prompt_tokens=metrics.prompt_tokens,
        output_tokens=metrics.output_tokens,
        prompt_throughput_tps=metrics.prompt_throughput_tps,
        generation_throughput_tps=metrics.generation_throughput_tps,
        hardware_snapshot=(
            imported.hardware_snapshot.model_dump()
            if imported.hardware_snapshot is not None
            else None
        ),
    )
    session.add(run)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        duplicate = session.scalar(
            select(BenchmarkRun.id).where(
                BenchmarkRun.owner_id == LOCAL_OWNER_ID,
                BenchmarkRun.import_fingerprint == fingerprint,
            )
        )
        if duplicate is not None:
            return _duplicate(
                "source_run_id" if imported.source_run_id is not None else "request"
            )
        logger.error("Run import transaction failed with integrity error")
        raise
    except Exception:
        session.rollback()
        logger.error("Run import transaction failed")
        raise
    return {"ok": True, "run": _run_response(run)}
