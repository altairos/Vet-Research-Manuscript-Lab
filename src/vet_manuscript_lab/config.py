"""Runtime configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from vet_manuscript_lab.domain.conventions import RUN_MODE_ENV, RunMode
from vet_manuscript_lab.infrastructure.database.backends import PoolConfig


@dataclass(frozen=True, slots=True)
class Settings:
    environment: str
    database_url: str
    artifact_root: Path
    checkpoint_path: Path
    zotero_api_key: str
    zotero_library_id: str
    zotero_library_type: str
    db_pool_size: int
    db_max_overflow: int
    db_pool_recycle: int
    run_mode: RunMode = RunMode.DEMO

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            environment=os.getenv("VET_LAB_ENV", "development"),
            database_url=os.getenv("VET_LAB_DATABASE_URL", "sqlite:///./vet_lab.db"),
            artifact_root=Path(os.getenv("VET_LAB_ARTIFACT_ROOT", "./artifacts")),
            checkpoint_path=Path(
                os.getenv("VET_LAB_CHECKPOINT_PATH", "./artifacts/checkpoints.sqlite")
            ),
            zotero_api_key=os.getenv("ZOTERO_API_KEY", ""),
            zotero_library_id=os.getenv("ZOTERO_LIBRARY_ID", ""),
            zotero_library_type=os.getenv("ZOTERO_LIBRARY_TYPE", "user"),
            db_pool_size=int(os.getenv("VET_LAB_DB_POOL_SIZE", "5")),
            db_max_overflow=int(os.getenv("VET_LAB_DB_MAX_OVERFLOW", "10")),
            db_pool_recycle=int(os.getenv("VET_LAB_DB_POOL_RECYCLE", "1800")),
            run_mode=RunMode(os.getenv(RUN_MODE_ENV, RunMode.DEMO.value)),
        )

    @property
    def zotero_enabled(self) -> bool:
        """True when both API key and library id are configured."""

        return bool(self.zotero_api_key.strip() and self.zotero_library_id.strip())

    @property
    def is_sqlite(self) -> bool:
        """True when the configured database URL targets SQLite."""

        return self.database_url.startswith("sqlite")

    @property
    def is_postgres(self) -> bool:
        """True when the configured database URL targets PostgreSQL."""

        return self.database_url.startswith(("postgresql", "postgresql+psycopg"))

    @property
    def is_production(self) -> bool:
        """True when the system is running in production fail-closed mode."""

        return self.run_mode == RunMode.PRODUCTION

    @property
    def is_demo(self) -> bool:
        """True when running in demo mode (mock fallbacks permitted)."""

        return self.run_mode == RunMode.DEMO

    @property
    def allows_mock_fallback(self) -> bool:
        """True when mock fallbacks are permitted by the current run mode."""

        return self.run_mode != RunMode.PRODUCTION

    @property
    def pool_config(self) -> PoolConfig:
        """Build a ``PoolConfig`` from the current settings.

        Only effective for PostgreSQL; SQLite ignores pool parameters.
        """

        return PoolConfig(
            pool_size=self.db_pool_size,
            max_overflow=self.db_max_overflow,
            pool_recycle=self.db_pool_recycle,
        )
