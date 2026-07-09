"""DOCX renderer service.

The ``DocxRenderer`` Protocol defines the contract for converting a
Quarto markdown (QMD) source + BibTeX references into a Word DOCX file.

``QuartoDocxRenderer`` calls ``quarto render`` via subprocess.
``PandocDocxRenderer`` is a fallback that calls ``pandoc`` directly.
``MockDocxRenderer`` produces a deterministic placeholder for offline
development when neither tool is installed.
"""

from __future__ import annotations

import base64
import hashlib
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True, slots=True)
class DocxRenderInput:
    """Inputs for DOCX rendering."""

    qmd_content: str
    bib_content: str
    title: str = "Untitled Manuscript"
    reference_doc_path: str | None = None


@dataclass(frozen=True, slots=True)
class DocxRenderResult:
    """Output from DOCX rendering."""

    docx_base64: str
    content_hash: str
    renderer_name: str
    media_type: str = (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    is_mock_output: bool = False


class DocxRenderer(Protocol):
    """Protocol for DOCX rendering backends."""

    def render(self, inputs: DocxRenderInput) -> DocxRenderResult: ...


def _bytes_to_hash(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def _bytes_to_base64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _find_executable(name: str) -> str | None:
    """Return the path to *name* if found on PATH, else ``None``."""
    return shutil.which(name)


# ---------------------------------------------------------------------------
# Quarto renderer
# ---------------------------------------------------------------------------


class QuartoDocxRenderer:
    """Render DOCX via ``quarto render``.

    Requires Quarto CLI (https://quarto.org/) installed and on PATH.
    If a ``reference_doc_path`` is provided, it is passed to Quarto
    via ``--reference-doc`` for style template matching.
    """

    def __init__(self, quarto_bin: str | None = None) -> None:
        self._quarto_bin = quarto_bin or _find_executable("quarto")

    def is_available(self) -> bool:
        """Return True if the Quarto CLI is available."""
        return self._quarto_bin is not None

    def render(self, inputs: DocxRenderInput) -> DocxRenderResult:
        if not self.is_available():
            raise FileNotFoundError(
                "Quarto CLI not found on PATH; install from https://quarto.org/"
            )
        return self._render_with_quarto(inputs)

    def _render_with_quarto(self, inputs: DocxRenderInput) -> DocxRenderResult:
        assert self._quarto_bin is not None  # checked by is_available()
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            qmd_path = Path(tmpdir) / "manuscript.qmd"
            bib_path = Path(tmpdir) / "references.bib"
            out_path = Path(tmpdir) / "manuscript.docx"

            # Write QMD with YAML front matter
            qmd_lines = [
                "---",
                f'title: "{inputs.title}"',
                "format:",
                "  docx:",
                "    bibliography: references.bib",
            ]
            if inputs.reference_doc_path:
                qmd_lines.append(f'    reference-doc: "{inputs.reference_doc_path}"')
            qmd_lines.append("---")
            qmd_lines.append("")
            # Strip existing front matter from qmd_content if present
            content = inputs.qmd_content
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    content = parts[2].lstrip("\n")
            qmd_lines.append(content)
            qmd_path.write_text("\n".join(qmd_lines), encoding="utf-8")
            bib_path.write_text(inputs.bib_content, encoding="utf-8")

            cmd = [
                self._quarto_bin,
                "render",
                str(qmd_path),
                "--to",
                "docx",
                "--output",
                str(out_path),
            ]
            subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                cwd=tmpdir,
            )

            docx_bytes = out_path.read_bytes()
            return DocxRenderResult(
                docx_base64=_bytes_to_base64(docx_bytes),
                content_hash=_bytes_to_hash(docx_bytes),
                renderer_name="quarto",
            )


# ---------------------------------------------------------------------------
# Pandoc fallback renderer
# ---------------------------------------------------------------------------


class PandocDocxRenderer:
    """Render DOCX via ``pandoc`` directly (no Quarto required).

    Falls back to pandoc when Quarto CLI is not installed.
    """

    def __init__(self, pandoc_bin: str | None = None) -> None:
        self._pandoc_bin = pandoc_bin or _find_executable("pandoc")

    def is_available(self) -> bool:
        """Return True if pandoc is available."""
        return self._pandoc_bin is not None

    def render(self, inputs: DocxRenderInput) -> DocxRenderResult:
        if not self.is_available():
            raise FileNotFoundError(
                "pandoc not found on PATH; install from https://pandoc.org/"
            )
        return self._render_with_pandoc(inputs)

    def _render_with_pandoc(self, inputs: DocxRenderInput) -> DocxRenderResult:
        assert self._pandoc_bin is not None  # checked by is_available()
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            md_path = Path(tmpdir) / "manuscript.md"
            bib_path = Path(tmpdir) / "references.bib"
            out_path = Path(tmpdir) / "manuscript.docx"

            # Write markdown (strip QMD YAML front matter, pandoc handles its own)
            content = inputs.qmd_content
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    content = parts[2].lstrip("\n")
            md_path.write_text(content, encoding="utf-8")
            bib_path.write_text(inputs.bib_content, encoding="utf-8")

            cmd = [
                self._pandoc_bin,
                str(md_path),
                "--from",
                "markdown",
                "--to",
                "docx",
                "--bibliography",
                str(bib_path),
                "--metadata",
                f"title={inputs.title}",
                "--output",
                str(out_path),
            ]
            if inputs.reference_doc_path:
                cmd.extend(["--reference-doc", inputs.reference_doc_path])

            subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                cwd=tmpdir,
            )

            docx_bytes = out_path.read_bytes()
            return DocxRenderResult(
                docx_base64=_bytes_to_base64(docx_bytes),
                content_hash=_bytes_to_hash(docx_bytes),
                renderer_name="pandoc",
            )


