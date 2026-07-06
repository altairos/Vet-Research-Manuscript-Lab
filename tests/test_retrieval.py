"""Tests for text chunking and hybrid retrieval.

All tests use deterministic mock backends; no LlamaIndex or network
access is required.
"""

from __future__ import annotations

import unittest

from vet_manuscript_lab.services.documents.types import (
    ParseResult,
    ParseStatus,
    PdfPage,
)
from vet_manuscript_lab.services.retrieval.chunker import TextChunker
from vet_manuscript_lab.services.retrieval.index import (
    HybridRetriever,
    MockBM25Backend,
    RetrievalCandidate,
    RetrievalResult,
)
from vet_manuscript_lab.services.retrieval.types import TextChunk

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _make_pages() -> list[PdfPage]:
    return [
        PdfPage(
            page_number=1,
            text=(
                "Abstract\n\n"
                "This study examines canine chronic kidney disease "
                "progression in referral hospitals.\n\n"
                "Introduction\n\n"
                "Chronic kidney disease is a common condition in dogs "
                "and cats. The progression varies by breed and age. "
                "Early detection is critical for management."
            ),
            char_count=250,
        ),
        PdfPage(
            page_number=2,
            text=(
                "Methods\n\n"
                "We conducted a retrospective analysis of 200 canine "
                "patients diagnosed with CKD between 2018 and 2023. "
                "Blood work, urinalysis, and survival data were "
                "collected from medical records.\n\n"
                "Statistical analysis used Kaplan-Meier survival curves."
            ),
            char_count=250,
        ),
        PdfPage(
            page_number=3,
            text=(
                "Results\n\n"
                "The median survival time for canine CKD patients was "
                "18 months. Cats showed similar progression patterns. "
                "Bovine references appeared in the discussion only."
            ),
            char_count=170,
        ),
    ]


def _make_parse_result() -> ParseResult:
    return ParseResult(
        content_hash="sha256:abc123",
        status=ParseStatus.PARSED,
        pages=_make_pages(),
        page_count=3,
        parsed_at="2025-01-01T00:00:00Z",
    )


# ---------------------------------------------------------------------------
# Chunker tests
# ---------------------------------------------------------------------------


class TestTextChunker(unittest.TestCase):
    """Unit tests for TextChunker."""

    def setUp(self) -> None:
        self.parse_result = _make_parse_result()
        self.chunker = TextChunker(target_size=200, overlap=30)

    def test_chunk_produces_non_empty_list(self) -> None:
        chunks = self.chunker.chunk(
            self.parse_result,
            attachment_version_id="att-v1",
            literature_record_id="lit-1",
        )
        self.assertGreater(len(chunks), 0)

    def test_chunk_preserves_page_numbers(self) -> None:
        chunks = self.chunker.chunk(self.parse_result, attachment_version_id="att-v1")
        page_numbers = {c.page_number for c in chunks}
        self.assertIn(1, page_numbers)
        self.assertIn(2, page_numbers)
        self.assertIn(3, page_numbers)

    def test_chunk_preserves_attachment_version_id(self) -> None:
        chunks = self.chunker.chunk(self.parse_result, attachment_version_id="att-xyz")
        for chunk in chunks:
            self.assertEqual(chunk.attachment_version_id, "att-xyz")

    def test_chunk_preserves_literature_record_id(self) -> None:
        chunks = self.chunker.chunk(
            self.parse_result,
            attachment_version_id="att-v1",
            literature_record_id="lit-42",
        )
        for chunk in chunks:
            self.assertEqual(chunk.literature_record_id, "lit-42")

    def test_chunk_char_offsets_are_valid(self) -> None:
        chunks = self.chunker.chunk(self.parse_result, attachment_version_id="att-v1")
        for chunk in chunks:
            self.assertGreaterEqual(chunk.char_start, 0)
            self.assertGreater(chunk.char_end, chunk.char_start)
            self.assertEqual(chunk.char_count, chunk.char_end - chunk.char_start)

    def test_chunk_indices_are_sequential(self) -> None:
        chunks = self.chunker.chunk(self.parse_result, attachment_version_id="att-v1")
        for i, chunk in enumerate(chunks):
            self.assertEqual(chunk.chunk_index, i)

    def test_chunk_section_detection(self) -> None:
        chunks = self.chunker.chunk(self.parse_result, attachment_version_id="att-v1")
        sections = {c.section_label for c in chunks if c.section_label}
        # At least some standard sections should be detected
        self.assertTrue(
            any(s.lower() in {"abstract", "introduction"} for s in sections),
            f"Expected section labels in {sections}",
        )

    def test_chunk_ids_are_unique_and_deterministic(self) -> None:
        chunks1 = self.chunker.chunk(self.parse_result, attachment_version_id="att-v1")
        chunks2 = self.chunker.chunk(self.parse_result, attachment_version_id="att-v1")
        ids1 = [c.chunk_id for c in chunks1]
        ids2 = [c.chunk_id for c in chunks2]
        self.assertEqual(ids1, ids2)
        self.assertEqual(len(ids1), len(set(ids1)))

    def test_chunk_different_attachment_yields_different_ids(self) -> None:
        chunks_a = self.chunker.chunk(self.parse_result, attachment_version_id="att-a")
        chunks_b = self.chunker.chunk(self.parse_result, attachment_version_id="att-b")
        ids_a = {c.chunk_id for c in chunks_a}
        ids_b = {c.chunk_id for c in chunks_b}
        self.assertNotEqual(ids_a, ids_b)

    def test_chunk_empty_pages_returns_empty(self) -> None:
        empty = ParseResult(
            content_hash="sha256:empty",
            status=ParseStatus.PARSED,
            pages=[PdfPage(page_number=1, text="", char_count=0)],
            page_count=1,
            parsed_at="2025-01-01T00:00:00Z",
        )
        chunks = self.chunker.chunk(empty, attachment_version_id="att-v1")
        self.assertEqual(len(chunks), 0)

    def test_invalid_target_size_raises(self) -> None:
        with self.assertRaises(ValueError):
            TextChunker(target_size=0)

    def test_invalid_overlap_raises(self) -> None:
        with self.assertRaises(ValueError):
            TextChunker(target_size=100, overlap=100)


