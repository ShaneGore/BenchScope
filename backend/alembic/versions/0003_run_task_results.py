"""Store benchmark task results for v2 imports.

Revision ID: 0003_run_task_results
Revises: 0002_run_benchmark_config
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_run_task_results"
down_revision: str | None = "0002_run_benchmark_config"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("benchmark_runs", sa.Column("benchmark_details", sa.JSON()))
    op.add_column("benchmark_runs", sa.Column("task_results", sa.JSON()))


def downgrade() -> None:
    op.drop_column("benchmark_runs", "task_results")
    op.drop_column("benchmark_runs", "benchmark_details")
