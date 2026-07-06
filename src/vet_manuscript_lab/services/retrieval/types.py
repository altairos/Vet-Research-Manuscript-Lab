"""Typed representations for text chunks and retrieval candidates.

A ``TextChunk`` is a unit of text extracted from a parsed PDF page,
carrying the metadata needed to create a ``SourceSpan`` later (page,
section, char offsets, attachment version).

A ``RetrievalCandidate`` is the output of a hybrid retrieval query: a
ranked chunk plus a relevance score.  Candidates must never become
formal evidence without human review.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TextChunk:
    """A chunk of text with provenance back to a specific PDF location.

    Attributes
    ----------
    chunk_id
        Stable identifier derived from content hash + position.
    text
        The extracted text content of this chunk.
    page_number
        1-based PDF page number.
    char_start
        Character offset within the page where the chunk starts.
    char_end
        Character offset within the page where the chunk ends (exclusive).
    chunk_index
        Global sequential index (0-based) across all chunks from one document.
    attachment_version_id
        The immutable attachment version this chunk was extracted from.
    section_label
        Best-effort section heading detected from surrounding text
        (e.g. ``"Results"``, ``"Methods"``).
    literature_record_id
        The literature record this chunk belongs to.
    """

    chunk_id: str
    text: str
    page_number: int
    char_start: int
    char_end: int
    chunk_index: int
    attachment_version_id: str
    section_label: str | None = None
    literature_record_id: str | None = None

    @property
    def char_count(self) -> int:
        return self.char_end - self.char_start
