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

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            environment=os.getenv("VET_LAB_ENV", "development"),
            database_url=os.getenv("VET_LAB_DATABASE_URL", "sqlite:///./vet_lab.db"),
            artifact_root=Path(os.getenv("VET_LAB_ARTIFACT_ROOT", "./artifacts")),
            checkpoint_path=Path(
                os.getenv("VET_LAB_CHECKPOINT_PATH", "./artifacts/checkpoints.sqlite")
            ),
        )
