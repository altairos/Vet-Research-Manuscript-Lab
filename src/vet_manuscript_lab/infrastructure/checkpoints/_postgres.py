"""PostgreSQL checkpointer adapter (lazy-loaded).

This module imports ``langgraph-checkpoint-postgres`` only when actually
needed, keeping the base installation free of PostgreSQL dependencies.
"""

from __future__ import annotations

import logging
from importlib import import_module
from typing import Any

logger = logging.getLogger(__name__)


def open_postgres_checkpointer(url: str) -> tuple[Any, Any]:
    """Create a LangGraph ``PostgresSaver`` connected to *url*.

    Returns a ``(connection, checkpointer)`` tuple mirroring the SQLite
    counterpart.  Raises ``ImportError`` if the optional dependency is
    not installed; callers should catch this and fall back to SQLite.
    """

    psycopg = import_module("psycopg")
    postgres = import_module("langgraph.checkpoint.postgres")

    logger.info("Opening PostgreSQL checkpointer at %s", _redact_url(url))
    connection = psycopg.connect(url, autocommit=True)
    checkpointer = postgres.PostgresSaver(connection)
    checkpointer.setup()
    return connection, checkpointer


def is_postgres_checkpoint_available() -> bool:
    """Return ``True`` when the optional PostgreSQL checkpoint package is installed."""

    try:
        import_module("psycopg")
        import_module("langgraph.checkpoint.postgres")
    except (ImportError, ModuleNotFoundError):
        return False
    return True


def _redact_url(url: str) -> str:
    """Remove password from a PostgreSQL URL for safe logging."""

    if "@" not in url:
        return url
    scheme_and_rest = url.split("://", 1)
    if len(scheme_and_rest) != 2:
        return url
    scheme, rest = scheme_and_rest
    creds, host_part = rest.rsplit("@", 1)
    user = creds.split(":", 1)[0] if ":" in creds else creds
    return f"{scheme}://{user}:***@{host_part}"