# ---------------------------------------------------------------------------
# Retriever tests
# ---------------------------------------------------------------------------


class TestMockBM25Backend(unittest.TestCase):
    """Unit tests for the default MockBM25Backend."""

    def setUp(self) -> None:
        self.chunks = [
            TextChunk(
                chunk_id="c1",
                text="Canine chronic kidney disease progression in dogs",
                page_number=1,
                char_start=0,
                char_end=50,
                chunk_index=0,
                attachment_version_id="att-1",
            ),
            TextChunk(
                chunk_id="c2",
                text="Feline hyperthyroidism treatment outcomes",
                page_number=2,
                char_start=0,
                char_end=40,
                chunk_index=1,
                attachment_version_id="att-1",
            ),
            TextChunk(
                chunk_id="c3",
                text="Bovine mastitis antibiotic resistance patterns",
                page_number=3,
                char_start=0,
                char_end=42,
                chunk_index=2,
                attachment_version_id="att-1",
            ),
        ]
        self.backend = MockBM25Backend()

    def test_search_returns_relevant_chunks(self) -> None:
        results = self.backend.search("canine kidney disease", self.chunks, top_k=3)
        self.assertGreater(len(results), 0)
        # The canine chunk should be the top hit
        top_idx = results[0][0]
        self.assertEqual(top_idx, 0)

    def test_search_returns_empty_for_no_match(self) -> None:
        results = self.backend.search("quantum physics", self.chunks, top_k=3)
        self.assertEqual(len(results), 0)

    def test_search_respects_top_k(self) -> None:
        results = self.backend.search("disease treatment", self.chunks, top_k=1)
        self.assertLessEqual(len(results), 1)

    def test_search_empty_chunks(self) -> None:
        results = self.backend.search("canine", [], top_k=5)
        self.assertEqual(len(results), 0)

    def test_scores_are_positive(self) -> None:
        results = self.backend.search("canine disease", self.chunks, top_k=3)
        for _, score, _ in results:
            self.assertGreater(score, 0.0)


