import importlib.util
from pathlib import Path

import pytest

MIGRATION_PATH = (
    Path(__file__).parents[1] / "alembic" / "versions" / "0005_cancelled_run_status.py"
)
SPEC = importlib.util.spec_from_file_location("cancelled_run_migration", MIGRATION_PATH)
assert SPEC is not None and SPEC.loader is not None
MIGRATION = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MIGRATION)


def test_downgrade_guard_precedes_constraint_changes(monkeypatch) -> None:
    operations: list[str] = []

    def execute(statement) -> None:
        sql = str(statement)
        operations.append("guard")
        assert (
            "IF EXISTS (SELECT 1 FROM benchmark_runs WHERE status = 'cancelled')" in sql
        )
        assert "RAISE EXCEPTION" in sql
        raise RuntimeError("Cannot downgrade while cancelled benchmark runs exist")

    monkeypatch.setattr(MIGRATION.op, "execute", execute)
    monkeypatch.setattr(
        MIGRATION.op,
        "drop_constraint",
        lambda *args, **kwargs: operations.append("drop constraint"),
    )
    monkeypatch.setattr(
        MIGRATION.op,
        "create_check_constraint",
        lambda *args, **kwargs: operations.append("create constraint"),
    )

    with pytest.raises(RuntimeError, match="cancelled benchmark runs exist"):
        MIGRATION.downgrade()

    assert operations == ["guard"]
