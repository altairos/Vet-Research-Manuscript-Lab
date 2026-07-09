"""Stress tests for PDF text extraction and chunking on messy inputs.

Tests the system's ability to handle:
- Double-column layouts with intermixed headers/footers
- Scanned/image-based content with garbled OCR output
- Cross-page tables with continuation markers

Each test verifies that the system either produces correct output or
correctly flags the input for human review (fail-closed behaviour).
"""

from __future__ import annotations

import unittest
from pathlib import Path

from vet_manuscript_lab.domain.conventions import sha256_bytes
from vet_manuscript_lab.services.documents.parser import PdfParser
from vet_manuscript_lab.services.documents.types import (
    ParseResult,
    ParseStatus,
    PdfPage,
)
from vet_manuscript_lab.services.retrieval.chunker import TextChunker

_FIXTURE_ROOT = Path(__file__).resolve().parent.parent / "fixtures" / "stress_projects"


def _make_parse_result(text: str, *, page_count: int = 1) -> ParseResult:
    """Build a ParseResult from a single text blob."""

    pages = [
        PdfPage(page_number=i + 1, text=text, char_count=len(text))
        for i in range(page_count)
    ]
    return ParseResult(
        content_hash=sha256_bytes(text.encode()),
        status=ParseStatus.PARSED,
        pages=pages,
        page_count=page_count,
        parsed_at="2024-01-01T00:00:00Z",
    )


class DoubleColumnStressTests(unittest.TestCase):
    """Tests chunking of double-column text with intermixed page furniture."""

    def setUp(self) -> None:
        self.text = (
            _FIXTURE_ROOT / "pdf_stress" / "double_column_sample.txt"
        ).read_text(encoding="utf-8")
        self.chunker = TextChunker(target_size=300, overlap=30)
        self.parse_result = _make_parse_result(self.text)

    def test_produces_non_empty_chunks(self) -> None:
        """Double-column text must produce at least some chunks."""

        chunks = self.chunker.chunk(
            self.parse_result,
            attachment_version_id="av-001",
            literature_record_id="stress-001",
        )
        self.assertGreater(len(chunks), 0)

    def test_chunks_contain_section_detection(self) -> None:
        """Section headings should be detected in at least some chunks."""

        chunks = self.chunker.chunk(
            self.parse_result,
            attachment_version_id="av-001",
            literature_record_id="stress-001",
        )
        sections_found = {c.section_label for c in chunks if c.section_label}
        self.assertTrue(
            len(sections_found) > 0,
            "No sections detected; expected at least one from: "
            "ABSTRACT, INTRODUCTION, MATERIALS AND METHODS",
        )

    def test_header_footer_does_not_crash(self) -> None:
        """Page headers/footers must not cause chunker errors."""

        chunks = self.chunker.chunk(
            self.parse_result,
            attachment_version_id="av-001",
            literature_record_id="stress-001",
        )
        for c in chunks:
            self.assertTrue(c.chunk_id)
            self.assertGreater(len(c.text), 0)

    def test_chunk_ids_are_deterministic(self) -> None:
        """Same input → same chunk IDs."""

        kwargs = dict(
            attachment_version_id="av-001",
            literature_record_id="stress-001",
        )
        chunks1 = self.chunker.chunk(self.parse_result, **kwargs)
        chunks2 = self.chunker.chunk(self.parse_result, **kwargs)
        self.assertEqual(
            [c.chunk_id for c in chunks1],
            [c.chunk_id for c in chunks2],
        )


class ScannedDocumentStressTests(unittest.TestCase):
    """Tests handling of scanned/image-based PDF content."""

    def setUp(self) -> None:
        self.text = (_FIXTURE_ROOT / "pdf_stress" / "scanned_sample.txt").read_text(
            encoding="utf-8"
        )

    def test_scanned_content_produces_sparse_chunks(self) -> None:
        """Scanned content should produce mostly non-alphabetic text."""

        parse_result = _make_parse_result(self.text)
        chunker = TextChunker(target_size=200, overlap=20)
        chunks = chunker.chunk(
            parse_result,
            attachment_version_id="av-002",
            literature_record_id="stress-002",
        )
        total_text = "".join(c.text for c in chunks)
        if total_text:
            alpha_ratio = sum(c.isalpha() for c in total_text) / len(total_text)
            self.assertLess(
                alpha_ratio,
                0.5,
                f"Expected mostly non-alpha characters, "
                f"got alpha_ratio={alpha_ratio:.2f}",
            )

    def test_pdf_parser_flags_scanned_content(self) -> None:
        """PdfParser should flag scanned content as needs_human_review."""

        class ScannedBackend:
            """Backend that returns very little text (simulates scanned PDF)."""

            def extract_pages(self, pdf_bytes: bytes) -> list[dict]:
                return [
                    {"page_number": 1, "text": ". . . .. . . ..", "char_count": 12},
                ]

        parser = PdfParser(backend=ScannedBackend(), max_retries=0)
        result = parser.parse(b"fake-scanned-pdf")
        self.assertIn(
            result.status,
            (ParseStatus.NEEDS_HUMAN_REVIEW, ParseStatus.FAILED),
        )


class CrossPageTableStressTests(unittest.TestCase):
    """Tests handling of tables that span multiple pages."""

    def setUp(self) -> None:
        self.text = (_FIXTURE_ROOT / "pdf_stress" / "cross_page_table.txt").read_text(
            encoding="utf-8"
        )
        self.parse_result = _make_parse_result(self.text)

    def test_table_content_is_extracted(self) -> None:
        """Statistical values from the table should survive chunking."""

        chunker = TextChunker(target_size=400, overlap=50)
        chunks = chunker.chunk(
            self.parse_result,
            attachment_version_id="av-003",
            literature_record_id="stress-003",
        )
        all_text = " ".join(c.text for c in chunks)
        self.assertIn("1.05", all_text)
        self.assertIn("0.003", all_text)
        self.assertIn("hazard ratio", all_text.lower())

    def test_continuation_marker_preserved(self) -> None:
        """Cross-page continuation markers should not be lost."""

        chunker = TextChunker(target_size=500, overlap=50)
        chunks = chunker.chunk(
            self.parse_result,
            attachment_version_id="av-003",
            literature_record_id="stress-003",
        )
        all_text = " ".join(c.text for c in chunks)
        self.assertIn("continued", all_text.lower())


class EmptyPageStressTests(unittest.TestCase):
    """Tests handling of empty or near-empty pages."""

    def test_empty_pages_produce_no_chunks(self) -> None:
        """An empty ParseResult should produce no chunks."""

        parse_result = ParseResult(
            content_hash="empty",
            status=ParseStatus.PARSED,
            pages=[],
            page_count=0,
        )
        chunker = TextChunker()
        chunks = chunker.chunk(
            parse_result,
            attachment_version_id="av-004",
            literature_record_id="stress-004",
        )
        self.assertEqual(len(chunks), 0)

    def test_whitespace_only_page_produces_no_meaningful_chunks(self) -> None:
        """A page with only whitespace should produce no content chunks."""

        parse_result = _make_parse_result("   \n\n  \t  \n")
        chunker = TextChunker(target_size=200, overlap=20)
        chunks = chunker.chunk(
            parse_result,
            attachment_version_id="av-005",
            literature_record_id="stress-005",
        )
        for c in chunks:
            self.assertTrue(c.text.strip(), "Chunk should not be empty whitespace")


if __name__ == "__main__":
    unittest.main()
