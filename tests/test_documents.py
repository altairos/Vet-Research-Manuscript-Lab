"""Tests for PDF document import and text extraction.

All tests use deterministic mock backends; no real PDF files or PyMuPDF
calls are required.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any

from vet_manuscript_lab.infrastructure.artifacts.store import LocalArtifactStore
from vet_manuscript_lab.infrastructure.database import create_database
from vet_manuscript_lab.infrastructure.database.literature import (
    LiteratureInput,
    LiteratureRepository,
)
from vet_manuscript_lab.infrastructure.database.repository import (
    FoundationRepository,
    ProjectInput,
)
from vet_manuscript_lab.services.documents.importer import DocumentImporter
from vet_manuscript_lab.services.documents.parser import PdfParser
from vet_manuscript_lab.services.documents.types import ParseStatus

# ---------------------------------------------------------------------------
# Mock PDF parse backend
# ---------------------------------------------------------------------------


class MockPdfBackend:
    """Deterministic mock that returns predefined pages for given bytes."""

    def __init__(
        self,
        pages: list[dict[str, Any]] | None = None,
        error: str | None = None,
        fail_first: bool = False,
    ) -> None:
        self._pages = pages or []
        self._error = error
        self._fail_first = fail_first
        self._call_count = 0

    def extract_pages(self, pdf_bytes: bytes) -> list[dict[str, Any]]:
        self._call_count += 1
        if self._fail_first and self._call_count == 1:
            raise RuntimeError("Transient backend failure")
        if self._error:
            raise RuntimeError(self._error)
        return list(self._pages)


def _normal_pages() -> list[dict[str, Any]]:
    return [
        {
            "page_number": 1,
            "text": "This is the introduction of the paper. " * 5,
            "char_count": 170,
        },
        {
            "page_number": 2,
            "text": "Methods section with detailed experimental design. " * 5,
            "char_count": 205,
        },
        {
            "page_number": 3,
            "text": "Results show significant findings in canine patients. " * 5,
            "char_count": 209,
        },
    ]


def _scanned_pages() -> list[dict[str, Any]]:
    return [
        {"page_number": 1, "text": "", "char_count": 0},
        {"page_number": 2, "text": "  \n  ", "char_count": 5},
        {"page_number": 3, "text": "", "char_count": 0},
    ]


def _partial_scanned_pages() -> list[dict[str, Any]]:
    return [
        {
            "page_number": 1,
            "text": "Title page with abstract text " * 5,
            "char_count": 150,
        },
        {"page_number": 2, "text": "", "char_count": 0},
        {
            "page_number": 3,
            "text": "Discussion section with conclusions. " * 5,
            "char_count": 175,
        },
    ]


# ---------------------------------------------------------------------------
# Parser tests
# ---------------------------------------------------------------------------


class TestPdfParser(unittest.TestCase):
    """Unit tests for PdfParser with mock backends."""

    def test_parse_normal_pdf(self) -> None:
        backend = MockPdfBackend(_normal_pages())
        parser = PdfParser(backend=backend)
        result = parser.parse(b"fake-pdf-bytes")

        self.assertEqual(result.status, ParseStatus.PARSED)
        self.assertEqual(result.page_count, 3)
        self.assertFalse(result.needs_human_review)
        self.assertIsNone(result.review_reason)
        self.assertTrue(result.content_hash.startswith("sha256:"))

    def test_parse_all_scanned_pdf(self) -> None:
        backend = MockPdfBackend(_scanned_pages())
        parser = PdfParser(backend=backend)
        result = parser.parse(b"scanned-pdf")

        self.assertEqual(result.status, ParseStatus.NEEDS_HUMAN_REVIEW)
        self.assertTrue(result.needs_human_review)
        self.assertIsNotNone(result.review_reason)
        self.assertIn("scanned", result.review_reason.lower())

    def test_parse_partial_scanned_pdf(self) -> None:
        backend = MockPdfBackend(_partial_scanned_pages())
        parser = PdfParser(backend=backend)
        result = parser.parse(b"partial-scanned")

        self.assertEqual(result.status, ParseStatus.NEEDS_HUMAN_REVIEW)
        self.assertTrue(result.needs_human_review)
        self.assertIn("1 of 3", result.review_reason)

    def test_parse_failure_no_retry(self) -> None:
        backend = MockPdfBackend(error="Corrupted PDF structure")
        parser = PdfParser(backend=backend, max_retries=0)
        result = parser.parse(b"broken-pdf")

        self.assertEqual(result.status, ParseStatus.FAILED)
        self.assertIsNone(result.review_reason)
        self.assertIn("Corrupted", result.error_message or "")

    def test_parse_retry_success(self) -> None:
        backend = MockPdfBackend(_normal_pages(), fail_first=True)
        parser = PdfParser(backend=backend, max_retries=1)
        result = parser.parse(b"retry-pdf")

        self.assertEqual(result.status, ParseStatus.PARSED)
        self.assertEqual(result.page_count, 3)
        self.assertEqual(backend._call_count, 2)

    def test_parse_retry_exhausted(self) -> None:
        backend = MockPdfBackend(error="Permanent failure")
        parser = PdfParser(backend=backend, max_retries=2)
        result = parser.parse(b"always-fail")

        self.assertEqual(result.status, ParseStatus.FAILED)
        self.assertEqual(backend._call_count, 3)

    def test_content_hash_deterministic(self) -> None:
        backend1 = MockPdfBackend(_normal_pages())
        backend2 = MockPdfBackend(_normal_pages())
        parser1 = PdfParser(backend=backend1)
        parser2 = PdfParser(backend=backend2)

        result1 = parser1.parse(b"same-bytes")
        result2 = parser2.parse(b"same-bytes")

        self.assertEqual(result1.content_hash, result2.content_hash)

    def test_page_numbers_are_sequential(self) -> None:
        pages = _normal_pages()
        backend = MockPdfBackend(pages)
        parser = PdfParser(backend=backend)
        result = parser.parse(b"page-test")

        for i, page in enumerate(result.pages, start=1):
            self.assertEqual(page.page_number, i)


# ---------------------------------------------------------------------------
# Importer tests
# ---------------------------------------------------------------------------


class TestDocumentImporter(unittest.TestCase):
    """Integration tests for DocumentImporter with real artifact store."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.root = Path(self._tmpdir.name)
        self.db = create_database(f"sqlite:///{self.root / 'test.db'}")
        self.db.create_schema()
        self.store = LocalArtifactStore(self.root / "artifacts")
        self.repo = LiteratureRepository(self.db.sessions)
        self.foundation_repo = FoundationRepository(self.db.sessions)
        self.importer = DocumentImporter(self.store, self.repo)

        self.project = self.foundation_repo.create_project(
            data=ProjectInput(
                title="Test Project",
                study_type="systematic_review",
                species_scope=["canine", "feline"],
                owner_id="test-owner",
            )
        )
        self.literature = self.repo.create_literature_record(
            project_id=self.project.id,
            data=LiteratureInput(
                title="Test Article",
                doi="10.1000/test",
            ),
        )

    def tearDown(self) -> None:
        self.db.engine.dispose()

    def test_import_bytes_creates_version(self) -> None:
        pdf_bytes = b"%PDF-1.4 fake content for testing"
        result = self.importer.import_bytes(
            project_id=self.project.id,
            literature_record_id=self.literature.id,
            attachment_key="pdf-001",
            pdf_bytes=pdf_bytes,
        )

        self.assertTrue(result.is_new)
        self.assertEqual(result.version, 1)
        self.assertTrue(result.content_hash.startswith("sha256:"))
        self.assertTrue(result.uri.startswith("file:///"))
        self.assertEqual(result.media_type, "application/pdf")
        self.assertGreater(result.size_bytes, 0)

    def test_import_is_idempotent(self) -> None:
        pdf_bytes = b"%PDF-1.4 same content"
        first = self.importer.import_bytes(
            project_id=self.project.id,
            literature_record_id=self.literature.id,
            attachment_key="pdf-001",
            pdf_bytes=pdf_bytes,
        )
        second = self.importer.import_bytes(
            project_id=self.project.id,
            literature_record_id=self.literature.id,
            attachment_key="pdf-001",
            pdf_bytes=pdf_bytes,
        )

        self.assertTrue(first.is_new)
        self.assertFalse(second.is_new)
        self.assertEqual(first.attachment_version_id, second.attachment_version_id)
        self.assertEqual(first.version, second.version)
        self.assertEqual(first.content_hash, second.content_hash)

    def test_import_different_version_increments(self) -> None:
        v1 = self.importer.import_bytes(
            project_id=self.project.id,
            literature_record_id=self.literature.id,
            attachment_key="pdf-001",
            pdf_bytes=b"version one content",
        )
        v2 = self.importer.import_bytes(
            project_id=self.project.id,
            literature_record_id=self.literature.id,
            attachment_key="pdf-001",
            pdf_bytes=b"version two content is different",
        )

        self.assertEqual(v1.version, 1)
        self.assertEqual(v2.version, 2)
        self.assertNotEqual(v1.content_hash, v2.content_hash)

    def test_verify_after_import(self) -> None:
        pdf_bytes = b"%PDF-1.4 verification test"
        result = self.importer.import_bytes(
            project_id=self.project.id,
            literature_record_id=self.literature.id,
            attachment_key="pdf-001",
            pdf_bytes=pdf_bytes,
        )

        self.assertTrue(self.importer.verify(result.content_hash))
        self.assertFalse(self.importer.verify("sha256:" + "0" * 64))

    def test_get_bytes_after_import(self) -> None:
        pdf_bytes = b"%PDF-1.4 retrieval test"
        result = self.importer.import_bytes(
            project_id=self.project.id,
            literature_record_id=self.literature.id,
            attachment_key="pdf-001",
            pdf_bytes=pdf_bytes,
        )

        retrieved = self.importer.get_bytes(result.content_hash)
        self.assertEqual(retrieved, pdf_bytes)

    def test_import_from_path(self) -> None:
        pdf_path = self.root / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 from path")

        result = self.importer.import_from_path(
            project_id=self.project.id,
            literature_record_id=self.literature.id,
            attachment_key="pdf-path",
            file_path=pdf_path,
        )

        self.assertTrue(result.is_new)
        self.assertEqual(result.version, 1)

    def test_import_empty_bytes_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.importer.import_bytes(
                project_id=self.project.id,
                literature_record_id=self.literature.id,
                attachment_key="pdf-empty",
                pdf_bytes=b"",
            )


