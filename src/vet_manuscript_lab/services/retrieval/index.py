"""Hybrid retrieval (BM25 + vector) producing evidence candidates only.

The retriever combines BM25 keyword scoring with optional dense-vector
similarity to produce ranked ``RetrievalCandidate`` objects.  Per the
DEVELOPMENT.md exit criteria: *"top-k retrieval results cannot directly
become formal evidence"*.  Candidates carry provenance metadata and a
relevance score but are never promoted to ``EvidenceItem`` without human
review.

The backend follows the same Protocol + lazy-import pattern used by the
Zotero and PDF integrations: ``RetrievalBackend`` is a structural
interface satisfied by both ``LlamaIndexBackend`` (production) and
``MockBM25Backend`` (testing / offline).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from vet_manuscript_lab.services.retrieval.types import TextChunk


@dataclass(frozen=True, slots=True)
class RetrievalCandidate:
    """A ranked chunk returned by the hybrid retriever.

    Attributes
    ----------
    chunk
        The original ``TextChunk`` that matched the query.
    score
        Combined relevance score from BM25 and/or vector retrieval.
        Higher is more relevant.
    rank
        1-based position in the result list.
    source
        Which retrieval method contributed most to this candidate
        (``"bm25"``, ``"vector"``, or ``"hybrid"``).
    """

    chunk: TextChunk
    score: float
    rank: int
    source: str = "hybrid"


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    """Outcome of a single retrieval query."""

    query: str
    candidates: list[RetrievalCandidate] = field(default_factory=list)
    total_chunks_searched: int = 0


class RetrievalBackend(Protocol):
    """Minimal scoring interface the retriever relies on."""

    def search(
        self,
        query: str,
        chunks: list[TextChunk],
        *,
        top_k: int,
    ) -> list[tuple[int, float, str]]:
        """Return ``(chunk_index, score, source_label)`` tuples, best first."""
        ...


class RerankerBackend(Protocol):
    """Optional reranking interface for improving initial retrieval results."""

    def rerank(
        self,
        query: str,
        chunks: list[TextChunk],
        *,
        top_k: int,
    ) -> list[tuple[int, float]]:
        """Return ``(chunk_index, score)`` tuples, reranked best first."""
        ...


class HybridRetriever:
    """Hybrid retrieval with optional reranking.

    Parameters
    ----------
    backend
        ``RetrievalBackend`` for initial retrieval.  When omitted a
        ``MockBM25Backend`` is used (simple keyword overlap scoring).
    reranker
        Optional ``RerankerBackend`` for second-stage reranking.
    """

    def __init__(
        self,
        *,
        backend: RetrievalBackend | None = None,
        reranker: RerankerBackend | None = None,
    ) -> None:
        self._backend = backend
        self._reranker = reranker

    def retrieve(
        self,
        query: str,
        chunks: list[TextChunk],
        *,
        top_k: int = 10,
    ) -> RetrievalResult:
        """Search *chunks* for *query* and return ranked candidates.

        The candidates are evidence suggestions only: they must be
        validated by a human before being promoted to ``EvidenceItem``.
        """

        if not chunks:
            return RetrievalResult(
                query=query,
                candidates=[],
                total_chunks_searched=0,
            )

        backend = self._get_backend()
        raw_results = backend.search(query, chunks, top_k=top_k)

        # Apply optional reranking on the initial results
        if self._reranker is not None and raw_results:
            top_indices = [idx for idx, _, _ in raw_results]
            rerank_pool = [chunks[i] for i in top_indices if i < len(chunks)]
            reranked = self._reranker.rerank(query, rerank_pool, top_k=top_k)

            candidates: list[RetrievalCandidate] = []
            for rank, (local_idx, score) in enumerate(reranked, start=1):
                global_idx = top_indices[local_idx]
                if global_idx < len(chunks):
                    candidates.append(
                        RetrievalCandidate(
                            chunk=chunks[global_idx],
                            score=score,
                            rank=rank,
                            source="reranked",
                        )
                    )
        else:
            candidates = [
                RetrievalCandidate(
                    chunk=chunks[idx],
                    score=score,
                    rank=rank,
                    source=source_label,
                )
                for rank, (idx, score, source_label) in enumerate(raw_results, start=1)
            ]

        return RetrievalResult(
            query=query,
            candidates=candidates,
            total_chunks_searched=len(chunks),
        )

    def _get_backend(self) -> RetrievalBackend:
        if self._backend is not None:
            return self._backend
        return _create_default_backend()


# ---------------------------------------------------------------------------
# Default backend: simple BM25-style keyword overlap (no dependencies)
# ---------------------------------------------------------------------------


class MockBM25Backend:
    """Deterministic BM25-style scoring using keyword overlap.

    This is the default backend used when no LlamaIndex backend is
    configured.  It provides reasonable ranking for keyword queries
    without any external dependencies.
    """

    def search(
        self,
        query: str,
        chunks: list[TextChunk],
        *,
        top_k: int,
    ) -> list[tuple[int, float, str]]:
        query_terms = _tokenize(query)
        if not query_terms:
            return []

        scored: list[tuple[int, float, str]] = []
        for idx, chunk in enumerate(chunks):
            chunk_terms = _tokenize(chunk.text)
            if not chunk_terms:
                continue
            overlap = len(query_terms & chunk_terms)
            if overlap == 0:
                continue
            # Simple TF-based score normalised by chunk length
            score = overlap / (len(chunk_terms) ** 0.5)
            scored.append((idx, score, "bm25"))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]


def _tokenize(text: str) -> set[str]:
    """Lowercase, strip punctuation, return unique terms."""

    import re

    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return set(tokens) - {"the", "a", "an", "and", "or", "of", "in", "to", "for"}


def _create_default_backend() -> RetrievalBackend:
    """Create the default backend (no external dependencies)."""

    return MockBM25Backend()


__all__ = [
    "HybridRetriever",
    "MockBM25Backend",
    "RerankerBackend",
    "RetrievalBackend",
    "RetrievalCandidate",
    "RetrievalResult",
]
