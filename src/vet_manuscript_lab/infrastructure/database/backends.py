"""Database backend abstraction for SQLite and PostgreSQL.

Provides a Protocol-based abstraction so that ``create_database`` can select
the appropriate engine configuration based on the connection URL scheme.
SQLite remains the default local backend; PostgreSQL is available for
future production deployments.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.pool import QueuePool


@dataclass(frozen=True, slots=True)
class PoolConfig:
    """Connection pool parameters for PostgreSQL (ignored by SQLite)."""

    pool_size: int = 5
    max_overflow: int = 10
    pool_recycle: int = 1800
    pool_pre_ping: bool = True


@runtime_checkable
class DatabaseBackend(Protocol):
    """Creates a SQLAlchemy engine configured for a specific database."""

    def create_engine(self, url: str, *, pool_config: PoolConfig) -> Engine: ...


class SqliteBackend:
    """SQLite engine with foreign-key enforcement and thread-safe connections."""

    def create_engine(self, url: str, *, pool_config: PoolConfig) -> Engine:
        engine = create_engine(
            url,
            connect_args={"check_same_thread": False},
        )

        @event.listens_for(engine, "connect")
        def enable_sqlite_foreign_keys(dbapi_connection: object, _: object) -> None:
            cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        return engine


class PostgresBackend:
    """PostgreSQL engine with connection pooling and pre-ping health checks."""

    def create_engine(self, url: str, *, pool_config: PoolConfig) -> Engine:
        return create_engine(
            url,
            poolclass=QueuePool,
            pool_size=pool_config.pool_size,
            max_overflow=pool_config.max_overflow,
            pool_recycle=pool_config.pool_recycle,
            pool_pre_ping=pool_config.pool_pre_ping,
        )


def select_backend(url: str) -> DatabaseBackend:
    """Choose the appropriate backend based on the URL scheme.

    Raises ``ValueError`` for unsupported schemes so configuration errors
    surface early with an actionable message.
    """

    if url.startswith("sqlite"):
        return SqliteBackend()
    if url.startswith(("postgresql", "postgresql+psycopg")):
        return PostgresBackend()
    raise ValueError(
        f"Unsupported database URL scheme: {url.split('://')[0]!r}. "
        "Use 'sqlite' or 'postgresql'."
    )
