"""SQLite checkpointer construction for local workflows."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver


def open_sqlite_checkpointer(path: Path) -> tuple[sqlite3.Connection, SqliteSaver]:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, check_same_thread=False)
    return connection, SqliteSaver(connection)