class TestHybridRetriever(unittest.TestCase):
    """Unit tests for HybridRetriever with mock backends."""

    def setUp(self) -> None:
        self.chunks = [
            TextChunk(
                chunk_id="c1",
                text="Canine CKD progression study results show survival",
                page_number=1,
                char_start=0,
                char_end=50,
                chunk_index=0,
                attachment_version_id="att-1",
                section_label="Results",
            ),
            TextChunk(
                chunk_id="c2",
                text="Methods section retrospective analysis of patient data",
                page_number=2,
                char_start=0,
                char_end=50,
                chunk_index=1,
                attachment_version_id="att-1",
                section_label="Methods",
            ),
        ]

    def test_retrieve_default_backend(self) -> None:
        retriever = HybridRetriever()
        result = retriever.retrieve("canine CKD survival", self.chunks, top_k=2)

        self.assertIsInstance(result, RetrievalResult)
        self.assertEqual(result.query, "canine CKD survival")
        self.assertGreater(len(result.candidates), 0)
        self.assertEqual(result.total_chunks_searched, 2)

    def test_retrieve_ranks_relevant_first(self) -> None:
        retriever = HybridRetriever()
        result = retriever.retrieve("canine CKD survival", self.chunks, top_k=2)

        top = result.candidates[0]
        self.assertIsInstance(top, RetrievalCandidate)
        self.assertEqual(top.chunk.chunk_id, "c1")
        self.assertEqual(top.rank, 1)
        self.assertGreater(top.score, 0.0)

    def test_retrieve_empty_chunks(self) -> None:
        retriever = HybridRetriever()
        result = retriever.retrieve("query", [], top_k=5)

        self.assertEqual(len(result.candidates), 0)
        self.assertEqual(result.total_chunks_searched, 0)

    def test_retrieve_with_mock_backend(self) -> None:
        class CustomBackend:
            def search(
                self,
                query: str,
                chunks: list[TextChunk],
                *,
                top_k: int,
            ) -> list[tuple[int, float, str]]:
                return [(1, 0.95, "custom")]

        retriever = HybridRetriever(backend=CustomBackend())
        result = retriever.retrieve("test", self.chunks, top_k=1)

        self.assertEqual(len(result.candidates), 1)
        self.assertEqual(result.candidates[0].chunk.chunk_id, "c2")
        self.assertEqual(result.candidates[0].score, 0.95)
        self.assertEqual(result.candidates[0].source, "custom")

    def test_retrieve_with_reranker(self) -> None:
        class FixedBackend:
            def search(
                self,
                query: str,
                chunks: list[TextChunk],
                *,
                top_k: int,
            ) -> list[tuple[int, float, str]]:
                return [(0, 0.5, "bm25"), (1, 0.4, "bm25")]

        class SwapReranker:
            def rerank(
                self,
                query: str,
                chunks: list[TextChunk],
                *,
                top_k: int,
            ) -> list[tuple[int, float]]:
                return [(1, 0.99), (0, 0.88)]

        retriever = HybridRetriever(backend=FixedBackend(), reranker=SwapReranker())
        result = retriever.retrieve("test", self.chunks, top_k=2)

        self.assertEqual(len(result.candidates), 2)
        self.assertEqual(result.candidates[0].chunk.chunk_id, "c2")
        self.assertEqual(result.candidates[0].score, 0.99)
        self.assertEqual(result.candidates[0].source, "reranked")
        self.assertEqual(result.candidates[1].chunk.chunk_id, "c1")

    def test_retrieve_respects_top_k(self) -> None:
        retriever = HybridRetriever()
        result = retriever.retrieve("disease", self.chunks, top_k=1)
        self.assertLessEqual(len(result.candidates), 1)

    def test_candidates_carry_provenance(self) -> None:
        retriever = HybridRetriever()
        result = retriever.retrieve("canine CKD", self.chunks, top_k=2)

        for candidate in result.candidates:
            self.assertIsNotNone(candidate.chunk.attachment_version_id)
            self.assertGreater(candidate.chunk.page_number, 0)


# ---------------------------------------------------------------------------
# Integration: chunker + retriever
# ---------------------------------------------------------------------------


class TestChunkAndRetrieveIntegration(unittest.TestCase):
    """Verify chunked text can be searched end-to-end."""

    def test_chunk_then_retrieve(self) -> None:
        parse_result = _make_parse_result()
        chunker = TextChunker(target_size=300, overlap=50)
        chunks = chunker.chunk(parse_result, attachment_version_id="att-1")

        self.assertGreater(len(chunks), 0)

        retriever = HybridRetriever()
        result = retriever.retrieve("canine kidney disease survival", chunks, top_k=3)

        self.assertGreater(len(result.candidates), 0)
        top = result.candidates[0]
        self.assertIn("canine", top.chunk.text.lower())


if __name__ == "__main__":
    unittest.main()
