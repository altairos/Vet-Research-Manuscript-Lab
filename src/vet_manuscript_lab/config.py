"""Runtime configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Settings:
    environment: str
    database_url: str
    artifact_root: Path
    checkpoint_path: Path
    zotero_api_key: str
    zotero_library_id: str
    zotero_library_type: str

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
        )

    @property
    def zotero_enabled(self) -> bool:
        """True when both API key and library id are configured."""

        return bool(self.zotero_api_key.strip() and self.zotero_library_id.strip())
