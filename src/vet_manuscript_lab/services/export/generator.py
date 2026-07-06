"""Export generator service.

The ``ExportGenerator`` Protocol defines the contract;
``MockExportGenerator`` provides a deterministic implementation that
assembles the export package from manuscript sections, references, and
metadata.  When a ``DocxRenderer`` is supplied, a rendered DOCX component
is included in the package.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Protocol

from vet_manuscript_lab.services.export.renderer import (
    DocxRenderer,
    DocxRenderInput,
    DocxRenderResult,
)
from vet_manuscript_lab.services.export.types import (
    ExportComponent,
    ExportManifest,
    ExportResult,
)


@dataclass(frozen=True, slots=True)
class ExportInput:
    """Inputs provided to the export generator."""

    sections: tuple[dict[str, Any], ...]
    citations: tuple[dict[str, Any], ...]
    results: tuple[dict[str, Any], ...]
    literature_records: tuple[dict[str, Any], ...]
    analysis_plan_summary: dict[str, Any]
    ai_usage: dict[str, Any]
    sign_off_approval: dict[str, Any]
    manuscript_summary: dict[str, Any]


class ExportGenerator(Protocol):
    """Protocol for export generation backends."""

    def generate(self, inputs: ExportInput) -> ExportResult: ...


def _content_hash(text: str) -> str:
    return f"sha256:{hashlib.sha256(text.encode()).hexdigest()}"


class MockExportGenerator:
    """Deterministic mock export generator.

    Generates:
    - ``manuscript.qmd``: Quarto markdown assembled from sections.
    - ``references.bib``: BibTeX entries from literature records.
    - ``manuscript.docx``: Word document rendered via the DocxRenderer
      (only when a renderer is supplied).
    - ``manifest.json``: All artifact versions + sign-off binding.
    - ``ai_usage.json``: AI usage statistics.
    """

    def __init__(
        self,
        *,
        docx_renderer: DocxRenderer | None = None,
    ) -> None:
        self._docx_renderer = docx_renderer

    def generate(self, inputs: ExportInput) -> ExportResult:
        project_id = inputs.manuscript_summary.get("manuscript_id", "unknown")
        sign_off_id = inputs.sign_off_approval.get("approval_id", "")

        # --- manuscript.qmd ---
        sorted_sections = sorted(inputs.sections, key=lambda s: s.get("order", 0))
        qmd_lines: list[str] = [
            "---",
            f'title: "{inputs.manuscript_summary.get("title", "Untitled Manuscript")}"',
            "format: docx",
            "bibliography: references.bib",
            "---",
            "",
        ]
        for s in sorted_sections:
            stype = s.get("section_type", "section")
            content = s.get("content", "")
            qmd_lines.append(f"## {stype.title()}")
            qmd_lines.append("")
            qmd_lines.append(content)
            qmd_lines.append("")
        qmd_text = "\n".join(qmd_lines)
        qmd_component = ExportComponent(
            role="manuscript",
            filename="manuscript.qmd",
            content=qmd_text,
            content_hash=_content_hash(qmd_text),
            media_type="text/markdown",
        )

        # --- references.bib ---
        bib_lines: list[str] = []
        for rec in inputs.literature_records:
            rec_id = rec.get("record_id", rec.get("id", "unknown"))
            bib_lines.append(f"@misc{{{rec_id},")
            for field_name in ("title", "author", "year", "journal", "doi"):
                val = rec.get(field_name)
                if val:
                    bib_lines.append(f"  {field_name} = {{{val}}},")
            bib_lines.append("}")
            bib_lines.append("")
        bib_text = "\n".join(bib_lines) if bib_lines else "% No references"
        bib_component = ExportComponent(
            role="references",
            filename="references.bib",
            content=bib_text,
            content_hash=_content_hash(bib_text),
            media_type="application/x-bibtex",
        )

        # --- manuscript.docx (optional) ---
        docx_component: ExportComponent | None = None
        if self._docx_renderer is not None:
            docx_result: DocxRenderResult = self._docx_renderer.render(
                DocxRenderInput(
                    qmd_content=qmd_text,
                    bib_content=bib_text,
                    title=inputs.manuscript_summary.get("title", "Untitled Manuscript"),
                )
            )
            docx_component = ExportComponent(
                role="docx",
                filename="manuscript.docx",
                content=docx_result.docx_base64,
                content_hash=docx_result.content_hash,
                media_type=docx_result.media_type,
            )

        # --- manifest.json ---
        artifact_versions: list[tuple[str, str]] = []
        for key in ("protocol", "guideline_mapping", "analysis_plan", "manuscript"):
            av = inputs.sign_off_approval.get(key)
            if av:
                artifact_versions.append((key, av))
        component_hashes: dict[str, str] = {
            qmd_component.filename: qmd_component.content_hash,
            bib_component.filename: bib_component.content_hash,
        }
        if docx_component is not None:
            component_hashes[docx_component.filename] = docx_component.content_hash
        manifest_dict = {
            "project_id": project_id,
            "sign_off_id": sign_off_id,
            "manuscript_hash": inputs.manuscript_summary.get("content_hash", ""),
            "artifact_versions": artifact_versions,
            "component_hashes": component_hashes,
        }
        manifest_text = json.dumps(manifest_dict, sort_keys=True, indent=2)
        manifest_component = ExportComponent(
            role="manifest",
            filename="manifest.json",
            content=manifest_text,
            content_hash=_content_hash(manifest_text),
            media_type="application/json",
        )

        # --- ai_usage.json ---
        ai_usage_text = json.dumps(inputs.ai_usage or {}, sort_keys=True, indent=2)
        ai_usage_component = ExportComponent(
            role="ai_usage",
            filename="ai_usage.json",
            content=ai_usage_text,
            content_hash=_content_hash(ai_usage_text),
            media_type="application/json",
        )

        components_list = [
            qmd_component,
            bib_component,
            manifest_component,
            ai_usage_component,
        ]
        if docx_component is not None:
            components_list.append(docx_component)
        components = tuple(components_list)

        # --- package_hash ---
        all_hashes = "|".join(c.content_hash for c in components)
        package_hash = _content_hash(all_hashes)
        package_uri = f"mock://export/{project_id}/{sign_off_id}/{package_hash[:16]}"

        manifest = ExportManifest(
            project_id=project_id,
            sign_off_id=sign_off_id,
            artifact_versions=tuple(artifact_versions),
            ai_usage=inputs.ai_usage or {},
        )

        return ExportResult(
            manifest=manifest,
            components=components,
            package_hash=package_hash,
            package_uri=package_uri,
        )


__all__ = [
    "ExportGenerator",
    "ExportInput",
    "MockExportGenerator",
]
