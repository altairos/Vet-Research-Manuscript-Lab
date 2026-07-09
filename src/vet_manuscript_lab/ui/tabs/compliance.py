"""Compliance and export rendering (tab: Export)."""

from __future__ import annotations

import base64
from typing import Any

import streamlit as st

from vet_manuscript_lab.ui.i18n import translate


def render_compliance_findings(state: dict[str, Any]) -> None:
    """Display compliance check results."""

    findings = state.get("compliance_findings", [])
    summary = state.get("compliance_summary")

    st.subheader(translate("section_compliance"))

    if summary:
        passed = summary.get("passed", True)
        col1, col2 = st.columns(2)
        col1.metric(
            translate("label_compliance_status"),
            translate("label_pass") if passed else translate("label_fail"),
        )
        col2.metric(
            translate("label_findings_count"),
            summary.get("findings_count", len(findings)),
        )

    if findings:
        rows = []
        for f in findings:
            rows.append(
                {
                    translate("col_rule_id"): f.get("rule_id", ""),
                    translate("col_severity"): f.get("severity", ""),
                    translate("col_message"): f.get("message", ""),
                    translate("col_object_id"): f.get("object_id", "")[:40],
                }
            )
        st.dataframe(rows, width="stretch", hide_index=True)


def render_export(state: dict[str, Any]) -> None:
    """Display export package summary with download buttons."""

    package = state.get("export_package")
    if package is None:
        st.info(translate("info_no_export"))
        return

    st.subheader(translate("section_export"))

    col1, col2 = st.columns(2)
    col1.metric(
        translate("col_components"),
        package.get("component_count", 0),
    )
    col2.metric(
        translate("label_manuscript_status"),
        package.get("status", ""),
    )
    from vet_manuscript_lab.services.export import (
        ExportInput,
        MockExportGenerator,
        create_docx_renderer,
    )

    sections = tuple(dict(s) for s in state.get("section_drafts", []))
    citations = tuple(dict(c) for c in state.get("citation_drafts", []))
    results = tuple(dict(r) for r in state.get("result_drafts", []))
    literature = tuple(dict(r) for r in state.get("literature_record_drafts", []))
    analysis_plan = dict(state.get("analysis_plan_summary") or {})
    ai_usage = dict(state.get("ai_usage") or {})
    manuscript = dict(state.get("manuscript_summary") or {})
    sign_off = dict(state.get("approvals", {}).get("final_sign_off", {}))
    sign_off["approval_id"] = (
        state.get("sign_off_binding", {}).get("approval_id", "")
        if state.get("sign_off_binding")
        else ""
    )

    try:
        renderer = create_docx_renderer()
        generator = MockExportGenerator(docx_renderer=renderer)
        export_result = generator.generate(
            ExportInput(
                sections=sections,
                citations=citations,
                results=results,
                literature_records=literature,
                analysis_plan_summary=analysis_plan,
                ai_usage=ai_usage,
                sign_off_approval=sign_off,
                manuscript_summary=manuscript,
            )
        )
    except Exception as exc:
        st.error(f"{translate('label_regenerating')} {exc}")
        return

    dl_cols = st.columns(min(len(export_result.components), 5))
    for i, comp in enumerate(export_result.components):
        col = dl_cols[i % len(dl_cols)]
        label_key = {
            "manuscript": "label_download_qmd",
            "references": "label_download_bib",
            "manifest": "label_download_manifest",
            "docx": "label_download_docx",
        }.get(comp.role, "col_filename")
        label = translate(label_key) if label_key != "col_filename" else comp.filename

        is_binary = comp.media_type in (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/octet-stream",
        )
        if is_binary:
            try:
                data = base64.b64decode(comp.content)
                col.download_button(
                    label,
                    data=data,
                    file_name=comp.filename,
                    mime=comp.media_type,
                    key=f"dl-{comp.role}",
                )
            except Exception:
                col.download_button(
                    label,
                    data=comp.content.encode(),
                    file_name=comp.filename,
                    mime="text/plain",
                    key=f"dl-{comp.role}-fallback",
                )
        else:
            col.download_button(
                label,
                data=comp.content.encode("utf-8"),
                file_name=comp.filename,
                mime=comp.media_type,
                key=f"dl-{comp.role}",
            )

    comp_rows = []
    for comp in export_result.components:
        comp_rows.append(
            {
                translate("col_filename"): comp.filename,
                translate("col_media_type"): comp.media_type,
                translate("col_task_kind"): comp.role,
            }
        )
    if comp_rows:
        st.dataframe(comp_rows, width="stretch", hide_index=True)


def render_ai_disclosure(state: dict[str, Any]) -> None:
    """Render a formatted AI-usage disclosure block."""

    usage = state.get("ai_usage")
    if not usage:
        st.info(translate("info_no_ai_usage"))
        return

    st.subheader(translate("section_ai_disclosure"))

    total_invocations = usage.get("total_invocations", 0)
    total_cost = usage.get("total_cost_cents", 0)
    total_input_tokens = usage.get("total_input_tokens", 0)
    total_output_tokens = usage.get("total_output_tokens", 0)
    fallback = usage.get("fallback_count", 0)
    failure = usage.get("failure_count", 0)

    col1, col2 = st.columns(2)
    col1.metric(translate("label_total_invocations"), total_invocations)
    col2.metric(
        translate("label_total_cost"),
        f"${total_cost / 100:.2f}",
    )

    lines = [
        "# AI Usage Disclosure",
        "",
        (
            "This manuscript was prepared with assistance from "
            "AI-based language models during the drafting, "
            "review, and revision phases."
        ),
        "",
        "## Summary of Model Usage",
        f"- Total model invocations: {total_invocations}",
        f"- Total estimated cost: ${total_cost / 100:.2f} USD",
        f"- Input tokens consumed: {total_input_tokens:,}",
        f"- Output tokens consumed: {total_output_tokens:,}",
    ]
    if fallback or failure:
        lines.append("")
        lines.append("## Fallbacks and Failures")
        lines.append(f"- Fallback invocations: {fallback}")
        lines.append(f"- Failed invocations: {failure}")

    cost_by_stage = usage.get("cost_by_stage", {})
    if cost_by_stage:
        lines.append("")
        lines.append("## Breakdown by Task")
        lines.append(
            f"| {translate('col_task_kind')} | "
            f"{translate('col_invocations')} | "
            f"{translate('label_total_cost')} |"
        )
        lines.append("|---|---|---|")
        for task_kind, data in cost_by_stage.items():
            if task_kind == "__total__":
                continue
            invocations = data.get("invocations", 0)
            cost_cents = data.get("cost_cents", 0)
            lines.append(f"| {task_kind} | {invocations} | ${cost_cents / 100:.2f} |")

    lines.append("")
    lines.append(
        "All AI-assisted content was reviewed and validated by "
        "the authors prior to publication."
    )

    disclosure_text = "\n".join(lines)
    with st.expander(translate("section_ai_disclosure"), expanded=False):
        st.code(disclosure_text, language="markdown")
    st.download_button(
        translate("label_download_manifest"),
        data=disclosure_text.encode("utf-8"),
        file_name="ai_usage_disclosure.md",
        mime="text/markdown",
    )
