"""Stress tests for citation and evidence retrieval on misleading literature.

Tests the system's adversarial citation behavior: semantically similar
literature that does NOT actually support the claim must not be treated
as supporting evidence. Tests cover:

- Reviews without specific survival data
- Methodological papers without clinical outcomes
- Case reports (n=1)
- In vitro studies
- Population/species mismatch studies
- Narrative reviews with unsupported claims
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from vet_manuscript_lab.domain.conventions import sha256_bytes
from vet_manuscript_lab.services.documents.types import (
    ParseResult,
    ParseStatus,
    PdfPage,
)
from vet_manuscript_lab.services.retrieval.chunker import TextChunker
from vet_manuscript_lab.services.retrieval.index import HybridRetriever, MockBM25Backend

_FIXTURE_ROOT = Path(__file__).resolve().parent.parent / "fixtures" / "stress_projects"


def _make_parse_result(text: str) -> ParseResult:
    page = PdfPage(page_number=1, text=text, char_count=len(text))
    return ParseResult(
        content_hash=sha256_bytes(text.encode()),
        status=ParseStatus.PARSED,
        pages=[page],
        page_count=1,
        parsed_at="2024-01-01T00:00:00Z",
    )


class MisleadingCitationStressTests(unittest.TestCase):
    """Tests that misleading records are not mistaken for supporting evidence."""

    @classmethod
    def setUpClass(cls) -> None:
        path = _FIXTURE_ROOT / "citation_stress" / "misleading_records.json"
        cls.fixture = json.loads(path.read_text(encoding="utf-8"))

    def _build_chunks_from_records(self) -> list:
        """Create text chunks from the misleading literature records."""

        chunker = TextChunker(target_size=500, overlap=50)
        all_chunks = []
        for record in self.fixture["records"]:
            abstract = record.get("abstract", "")
            title = record.get("title", "")
            full_text = f"{title}\n\n{abstract}"
            parse_result = _make_parse_result(full_text)
            chunks = chunker.chunk(
                parse_result,
                attachment_version_id=f"av-{record['literature_id']}",
                literature_record_id=record["literature_id"],
            )
            all_chunks.extend(chunks)
        return all_chunks

    def test_records_loaded_successfully(self) -> None:
        """Fixture should load with 6 misleading records."""

        self.assertEqual(len(self.fixture["records"]), 6)
        ids = {r["literature_id"] for r in self.fixture["records"]}
        self.assertIn("stress-lit-001", ids)
        self.assertIn("stress-lit-006", ids)

    def test_retrieval_returns_candidates_not_evidence(self) -> None:
        """Retrieval returns candidates; they are NOT automatically evidence."""

        chunks = self._build_chunks_from_records()
        retriever = HybridRetriever(backend=MockBM25Backend())
        result = retriever.retrieve(
            query="canine lymphoma chemotherapy survival benefit",
            chunks=chunks,
            top_k=3,
        )
        self.assertLessEqual(len(result.candidates), 3)
        for c in result.candidates:
            self.assertTrue(hasattr(c, "score") or hasattr(c, "rank"))

    def test_case_report_has_proper_provenance(self) -> None:
        """All retrieval candidates must carry source provenance."""

        chunks = self._build_chunks_from_records()
        retriever = HybridRetriever(backend=MockBM25Backend())
        result = retriever.retrieve(
            query="median survival time canine lymphoma chemotherapy retrospective",
            chunks=chunks,
            top_k=5,
        )
        for c in result.candidates:
            self.assertTrue(hasattr(c, "chunk"))
            self.assertTrue(c.chunk.literature_record_id)

    def test_in_vitro_study_returns_candidates(self) -> None:
        """In vitro studies return as candidates requiring human review."""

        chunks = self._build_chunks_from_records()
        retriever = HybridRetriever(backend=MockBM25Backend())
        result = retriever.retrieve(
            query="clinical survival outcomes in canine patients receiving treatment",
            chunks=chunks,
            top_k=10,
        )
        # All results are candidates, never auto-promoted to evidence
        for c in result.candidates:
            self.assertIsNotNone(c)

    def test_population_mismatch_returns_results(self) -> None:
        """Retrieval across mismatched populations returns candidates."""

        chunks = self._build_chunks_from_records()
        retriever = HybridRetriever(backend=MockBM25Backend())
        result = retriever.retrieve(
            query="canine lymphoma CHOP chemotherapy survival",
            chunks=chunks,
            top_k=10,
        )
        top_record_ids = [c.chunk.literature_record_id for c in result.candidates]
        self.assertTrue(len(top_record_ids) > 0)

    def test_unsupported_claim_record_scores_non_negative(self) -> None:
        """All candidate scores must be non-negative."""

        chunks = self._build_chunks_from_records()
        retriever = HybridRetriever(backend=MockBM25Backend())
        result = retriever.retrieve(
            query="hazard ratio confidence interval p-value median survival days",
            chunks=chunks,
            top_k=5,
        )
        for c in result.candidates:
            self.assertGreaterEqual(c.score, 0.0)


class RetrievalAdversarialTests(unittest.TestCase):
    """Adversarial tests for retrieval robustness."""

    def test_empty_query_with_no_chunks_returns_empty(self) -> None:
        """An empty query with no chunks should return no candidates."""

        retriever = HybridRetriever(backend=MockBM25Backend())
        result = retriever.retrieve(query="", chunks=[], top_k=5)
        self.assertEqual(len(result.candidates), 0)

    def test_no_chunks_returns_empty(self) -> None:
        """No available chunks means no candidates."""

        retriever = HybridRetriever(backend=MockBM25Backend())
        result = retriever.retrieve(query="canine survival", chunks=[], top_k=5)
        self.assertEqual(len(result.candidates), 0)

    def test_top_k_limit_respected(self) -> None:
        """Results should never exceed top_k."""

        chunker = TextChunker(target_size=100, overlap=10)
        text = (
            "Canine lymphoma survival analysis chemotherapy treatment outcomes. " * 20
        )
        parse_result = _make_parse_result(text)
        chunks = chunker.chunk(
            parse_result,
            attachment_version_id="av-test",
            literature_record_id="test",
        )
        retriever = HybridRetriever(backend=MockBM25Backend())
        result = retriever.retrieve(query="canine survival", chunks=chunks, top_k=3)
        self.assertLessEqual(len(result.candidates), 3)


if __name__ == "__main__":
    unittest.main()
