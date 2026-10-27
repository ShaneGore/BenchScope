"""Store the allowlisted benchmark configuration on imported runs.

Revision ID: 0002_run_benchmark_config
Revises: 0001_initial_storage
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_run_benchmark_config"
down_revision: str | None = "0001_initial_storage"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "benchmark_runs",
        sa.Column("benchmark_config", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("benchmark_runs", "benchmark_config")
