import os
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from alembic import command
from app.database import LOCAL_OWNER_ID
from app.models import BenchmarkRun, ModelProfile

BACKEND_DIR = os.path.dirname(os.path.dirname(__file__))


def test_postgres_baseline_migration_and_storage_contract() -> None:
    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("Set TEST_DATABASE_URL to run PostgreSQL integration tests")
    if make_url(database_url).get_backend_name() != "postgresql":
        pytest.fail("TEST_DATABASE_URL must use PostgreSQL")

    engine = create_engine(database_url)
    schema = f"benchscope_test_{uuid4().hex}"
    try:
        with engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        with engine.connect() as connection:
            connection.exec_driver_sql(f'SET search_path TO "{schema}"')
            connection.commit()
            alembic_config = Config(os.path.join(BACKEND_DIR, "alembic.ini"))
            alembic_config.attributes["connection"] = connection

            command.upgrade(alembic_config, "head")
            first_revision = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
            tables_after_first_upgrade = set(inspect(connection).get_table_names())
            command.upgrade(alembic_config, "head")
            assert (
                connection.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar_one()
                == first_revision
            )
            command.check(alembic_config)
            assert (
                set(inspect(connection).get_table_names()) == tables_after_first_upgrade
            )
            assert tables_after_first_upgrade == {
                "alembic_version",
                "benchmark_runs",
                "incident_records",
                "model_profiles",
            }

            run_columns = {
                column["name"]: column
                for column in inspect(connection).get_columns("benchmark_runs")
            }
            profile_columns = {
                column["name"]: column
                for column in inspect(connection).get_columns("model_profiles")
            }
            assert run_columns["owner_id"]["nullable"] is False
            assert profile_columns["owner_id"]["nullable"] is False
            metric_columns = {
                "quality_score",
                "pass_rate",
                "ttft_ms",
                "elapsed_ms",
                "prompt_tokens",
                "output_tokens",
                "prompt_throughput_tps",
                "generation_throughput_tps",
            }
            assert all(run_columns[name]["nullable"] for name in metric_columns)
            forbidden_columns = {
                "prompt",
                "generated_code",
                "raw_benchmark_output",
                "api_key",
                "password",
                "secret",
                "credential",
            }
            assert not forbidden_columns & (run_columns.keys() | profile_columns.keys())

            indexes = {
                index["name"]: index
                for index in inspect(connection).get_indexes("benchmark_runs")
            }
            assert set(indexes) == {
                "ix_benchmark_runs_owner_created_at",
                "ix_benchmark_runs_owner_id",
                "ix_benchmark_runs_owner_status",
                "uq_benchmark_runs_owner_fingerprint",
            }
            fingerprint_index = indexes["uq_benchmark_runs_owner_fingerprint"]
            assert fingerprint_index["unique"] is True
            assert fingerprint_index["column_names"] == [
                "owner_id",
                "import_fingerprint",
            ]
            assert (
                "IS NOT NULL"
                in fingerprint_index["dialect_options"]["postgresql_where"].upper()
            )
            assert (
                "owner_id" in indexes["ix_benchmark_runs_owner_status"]["column_names"]
            )

            constraints = {
                item["name"]
                for item in inspect(connection).get_check_constraints("benchmark_runs")
            }
            assert constraints == {
                "ck_benchmark_runs_source",
                "ck_benchmark_runs_status",
            }
            assert {
                index["name"]
                for index in inspect(connection).get_indexes("model_profiles")
            } == {
                "ix_model_profiles_owner_id",
                "ix_model_profiles_owner_model_name",
            }
            connection.commit()

            session = Session(connection)
            profile = ModelProfile(
                owner_id=LOCAL_OWNER_ID,
                name="local profile",
                model_name="example-model",
            )
            session.add(profile)
            session.flush()
            run_kwargs = {
                "owner_id": LOCAL_OWNER_ID,
                "source": "imported",
                "status": "completed",
                "profile_id": profile.id,
                "profile_snapshot": {"model_name": profile.model_name},
                "started_at": datetime.now(UTC),
            }
            zero_run = BenchmarkRun(
                **run_kwargs,
                quality_score=Decimal(0),
                import_fingerprint="fingerprint-zero",
            )
            null_run = BenchmarkRun(**run_kwargs)
            duplicate_null_run = BenchmarkRun(**run_kwargs)
            session.add_all([zero_run, null_run, duplicate_null_run])
            session.commit()

            assert session.get(BenchmarkRun, zero_run.id).quality_score == Decimal(0)
            assert session.get(BenchmarkRun, null_run.id).quality_score is None

            with pytest.raises(IntegrityError):
                session.add(BenchmarkRun(**{**run_kwargs, "source": "unknown"}))
                session.flush()
            session.rollback()
            with pytest.raises(IntegrityError):
                session.add(BenchmarkRun(**{**run_kwargs, "profile_id": uuid4()}))
                session.flush()
            session.rollback()

            session.add(BenchmarkRun(**run_kwargs, import_fingerprint="duplicate"))
            session.commit()
            session.add(BenchmarkRun(**run_kwargs, import_fingerprint="duplicate"))
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()

            session.add(
                BenchmarkRun(
                    **{**run_kwargs, "owner_id": "another-owner"},
                    import_fingerprint="duplicate",
                )
            )
            session.commit()
            session.close()
    finally:
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        engine.dispose()
