"""Paragraph-aware text chunker with provenance metadata.

Splits parsed PDF pages into overlapping chunks that carry full
provenance back to the source document.  Each chunk records the page
number, character offsets, section heading, and attachment version so
that ``LiteratureRepository.create_source_span`` can be called later
without any additional lookups.

The chunker is deterministic: given the same ``ParseResult`` it always
produces the same set of chunks and IDs.
"""

from __future__ import annotations

import re

from vet_manuscript_lab.domain.conventions import sha256_bytes
from vet_manuscript_lab.services.documents.types import ParseResult, PdfPage
from vet_manuscript_lab.services.retrieval.types import TextChunk

# Regex matching common academic section headings on a line by themselves.
_SECTION_PATTERN = re.compile(
    r"^\s*("
    r"(?:abstract|introduction|background|methods?|materials and methods?"
    r"|results?|discussion|conclusions?|references?|acknowledg(e?)ments?"
    r"|funding|conflicts? of interest|data availability"
    r"|supplementary (?:materials?|data|information))"
    r")\s*[:.\-]?\s*$",
    re.IGNORECASE,
)

# Minimum chunk size: a chunk below this is merged into the previous one.
_MIN_CHUNK_CHARS = 50


class TextChunker:
    """Split a ``ParseResult`` into provenance-bearing ``TextChunk`` objects.

    Parameters
    ----------
    target_size
        Target character length for each chunk (default 1000).
    overlap
        Number of characters of overlap between consecutive chunks on the
        same page (default 100).
    """

    def __init__(
        self,
        *,
        target_size: int = 1000,
        overlap: int = 100,
    ) -> None:
        if target_size <= 0:
            raise ValueError("target_size must be positive")
        if overlap < 0 or overlap >= target_size:
            raise ValueError("overlap must be in [0, target_size)")
        self._target_size = target_size
        self._overlap = overlap

    def chunk(
        self,
        parse_result: ParseResult,
        *,
        attachment_version_id: str,
        literature_record_id: str | None = None,
    ) -> list[TextChunk]:
        """Produce ``TextChunk`` objects from a parsed PDF.

        Pages are processed sequentially; each page's text is split into
        segments at paragraph boundaries, then segments are combined to
        approach ``target_size`` with ``overlap``.
        """

        chunks: list[TextChunk] = []
        global_index = 0
        current_section: str | None = None

        for page in parse_result.pages:
            page_chunks, global_index, current_section = self._chunk_page(
                page=page,
                global_index=global_index,
                current_section=current_section,
                attachment_version_id=attachment_version_id,
                literature_record_id=literature_record_id,
            )
            chunks.extend(page_chunks)

        return chunks

    def _chunk_page(
        self,
        *,
        page: PdfPage,
        global_index: int,
        current_section: str | None,
        attachment_version_id: str,
        literature_record_id: str | None,
    ) -> tuple[list[TextChunk], int, str | None]:
        """Chunk a single page, returning chunks, next index, and section."""

        text = page.text
        if not text.strip():
            return [], global_index, current_section

        segments = self._split_into_segments(text)
        chunks: list[TextChunk] = []
        buffer = ""
        buffer_start = 0
        section = current_section

        for seg_text, seg_start in segments:
            # Detect section heading
            heading = self._detect_section(seg_text)
            if heading is not None:
                section = heading

            # If buffer + segment exceeds target, flush buffer
            if buffer and len(buffer) + len(seg_text) > self._target_size:
                chunk = self._make_chunk(
                    text=buffer,
                    page_number=page.page_number,
                    char_start=buffer_start,
                    char_end=buffer_start + len(buffer),
                    chunk_index=global_index,
                    section=section,
                    attachment_version_id=attachment_version_id,
                    literature_record_id=literature_record_id,
                )
                chunks.append(chunk)
                global_index += 1

                # Start new buffer with overlap from the end of previous
                overlap_text = buffer[-self._overlap :] if self._overlap else ""
                buffer = overlap_text + seg_text
                buffer_start = seg_start - len(overlap_text)
            else:
                if not buffer:
                    buffer_start = seg_start
                buffer += seg_text

        # Flush remaining buffer
        if buffer and len(buffer.strip()) >= _MIN_CHUNK_CHARS:
            chunk = self._make_chunk(
                text=buffer,
                page_number=page.page_number,
                char_start=buffer_start,
                char_end=buffer_start + len(buffer),
                chunk_index=global_index,
                section=section,
                attachment_version_id=attachment_version_id,
                literature_record_id=literature_record_id,
            )
            chunks.append(chunk)
            global_index += 1
        elif buffer and chunks:
            # Merge small remainder into the last chunk
            last = chunks[-1]
            merged_text = last.text + buffer
            chunks[-1] = TextChunk(
                chunk_id=last.chunk_id,
                text=merged_text,
                page_number=last.page_number,
                char_start=last.char_start,
                char_end=last.char_start + len(merged_text),
                chunk_index=last.chunk_index,
                attachment_version_id=last.attachment_version_id,
                section_label=last.section_label,
                literature_record_id=last.literature_record_id,
            )

        return chunks, global_index, section

    def _split_into_segments(self, text: str) -> list[tuple[str, int]]:
        """Split text into paragraphs, returning (segment_text, char_offset)."""

        segments: list[tuple[str, int]] = []
        pos = 0
        for match in re.finditer(r"\n\s*\n", text):
            end = match.start()
            seg = text[pos:end]
            if seg.strip():
                segments.append((seg, pos))
            pos = match.end()
        # Last segment
        if pos < len(text):
            seg = text[pos:]
            if seg.strip():
                segments.append((seg, pos))
        return segments

    @staticmethod
    def _detect_section(text: str) -> str | None:
        """Return a normalised section label if *text* looks like a heading."""

        stripped = text.strip()
        # Only check short lines (headings are typically < 80 chars)
        if len(stripped) > 80:
            return None
        match = _SECTION_PATTERN.match(stripped)
        if match:
            return match.group(1).strip().title()
        return None

    @staticmethod
    def _make_chunk(
        *,
        text: str,
        page_number: int,
        char_start: int,
        char_end: int,
        chunk_index: int,
        section: str | None,
        attachment_version_id: str,
        literature_record_id: str | None,
    ) -> TextChunk:
        """Create a TextChunk with a deterministic ID."""

        content_for_hash = (
            f"{attachment_version_id}:{page_number}:"
            f"{char_start}:{chunk_index}:{text[:200]}"
        )
        chunk_hash = sha256_bytes(content_for_hash.encode())
        # Short stable ID: first 16 hex chars of the digest
        digest = chunk_hash.partition(":")[2][:16]
        chunk_id = f"chunk-{digest}"

        return TextChunk(
            chunk_id=chunk_id,
            text=text.strip(),
            page_number=page_number,
            char_start=char_start,
            char_end=char_end,
            chunk_index=chunk_index,
            attachment_version_id=attachment_version_id,
            section_label=section,
            literature_record_id=literature_record_id,
        )


__all__ = ["TextChunker"]
