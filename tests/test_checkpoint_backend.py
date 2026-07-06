"""Tests for the checkpointer factory and PostgreSQL fallback behavior."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from langgraph.checkpoint.sqlite import SqliteSaver

from vet_manuscript_lab.infrastructure.checkpoints import open_checkpointer
from vet_manuscript_lab.infrastructure.checkpoints._postgres import (
    _redact_url,
    is_postgres_checkpoint_available,
)


class OpenCheckpointerFactoryTests(unittest.TestCase):
    """``open_checkpointer`` selects backend based on the database URL."""

    def test_sqlite_url_returns_sqlite_saver(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "checkpoints.sqlite"
            conn, saver = open_checkpointer(
                database_url="sqlite:///./test.db",
                checkpoint_path=path,
            )
            self.assertIsInstance(saver, SqliteSaver)
            conn.close()

    def test_empty_url_falls_back_to_sqlite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "checkpoints.sqlite"
            conn, saver = open_checkpointer(checkpoint_path=path)
            self.assertIsInstance(saver, SqliteSaver)
            conn.close()

    def test_default_checkpoint_path_when_none(self) -> None:
        """When checkpoint_path is None, a default is used without error."""

        conn, saver = open_checkpointer(database_url="sqlite:///./test.db")
        self.assertIsInstance(saver, SqliteSaver)
        conn.close()

    def test_postgres_url_without_dependency_falls_back_to_sqlite(self) -> None:
        """PostgreSQL URL without installed deps should fall back to SQLite."""

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "checkpoints.sqlite"
            with mock.patch(
                "vet_manuscript_lab.infrastructure.checkpoints."
                "is_postgres_checkpoint_available",
                return_value=False,
            ):
                conn, saver = open_checkpointer(
                    database_url="postgresql://localhost/db",
                    checkpoint_path=path,
                )
                self.assertIsInstance(saver, SqliteSaver)
                conn.close()


class PostgresAvailabilityTests(unittest.TestCase):
    """``is_postgres_checkpoint_available`` reflects installed packages."""

    def test_returns_false_when_package_missing(self) -> None:
        """When psycopg is absent, availability returns False."""

        import sys

        # Save and restore sys.modules state
        saved_pg = sys.modules.get("langgraph.checkpoint.postgres")
        saved_ps = sys.modules.get("psycopg")
        sys.modules["langgraph.checkpoint.postgres"] = None  # type: ignore[assignment]
        try:
            result = is_postgres_checkpoint_available()
            self.assertFalse(result)
        finally:
            if saved_pg is not None:
                sys.modules["langgraph.checkpoint.postgres"] = saved_pg
            else:
                sys.modules.pop("langgraph.checkpoint.postgres", None)
            if saved_ps is not None:
                sys.modules["psycopg"] = saved_ps
            else:
                sys.modules.pop("psycopg", None)

    def test_returns_true_when_packages_present(self) -> None:
        """When both packages are importable, availability returns True."""

        import sys
        import types

        # Create fake module objects
        fake_pg = types.ModuleType("langgraph.checkpoint.postgres")
        fake_ps = types.ModuleType("psycopg")
        saved_pg = sys.modules.get("langgraph.checkpoint.postgres")
        saved_ps = sys.modules.get("psycopg")
        sys.modules["langgraph.checkpoint.postgres"] = fake_pg
        sys.modules["psycopg"] = fake_ps
        try:
            self.assertTrue(is_postgres_checkpoint_available())
        finally:
            if saved_pg is not None:
                sys.modules["langgraph.checkpoint.postgres"] = saved_pg
            else:
                sys.modules.pop("langgraph.checkpoint.postgres", None)
            if saved_ps is not None:
                sys.modules["psycopg"] = saved_ps
            else:
                sys.modules.pop("psycopg", None)


class RedactUrlTests(unittest.TestCase):
    """``_redact_url`` strips credentials for safe logging."""

    def test_password_is_redacted(self) -> None:
        result = _redact_url("postgresql://admin:secret@localhost:5432/db")
        self.assertIn("***", result)
        self.assertNotIn("secret", result)
        self.assertIn("admin", result)

    def test_url_without_credentials_unchanged(self) -> None:
        url = "postgresql://localhost:5432/db"
        self.assertEqual(_redact_url(url), url)

    def test_sqlite_url_unchanged(self) -> None:
        url = "sqlite:///./checkpoints.sqlite"
        self.assertEqual(_redact_url(url), url)


if __name__ == "__main__":
    unittest.main()