# ---------------------------------------------------------------------------
# Integration: parser + importer round-trip
# ---------------------------------------------------------------------------


class TestParseAfterImport(unittest.TestCase):
    """Verify that parsed content matches imported content."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.root = Path(self._tmpdir.name)
        self.db = create_database(f"sqlite:///{self.root / 'test.db'}")
        self.db.create_schema()
        self.store = LocalArtifactStore(self.root / "artifacts")
        self.repo = LiteratureRepository(self.db.sessions)
        self.foundation_repo = FoundationRepository(self.db.sessions)
        self.importer = DocumentImporter(self.store, self.repo)

        self.project = self.foundation_repo.create_project(
            data=ProjectInput(
                title="Round-Trip Project",
                study_type="systematic_review",
                species_scope=["canine"],
                owner_id="test-owner",
            )
        )
        self.literature = self.repo.create_literature_record(
            project_id=self.project.id,
            data=LiteratureInput(title="Round-Trip Article"),
        )

    def tearDown(self) -> None:
        self.db.engine.dispose()

    def test_import_then_parse(self) -> None:
        pdf_bytes = b"%PDF-1.4 some content"
        imported = self.importer.import_bytes(
            project_id=self.project.id,
            literature_record_id=self.literature.id,
            attachment_key="pdf-001",
            pdf_bytes=pdf_bytes,
        )

        # Retrieve bytes and parse with mock backend
        retrieved = self.importer.get_bytes(imported.content_hash)
        self.assertEqual(retrieved, pdf_bytes)

        backend = MockPdfBackend(_normal_pages())
        parser = PdfParser(backend=backend)
        result = parser.parse(retrieved)

        self.assertEqual(result.status, ParseStatus.PARSED)
        self.assertEqual(result.content_hash, imported.content_hash)


if __name__ == "__main__":
    unittest.main()
