from datetime import datetime
from typing import Annotated, Any
from urllib.parse import parse_qsl, urlsplit
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.auth import current_owner
from app.database import get_session
from app.models import BenchmarkRun, ModelProfile

router = APIRouter()
# ponytail: common credential query keys only; custom schemes need an explicit profile schema.
_CREDENTIAL_QUERY_KEYS = {
    "accesskey",
    "accesstoken",
    "apikey",
    "auth",
    "authtoken",
    "apitoken",
    "authorization",
    "bearer",
    "bearertoken",
    "clientsecret",
    "credential",
    "credentials",
    "key",
    "password",
    "privatekey",
    "secret",
    "secretkey",
    "sig",
    "signature",
    "token",
    "xapikey",
}


def _validate_endpoint_url(value: str | None) -> str | None:
    if value is None:
        return value
    try:
        parts = urlsplit(value)
        has_userinfo = parts.username is not None or parts.password is not None
        hostname = parts.hostname
        _ = parts.port
    except ValueError:
        raise ValueError("Invalid endpoint URL") from None
    if (
        parts.scheme.casefold() not in {"http", "https"}
        or not parts.netloc
        or not hostname
    ):
        raise ValueError("Endpoint URL must be an HTTP(S) URL with a host")
    has_credential_query = any(
        key.casefold().replace("_", "").replace("-", "").replace(".", "")
        in _CREDENTIAL_QUERY_KEYS
        for key, _ in parse_qsl(parts.query, keep_blank_values=True)
    )
    if has_userinfo or has_credential_query:
        raise ValueError("Credentials must not be embedded in endpoint_url")
    return value


class ProfileFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(max_length=255)
    model_name: str = Field(max_length=255)
    model_version: str | None = Field(default=None, max_length=255)
    quantisation: str | None = Field(default=None, max_length=100)
    endpoint_url: str | None = Field(
        default=None,
        description="Local mode only; treated as data and must not contain credentials.",
    )
    hardware_notes: str | None = None
    inference_config: dict[str, Any] | None = None

    @field_validator("endpoint_url")
    @classmethod
    def endpoint_url_has_no_credentials(cls, value: str | None) -> str | None:
        return _validate_endpoint_url(value)


class ProfileCreate(ProfileFields):
    pass


class ProfileUpdate(ProfileFields):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"minProperties": 1},
    )

    # Defaults make fields optional in PATCH while non-optional annotations reject null.
    name: str = Field(default=None, max_length=255)  # type: ignore[assignment]
    model_name: str = Field(default=None, max_length=255)  # type: ignore[assignment]


class ProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    owner_id: str
    name: str
    model_name: str
    model_version: str | None
    quantisation: str | None
    endpoint_url: str | None
    hardware_notes: str | None
    inference_config: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime


def _validate_mode_fields(
    fields: BaseModel, payload: dict[str, Any], hosted: bool
) -> None:
    if not hosted:
        return
    errors = {}
    if "endpoint_url" in fields.model_fields_set:
        errors["endpoint_url"] = "endpoint_url is not allowed in hosted mode"
    if payload.get("inference_config") is not None:
        errors["inference_config"] = "inference_config is not allowed in hosted mode"
    if errors:
        raise HTTPException(status_code=422, detail=errors)


@router.get("/profiles", response_model=list[ProfileResponse])
def list_profiles(
    owner_id: Annotated[str, Depends(current_owner)],
    session: Annotated[Session, Depends(get_session)],
) -> list[ModelProfile]:
    return list(
        session.scalars(
            select(ModelProfile)
            .where(ModelProfile.owner_id == owner_id)
            .order_by(ModelProfile.created_at, ModelProfile.id)
        )
    )


@router.post(
    "/profiles",
    response_model=ProfileResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_profile(
    owner_id: Annotated[str, Depends(current_owner)],
    profile: ProfileCreate,
    session: Annotated[Session, Depends(get_session)],
    request: Request,
) -> ModelProfile:
    payload = profile.model_dump()
    _validate_mode_fields(
        profile, payload, request.app.state.settings.app_mode == "hosted"
    )
    model_profile = ModelProfile(owner_id=owner_id, **payload)
    session.add(model_profile)
    session.commit()
    session.refresh(model_profile)
    return model_profile


def _get_profile(session: Session, profile_id: UUID, owner_id: str) -> ModelProfile:
    profile = session.scalar(
        select(ModelProfile).where(
            ModelProfile.id == profile_id,
            ModelProfile.owner_id == owner_id,
        )
    )
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@router.get("/profiles/{id}", response_model=ProfileResponse)
def get_profile(
    id: UUID,
    owner_id: Annotated[str, Depends(current_owner)],
    session: Annotated[Session, Depends(get_session)],
) -> ModelProfile:
    return _get_profile(session, id, owner_id)


@router.patch("/profiles/{id}", response_model=ProfileResponse)
def update_profile(
    owner_id: Annotated[str, Depends(current_owner)],
    id: UUID,
    profile: ProfileUpdate,
    session: Annotated[Session, Depends(get_session)],
    request: Request,
) -> ModelProfile:
    payload = profile.model_dump(exclude_unset=True)
    if not payload:
        raise HTTPException(status_code=422, detail={"request": "No fields to update"})
    _validate_mode_fields(
        profile, payload, request.app.state.settings.app_mode == "hosted"
    )
    model_profile = _get_profile(session, id, owner_id)
    for field, value in payload.items():
        setattr(model_profile, field, value)
    session.commit()
    session.refresh(model_profile)
    return model_profile


@router.delete("/profiles/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_profile(
    id: UUID,
    owner_id: Annotated[str, Depends(current_owner)],
    session: Annotated[Session, Depends(get_session)],
) -> Response:
    model_profile = _get_profile(session, id, owner_id)
    session.execute(
        update(BenchmarkRun)
        .where(
            BenchmarkRun.owner_id == owner_id,
            BenchmarkRun.profile_id == model_profile.id,
        )
        .values(profile_id=None)
    )
    session.delete(model_profile)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
