from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


class MigrationTests(unittest.TestCase):
    def test_foundation_migration_upgrades_empty_database(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "migrated.sqlite"
            config = Config("alembic.ini")
            config.set_main_option("sqlalchemy.url", f"sqlite:///{path}")
            command.upgrade(config, "head")

            engine = create_engine(f"sqlite:///{path}")
            tables = set(inspect(engine).get_table_names())
            self.assertTrue(
                {
                    "projects",
                    "workflow_runs",
                    "artifacts",
                    "artifact_versions",
                    "approvals",
                    "locks",
                    "audit_events",
                    "alembic_version",
                }.issubset(tables)
            )
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
