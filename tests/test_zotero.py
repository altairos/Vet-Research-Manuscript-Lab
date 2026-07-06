"""Tests for Zotero integration: types, mapper, client, and synchroniser.

All tests use deterministic mock backends and fixture payloads; no network
access is required.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any

from vet_manuscript_lab.infrastructure.database import create_database
from vet_manuscript_lab.infrastructure.database.literature import LiteratureRepository
from vet_manuscript_lab.infrastructure.database.repository import (
    FoundationRepository,
    ProjectInput,
)
from vet_manuscript_lab.services.zotero.client import (
    ZoteroClient,
    ZoteroConfig,
)
from vet_manuscript_lab.services.zotero.mapper import (
    ZoteroMappingError,
    map_zotero_item,
)
from vet_manuscript_lab.services.zotero.sync import (
    ZoteroSynchroniser,
)
from vet_manuscript_lab.services.zotero.types import (
    parse_zotero_attachment,
    parse_zotero_item,
)

# ---------------------------------------------------------------------------
# Fixture payloads mimicking pyzotero API responses
# ---------------------------------------------------------------------------

ITEM_CKD = {
    "key": "CKDKEY01",
    "version": 100,
    "library": {"id": "12345"},
    "data": {
        "itemType": "journalArticle",
        "title": "Canine CKD progression in referral hospitals",
        "DOI": "10.1000/canine-ckd",
        "date": "2024-03-15",
        "publicationTitle": "J Vet Intern Med",
        "creators": [
            {"firstName": "Jane", "lastName": "Smith", "creatorType": "author"}
        ],
        "extra": "PMID: 12345678",
        "citationKey": "smith2024ckd",
    },
}

ITEM_BOVINE = {
    "key": "BOVKEY02",
    "version": 110,
    "library": {"id": "12345"},
    "data": {
        "itemType": "journalArticle",
        "title": "Bovine mastitis antibiotic resistance",
        "DOI": "10.1000/bovine-mastitis",
        "date": "2022",
        "publicationTitle": "J Dairy Sci",
    },
}

ITEM_NOTE = {
    "key": "NOTEKEY03",
    "version": 115,
    "data": {
        "itemType": "note",
        "note": "<p>This is a standalone note, not a reference.</p>",
    },
}

ITEM_NO_TITLE = {
    "key": "NOTITLE04",
    "version": 120,
    "data": {
        "itemType": "journalArticle",
        "DOI": "10.1000/no-title",
    },
}

ATTACHMENT_PDF = {
    "key": "ATTKEY01",
    "version": 200,
    "data": {
        "itemType": "attachment",
        "linkMode": "imported_file",
        "filename": "smith2024.pdf",
        "contentType": "application/pdf",
        "md5": "abc123",
        "size": 1048576,
    },
}


class _MockBackend:
    """In-memory implementation of the ``ZoteroBackend`` protocol."""

    def __init__(
        self,
        *,
        items: list[dict[str, Any]],
        children: dict[str, list[dict[str, Any]]] | None = None,
        version: int = 0,
    ) -> None:
        self._items = items
        self._children = children or {}
        self._version = version

    def fetch_items(self, since_version: int) -> list[dict[str, Any]]:
        if since_version:
            return [
                item for item in self._items if item.get("version", 0) > since_version
            ]
        return list(self._items)

    def fetch_children(self, item_key: str) -> list[dict[str, Any]]:
        return list(self._children.get(item_key, []))

    def last_modified_version(self) -> int:
        return self._version


# ---------------------------------------------------------------------------
# Type parser tests
# ---------------------------------------------------------------------------


class ZoteroTypeParserTests(unittest.TestCase):
    def test_parse_item_extracts_core_fields(self) -> None:
        item = parse_zotero_item(ITEM_CKD, library_id="12345")
        self.assertEqual(item.item_key, "CKDKEY01")
        self.assertEqual(item.title, "Canine CKD progression in referral hospitals")
        self.assertEqual(item.doi, "10.1000/canine-ckd")
        self.assertEqual(item.pmid, "12345678")
        self.assertEqual(item.publication_year, 2024)
        self.assertEqual(item.journal, "J Vet Intern Med")
        self.assertEqual(item.bibtex_key, "smith2024ckd")
        self.assertEqual(item.library_id, "12345")
        self.assertEqual(item.version, 100)

    def test_parse_item_handles_year_only_date(self) -> None:
        item = parse_zotero_item(ITEM_BOVINE)
        self.assertEqual(item.publication_year, 2022)

    def test_parse_item_extracts_pmid_from_extra_field(self) -> None:
        raw = {
            "key": "K1",
            "data": {
                "itemType": "journalArticle",
                "title": "Test",
                "extra": "Some note\nPMID: 99998888\nAnother line",
            },
        }
        item = parse_zotero_item(raw)
        self.assertEqual(item.pmid, "99998888")

    def test_parse_item_returns_none_pmid_when_absent(self) -> None:
        item = parse_zotero_item(ITEM_BOVINE)
        self.assertIsNone(item.pmid)

    def test_parse_attachment_extracts_metadata(self) -> None:
        att = parse_zotero_attachment(ATTACHMENT_PDF)
        self.assertEqual(att.attachment_key, "ATTKEY01")
        self.assertEqual(att.filename, "smith2024.pdf")
        self.assertEqual(att.content_type, "application/pdf")
        self.assertEqual(att.md5_hash, "abc123")
        self.assertEqual(att.size_bytes, 1048576)


# ---------------------------------------------------------------------------
# Mapper tests
# ---------------------------------------------------------------------------


class ZoteroMapperTests(unittest.TestCase):
    def test_map_item_to_literature_input(self) -> None:
        item = parse_zotero_item(ITEM_CKD)
        result = map_zotero_item(item)
        self.assertEqual(result.title, "Canine CKD progression in referral hospitals")
        self.assertEqual(result.doi, "10.1000/canine-ckd")
        self.assertEqual(result.pmid, "12345678")
        self.assertEqual(result.zotero_item_key, "CKDKEY01")
        self.assertEqual(result.zotero_library_id, "12345")
        self.assertEqual(result.bibtex_key, "smith2024ckd")
        self.assertEqual(result.publication_year, 2024)
        self.assertEqual(result.journal, "J Vet Intern Med")
        self.assertIn("zotero_item_type", result.metadata_json or {})

    def test_map_item_strips_doi_url_prefix(self) -> None:
        raw = {
            "key": "K1",
            "data": {
                "itemType": "journalArticle",
                "title": "Test",
                "DOI": "https://doi.org/10.1000/url-prefix",
            },
        }
        item = parse_zotero_item(raw)
        result = map_zotero_item(item)
        self.assertEqual(result.doi, "10.1000/url-prefix")

    def test_map_item_raises_on_missing_title(self) -> None:
        item = parse_zotero_item(ITEM_NO_TITLE)
        with self.assertRaises(ZoteroMappingError):
            map_zotero_item(item)


# ---------------------------------------------------------------------------
# Client tests
# ---------------------------------------------------------------------------


class ZoteroClientTests(unittest.TestCase):
    def test_fetch_items_returns_parsed_items(self) -> None:
        backend = _MockBackend(items=[ITEM_CKD, ITEM_BOVINE], version=500)
        client = ZoteroClient(
            ZoteroConfig(library_id="12345", api_key="key"),
            backend=backend,
        )
        items = client.fetch_items()
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].title, "Canine CKD progression in referral hospitals")

    def test_fetch_items_since_version_filters(self) -> None:
        backend = _MockBackend(items=[ITEM_CKD, ITEM_BOVINE], version=500)
        client = ZoteroClient(
            ZoteroConfig(library_id="12345", api_key="key"),
            backend=backend,
        )
        # version 100 → CKD (v100) filtered out, BOVINE (v110) also filtered
        items = client.fetch_items(since_version=105)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].item_key, "BOVKEY02")

    def test_fetch_attachments_returns_only_file_attachments(self) -> None:
        children = {
            "CKDKEY01": [ATTACHMENT_PDF, ITEM_NOTE],
        }
        backend = _MockBackend(items=[], children=children, version=500)
        client = ZoteroClient(
            ZoteroConfig(library_id="12345", api_key="key"),
            backend=backend,
        )
        attachments = client.fetch_attachments("CKDKEY01")
        self.assertEqual(len(attachments), 1)
        self.assertEqual(attachments[0].attachment_key, "ATTKEY01")

    def test_latest_version(self) -> None:
        backend = _MockBackend(items=[], version=999)
        client = ZoteroClient(
            ZoteroConfig(library_id="12345", api_key="key"),
            backend=backend,
        )
        self.assertEqual(client.latest_version(), 999)


# ---------------------------------------------------------------------------
# Synchroniser tests
# ---------------------------------------------------------------------------


class ZoteroSynchroniserTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.database = create_database(f"sqlite:///{root / 'zotero.sqlite'}")
        self.database.create_schema()

        self.foundation = FoundationRepository(self.database.sessions)
        self.repo = LiteratureRepository(self.database.sessions)
        self.project = self.foundation.create_project(
            ProjectInput(
                title="Zotero Sync Test",
                study_type="retrospective_observational_clinical_study",
                species_scope=["canine"],
                owner_id="owner-1",
            )
        )

    def tearDown(self) -> None:
        self.database.engine.dispose()

    def _make_synchroniser(
        self, items: list[dict[str, Any]], *, version: int = 500
    ) -> ZoteroSynchroniser:
        backend = _MockBackend(items=items, version=version)
        client = ZoteroClient(
            ZoteroConfig(library_id="12345", api_key="key"),
            backend=backend,
        )
        return ZoteroSynchroniser(client, self.repo)

    def test_sync_creates_records_for_valid_items(self) -> None:
        sync = self._make_synchroniser([ITEM_CKD, ITEM_BOVINE])
        result = sync.sync_library(project_id=self.project.id)
        self.assertEqual(result.fetched, 2)
        self.assertEqual(result.created, 2)
        self.assertEqual(result.skipped, 0)
        self.assertEqual(result.latest_version, 500)
        self.assertEqual(len(result.created_records), 2)

        records = self.repo.list_literature_records(self.project.id)
        self.assertEqual(len(records), 2)

    def test_sync_skips_notes_and_attachments(self) -> None:
        sync = self._make_synchroniser([ITEM_CKD, ITEM_NOTE])
        result = sync.sync_library(project_id=self.project.id)
        self.assertEqual(result.created, 1)
        self.assertEqual(result.skipped, 1)

    def test_sync_handles_duplicate_doi_gracefully(self) -> None:
        sync = self._make_synchroniser([ITEM_CKD])
        sync.sync_library(project_id=self.project.id)

        # Second sync with the same DOI should skip, not crash.
        sync2 = self._make_synchroniser([ITEM_CKD])
        result2 = sync2.sync_library(project_id=self.project.id)
        self.assertEqual(result2.created, 0)
        self.assertEqual(result2.skipped, 1)
        self.assertTrue(any("Duplicate" in e for e in result2.errors))

    def test_sync_handles_items_without_title(self) -> None:
        sync = self._make_synchroniser([ITEM_NO_TITLE])
        result = sync.sync_library(project_id=self.project.id)
        self.assertEqual(result.created, 0)
        self.assertEqual(result.skipped, 1)
        self.assertTrue(any("no title" in e for e in result.errors))

    def test_incremental_sync_uses_since_version(self) -> None:
        sync = self._make_synchroniser([ITEM_CKD, ITEM_BOVINE], version=500)
        # Full sync
        sync.sync_library(project_id=self.project.id)
        # Incremental: nothing new since version 500
        result2 = sync.sync_library(project_id=self.project.id, since_version=500)
        self.assertEqual(result2.fetched, 0)
        self.assertEqual(result2.created, 0)


if __name__ == "__main__":
    unittest.main()
