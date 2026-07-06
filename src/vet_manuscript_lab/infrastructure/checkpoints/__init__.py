"""LangGraph checkpoint adapters.

Provides a factory ``open_checkpointer`` that selects SQLite (default) or
PostgreSQL based on the application settings.  PostgreSQL dependencies are
lazily loaded and gracefully degrade to SQLite when unavailable.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from vet_manuscript_lab.infrastructure.checkpoints._postgres import (
    is_postgres_checkpoint_available,
)
from vet_manuscript_lab.infrastructure.checkpoints.sqlite import (
    open_sqlite_checkpointer,
)

logger = logging.getLogger(__name__)

__all__ = [
    "CheckpointPair",
    "CheckpointerFactory",
    "open_checkpointer",
    "open_sqlite_checkpointer",
]


@runtime_checkable
class CheckpointerFactory(Protocol):
    """Protocol for checkpointer creation functions."""

    def __call__(self, *args: Any, **kwargs: Any) -> tuple[Any, Any]: ...


# Type alias: (connection_object, saver_instance)
CheckpointPair = tuple[Any, Any]


def open_checkpointer(
    *,
    database_url: str = "",
    checkpoint_path: Path | None = None,
) -> CheckpointPair:
    """Select and open the appropriate checkpointer based on the database URL.

    * If *database_url* is a PostgreSQL URL and the optional
      ``langgraph-checkpoint-postgres`` package is installed, a
      ``PostgresSaver`` is returned.
    * Otherwise the SQLite checkpointer is used with *checkpoint_path*.

    This ensures the system always boots — PostgreSQL is an opt-in upgrade.
    """

    if database_url.startswith(("postgresql", "postgresql+psycopg")):
        if is_postgres_checkpoint_available():
            from vet_manuscript_lab.infrastructure.checkpoints._postgres import (
                open_postgres_checkpointer,
            )

            return open_postgres_checkpointer(database_url)
        logger.warning(
            "PostgreSQL checkpointer requested but 'langgraph-checkpoint-postgres' "
            "or 'psycopg' is not installed. Falling back to SQLite checkpointer."
        )

    if checkpoint_path is None:
        checkpoint_path = Path("./artifacts/checkpoints.sqlite")
    return open_sqlite_checkpointer(checkpoint_path)
