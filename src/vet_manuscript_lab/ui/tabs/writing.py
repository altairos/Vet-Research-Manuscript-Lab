"""Writing and review rendering (tabs: Manuscript, Review & Compliance)."""

from __future__ import annotations

import html
from typing import Any

import streamlit as st

from vet_manuscript_lab.ui.components import short_hash
from vet_manuscript_lab.ui.i18n import translate

# Background colours for diff highlighting.
_DIFF_TONES: dict[str, str] = {
    "success": "#DFF3E8",
    "danger": "#FEE4E2",
}


def _render_highlighted_lines(lines: list[str], *, tone: str) -> None:
    """Render diff lines with a coloured background (green=added, red=removed)."""

    bg = _DIFF_TONES.get(tone, "#EEF2F6")
    blocks: list[str] = []
    for line in lines:
        safe = html.escape(line)
        blocks.append(
            f'<div style="background:{bg};'
            f'border-radius:4px;padding:.15rem .5rem;'
            f'margin-bottom:.15rem;font-size:.85rem;">{safe}</div>'
        )
    st.markdown(
        f'<div>{"".join(blocks)}</div>',
        unsafe_allow_html=True,
    )


def render_manuscript(state: dict[str, Any]) -> None:
    """Display manuscript sections with word counts and content."""

    summary = state.get("manuscript_summary")
    sections = state.get("section_drafts", [])
    if not summary and not sections:
        st.info(translate("info_no_manuscript"))
        return

    st.subheader(translate("section_manuscript"))

    if summary:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric(
            translate("label_manuscript_version"),
            summary.get("version", 1),
        )
        col2.metric(
            translate("label_section_count"),
            summary.get("section_count", 0),
        )
        col3.metric(
            translate("label_claim_count"),
            summary.get("claim_count", 0),
        )
        col4.metric(
            translate("label_manuscript_status"),
            summary.get("status", ""),
        )

    total_words = sum(s.get("word_count", 0) for s in sections)
    if total_words:
        st.caption(f"{translate('label_word_count')}: {total_words}")

    claims = state.get("claim_drafts", [])
    supports = state.get("support_drafts", [])
    support_by_claim: dict[str, int] = {}
    for sp in supports:
        cid = sp.get("claim_id", "")
        support_by_claim[cid] = support_by_claim.get(cid, 0) + 1

    claims_by_section: dict[str, list[dict[str, Any]]] = {}
    for c in claims:
        sid = c.get("section_id", "")
        claims_by_section.setdefault(sid, []).append(c)

    for section in sorted(sections, key=lambda s: s.get("order", 0)):
        stype = section.get("section_type", "section")
        content = section.get("content", "")
        sid = section.get("section_id", "")
        section_claims = claims_by_section.get(sid, [])
        header = stype.title()
        if section_claims:
            header += f" ({len(section_claims)} {translate('label_claim_bound')})"
        with st.expander(header, expanded=False):
            st.write(content)
            if section_claims:
                st.markdown(f"**{translate('label_claim_bound')}:**")
                badges = []
                for c in section_claims:
                    cid = c.get("claim_id", "")
                    ctype = c.get("claim_type", "")
                    count = support_by_claim.get(cid, 0)
                    if ctype == "hypothesis":
                        sl = translate("label_claim_status_hypothesis")
                        icon = "\U0001f914"
                    elif count > 0:
                        sl = translate("label_claim_status_supported")
                        icon = "\u2705"
                    else:
                        sl = translate("label_claim_status_unsupported")
                        icon = "\u26a0\ufe0f"
                    badges.append(f"{icon} {sl}: {c.get('text', '')[:80]}")
                for badge in badges:
                    st.markdown(f"- {badge}")