# ---------------------------------------------------------------------------
# Auto-detect renderer
# ---------------------------------------------------------------------------


def create_docx_renderer(
    *,
    prefer: str = "quarto",
) -> DocxRenderer:
    """Create a DOCX renderer, preferring Quarto then pandoc, else mock.

    Order of preference:
    1. If ``prefer`` is ``"quarto"`` and Quarto is installed → ``QuartoDocxRenderer``
    2. If pandoc is installed → ``PandocDocxRenderer``
    3. Otherwise → ``MockDocxRenderer`` (placeholder)
    """

    if prefer == "quarto":
        quarto = QuartoDocxRenderer()
        if quarto.is_available():
            return quarto
    pandoc = PandocDocxRenderer()
    if pandoc.is_available():
        return pandoc
    return MockDocxRenderer()


# ---------------------------------------------------------------------------
# Mock renderer (deterministic placeholder)
# ---------------------------------------------------------------------------


def _escape_xml(text: str) -> str:
    """Escape XML special characters in text content."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def _qmd_to_body_xml(qmd_content: str, *, title: str) -> str:
    """Convert Quarto markdown content into OOXML ``<w:body>`` XML.

    Handles YAML front-matter stripping, ``#``/``##`` headings, and
    plain-text paragraphs.  Produces well-formed XML that Word/LibreOffice
    can open.
    """

    # Strip YAML front matter if present
    content = qmd_content
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            content = parts[2].lstrip("\n")

    paragraphs: list[str] = []

    # Title paragraph
    paragraphs.append(
        '<w:p><w:pPr><w:pStyle w:val="Title"/></w:pPr>'
        f'<w:r><w:t xml:space="preserve">{_escape_xml(title)}</w:t></w:r></w:p>'
    )

    for line in content.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("### "):
            heading = _escape_xml(stripped[4:])
            paragraphs.append(
                '<w:p><w:pPr><w:pStyle w:val="Heading3"/></w:pPr>'
                f'<w:r><w:t xml:space="preserve">{heading}</w:t></w:r></w:p>'
            )
        elif stripped.startswith("## "):
            heading = _escape_xml(stripped[3:])
            paragraphs.append(
                '<w:p><w:pPr><w:pStyle w:val="Heading2"/></w:pPr>'
                f'<w:r><w:t xml:space="preserve">{heading}</w:t></w:r></w:p>'
            )
        elif stripped.startswith("# "):
            heading = _escape_xml(stripped[2:])
            paragraphs.append(
                '<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr>'
                f'<w:r><w:t xml:space="preserve">{heading}</w:t></w:r></w:p>'
            )
        else:
            text = _escape_xml(stripped)
            paragraphs.append(
                f'<w:p><w:r><w:t xml:space="preserve">{text}</w:t></w:r></w:p>'
            )

    return "<w:body>" + "\n".join(paragraphs) + "<w:sectPr/></w:body>"


# XML templates for the minimal DOCX package ---------------------------------

_CONTENT_TYPES_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" '
    'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/word/document.xml" '
    'ContentType="application/vnd.openxmlformats-officedocument.'
    'wordprocessingml.document.main+xml"/>'
    '<Override PartName="/word/styles.xml" '
    'ContentType="application/vnd.openxmlformats-officedocument.'
    'wordprocessingml.styles+xml"/>'
    "</Types>"
)

_RELS_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" '
    'Type="http://schemas.openxmlformats.org/'
    'officeDocument/2006/relationships/officeDocument" '
    'Target="word/document.xml"/>'
    "</Relationships>"
)

_DOC_RELS_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" '
    'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
    'Target="styles.xml"/>'
    "</Relationships>"
)

_STYLES_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
    "<w:docDefaults>"
    "<w:rPrDefault><w:rPr>"
    '<w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:eastAsia="SimSun"/>'
    '<w:sz w:val="22"/><w:szCs w:val="22"/>'
    "</w:rPr></w:rPrDefault>"
    "</w:docDefaults>"
    # Title
    '<w:style w:type="paragraph" w:styleId="Title">'
    '<w:name w:val="Title"/>'
    '<w:pPr><w:spacing w:after="240"/></w:pPr>'
    '<w:rPr><w:b/><w:sz w:val="40"/><w:szCs w:val="40"/></w:rPr>'
    "</w:style>"
    # Heading 1
    '<w:style w:type="paragraph" w:styleId="Heading1">'
    '<w:name w:val="heading 1"/>'
    '<w:pPr><w:spacing w:before="360" w:after="120"/></w:pPr>'
    '<w:rPr><w:b/><w:sz w:val="32"/><w:szCs w:val="32"/></w:rPr>'
    "</w:style>"
    # Heading 2
    '<w:style w:type="paragraph" w:styleId="Heading2">'
    '<w:name w:val="heading 2"/>'
    '<w:pPr><w:spacing w:before="280" w:after="100"/></w:pPr>'
    '<w:rPr><w:b/><w:sz w:val="28"/><w:szCs w:val="28"/></w:rPr>'
    "</w:style>"
    # Heading 3
    '<w:style w:type="paragraph" w:styleId="Heading3">'
    '<w:name w:val="heading 3"/>'
    '<w:pPr><w:spacing w:before="200" w:after="80"/></w:pPr>'
    '<w:rPr><w:b/><w:sz w:val="24"/><w:szCs w:val="24"/></w:rPr>'
    "</w:style>"
    "</w:styles>"
)


class MockDocxRenderer:
    """Deterministic DOCX renderer for offline development.

    Generates a **valid** OOXML/ZIP package (``.docx``) that can be opened
    by Microsoft Word, LibreOffice, Google Docs, or any compliant reader.
    The QMD markdown content is converted to WordprocessingML paragraphs;
    ``#``/``##``/``###`` headings become styled paragraph runs.
    """

    def render(self, inputs: DocxRenderInput) -> DocxRenderResult:
        import io
        import zipfile

        body_xml = _qmd_to_body_xml(inputs.qmd_content, title=inputs.title)
        document_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            f"{body_xml}"
            "</w:document>"
        )

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("[Content_Types].xml", _CONTENT_TYPES_XML)
            zf.writestr("_rels/.rels", _RELS_XML)
            zf.writestr("word/document.xml", document_xml)
            zf.writestr("word/styles.xml", _STYLES_XML)
            zf.writestr("word/_rels/document.xml.rels", _DOC_RELS_XML)

        docx_bytes = buf.getvalue()
        return DocxRenderResult(
            docx_base64=_bytes_to_base64(docx_bytes),
            content_hash=_bytes_to_hash(docx_bytes),
            renderer_name="mock",
            is_mock_output=True,
        )


__all__ = [
    "DocxRenderInput",
    "DocxRenderResult",
    "DocxRenderer",
    "MockDocxRenderer",
    "PandocDocxRenderer",
    "QuartoDocxRenderer",
    "create_docx_renderer",
]
