"""Literature and evidence rendering (tab: Literature & Evidence)."""

from __future__ import annotations

from typing import Any

import streamlit as st

from vet_manuscript_lab.ui.components import badge, section_header
from vet_manuscript_lab.ui.i18n import translate


def _rows_to_html(rows: list[dict[str, Any]]) -> str:
    """Render simple HTML table so badges can display inside cells."""

    import html

    if not rows:
        return ""
    headers = list(rows[0].keys())
    head = "".join(f"<th>{html.escape(str(h))}</th>" for h in headers)
    body_rows = []
    for row in rows:
        cells = []
        for header in headers:
            value = str(row.get(header, ""))
            if "vrl-badge" in value:
                cells.append(f"<td>{value}</td>")
            else:
                cells.append(f"<td>{html.escape(value)}</td>")
        body_rows.append(f"<tr>{''.join(cells)}</tr>")
    body = "".join(body_rows)
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def render_literature_records(state: dict[str, Any]) -> None:
    """Display the literature record drafts in a table."""

    records = state.get("literature_record_drafts", [])
    if not records:
        st.info(translate("info_no_literature"))
        return

    section_header(translate("section_literature"))

    summary = state.get("literature_summary", {})
    if summary:
        col1, col2 = st.columns(2)
        col1.metric(
            translate("label_included_count"),
            summary.get("included_count", 0),
        )
        col2.metric(
            translate("label_excluded_count"),
            summary.get("excluded_count", 0),
        )

    st.caption(translate("info_screening_hint"))

    rows = []
    for rec in records:
        decision = rec.get("screening_decision", "pending")
        tone = (
            "success"
            if decision == "included"
            else "danger"
            if decision == "excluded"
            else "neutral"
        )
        rows.append(
            {
                translate("col_record_id"): rec.get("record_id", "")[:12],
                translate("col_title"): rec.get("title", ""),
                translate("col_doi"): rec.get("doi", ""),
                translate("label_screening_auto"): badge(decision, tone=tone),
            }
        )
    st.markdown(
        '<div class="vrl-html-table">' + _rows_to_html(rows) + "</div>",
        unsafe_allow_html=True,
    )


def render_evidence_items(state: dict[str, Any]) -> None:
    """Display extracted evidence drafts and their source spans."""

    drafts = state.get("evidence_drafts", [])
    spans = state.get("source_span_drafts", [])
    if not drafts:
        st.info(translate("info_no_evidence"))
        return

    section_header(translate("section_evidence"))

    summary = state.get("evidence_summary", {})
    if summary:
        col1, col2 = st.columns(2)
        col1.metric(
            translate("label_total_evidence"),
            summary.get("total_evidence_items", 0),
        )
        col2.metric(
            translate("label_items_review"),
            summary.get("items_requiring_review", 0),
        )

    span_lookup: dict[str, dict[str, Any]] = {s["span_id"]: s for s in spans}

    rows = []
    for draft in drafts:
        first_span_id = (
            draft.get("source_span_ids", [""])[0]
            if draft.get("source_span_ids")
            else ""
        )
        span = span_lookup.get(first_span_id, {})
        rows.append(
            {
                translate("col_concept"): draft.get("concept", ""),
                translate("col_value"): str(draft.get("value", ""))[:120],
                translate("col_page"): span.get("page", ""),
                translate("col_section"): span.get("section_label", ""),
                translate("col_review"): (
                    translate("label_yes")
                    if draft.get("requires_human_review")
                    else translate("label_no")
                ),
                translate("col_status"): draft.get("extraction_status", ""),
            }
        )
    st.dataframe(rows, width="stretch", hide_index=True)

    with st.expander(translate("section_source_spans"), expanded=False):
        span_rows = []
        for span in spans:
            span_rows.append(
                {
                    translate("col_span_id"): span.get("span_id", "")[:16],
                    translate("col_record_id"): span.get("literature_record_id", "")[
                        :12
                    ],
                    translate("col_page"): span.get("page", ""),
                    translate("col_section"): span.get("section_label", ""),
                }
            )
        if span_rows:
            st.dataframe(span_rows, width="stretch", hide_index=True)
        else:
            st.info(translate("info_no_evidence"))


def render_search_strategy_detail(state: dict[str, Any]) -> None:
    """Show the search strategy artifact details when available."""

    artifacts = state.get("artifacts", {})
    strategy = artifacts.get("search_strategy")
    if strategy is None:
        return
    with st.expander(translate("gate.search_strategy.title"), expanded=False):
        st.caption(translate("gate.search_strategy.summary"))
        st.json(
            {
                "version": strategy.get("version"),
                "version_id": strategy.get("version_id"),
                "content_hash": strategy.get("content_hash"),
            }
        )
