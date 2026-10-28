"""Persist a bounded sanitized investigation summary.

Revision ID: 0006_incident_summary
Revises: 0005_cancelled_run_status
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006_incident_summary"
down_revision: str | None = "0005_cancelled_run_status"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "incident_records",
        sa.Column("investigation_summary", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("incident_records", "investigation_summary")


