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
    text,
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
    application_revision: Mapped[str | None] = mapped_column(String(64))
    investigation_summary: Mapped[str | None] = mapped_column(Text)
    investigation_status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="not_started",
        server_default=text("'not_started'"),
    )
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
        CheckConstraint(
            "investigation_status IN ('not_started', 'queued', 'investigating', "
            "'blocked', 'completed', 'failed')",
            name="ck_incident_records_investigation_status",
        ),
    )


class IncidentAuditEvent(Base):
    __tablename__ = "incident_audit_events"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    incident_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("incident_records.id", ondelete="RESTRICT"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(48), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "event_type IN ('alert_received', 'alert_resolved', "
            "'evidence_collected', 'investigation_dispatch', 'recovery_attempt', "
            "'repair_dispatch', 'repair_attempt', 'repair_pull_request', 'repair_ci', "
            "'repair_release_check')",
            name="ck_incident_audit_events_type",
        ),
        CheckConstraint(
            "outcome IN ('accepted', 'complete', 'partial', 'failed', "
            "'blocked', 'rejected')",
            name="ck_incident_audit_events_outcome",
        ),
        Index(
            "ix_incident_audit_events_incident_created",
            "incident_id",
            "created_at",
        ),
    )


class IncidentRepairJob(Base):
    __tablename__ = "incident_repair_jobs"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    incident_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("incident_records.id", ondelete="RESTRICT"),
        nullable=False,
    )
    fingerprint: Mapped[str] = mapped_column(String(16), nullable=False)
    source_revision: Mapped[str] = mapped_column(String(64), nullable=False)
    model_name: Mapped[str | None] = mapped_column(String(64))
    user_requests: Mapped[int | None] = mapped_column(Integer)
    premium_request_cost: Mapped[Decimal | None] = mapped_column(Numeric)
    nano_aiu: Mapped[Decimal | None] = mapped_column(Numeric)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    root_cause: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric)
    branch_name: Mapped[str | None] = mapped_column(String(255))
    pull_request_number: Mapped[int | None] = mapped_column(Integer)
    pull_request_url: Mapped[str | None] = mapped_column(Text)
    pull_request_sha: Mapped[str | None] = mapped_column(String(64))
    ci_status: Mapped[str | None] = mapped_column(String(16))
    failure_code: Mapped[str | None] = mapped_column(String(48))
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
            "status IN ('queued', 'investigating', 'testing', 'pr_open', "
            "'ci_running', 'ci_passed', 'ci_failed', 'recovered', 'escalated', "
            "'failed', 'closed')",
            name="ck_incident_repair_jobs_status",
        ),
        CheckConstraint(
            "attempts BETWEEN 0 AND 1", name="ck_incident_repair_jobs_attempts"
        ),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_incident_repair_jobs_confidence",
        ),
        UniqueConstraint("incident_id", name="uq_incident_repair_jobs_incident"),
        Index(
            "uq_incident_repair_jobs_active_fingerprint",
            "fingerprint",
            unique=True,
            postgresql_where=text(
                "status IN ('queued', 'investigating', 'testing', 'pr_open', "
                "'ci_running', 'ci_passed', 'ci_failed')"
            ),
            sqlite_where=text(
                "status IN ('queued', 'investigating', 'testing', 'pr_open', "
                "'ci_running', 'ci_passed', 'ci_failed')"
            ),
        ),
        Index(
            "uq_incident_repair_jobs_single_worker",
            text("(1)"),
            unique=True,
            postgresql_where=text(
                "status IN ('investigating', 'testing', 'ci_running')"
            ),
            sqlite_where=text("status IN ('investigating', 'testing', 'ci_running')"),
        ),
    )
