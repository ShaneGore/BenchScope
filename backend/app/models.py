from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    desc,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ModelProfile(Base):
    __tablename__ = "model_profiles"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    owner_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    model_version: Mapped[str | None] = mapped_column(String(255))
    quantisation: Mapped[str | None] = mapped_column(String(100))
    endpoint_url: Mapped[str | None] = mapped_column(Text)
    hardware_notes: Mapped[str | None] = mapped_column(Text)
    inference_config: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index("ix_model_profiles_owner_model_name", "owner_id", "model_name"),
    )


class BenchmarkRun(Base):
    __tablename__ = "benchmark_runs"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    owner_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    profile_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("model_profiles.id")
    )
    profile_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    benchmark_config: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    source_run_id: Mapped[str | None] = mapped_column(String(255))
    import_fingerprint: Mapped[str | None] = mapped_column(String(255))
    benchmark_version: Mapped[str | None] = mapped_column(String(255))
    benchmark_details: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    task_results: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    elapsed_ms: Mapped[int | None] = mapped_column(Integer)
    quality_score: Mapped[Decimal | None] = mapped_column(Numeric)
    pass_rate: Mapped[Decimal | None] = mapped_column(Numeric)
    ttft_ms: Mapped[Decimal | None] = mapped_column(Numeric)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    prompt_throughput_tps: Mapped[Decimal | None] = mapped_column(Numeric)
    generation_throughput_tps: Mapped[Decimal | None] = mapped_column(Numeric)
    hardware_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    error_category: Mapped[str | None] = mapped_column(String(255))
    error_message_sanitised: Mapped[str | None] = mapped_column(Text)
    process_exit_code: Mapped[int | None] = mapped_column(Integer)
    artifact_ref: Mapped[str | None] = mapped_column(String(1024))
    related_run_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("benchmark_runs.id")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        CheckConstraint(
            "source IN ('imported', 'launched')", name="ck_benchmark_runs_source"
        ),
        CheckConstraint(
            "status IN ('running', 'completed', 'failed', 'interrupted', 'cancelled')",
            name="ck_benchmark_runs_status",
        ),
        Index(
            "uq_benchmark_runs_owner_fingerprint",
            "owner_id",
            "import_fingerprint",
            unique=True,
            postgresql_where=import_fingerprint.is_not(None),
        ),
        Index(
            "ix_benchmark_runs_owner_created_at",
            "owner_id",
            desc("created_at"),
        ),
        Index("ix_benchmark_runs_owner_status", "owner_id", "status"),
    )


class IncidentRecord(Base):
    __tablename__ = "incident_records"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    alert_name: Mapped[str] = mapped_column(String(100), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(16), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    alert_status: Mapped[str] = mapped_column(String(16), nullable=False)
    evidence_status: Mapped[str] = mapped_column(String(16), nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    investigation_summary: Mapped[str | None] = mapped_column(Text)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint(
            "fingerprint", "starts_at", name="uq_incident_records_fingerprint_start"
        ),
        CheckConstraint(
            "alert_status IN ('firing', 'resolved')",
            name="ck_incident_records_alert_status",
        ),
        CheckConstraint(
            "evidence_status IN ('complete', 'partial', 'failed')",
            name="ck_incident_records_evidence_status",
        ),
    )
