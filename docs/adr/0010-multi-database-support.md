# ADR-0010: Multi-Database Backend Support (SQLite + PostgreSQL)

Status: accepted

## Context

Phase 6 (Productionization) requires the system to support both SQLite (local
development) and PostgreSQL (future production deployment). The existing
codebase hardcodes SQLite-specific engine creation in `session.py`, uses a
SQLite-only LangGraph checkpointer, and relies on `server_default` string
literals that are not portable across databases.

The system must maintain its "local-first" principle: SQLite remains the
default, no new hard dependencies are introduced, and all existing tests
continue to pass without modification.

## Decision

1. **Database backend Protocol abstraction.** A `DatabaseBackend` Protocol
   with `SqliteBackend` and `PostgresBackend` implementations isolates
   engine-creation differences. `select_backend(url)` dispatches based on
   the URL scheme. This follows the project's established pattern
   (Protocol + lazy adapter, as seen in Zotero, PDF, and retrieval modules).

2. **Connection pool configuration.** A `PoolConfig` dataclass encapsulates
   pool parameters (`pool_size`, `max_overflow`, `pool_recycle`,
   `pool_pre_ping`). These are only effective for PostgreSQL (QueuePool);
   SQLite ignores them (StaticPool/SingletonThreadPool). Defaults:
   pool_size=5, max_overflow=10, pool_recycle=1800, pool_pre_ping=True.

3. **`create_database` accepts optional `pool_config` and `backend`.**
   When neither is provided, the backend is auto-selected and a default
   `PoolConfig` is used. This preserves backward compatibility with all
   existing callers.

4. **`Database` gains `health_check()` and `dialect_name`.** The health
   check executes `SELECT 1` to verify connectivity. `dialect_name`
   exposes the SQLAlchemy dialect for runtime branching.

5. **Checkpoint backend factory.** `open_checkpointer(database_url, path)`
   selects SQLite or PostgreSQL based on the URL. PostgreSQL support is
   lazy-loaded; when `langgraph-checkpoint-postgres` or `psycopg` is not
   installed, the factory gracefully degrades to SQLite with a logged
   warning. This ensures the system always boots.

6. **Configuration layer.** `Settings` gains `is_sqlite`, `is_postgres`,
   `pool_config` properties and `db_pool_size`, `db_max_overflow`,
   `db_pool_recycle` fields read from environment variables
   (`VET_LAB_DB_POOL_SIZE`, `VET_LAB_DB_MAX_OVERFLOW`,
   `VET_LAB_DB_POOL_RECYCLE`).

7. **Alembic environment variable override.** `migrations/env.py` reads
   `VET_LAB_DATABASE_URL` at runtime, allowing production migration without
   editing `alembic.ini`. `compare_server_default=True` is enabled for
   future autogenerate compatibility.

8. **Migration `server_default` portability fix.** All `server_default`
   values are wrapped in `sa.text()`: integers as `sa.text("0")` and
   strings as `sa.text("'value'")`. PostgreSQL treats bare string defaults
   as SQL identifiers; the single-quote wrapping ensures they are parsed as
   string literals.

9. **No new hard dependencies.** `psycopg2`/`psycopg` and
   `langgraph-checkpoint-postgres` are optional. All PostgreSQL-related
   imports are lazy-loaded inside functions, keeping the base installation
   lightweight and offline-capable.

## Consequences

- SQLite remains the zero-configuration default; existing tests and local
  development workflows are unchanged.
- Switching to PostgreSQL requires only setting `VET_LAB_DATABASE_URL` and
  installing the optional dependencies.
- The checkpointer factory's graceful degradation means a misconfigured
  PostgreSQL URL will not crash the application but will silently fall back
  to SQLite. This is acceptable for Phase 6 because the migration is
  opt-in; a future phase should add a strict mode that fails loudly.
- Future migrations must use `sa.text()` for all `server_default` values to
  maintain cross-database compatibility.