def render_claims(state: dict[str, Any]) -> None:
    """Display manuscript claims with support linkage."""

    claims = state.get("claim_drafts", [])
    supports = state.get("support_drafts", [])
    if not claims:
        st.info(translate("info_no_claims"))
        return

    st.subheader(translate("section_claims"))

    support_counts: dict[str, int] = {}
    for s in supports:
        cid = s.get("claim_id", "")
        support_counts[cid] = support_counts.get(cid, 0) + 1

    rows = []
    for c in claims:
        cid = c.get("claim_id", "")
        count = support_counts.get(cid, 0)
        rows.append(
            {
                translate("col_claim_type"): c.get("claim_type", ""),
                translate("col_claim_text"): c.get("text", "")[:200],
                translate("col_certainty"): c.get("certainty", ""),
                translate("col_has_support"): (
                    translate("label_yes") if count else translate("label_no")
                ),
                translate("col_support_count"): count,
                translate("col_ref_numbers"): str(c.get("referenced_numbers", [])),
            }
        )
    st.dataframe(rows, use_container_width=True, hide_index=True)


def render_citations(state: dict[str, Any]) -> None:
    """Display citation drafts linking claims to literature."""

    citations = state.get("citation_drafts", [])
    if not citations:
        st.info(translate("info_no_citations"))
        return

    st.subheader(translate("section_citations"))
    rows = []
    for c in citations:
        rows.append(
            {
                translate("col_citation_key"): short_hash(
                    c.get("citation_key", ""), length=20
                ),
                translate("col_lit_record"): c.get("literature_record_id", "")[:16],
                translate("col_section"): c.get("section_id", "")[:24],
                translate("col_claim_type"): c.get("claim_id", "")[:24],
            }
        )
    st.dataframe(rows, use_container_width=True, hide_index=True)


def render_claim_audit(state: dict[str, Any]) -> None:
    """Display claim audit results."""

    artifacts = state.get("artifacts", {})
    audit = artifacts.get("claim_audit")
    if audit is None:
        st.info(translate("info_no_claim_audit"))
        return

    st.subheader(translate("section_claim_audit"))

    status = audit.get("status", "")
    col1, col2 = st.columns(2)
    col1.metric(
        translate("label_audit_passed"),
        translate("label_yes") if "passed" in status else translate("label_no"),
    )
    col2.metric(
        translate("label_audit_errors"),
        "0" if "passed" in status else ">0",
    )
    st.caption(f"status: {status}")


def render_review(state: dict[str, Any]) -> None:
    """Display reviewer critique findings and revision decisions."""

    findings = state.get("review_findings", [])
    decisions = state.get("revision_decisions", [])
    revision_summary = state.get("revision_summary")
    if not findings and not revision_summary:
        st.info(translate("info_no_review"))
        return

    st.subheader(translate("section_review"))

    if findings:
        decision_map = {  # noqa: F841
            d.get("finding_id", ""): d.get("decision", "") for d in decisions
        }
        rows = []
        for f in findings:
            rows.append(
                {
                    translate("col_category"): f.get("category", ""),
                    translate("col_severity"): f.get("severity", ""),
                    translate("col_location"): f.get("location", ""),
                    translate("col_rationale"): f.get("rationale", ""),
                    translate("col_recommendation"): f.get("recommendation", ""),
                    translate("col_status"): f.get("status", ""),
                }
            )
        st.dataframe(rows, use_container_width=True, hide_index=True)

    if revision_summary:
        with st.expander(translate("section_revision"), expanded=False):
            col1, col2, col3, col4 = st.columns(4)
            col1.metric(
                translate("label_revision_round"),
                revision_summary.get("round", 0),
            )
            col2.metric(
                translate("label_accepted"),
                revision_summary.get("accepted_count", 0),
            )
            col3.metric(
                translate("label_rejected"),
                revision_summary.get("rejected_count", 0),
            )
            col4.metric(
                translate("label_deferred"),
                revision_summary.get("deferred_count", 0),
            )


