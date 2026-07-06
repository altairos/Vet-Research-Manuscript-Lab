"""Type definitions for the export service layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class ExportFormat(StrEnum):
    """Supported export formats."""

    DOCX = "docx"
    PDF = "pdf"
    QMD = "qmd"


@dataclass(frozen=True, slots=True)
class ExportComponent:
    """A single file component in the export package."""

    role: str
    filename: str
    content: str
    content_hash: str
    media_type: str = "text/plain"


@dataclass(frozen=True, slots=True)
class ExportManifest:
    """Manifest describing all artifact versions in the export package."""

    project_id: str
    sign_off_id: str
    artifact_versions: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    ai_usage: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ExportResult:
    """Complete output from the export generator."""

    manifest: ExportManifest
    components: tuple[ExportComponent, ...]
    package_hash: str
    package_uri: str


__all__ = [
    "ExportComponent",
    "ExportFormat",
    "ExportManifest",
    "ExportResult",
]
