"""Import PDF attachments: hash, store, and create immutable version records.

The importer is the single entry point for adding a PDF (or any binary
attachment) to a literature record.  It ensures that the raw bytes are
content-addressed in the artifact store *before* a version row is written
to the database, so the ``content_hash`` always resolves to a real file.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from vet_manuscript_lab.infrastructure.artifacts.store import (
    LocalArtifactStore,
    StoredPayload,
)
from vet_manuscript_lab.infrastructure.database.literature import (
    AttachmentInput,
    LiteratureRepository,
)
from vet_manuscript_lab.infrastructure.database.models import AttachmentVersionRecord


@dataclass(frozen=True, slots=True)
class ImportResult:
    """Outcome of importing a single attachment."""

    content_hash: str
    attachment_version_id: str
    uri: str
    media_type: str
    size_bytes: int
    version: int
    is_new: bool


class DocumentImporter:
    """Import PDF bytes into the artifact store and database.

    Parameters
    ----------
    artifact_store
        Content-addressed store for raw attachment bytes.
    repository
        Literature repository for creating attachment version records.
    """

    def __init__(
        self,
        artifact_store: LocalArtifactStore,
        repository: LiteratureRepository,
    ) -> None:
        self._store = artifact_store
        self._repository = repository

    def import_bytes(
        self,
        *,
        project_id: str,
        literature_record_id: str,
        attachment_key: str,
        pdf_bytes: bytes,
        media_type: str = "application/pdf",
        run_id: str | None = None,
    ) -> ImportResult:
        """Store *pdf_bytes* and create an immutable ``AttachmentVersion``.

        If the same content hash already exists on this literature record,
        the existing version is returned (idempotent import).
        """

        if not pdf_bytes:
            raise ValueError("Cannot import an empty attachment")

        stored = self._store.put(pdf_bytes)
        existing = self._find_by_hash(literature_record_id, stored.content_hash)
        if existing is not None:
            return ImportResult(
                content_hash=existing.content_hash,
                attachment_version_id=existing.id,
                uri=existing.uri,
                media_type=existing.media_type,
                size_bytes=stored.size_bytes,
                version=existing.version,
                is_new=False,
            )

        record = self._repository.create_attachment_version(
            project_id=project_id,
            data=AttachmentInput(
                literature_record_id=literature_record_id,
                attachment_key=attachment_key,
                content_hash=stored.content_hash,
                uri=stored.uri,
                media_type=media_type,
                created_by_run_id=run_id,
            ),
        )
        return self._to_result(record, stored, is_new=True)

    def import_from_path(
        self,
        *,
        project_id: str,
        literature_record_id: str,
        attachment_key: str,
        file_path: Path,
        media_type: str = "application/pdf",
        run_id: str | None = None,
    ) -> ImportResult:
        """Import a file from the local filesystem."""

        pdf_bytes = file_path.read_bytes()
        return self.import_bytes(
            project_id=project_id,
            literature_record_id=literature_record_id,
            attachment_key=attachment_key,
            pdf_bytes=pdf_bytes,
            media_type=media_type,
            run_id=run_id,
        )

    def verify(self, content_hash: str) -> bool:
        """Verify that stored bytes still match the recorded hash."""

        return self._store.verify(content_hash)

    def get_bytes(self, content_hash: str) -> bytes:
        """Retrieve the raw bytes for a previously-imported attachment."""

        return self._store.get(content_hash)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _find_by_hash(
        self, literature_record_id: str, content_hash: str
    ) -> AttachmentVersionRecord | None:
        """Return the existing attachment version for *content_hash*, if any."""

        attachments = self._repository.list_attachment_versions(literature_record_id)
        for att in attachments:
            if att.content_hash == content_hash:
                return att
        return None

    @staticmethod
    def _to_result(
        record: AttachmentVersionRecord,
        stored: StoredPayload,
        *,
        is_new: bool,
    ) -> ImportResult:
        return ImportResult(
            content_hash=record.content_hash,
            attachment_version_id=record.id,
            uri=record.uri,
            media_type=record.media_type,
            size_bytes=stored.size_bytes,
            version=record.version,
            is_new=is_new,
        )


__all__ = ["DocumentImporter", "ImportResult"]
