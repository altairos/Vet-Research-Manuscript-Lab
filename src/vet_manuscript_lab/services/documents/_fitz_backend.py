"""``PyMuPDF`` (``fitz``) adapter implementing the ``PdfParseBackend`` protocol.

Kept in a separate module so that ``parser.py`` stays importable without
``pymupdf`` installed.  The adapter opens a PDF from in-memory bytes and
extracts plain text for each page.
"""

from __future__ import annotations

from typing import Any


class FitzBackend:
    """Adapts ``fitz.Document`` to the ``PdfParseBackend`` protocol."""

    def extract_pages(self, pdf_bytes: bytes) -> list[dict[str, Any]]:
        import fitz  # type: ignore[import-untyped]

        pages: list[dict[str, Any]] = []
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            for index, page in enumerate(doc, start=1):
                text = page.get_text("text")
                pages.append(
                    {
                        "page_number": index,
                        "text": text,
                        "char_count": len(text),
                    }
                )
        return pages


__all__ = ["FitzBackend"]
