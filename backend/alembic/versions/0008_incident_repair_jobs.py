"""Persist bounded incident repair jobs and outcomes.

Revision ID: 0008_incident_repair_jobs
Revises: 0007_incident_audit
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0008_incident_repair_jobs"
down_revision: str | None = "0007_incident_audit"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_ACTIVE_STATUSES = (
    "'queued', 'investigating', 'testing', 'pr_open', "
    "'ci_running', 'ci_passed', 'ci_failed'"
)


def upgrade() -> None:
    op.add_column(
        "incident_records",
        sa.Column("application_revision", sa.String(length=64), nullable=True),
    )
    op.drop_constraint(
        "ck_incident_records_investigation_status",
        "incident_records",
        type_="check",
    )
    op.create_check_constraint(
        "ck_incident_records_investigation_status",
        "incident_records",
        "investigation_status IN ('not_started', 'queued', 'investigating', "
        "'blocked', 'completed', 'failed')",
    )
    op.drop_constraint(
        "ck_incident_audit_events_type",
        "incident_audit_events",
        type_="check",
    )
    op.create_check_constraint(
        "ck_incident_audit_events_type",
        "incident_audit_events",
        "event_type IN ('alert_received', 'alert_resolved', "
        "'evidence_collected', 'investigation_dispatch', 'recovery_attempt', "
        "'repair_dispatch', 'repair_attempt', 'repair_pull_request', 'repair_ci', "
        "'repair_release_check')",
    )
    op.create_table(
        "incident_repair_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("incident_id", sa.Uuid(), nullable=False),
        sa.Column("fingerprint", sa.String(length=16), nullable=False),
        sa.Column("source_revision", sa.String(length=64), nullable=False),
        sa.Column("model_name", sa.String(length=64), nullable=True),
        sa.Column("user_requests", sa.Integer(), nullable=True),
        sa.Column("premium_request_cost", sa.Numeric(), nullable=True),
        sa.Column("nano_aiu", sa.Numeric(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("root_cause", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Numeric(), nullable=True),
        sa.Column("branch_name", sa.String(length=255), nullable=True),
        sa.Column("pull_request_number", sa.Integer(), nullable=True),
        sa.Column("pull_request_url", sa.Text(), nullable=True),
        sa.Column("pull_request_sha", sa.String(length=64), nullable=True),
        sa.Column("ci_status", sa.String(length=16), nullable=True),
        sa.Column("failure_code", sa.String(length=48), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'investigating', 'testing', 'pr_open', "
            "'ci_running', 'ci_passed', 'ci_failed', 'recovered', 'escalated', "
            "'failed', 'closed')",
            name="ck_incident_repair_jobs_status",
        ),
        sa.CheckConstraint(
            "attempts BETWEEN 0 AND 1",
            name="ck_incident_repair_jobs_attempts",
        ),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_incident_repair_jobs_confidence",
        ),
        sa.ForeignKeyConstraint(
            ["incident_id"],
            ["incident_records.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("incident_id", name="uq_incident_repair_jobs_incident"),
    )
    op.create_index(
        "uq_incident_repair_jobs_active_fingerprint",
        "incident_repair_jobs",
        ["fingerprint"],
        unique=True,
        postgresql_where=sa.text(f"status IN ({_ACTIVE_STATUSES})"),
        sqlite_where=sa.text(f"status IN ({_ACTIVE_STATUSES})"),
    )
    op.create_index(
        "uq_incident_repair_jobs_single_worker",
        "incident_repair_jobs",
        [sa.text("(1)")],
        unique=True,
        postgresql_where=sa.text(
            "status IN ('investigating', 'testing', 'ci_running')"
        ),
        sqlite_where=sa.text("status IN ('investigating', 'testing', 'ci_running')"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_incident_repair_jobs_single_worker",
        table_name="incident_repair_jobs",
    )
    op.drop_index(
        "uq_incident_repair_jobs_active_fingerprint",
        table_name="incident_repair_jobs",
    )
    op.drop_table("incident_repair_jobs")
    op.drop_constraint(
        "ck_incident_audit_events_type",
        "incident_audit_events",
        type_="check",
    )
    op.create_check_constraint(
        "ck_incident_audit_events_type",
        "incident_audit_events",
        "event_type IN ('alert_received', 'alert_resolved', "
        "'evidence_collected', 'investigation_dispatch', 'recovery_attempt')",
    )
    op.drop_column("incident_records", "application_revision")
    op.drop_constraint(
        "ck_incident_records_investigation_status",
        "incident_records",
        type_="check",
    )
    op.create_check_constraint(
        "ck_incident_records_investigation_status",
        "incident_records",
        "investigation_status IN ('not_started', 'blocked', 'completed', 'failed')",
    )
