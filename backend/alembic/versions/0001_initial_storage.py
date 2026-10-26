"""Initial profile and benchmark-run storage.

Revision ID: 0001_initial_storage
Revises:
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001_initial_storage"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "model_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("model_name", sa.String(length=255), nullable=False),
        sa.Column("model_version", sa.String(length=255), nullable=True),
        sa.Column("quantisation", sa.String(length=100), nullable=True),
        sa.Column("endpoint_url", sa.Text(), nullable=True),
        sa.Column("hardware_notes", sa.Text(), nullable=True),
        sa.Column("inference_config", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_model_profiles_owner_id", "model_profiles", ["owner_id"])
    op.create_index(
        "ix_model_profiles_owner_model_name",
        "model_profiles",
        ["owner_id", "model_name"],
    )
    op.create_table(
        "benchmark_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", sa.String(length=255), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("profile_snapshot", sa.JSON(), nullable=False),
        sa.Column("source_run_id", sa.String(length=255), nullable=True),
        sa.Column("import_fingerprint", sa.String(length=255), nullable=True),
        sa.Column("benchmark_version", sa.String(length=255), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("elapsed_ms", sa.Integer(), nullable=True),
        sa.Column("quality_score", sa.Numeric(), nullable=True),
        sa.Column("pass_rate", sa.Numeric(), nullable=True),
        sa.Column("ttft_ms", sa.Numeric(), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("prompt_throughput_tps", sa.Numeric(), nullable=True),
        sa.Column("generation_throughput_tps", sa.Numeric(), nullable=True),
        sa.Column("hardware_snapshot", sa.JSON(), nullable=True),
        sa.Column("error_category", sa.String(length=255), nullable=True),
        sa.Column("error_message_sanitised", sa.Text(), nullable=True),
        sa.Column("process_exit_code", sa.Integer(), nullable=True),
        sa.Column("artifact_ref", sa.String(length=1024), nullable=True),
        sa.Column("related_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "source IN ('imported', 'launched')", name="ck_benchmark_runs_source"
        ),
        sa.CheckConstraint(
            "status IN ('running', 'completed', 'failed', 'interrupted')",
            name="ck_benchmark_runs_status",
        ),
        sa.ForeignKeyConstraint(["profile_id"], ["model_profiles.id"]),
        sa.ForeignKeyConstraint(["related_run_id"], ["benchmark_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_benchmark_runs_owner_id", "benchmark_runs", ["owner_id"])
    op.create_index(
        "ix_benchmark_runs_owner_created_at",
        "benchmark_runs",
        ["owner_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_benchmark_runs_owner_status", "benchmark_runs", ["owner_id", "status"]
    )
    op.create_index(
        "uq_benchmark_runs_owner_fingerprint",
        "benchmark_runs",
        ["owner_id", "import_fingerprint"],
        unique=True,
        postgresql_where=sa.text("import_fingerprint IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_benchmark_runs_owner_fingerprint", table_name="benchmark_runs")
    op.drop_index("ix_benchmark_runs_owner_status", table_name="benchmark_runs")
    op.drop_index("ix_benchmark_runs_owner_created_at", table_name="benchmark_runs")
    op.drop_index("ix_benchmark_runs_owner_id", table_name="benchmark_runs")
    op.drop_table("benchmark_runs")
    op.drop_index("ix_model_profiles_owner_model_name", table_name="model_profiles")
    op.drop_index("ix_model_profiles_owner_id", table_name="model_profiles")
    op.drop_table("model_profiles")
