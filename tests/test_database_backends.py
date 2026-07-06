"""Tests for database backend abstraction, session factory, and health check."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from sqlalchemy.pool import QueuePool

from vet_manuscript_lab.infrastructure.database import (
    Database,
    PoolConfig,
    PostgresBackend,
    SqliteBackend,
    create_database,
    select_backend,
)


class BackendSelectionTests(unittest.TestCase):
    """``select_backend`` dispatches based on the URL scheme."""

    def test_sqlite_url_returns_sqlite_backend(self) -> None:
        backend = select_backend("sqlite:///./test.db")
        self.assertIsInstance(backend, SqliteBackend)

    def test_postgresql_url_returns_postgres_backend(self) -> None:
        backend = select_backend("postgresql://user:pass@localhost/db")
        self.assertIsInstance(backend, PostgresBackend)

    def test_postgresql_psycopg_url_returns_postgres_backend(self) -> None:
        backend = select_backend("postgresql+psycopg://user:pass@localhost/db")
        self.assertIsInstance(backend, PostgresBackend)

    def test_unsupported_scheme_raises_value_error(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            select_backend("mysql://user:pass@localhost/db")
        self.assertIn("Unsupported database URL scheme", str(ctx.exception))


class SqliteBackendTests(unittest.TestCase):
    """SQLite engine configuration verification."""

    def test_sqlite_backend_creates_engine_with_foreign_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            url = f"sqlite:///{Path(tmp) / 'test.sqlite'}"
            backend = SqliteBackend()
            engine = backend.create_engine(url, pool_config=PoolConfig())
            from sqlalchemy import inspect

            self.assertEqual(inspect(engine).dialect.name, "sqlite")
            engine.dispose()

    def test_sqlite_backend_ignores_pool_config(self) -> None:
        """SQLite engine must not apply PostgreSQL-style pool parameters."""

        with tempfile.TemporaryDirectory() as tmp:
            url = f"sqlite:///{Path(tmp) / 'test.sqlite'}"
            backend = SqliteBackend()
            engine = backend.create_engine(url, pool_config=PoolConfig(pool_size=99))
            # SQLAlchemy 2.x may use QueuePool for file-based SQLite by default,
            # but the custom pool_size=99 must NOT have been applied.
            self.assertNotEqual(engine.pool.size(), 99)
            engine.dispose()


class PostgresBackendTests(unittest.TestCase):
    """PostgreSQL engine configuration verification (no live connection needed).

    These tests mock ``create_engine`` so no PostgreSQL driver is required.
    """

    @mock.patch("vet_manuscript_lab.infrastructure.database.backends.create_engine")
    def test_postgres_backend_creates_engine_with_queue_pool(
        self, mock_create: mock.MagicMock
    ) -> None:
        backend = PostgresBackend()
        backend.create_engine(
            "postgresql://user:pass@localhost:5432/testdb",
            pool_config=PoolConfig(pool_size=7, max_overflow=3, pool_recycle=600),
        )
        mock_create.assert_called_once()
        _, kwargs = mock_create.call_args
        self.assertIs(kwargs["poolclass"], QueuePool)
        self.assertEqual(kwargs["pool_size"], 7)
        self.assertEqual(kwargs["max_overflow"], 3)
        self.assertEqual(kwargs["pool_recycle"], 600)

    @mock.patch("vet_manuscript_lab.infrastructure.database.backends.create_engine")
    def test_postgres_backend_pool_pre_ping(self, mock_create: mock.MagicMock) -> None:
        backend = PostgresBackend()
        backend.create_engine(
            "postgresql://user:pass@localhost/db",
            pool_config=PoolConfig(pool_pre_ping=True),
        )
        _, kwargs = mock_create.call_args
        self.assertTrue(kwargs["pool_pre_ping"])


class DatabaseFactoryTests(unittest.TestCase):
    """``create_database`` integrates backend selection with session factory."""

    def test_create_database_with_sqlite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = create_database(f"sqlite:///{Path(tmp) / 'test.sqlite'}")
            self.assertIsInstance(db, Database)
            self.assertEqual(db.dialect_name, "sqlite")
            db.create_schema()
            self.assertTrue(db.health_check())
            db.engine.dispose()

    def test_create_database_with_custom_pool_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = create_database(
                f"sqlite:///{Path(tmp) / 'test.sqlite'}",
                pool_config=PoolConfig(pool_size=3),
            )
            self.assertEqual(db.dialect_name, "sqlite")
            db.engine.dispose()

    def test_create_database_with_explicit_backend(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = create_database(
                f"sqlite:///{Path(tmp) / 'test.sqlite'}",
                backend=SqliteBackend(),
            )
            self.assertEqual(db.dialect_name, "sqlite")
            db.engine.dispose()

    def test_create_database_invalid_url_raises(self) -> None:
        with self.assertRaises(ValueError):
            create_database("oracle://localhost/db")

    def test_health_check_returns_true_for_valid_connection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = create_database(f"sqlite:///{Path(tmp) / 'test.sqlite'}")
            self.assertTrue(db.health_check())
            db.engine.dispose()


if __name__ == "__main__":
    unittest.main()
