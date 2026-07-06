"""PDF text extraction with retry and human-review flagging.

Wraps ``PyMuPDF`` (``fitz``) so that the rest of the codebase depends on a
narrow, mockable interface.  Parse failures are retried once before the
result is marked ``FAILED``; scanned PDFs (zero text on all pages) are
flagged ``NEEDS_HUMAN_REVIEW`` per the MVP limitation in DEVELOPMENT.md.
"""

from __future__ import annotations

from typing import Any, Protocol

from vet_manuscript_lab.domain.conventions import sha256_bytes, utc_now
from vet_manuscript_lab.services.documents.types import (
    ParseResult,
    ParseStatus,
    PdfPage,
)

# Heuristic: if a page produces fewer characters than this threshold, it is
# treated as a non-text (scanned/image) page.
_MIN_PAGE_TEXT_CHARS = 20


class PdfParseBackend(Protocol):
    """Minimal extraction interface the parser relies on."""

    def extract_pages(self, pdf_bytes: bytes) -> list[dict[str, Any]]: ...


class PdfParser:
    """Parse PDF bytes into structured page results.

    Parameters
    ----------
    backend
        Optional ``PdfParseBackend`` for dependency injection (testing).
        When omitted the real ``PyMuPDF`` backend is created lazily.
    max_retries
        Number of retry attempts on backend errors (default 1).
    """

    def __init__(
        self,
        *,
        backend: PdfParseBackend | None = None,
        max_retries: int = 1,
    ) -> None:
        self._backend = backend
        self._max_retries = max_retries

    def parse(self, pdf_bytes: bytes) -> ParseResult:
        """Parse *pdf_bytes* and return a ``ParseResult``.

        The method is deterministic and side-effect-free: given the same
        bytes it always returns the same page content and hash.
        """

        content_hash = sha256_bytes(pdf_bytes)
        pages_raw: list[dict[str, Any]] | None = None
        last_error: str | None = None

        for _ in range(self._max_retries + 1):
            try:
                pages_raw = self._get_backend().extract_pages(pdf_bytes)
                break
            except Exception as exc:
                last_error = str(exc)

        if pages_raw is None:
            return ParseResult(
                content_hash=content_hash,
                status=ParseStatus.FAILED,
                page_count=0,
                error_message=last_error or "Unknown parse error",
                parsed_at=utc_now(),
            )

        pages = [
            PdfPage(
                page_number=int(p["page_number"]),
                text=str(p["text"]),
                char_count=int(p["char_count"]),
            )
            for p in pages_raw
        ]

        scanned_count = sum(
            1 for page in pages if page.char_count < _MIN_PAGE_TEXT_CHARS
        )
        total_text = sum(p.char_count for p in pages)

        # MVP limitation: scanned or empty PDFs must be flagged for manual review.
        if total_text == 0:
            return ParseResult(
                content_hash=content_hash,
                status=ParseStatus.NEEDS_HUMAN_REVIEW,
                pages=pages,
                page_count=len(pages),
                parsed_at=utc_now(),
                needs_human_review=True,
                review_reason="PDF contains no extractable text "
                "(scanned or image-only).",
            )

        if scanned_count > 0 and scanned_count == len(pages):
            return ParseResult(
                content_hash=content_hash,
                status=ParseStatus.NEEDS_HUMAN_REVIEW,
                pages=pages,
                page_count=len(pages),
                parsed_at=utc_now(),
                needs_human_review=True,
                review_reason=(
                    f"All {scanned_count} pages appear to be scanned images "
                    "with minimal extractable text."
                ),
            )

        status = (
            ParseStatus.NEEDS_HUMAN_REVIEW if scanned_count > 0 else ParseStatus.PARSED
        )
        review_reason = (
            f"{scanned_count} of {len(pages)} pages have minimal text "
            "and may require manual verification."
            if scanned_count > 0
            else None
        )

        return ParseResult(
            content_hash=content_hash,
            status=status,
            pages=pages,
            page_count=len(pages),
            parsed_at=utc_now(),
            needs_human_review=scanned_count > 0,
            review_reason=review_reason,
        )

    def _get_backend(self) -> PdfParseBackend:
        if self._backend is not None:
            return self._backend
        return _create_default_backend()


def _create_default_backend() -> PdfParseBackend:
    """Instantiate the real ``PyMuPDF`` backend lazily.

    Importing fitz at module load would couple every test to the binary
    dependency; deferring keeps the module importable without PyMuPDF.
    """

    from vet_manuscript_lab.services.documents._fitz_backend import FitzBackend

    return FitzBackend()


__all__ = ["ParseResult", "PdfParseBackend", "PdfParser"]