def render_revision_diff(state: dict[str, Any]) -> None:
    """Display section-level before/after diff as side-by-side cards."""

    import difflib

    revision_summary = state.get("revision_summary")
    if revision_summary is None:
        return

    diffs = revision_summary.get("section_diffs", [])
    if not diffs:
        return

    st.subheader(translate("section_revision_diff"))

    for d in diffs:
        section_id = d.get("section_id", "")
        before = d.get("before_content", "")
        after = d.get("after_content", "")
        resolved = d.get("resolved_finding_ids", [])

        if before == after:
            continue

        with st.expander(section_id, expanded=False):
            if resolved:
                st.caption(
                    f"{translate('label_resolved_findings')}: "
                    f"{', '.join(resolved)}"
                )

            col_before, col_after = st.columns(2, gap="medium")
            with col_before, st.container(border=True):
                st.markdown(f"**{translate('col_before')}**")
                if before:
                    before_lines = before.splitlines(keepends=False)
                    after_lines = after.splitlines(keepends=False)
                    # Use ndiff to identify removed/changed lines
                    diff = difflib.ndiff(before_lines, after_lines)
                    removed_lines = [
                        line[2:]
                        for line in diff
                        if line.startswith("- ")
                    ]
                    if removed_lines:
                        _render_highlighted_lines(
                            removed_lines, tone="danger"
                        )
                    else:
                        st.write(before)
                else:
                    st.caption(translate("label_no_changes"))

            with col_after, st.container(border=True):
                st.markdown(f"**{translate('col_after')}**")
                if after:
                    before_lines = before.splitlines(keepends=False)
                    after_lines = after.splitlines(keepends=False)
                    diff = difflib.ndiff(before_lines, after_lines)
                    added_lines = [
                        line[2:]
                        for line in diff
                        if line.startswith("+ ")
                    ]
                    if added_lines:
                        _render_highlighted_lines(
                            added_lines, tone="success"
                        )
                    else:
                        st.write(after)
                else:
                    st.caption(translate("label_no_changes"))


