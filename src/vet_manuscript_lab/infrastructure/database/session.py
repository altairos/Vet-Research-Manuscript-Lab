"""Database engine and transaction factory."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from vet_manuscript_lab.infrastructure.database.base import Base


@dataclass(frozen=True, slots=True)
class Database:
    engine: Engine
    sessions: sessionmaker[Session]

    def create_schema(self) -> None:
        # Import registers all mapped tables with Base.metadata.
        from vet_manuscript_lab.infrastructure.database import models  # noqa: F401

        Base.metadata.create_all(self.engine)


def create_database(url: str, *, echo: bool = False) -> Database:
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, echo=echo, connect_args=connect_args)

    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def enable_sqlite_foreign_keys(dbapi_connection: object, _: object) -> None:
            cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    sessions = sessionmaker(engine, expire_on_commit=False)
    return Database(engine=engine, sessions=sessions)
