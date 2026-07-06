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


class MockDocxRenderer:
    """Deterministic mock DOCX renderer for offline development.

    Produces a small binary blob that simulates a DOCX file.  The content
    is deterministic so hashes are reproducible.
    """

    def render(self, inputs: DocxRenderInput) -> DocxRenderResult:
        # Simulate DOCX content with a deterministic binary blob
        header = b"PK\x03\x04"  # ZIP magic bytes (DOCX is a ZIP archive)
        body = (
            f"[Mock DOCX]\nTitle: {inputs.title}\n"
            f"QMD hash: {_bytes_to_hash(inputs.qmd_content.encode())}\n"
            f"BIB hash: {_bytes_to_hash(inputs.bib_content.encode())}\n"
        ).encode()
        docx_bytes = header + body
        return DocxRenderResult(
            docx_base64=_bytes_to_base64(docx_bytes),
            content_hash=_bytes_to_hash(docx_bytes),
            renderer_name="mock",
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
