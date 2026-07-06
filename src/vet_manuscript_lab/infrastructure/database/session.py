"""Database engine and transaction factory."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Engine, text
from sqlalchemy.orm import Session, sessionmaker

from vet_manuscript_lab.infrastructure.database.backends import (
    DatabaseBackend,
    PoolConfig,
    select_backend,
)
from vet_manuscript_lab.infrastructure.database.base import Base


@dataclass(frozen=True, slots=True)
class Database:
    engine: Engine
    sessions: sessionmaker[Session]

    def create_schema(self) -> None:
        # Import registers all mapped tables with Base.metadata.
        from vet_manuscript_lab.infrastructure.database import models  # noqa: F401

        Base.metadata.create_all(self.engine)

    def health_check(self) -> bool:
        """Execute ``SELECT 1`` to verify the database connection is alive."""

        with self.sessions() as session:
            result = session.execute(text("SELECT 1")).scalar()
            return result == 1

    @property
    def dialect_name(self) -> str:
        """Return the SQLAlchemy dialect name (e.g. ``sqlite``, ``postgresql``)."""

        return self.engine.dialect.name


def create_database(
    url: str,
    *,
    echo: bool = False,
    pool_config: PoolConfig | None = None,
    backend: DatabaseBackend | None = None,
) -> Database:
    """Create a ``Database`` bound to *url*.

    The backend is auto-selected from the URL scheme unless *backend* is
    provided (useful for testing).  *pool_config* only affects PostgreSQL.
    """

    if pool_config is None:
        pool_config = PoolConfig()
    if backend is None:
        backend = select_backend(url)

    engine = backend.create_engine(url, pool_config=pool_config)
    if echo:
        engine.echo = True

    sessions = sessionmaker(engine, expire_on_commit=False)
    return Database(engine=engine, sessions=sessions)
