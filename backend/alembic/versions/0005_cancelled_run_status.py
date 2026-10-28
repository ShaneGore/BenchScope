"""Allow the distinct cancelled benchmark-run status.

Revision ID: 0005_cancelled_run_status
Revises: 0004_incident_records
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0005_cancelled_run_status"
down_revision: str | None = "0004_incident_records"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_benchmark_runs_status", "benchmark_runs", type_="check")
    op.create_check_constraint(
        "ck_benchmark_runs_status",
        "benchmark_runs",
        "status IN ('running', 'completed', 'failed', 'interrupted', 'cancelled')",
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM benchmark_runs WHERE status = 'cancelled') THEN
                RAISE EXCEPTION 'Cannot downgrade while cancelled benchmark runs exist';
            END IF;
        END;
        $$
        """
    )
    op.drop_constraint("ck_benchmark_runs_status", "benchmark_runs", type_="check")
    op.create_check_constraint(
        "ck_benchmark_runs_status",
        "benchmark_runs",
        "status IN ('running', 'completed', 'failed', 'interrupted')",
    )
