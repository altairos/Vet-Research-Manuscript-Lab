"""Incremental synchronisation between a Zotero library and the local database.

The synchroniser is read-only with respect to Zotero: it pulls items from the
remote library and persists them via ``LiteratureRepository``.  It tracks the
last-seen Zotero library version so that subsequent syncs only fetch new or
updated items.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from vet_manuscript_lab.domain.policies import PolicyViolation
from vet_manuscript_lab.infrastructure.database.literature import (
    LiteratureRepository,
)
from vet_manuscript_lab.infrastructure.database.models import LiteratureRecord
from vet_manuscript_lab.services.zotero.client import ZoteroClient
from vet_manuscript_lab.services.zotero.mapper import (
    ZoteroMappingError,
    map_zotero_item,
)
from vet_manuscript_lab.services.zotero.types import ZoteroItem


@dataclass(frozen=True, slots=True)
class SyncResult:
    """Outcome of a single Zotero synchronisation run."""

    fetched: int
    created: int
    skipped: int
    errors: list[str] = field(default_factory=list)
    latest_version: int = 0
    created_records: list[LiteratureRecord] = field(default_factory=list)


class ZoteroSynchroniser:
    """Orchestrates incremental Zotero → local database sync."""

    def __init__(
        self,
        client: ZoteroClient,
        repository: LiteratureRepository,
    ) -> None:
        self.client = client
        self.repository = repository

    def sync_library(
        self,
        *,
        project_id: str,
        since_version: int = 0,
        fetch_attachments: bool = False,
    ) -> SyncResult:
        """Fetch Zotero items and persist new ones to the local database.

        Parameters
        ----------
        project_id
            The project whose literature set is being synced.
        since_version
            The last-seen Zotero library version.  Only items updated after
            this version are fetched.
        fetch_attachments
            When ``True``, attachment metadata is fetched for each item and
            stored inside ``metadata_json`` on the created record.  This
            doubles the number of API calls and is deferred to the PDF import
            phase by default.
        """

        items = self.client.fetch_items(since_version=since_version)
        created: list[LiteratureRecord] = []
        skipped = 0
        errors: list[str] = []

        for item in items:
            if _should_skip(item):
                skipped += 1
                continue
            try:
                enriched = (
                    self._enrich_with_attachments(item) if fetch_attachments else item
                )
                literature_input = map_zotero_item(enriched)
                record = self.repository.create_literature_record(
                    project_id=project_id, data=literature_input
                )
                created.append(record)
            except ZoteroMappingError as exc:
                errors.append(str(exc))
                skipped += 1
            except PolicyViolation as exc:
                # Duplicate DOI/PMID — the item is already in the project.
                errors.append(str(exc))
                skipped += 1

        latest = self.client.latest_version()
        return SyncResult(
            fetched=len(items),
            created=len(created),
            skipped=skipped,
            errors=errors,
            latest_version=latest,
            created_records=created,
        )

    def _enrich_with_attachments(self, item: ZoteroItem) -> ZoteroItem:
        """Return a copy of *item* with its attachment metadata populated."""

        attachments = self.client.fetch_attachments(item.item_key)
        return replace(item, attachments=attachments)


def _should_skip(item: ZoteroItem) -> bool:
    """Skip attachment-only entries, notes, and standalone annotations."""

    return item.item_type in {"attachment", "note", "annotation"}


__all__ = ["SyncResult", "ZoteroSynchroniser"]
