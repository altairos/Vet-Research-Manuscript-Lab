"""Typed representations for PDF parse results and import outcomes.

These dataclasses decouple the workflow layer from the raw PDF parsing
backend (PyMuPDF / fitz) so that tests can inject deterministic mocks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class ParseStatus(StrEnum):
    """Lifecycle states for a PDF parse attempt."""

    PENDING = "pending"
    PARSED = "parsed"
    FAILED = "failed"
    NEEDS_HUMAN_REVIEW = "needs_human_review"


@dataclass(frozen=True, slots=True)
class PdfPage:
    """Extracted text for a single PDF page (1-based page number)."""

    page_number: int
    text: str
    char_count: int

    def quote_hash_source(self) -> str:
        """Return the text used to compute the source-span quote hash."""

        return self.text


@dataclass(frozen=True, slots=True)
class ParseResult:
    """Outcome of parsing a single PDF document."""

    content_hash: str
    status: ParseStatus
    pages: list[PdfPage] = field(default_factory=list)
    page_count: int = 0
    error_message: str | None = None
    parsed_at: str = ""
    needs_human_review: bool = False
    review_reason: str | None = None
