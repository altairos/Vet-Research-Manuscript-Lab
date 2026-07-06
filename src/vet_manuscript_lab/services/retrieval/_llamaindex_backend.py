"""LlamaIndex BM25 + vector hybrid backend (lazy import).

Kept in a separate module so that ``index.py`` stays importable without
``llama-index-core`` or ``llama-index-retrievers-bm25`` installed.  The
adapter builds a hybrid retriever from ``TextChunk`` objects and
delegates search to the LlamaIndex engine.
"""

from __future__ import annotations

from typing import Any

from vet_manuscript_lab.services.retrieval.types import TextChunk


class LlamaIndexBackend:
    """LlamaIndex hybrid retrieval adapter.

    Implements the ``RetrievalBackend`` protocol by wrapping
    ``llama-index-retrievers-bm25`` (BM25) and optionally a dense vector
    retriever.  All imports are deferred to ``__init__`` so the module
    can be imported without LlamaIndex installed.
    """

    def __init__(
        self,
        *,
        use_vector: bool = False,
        embed_model: str = "local:sentence-transformers/all-MiniLM-L6-v2",
    ) -> None:
        self._use_vector = use_vector
        self._embed_model_name = embed_model
        self._retriever: Any = None
        self._chunk_map: list[TextChunk] = []

    def search(
        self,
        query: str,
        chunks: list[TextChunk],
        *,
        top_k: int,
    ) -> list[tuple[int, float, str]]:
        """Search *chunks* using the LlamaIndex hybrid retriever."""

        if not chunks:
            return []

        # Rebuild index if chunk set changed
        if self._retriever is None or len(chunks) != len(self._chunk_map):
            self._build_index(chunks, top_k=top_k)

        results = self._retriever.retrieve(query)
        scored: list[tuple[int, float, str]] = []
        for node in results[:top_k]:
            idx = node.node.metadata.get("chunk_index", -1)
            score = float(node.score or 0.0)
            if 0 <= idx < len(chunks):
                scored.append((idx, score, "llamaindex_hybrid"))
        return scored

    def _build_index(self, chunks: list[TextChunk], *, top_k: int = 10) -> None:
        """Build the LlamaIndex BM25 (+ optional vector) retriever."""

        from llama_index.core import Document, VectorStoreIndex  # type: ignore[import-not-found]  # noqa: I001
        from llama_index.retrievers.bm25 import BM25Retriever  # type: ignore[import-not-found]

        self._chunk_map = list(chunks)
        documents = [
            Document(
                text=chunk.text,
                metadata={
                    "chunk_index": i,
                    "page_number": chunk.page_number,
                    "section_label": chunk.section_label or "",
                    "attachment_version_id": chunk.attachment_version_id,
                },
            )
            for i, chunk in enumerate(chunks)
        ]

        retrievers: list[Any] = []
        bm25 = BM25Retriever.from_defaults(documents=documents)
        retrievers.append(bm25)

        if self._use_vector:
            from llama_index.core import Settings
            from llama_index.embeddings.huggingface import (  # type: ignore[import-not-found]
                HuggingFaceEmbedding,
            )

            Settings.embed_model = HuggingFaceEmbedding(
                model_name=self._embed_model_name
            )
            vector_index = VectorStoreIndex(documents)
            retrievers.append(vector_index.as_retriever(similarity_top_k=top_k))

        if len(retrievers) == 1:
            self._retriever = retrievers[0]
        else:
            from llama_index.core.retrievers import (  # type: ignore[import-not-found]
                QueryFusionRetriever,
            )

            self._retriever = QueryFusionRetriever(
                retrievers=retrievers,
                num_queries=1,
                mode="reciprocal_rerank",
                use_async=False,
            )


__all__ = ["LlamaIndexBackend"]
