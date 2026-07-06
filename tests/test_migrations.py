from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

EXPECTED_TABLES = {
    "projects",
    "workflow_runs",
    "artifacts",
    "artifact_versions",
    "approvals",
    "locks",
    "audit_events",
    "literature_records",
    "attachment_versions",
    "source_spans",
    "evidence_items",
    "screening_decisions",
    "provenance_links",
    "datasets",
    "dataset_versions",
    "dataset_variables",
    "analysis_plan_versions",
    "analysis_plan_locks",
    "methodology_findings",
    "analysis_runs",
    "statistical_results",
    "manuscripts",
    "manuscript_versions",
    "manuscript_sections",
    "claims",
    "claim_supports",
    "citations",
    "review_findings",
    "revision_decisions",
    "compliance_findings",
    "export_packages",
    "alembic_version",
}


class MigrationTests(unittest.TestCase):
    def test_foundation_migration_upgrades_empty_database(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "migrated.sqlite"
            config = Config("alembic.ini")
            config.set_main_option("sqlalchemy.url", f"sqlite:///{path}")
            command.upgrade(config, "head")

            engine = create_engine(f"sqlite:///{path}")
            tables = set(inspect(engine).get_table_names())
            self.assertTrue(EXPECTED_TABLES.issubset(tables))
            engine.dispose()

    def test_alembic_env_variable_overrides_url(self) -> None:
        """``VET_LAB_DATABASE_URL`` should override the alembic.ini URL."""

        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "env_override.sqlite"
            url = f"sqlite:///{path}"
            config = Config("alembic.ini")
            config.set_main_option("sqlalchemy.url", url)
            command.upgrade(config, "head")

            engine = create_engine(url)
            tables = set(inspect(engine).get_table_names())
            self.assertIn("projects", tables)
            engine.dispose()


class PostgresMigrationTests(unittest.TestCase):
    """Optional PostgreSQL migration tests.

    Skipped unless ``VET_LAB_TEST_PG_URL`` environment variable is set
    to a live PostgreSQL connection URL.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.pg_url = os.getenv("VET_LAB_TEST_PG_URL", "")

    @unittest.skipUnless(
        os.getenv("VET_LAB_TEST_PG_URL"),
        "Set VET_LAB_TEST_PG_URL to a PostgreSQL URL to run this test.",
    )
    def test_postgresql_migration_upgrades_empty_database(self) -> None:
        config = Config("alembic.ini")
        config.set_main_option("sqlalchemy.url", self.pg_url)
        command.upgrade(config, "head")

        engine = create_engine(self.pg_url)
        try:
            tables = set(inspect(engine).get_table_names())
            self.assertTrue(EXPECTED_TABLES.issubset(tables))
        finally:
            # Clean up: drop all tables
            command.downgrade(config, "base")
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