def render_claim_traceability(state: dict[str, Any]) -> None:
    """Display claim traceability chain."""

    claims = state.get("claim_drafts", [])
    if not claims:
        return

    supports = state.get("support_drafts", [])
    evidence = state.get("evidence_drafts", [])
    results = state.get("result_drafts", [])
    spans = state.get("source_span_drafts", [])
    records = state.get("literature_record_drafts", [])
    citations = state.get("citation_drafts", [])

    support_by_claim: dict[str, list[dict[str, Any]]] = {}
    for s in supports:
        cid = s.get("claim_id", "")
        support_by_claim.setdefault(cid, []).append(s)

    evidence_by_id: dict[str, dict[str, Any]] = {
        e.get("evidence_id", ""): e for e in evidence
    }
    result_by_id: dict[str, dict[str, Any]] = {
        r.get("result_id", ""): r for r in results
    }
    span_by_id: dict[str, dict[str, Any]] = {s.get("span_id", ""): s for s in spans}
    record_by_id: dict[str, dict[str, Any]] = {
        r.get("record_id", ""): r for r in records
    }
    citation_by_claim: dict[str, list[dict[str, Any]]] = {}
    for c in citations:
        cid = c.get("claim_id", "")
        if cid:
            citation_by_claim.setdefault(cid, []).append(c)

    st.subheader(translate("section_traceability"))

    for c in claims:
        cid = c.get("claim_id", "")
        ctype = c.get("claim_type", "")
        text = c.get("text", "")
        certainty = c.get("certainty", "")
        section_id = c.get("section_id", "")

        claim_supports = support_by_claim.get(cid, [])
        has_support = len(claim_supports) > 0
        is_factual = ctype in ("factual", "result", "statistical")

        header = f"`{cid}` [{ctype}]"
        if not has_support and is_factual:
            header += " \u26a0\ufe0f"

        with st.expander(header, expanded=False):
            st.write(text)
            st.caption(
                f"{translate('col_certainty')}: {certainty} "
                f"| {translate('col_section_type')}: "
                f"{section_id}"
            )

            if not has_support and is_factual:
                st.warning(translate("label_claim_unsupported_warning"))

            if claim_supports:
                for s in claim_supports:
                    stype = s.get("support_type", "")
                    source_id = s.get("source_id", "")
                    relation = s.get("relation", "")
                    audit_status = s.get("audit_status", "")

                    st.markdown(
                        f"**{translate('label_support_type')}:** "
                        f"{stype} "
                        f"| **{translate('label_relation')}:** "
                        f"{relation} "
                        f"| **"
                        f"{translate('label_audit_status')}:** "
                        f"{audit_status}"
                    )

                    if stype == "evidence_item":
                        ev = evidence_by_id.get(source_id, {})
                        if ev:
                            st.markdown(
                                f"  - **"
                                f"{translate('col_concept')}:** "
                                f"{ev.get('concept', '')}"
                            )
                            st.markdown(
                                f"  - **"
                                f"{translate('col_value')}:** "
                                f"{ev.get('value', '')}"
                            )
                            if ev.get("units"):
                                st.markdown(
                                    f"  - {translate('col_unit')}: {ev.get('units')}"
                                )
                            if ev.get("population"):
                                st.markdown(
                                    f"  - "
                                    f"{translate('col_population')}:"
                                    f" {ev.get('population')}"
                                )
                            span_ids = ev.get("source_span_ids", [])
                            for sid in span_ids:
                                span = span_by_id.get(sid, {})
                                if span:
                                    rec_id = span.get(
                                        "literature_record_id",
                                        "",
                                    )
                                    rec = record_by_id.get(rec_id, {})
                                    st.markdown(
                                        f"  - "
                                        f"{translate('label_span_page')}:"
                                        f" {span.get('page', '')} "
                                        f"| "
                                        f"{translate('label_span_section')}:"
                                        f" "
                                        f"{span.get('section_label', '')}"
                                    )
                                    if rec:
                                        st.markdown(
                                            f"  - "
                                            f"{translate('col_title')}:"
                                            f" "
                                            f"{rec.get('title', '')} "
                                            f"| DOI: "
                                            f"{rec.get('doi', '') or '-'}"
                                        )
                                    if span.get("quote_hash"):
                                        st.caption(
                                            f"{translate('label_quote_hash')}:"
                                            f" "
                                            f"{str(span.get('quote_hash', ''))[:24]}..."
                                        )

                    elif stype == "statistical_result":
                        res = result_by_id.get(source_id, {})
                        if res:
                            lower = res.get("uncertainty_lower")
                            upper = res.get("uncertainty_upper")
                            ci_str = (
                                f"{lower} - {upper}"
                                if lower is not None and upper is not None
                                else ""
                            )
                            st.markdown(
                                f"  - **"
                                f"{translate('col_estimate')}:** "
                                f"{res.get('estimate', '')}"
                            )
                            if ci_str:
                                st.markdown(f"  - **{translate('col_ci')}:** {ci_str}")
                            st.markdown(
                                f"  - **"
                                f"{translate('col_p_value')}:** "
                                f"{res.get('p_value', '')}"
                            )
                            st.markdown(
                                f"  - **"
                                f"{translate('col_method')}:** "
                                f"{res.get('method', '')}"
                            )
                    st.markdown("---")

            claim_citations = citation_by_claim.get(cid, [])
            if claim_citations:
                for cit in claim_citations:
                    rec_id = cit.get("literature_record_id", "")
                    rec = record_by_id.get(rec_id, {})
                    locator = cit.get("locator", "")
                    st.markdown(
                        f"**"
                        f"{translate('col_citation_key')}:** "
                        f"{cit.get('citation_key', '')}"
                    )
                    if rec:
                        st.markdown(
                            f"  - {translate('col_title')}: {rec.get('title', '')}"
                        )
                        st.markdown(f"  - DOI: {rec.get('doi', '') or '-'}")
                    if locator:
                        st.markdown(
                            f"  - {translate('label_citation_locator')}: {locator}"
                        )
