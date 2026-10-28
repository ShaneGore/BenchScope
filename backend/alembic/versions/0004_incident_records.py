"""Persist sanitized local alert incidents.

Revision ID: 0004_incident_records
Revises: 0003_run_task_results
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004_incident_records"
down_revision: str | None = "0003_run_task_results"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "incident_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("alert_name", sa.String(length=100), nullable=False),
        sa.Column("fingerprint", sa.String(length=16), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("alert_status", sa.String(length=16), nullable=False),
        sa.Column("evidence_status", sa.String(length=16), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "alert_status IN ('firing', 'resolved')",
            name="ck_incident_records_alert_status",
        ),
        sa.CheckConstraint(
            "evidence_status IN ('complete', 'partial', 'failed')",
            name="ck_incident_records_evidence_status",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "fingerprint", "starts_at", name="uq_incident_records_fingerprint_start"
        ),
    )


def downgrade() -> None:
    op.drop_table("incident_records")
