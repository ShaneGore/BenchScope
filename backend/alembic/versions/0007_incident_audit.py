"""Persist deterministic incident dispatch and recovery audit events.

Revision ID: 0007_incident_audit
Revises: 0006_incident_summary
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007_incident_audit"
down_revision: str | None = "0006_incident_summary"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "incident_records",
        sa.Column(
            "investigation_status",
            sa.String(length=16),
            server_default=sa.text("'not_started'"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_incident_records_investigation_status",
        "incident_records",
        "investigation_status IN ('not_started', 'blocked', 'completed', 'failed')",
    )
    op.create_table(
        "incident_audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("incident_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("reason_code", sa.String(length=48), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "event_type IN ('alert_received', 'alert_resolved', "
            "'evidence_collected', 'investigation_dispatch', 'recovery_attempt')",
            name="ck_incident_audit_events_type",
        ),
        sa.CheckConstraint(
            "outcome IN ('accepted', 'complete', 'partial', 'failed', "
            "'blocked', 'rejected')",
            name="ck_incident_audit_events_outcome",
        ),
        sa.ForeignKeyConstraint(
            ["incident_id"],
            ["incident_records.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_incident_audit_events_incident_created",
        "incident_audit_events",
        ["incident_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_incident_audit_events_incident_created",
        table_name="incident_audit_events",
    )
    op.drop_table("incident_audit_events")
    op.drop_constraint(
        "ck_incident_records_investigation_status",
        "incident_records",
        type_="check",
    )
    op.drop_column("incident_records", "investigation_status")
