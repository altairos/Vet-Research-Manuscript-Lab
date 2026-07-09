"""Review queue and provenance inspector (tab: Needs Review).

This module implements the *审稿式 UI 工作台* concept (Phase G):

* **Needs Review Queue** - aggregates low-confidence evidence, un-locatable
  source spans, high-risk claims, unresolved methodology/review/compliance
  findings, and word-count / over-limit items into a single prioritised list.

* **Provenance Inspector** - lets the reviewer click on a claim, evidence
  item, or statistical result and trace it all the way back to the
  ``SourceSpan`` / ``AnalysisRun`` that produced it.

The heavy lifting lives in :func:`collect_review_items`, a pure function that
returns a sorted list of :class:`ReviewItem` dataclasses.  This separation
makes the aggregation logic unit-testable without spinning up Streamlit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import streamlit as st

from vet_manuscript_lab.ui.components import (
    finding_card,
    short_hash,
)
from vet_manuscript_lab.ui.i18n import translate

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

# Severity ranking — higher number = more urgent.
_SEVERITY_RANK: dict[str, int] = {
    "critical": 4,
    "error": 4,
    "high": 3,
    "warning": 2,
    "medium": 2,
    "info": 1,
    "low": 1,
}

# Category i18n key map.
_CATEGORY_I18N: dict[str, str] = {
    "evidence_low_confidence": "rq_category_evidence_low_confidence",
    "evidence_no_span": "rq_category_evidence_no_span",
    "evidence_needs_review": "rq_category_evidence_needs_review",
    "claim_high_risk": "rq_category_claim_high_risk",
    "claim_unsupported": "rq_category_claim_unsupported",
    "methodology_finding": "rq_category_methodology_finding",
    "review_finding": "rq_category_review_finding",
    "compliance_finding": "rq_category_compliance_finding",
    "section_over_limit": "rq_category_section_over_limit",
    "exploratory_in_abstract": "rq_category_exploratory_in_abstract",
}


@dataclass(frozen=True, slots=True)
class ReviewItem:
    """A single actionable item surfaced in the Needs Review Queue.

    ``source_type`` identifies the domain object kind so the Provenance
    Inspector can render the appropriate drill-down.  ``source_id`` is the
    object's identifier (``evidence_id``, ``claim_id``, ``finding_id`` …).
    """

    item_id: str
    category: str
    severity: str
    title: str
    detail: str
    source_type: str  # evidence | claim | finding | section | audit_warning
    source_id: str
    related_ids: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Pure aggregation logic
# ---------------------------------------------------------------------------


def collect_review_items(state: dict[str, Any]) -> list[ReviewItem]:
    """Scan *state* and return every item that needs human attention.

    The function inspects evidence drafts, source spans, claims, methodology
    findings, review findings, compliance findings, claim-audit warnings, and
    section word-counts.  Items are sorted by severity (descending) then
    category then item_id for deterministic ordering.
    """

    items: list[ReviewItem] = []

    # -- 1. Evidence low confidence / no span / needs review -----------------
    evidence = state.get("evidence_drafts", [])
    spans = state.get("source_span_drafts", [])
    span_ids = {s.get("span_id", "") for s in spans if isinstance(s, dict)}

    for ev in evidence:
        eid = ev.get("evidence_id", "")
        if not eid:
            continue

        requires_review = ev.get("requires_human_review", False)
        extraction_status = ev.get("extraction_status", "")
        source_span_ids = ev.get("source_span_ids", [])

        # No source spans at all
        if not source_span_ids:
            items.append(
                ReviewItem(
                    item_id=f"evidence_no_span:{eid}",
                    category="evidence_no_span",
                    severity="critical",
                    title=ev.get("concept", eid),
                    detail=translate("rq_detail_evidence_no_span"),
                    source_type="evidence",
                    source_id=eid,
                )
            )
        else:
            # Spans referenced but not found in state
            missing = [sid for sid in source_span_ids if sid not in span_ids]
            if missing:
                items.append(
                    ReviewItem(
                        item_id=f"evidence_missing_span:{eid}",
                        category="evidence_no_span",
                        severity="warning",
                        title=ev.get("concept", eid),
                        detail=translate("rq_detail_evidence_missing_span"),
                        source_type="evidence",
                        source_id=eid,
                        related_ids=missing,
                    )
                )

        if requires_review or extraction_status == "needs_review":
            items.append(
                ReviewItem(
                    item_id=f"evidence_needs_review:{eid}",
                    category="evidence_needs_review",
                    severity="warning",
                    title=ev.get("concept", eid),
                    detail=translate("rq_detail_evidence_needs_review"),
                    source_type="evidence",
                    source_id=eid,
                )
            )

        # Low certainty heuristic: check for "low" in any certainty-like field
        metadata = ev.get("metadata", {})
        certainty_raw = str(metadata.get("certainty", "")).lower()
        if "low" in certainty_raw or "uncertain" in certainty_raw:
            items.append(
                ReviewItem(
                    item_id=f"evidence_low_confidence:{eid}",
                    category="evidence_low_confidence",
                    severity="warning",
                    title=ev.get("concept", eid),
                    detail=translate("rq_detail_evidence_low_confidence"),
                    source_type="evidence",
                    source_id=eid,
                )
            )

    # -- 2. Claim high-risk / unsupported -----------------------------------
    claims = state.get("claim_drafts", [])
    supports = state.get("support_drafts", [])
    support_by_claim: dict[str, int] = {}
    for sp in supports:
        cid = sp.get("claim_id", "")
        support_by_claim[cid] = support_by_claim.get(cid, 0) + 1

    for c in claims:
        cid = c.get("claim_id", "")
        if not cid:
            continue
        ctype = c.get("claim_type", "")
        certainty = str(c.get("certainty", "")).lower()
        count = support_by_claim.get(cid, 0)
        text = c.get("text", "")

        # Factual/result claims without support → critical
        if ctype in ("factual", "result", "statistical") and count == 0:
            items.append(
                ReviewItem(
                    item_id=f"claim_unsupported:{cid}",
                    category="claim_unsupported",
                    severity="critical",
                    title=text[:80],
                    detail=translate("rq_detail_claim_unsupported"),
                    source_type="claim",
                    source_id=cid,
                )
            )

        # Hypothesis claims in Abstract or high-certainty claims flagged
        if ctype == "hypothesis" and "abstract" in c.get("section_id", "").lower():
            items.append(
                ReviewItem(
                    item_id=f"claim_high_risk:{cid}",
                    category="claim_high_risk",
                    severity="warning",
                    title=text[:80],
                    detail=translate("rq_detail_claim_hypothesis_abstract"),
                    source_type="claim",
                    source_id=cid,
                )
            )

        # Over-certain claims (high certainty without statistical support)
        if "high" in certainty and count == 0:
            items.append(
                ReviewItem(
                    item_id=f"claim_overcertain:{cid}",
                    category="claim_high_risk",
                    severity="warning",
                    title=text[:80],
                    detail=translate("rq_detail_claim_overcertain"),
                    source_type="claim",
                    source_id=cid,
                )
            )

    # -- 3. Methodology findings (open) -------------------------------------
    for f in state.get("methodology_findings", []):
        fid = f.get("finding_id", "")
        if not fid or f.get("status", "") == "addressed":
            continue
        severity = f.get("severity", "info")
        items.append(
            ReviewItem(
                item_id=f"methodology:{fid}",
                category="methodology_finding",
                severity=severity,
                title=f.get("rationale", fid)[:80],
                detail=f.get("recommendation", ""),
                source_type="finding",
                source_id=fid,
            )
        )

    # -- 4. Review findings (open) ------------------------------------------
    for f in state.get("review_findings", []):
        fid = f.get("finding_id", "")
        if not fid:
            continue
        status = f.get("status", "")
        if status in ("accepted", "rejected"):
            continue
        severity = f.get("severity", "info")
        items.append(
            ReviewItem(
                item_id=f"review:{fid}",
                category="review_finding",
                severity=severity,
                title=f.get("rationale", fid)[:80],
                detail=f.get("recommendation", ""),
                source_type="finding",
                source_id=fid,
            )
        )

    # -- 5. Compliance findings (blocking) ----------------------------------
    for f in state.get("compliance_findings", []):
        fid = f.get("finding_id", "")
        if not fid:
            continue
        severity = f.get("severity", "info")
        if severity in ("critical", "error", "high"):
            items.append(
                ReviewItem(
                    item_id=f"compliance:{fid}",
                    category="compliance_finding",
                    severity=severity,
                    title=f.get("recommendation", fid)[:80],
                    detail=f.get("evidence", ""),
                    source_type="finding",
                    source_id=fid,
                )
            )

    # -- 6. Claim-audit warnings (exploratory-in-abstract) ------------------
    artifacts = state.get("artifacts", {})
    audit = artifacts.get("claim_audit")
    if isinstance(audit, dict):
        warnings = audit.get("warnings", [])
        if isinstance(warnings, list):
            for w in warnings:
                wid = w.get("warning_id", "") or w.get("claim_id", "")
                items.append(
                    ReviewItem(
                        item_id=f"audit_warning:{wid}",
                        category="exploratory_in_abstract",
                        severity="warning",
                        title=w.get("message", wid)[:80],
                        detail=w.get("detail", ""),
                        source_type="audit_warning",
                        source_id=str(wid),
                    )
                )

    # -- 7. Section over-limit ----------------------------------------------
    sections = state.get("section_drafts", [])
    for s in sections:
        sid = s.get("section_id", "")
        word_count = s.get("word_count", 0)
        stype = s.get("section_type", "")
        limit = _SECTION_WORD_LIMITS.get(stype)
        if limit and word_count > limit:
            items.append(
                ReviewItem(
                    item_id=f"section_over_limit:{sid}",
                    category="section_over_limit",
                    severity="warning",
                    title=f"{stype}: {word_count} / {limit}",
                    detail=translate("rq_detail_section_over_limit"),
                    source_type="section",
                    source_id=sid,
                )
            )

    # -- Sort by severity desc, then category, then id ----------------------
    items.sort(
        key=lambda r: (
            -_SEVERITY_RANK.get(r.severity, 0),
            r.category,
            r.item_id,
        )
    )
    return items


# Rough word-count limits per section type for soft warnings.
_SECTION_WORD_LIMITS: dict[str, int] = {
    "abstract": 350,
    "introduction": 800,
    "methods": 2000,
    "results": 2500,
    "discussion": 2000,
    "conclusion": 500,
}


# ---------------------------------------------------------------------------
# Streamlit rendering
# ---------------------------------------------------------------------------


def render_review_queue(state: dict[str, Any]) -> None:
    """Display the Needs Review Queue as a prioritised, filterable list."""

    st.subheader(translate("rq_header"))

    items = collect_review_items(state)
    if not items:
        st.success(translate("rq_empty"))
        return

    # Summary metrics
    critical = sum(1 for i in items if i.severity in ("critical", "error"))
    warning = sum(1 for i in items if i.severity in ("warning", "high", "medium"))
    col1, col2, col3 = st.columns(3)
    col1.metric(translate("rq_total_items"), len(items))
    col2.metric(translate("rq_critical_items"), critical)
    col3.metric(translate("rq_warning_items"), warning)

    # Category filter
    categories = sorted({i.category for i in items})
    category_labels = {
        cat: translate(_CATEGORY_I18N.get(cat, "rq_category_other"))
        for cat in categories
    }
    selected = st.multiselect(
        translate("rq_filter_category"),
        options=categories,
        format_func=lambda c: category_labels.get(c, c),
    )
    visible = [i for i in items if not selected or i.category in selected]

    st.caption(
        translate("rq_items_showing").format(shown=len(visible), total=len(items))
    )

    # Render items as finding-card style with collapsible details
    for item in visible:
        cat_label = translate(_CATEGORY_I18N.get(item.category, "rq_category_other"))
        finding_card(
            severity=item.severity,
            title=item.title,
            location=cat_label,
            detail=item.detail,
        )
        with st.expander(translate("show_details"), expanded=False):
            meta_parts = [
                f"**{translate('rq_source_type')}:** `{item.source_type}`",
                f"**{translate('rq_source_id')}:** "
                f"`{short_hash(item.source_id)}`",
            ]
            if item.related_ids:
                meta_parts.append(
                    f"**{translate('rq_related')}:** "
                    f"{', '.join(short_hash(rid) for rid in item.related_ids[:5])}"
                )
            st.caption(" | ".join(meta_parts))


def render_provenance_inspector(state: dict[str, Any]) -> None:
    """Interactive provenance drill-down for a selected object.

    Lets the reviewer choose an object type (claim / evidence / result) and
    then trace it through the full chain:

    ``Claim → Support → EvidenceItem / StatResult → SourceSpan → LiteratureRecord``
    ``Claim → Support → StatResult → AnalysisRun``
    """

    st.subheader(translate("rq_provenance_header"))

    obj_type = st.selectbox(
        translate("rq_provenance_select_type"),
        options=["claim", "evidence", "result"],
        format_func=lambda t: {
            "claim": translate("rq_type_claim"),
            "evidence": translate("rq_type_evidence"),
            "result": translate("rq_type_result"),
        }.get(t, t),
    )

    claims = state.get("claim_drafts", [])
    evidence = state.get("evidence_drafts", [])
    results = state.get("result_drafts", [])
    supports = state.get("support_drafts", [])
    spans = state.get("source_span_drafts", [])
    records = state.get("literature_record_drafts", [])
    citations = state.get("citation_drafts", [])
    analysis_run = state.get("analysis_run_summary")

    # Build lookup tables
    span_by_id: dict[str, dict[str, Any]] = {
        s.get("span_id", ""): s for s in spans if isinstance(s, dict)
    }
    record_by_id: dict[str, dict[str, Any]] = {
        r.get("record_id", ""): r for r in records if isinstance(r, dict)
    }
    result_by_id: dict[str, dict[str, Any]] = {
        r.get("result_id", ""): r for r in results if isinstance(r, dict)
    }
    evidence_by_id: dict[str, dict[str, Any]] = {
        e.get("evidence_id", ""): e for e in evidence if isinstance(e, dict)
    }

    if obj_type == "claim":
        _provenance_for_claim(
            claims,
            supports,
            evidence_by_id,
            result_by_id,
            span_by_id,
            record_by_id,
            citations,
            analysis_run,
        )
    elif obj_type == "evidence":
        _provenance_for_evidence(
            evidence,
            supports,
            claims,
            span_by_id,
            record_by_id,
        )
    else:
        _provenance_for_result(results, supports, claims, analysis_run)


def _provenance_for_claim(
    claims: list[dict[str, Any]],
    supports: list[dict[str, Any]],
    evidence_by_id: dict[str, dict[str, Any]],
    result_by_id: dict[str, dict[str, Any]],
    span_by_id: dict[str, dict[str, Any]],
    record_by_id: dict[str, dict[str, Any]],
    citations: list[dict[str, Any]],
    analysis_run: dict[str, Any] | None,
) -> None:
    """Render provenance chain starting from a claim."""

    if not claims:
        st.info(translate("rq_provenance_no_claims"))
        return

    options = {c.get("claim_id", ""): c for c in claims}
    selected_id = st.selectbox(
        translate("rq_provenance_select_claim"),
        options=list(options.keys()),
        format_func=lambda cid: f"{cid}: {options[cid].get('text', '')[:50]}",
    )
    if not selected_id:
        return

    claim = options[selected_id]
    with st.container(border=True):
        st.markdown(f"**{translate('rq_provenance_claim_card')}**")
        st.write(claim.get("text", ""))
        st.caption(
            f"{translate('col_certainty')}: {claim.get('certainty', '')} "
            f"| {translate('col_section_type')}: {claim.get('section_id', '')}"
        )

    # Find support links
    claim_supports = [s for s in supports if s.get("claim_id") == selected_id]
    if not claim_supports:
        st.warning(translate("rq_provenance_no_support"))
    else:
        st.markdown(f"### {translate('rq_provenance_support_chain')}")
        for sp in claim_supports:
            stype = sp.get("support_type", "")
            source_id = sp.get("source_id", "")
            relation = sp.get("relation", "")

            if stype == "evidence_item":
                ev = evidence_by_id.get(source_id, {})
                if ev:
                    with st.container(border=True):
                        st.markdown(
                            f"**{translate('rq_provenance_evidence_card')}:** "
                            f"{ev.get('concept', '')}"
                        )
                        st.caption(
                            f"{translate('label_support_type')}: {stype} "
                            f"| {translate('label_relation')}: {relation}"
                        )
                        _render_span_chain(
                            ev.get("source_span_ids", []),
                            span_by_id,
                            record_by_id,
                        )
            elif stype == "statistical_result":
                res = result_by_id.get(source_id, {})
                if res:
                    with st.container(border=True):
                        st.markdown(
                            f"**{translate('rq_provenance_result_card')}:** "
                            f"{res.get('estimand', '')}"
                        )
                        est = res.get("estimate", "")
                        ci = res.get("uncertainty_lower")
                        cj = res.get("uncertainty_upper")
                        ci_str = (
                            f"{ci} - {cj}"
                            if ci is not None and cj is not None
                            else "-"
                        )
                        st.write(
                            f"{translate('col_estimate')}: **{est}** "
                            f"| {translate('col_ci')}: {ci_str} "
                            f"| {translate('col_p_value')}: {res.get('p_value', '')}"
                        )
                        st.caption(
                            f"{translate('col_method')}: {res.get('method', '')}"
                        )
                        if analysis_run:
                            with st.expander(
                                translate("rq_provenance_analysis_card"),
                                expanded=False,
                            ):
                                st.write(
                                    f"{translate('rq_run_id')}: "
                                    f"`{short_hash(analysis_run.get('run_id', ''))}`"
                                )
                                st.write(
                                    f"{translate('rq_provenance_status')}: "
                                    f"{analysis_run.get('status', '')}"
                                )
                                seed = analysis_run.get("seed")
                                if seed is not None:
                                    st.caption(
                                        f"{translate('label_seed')}: {seed}"
                                    )
                                pkg_versions = analysis_run.get(
                                    "package_versions", {}
                                )
                                if isinstance(pkg_versions, dict) and pkg_versions:
                                    st.caption(
                                        f"{translate('label_package_versions')}: "
                                        f"{', '.join(
                                            f'{k}=={v}'
                                            for k, v in list(pkg_versions.items())[:6]
                                        )}"
                                    )

    # Citations
    claim_citations = [c for c in citations if c.get("claim_id") == selected_id]
    if claim_citations:
        st.markdown(f"### {translate('section_citations')}")
        for cit in claim_citations:
            rec_id = cit.get("literature_record_id", "")
            rec = record_by_id.get(rec_id, {})
            with st.container(border=True):
                st.write(
                    f"**{translate('col_citation_key')}:** "
                    f"`{cit.get('citation_key', '')}`"
                )
                if rec:
                    st.caption(
                        f"{translate('col_title')}: {rec.get('title', '')} | "
                        f"DOI: {rec.get('doi', '') or '-'}"
                    )


def _render_span_chain(
    span_ids: list[str],
    span_by_id: dict[str, dict[str, Any]],
    record_by_id: dict[str, dict[str, Any]],
) -> None:
    """Render the source-span → literature-record sub-chain as nested cards."""

    for sid in span_ids:
        span = span_by_id.get(sid, {})
        if not span:
            st.caption(
                f"{translate('rq_provenance_span_card')}: "
                f"`{short_hash(sid)}` ({translate('rq_provenance_span_missing')})"
            )
            continue
        rec_id = span.get("literature_record_id", "")
        rec = record_by_id.get(rec_id, {})
        with st.container(border=True):
            st.write(
                f"**{translate('rq_provenance_span_card')}:** "
                f"{translate('label_span_page')} {span.get('page', '')} "
                f"| {translate('label_span_section')}: "
                f"{span.get('section_label', '')}"
            )
            if rec:
                st.caption(
                    f"{translate('col_title')}: {rec.get('title', '')} | "
                    f"DOI: {rec.get('doi', '') or '-'}"
                )
            qh = span.get("quote_hash", "")
            if qh:
                with st.expander(
                    translate("show_provenance_details"), expanded=False
                ):
                    st.code(
                        f"{translate('label_quote_hash')}: {qh}",
                        language="text",
                    )


def _provenance_for_evidence(
    evidence: list[dict[str, Any]],
    supports: list[dict[str, Any]],
    claims: list[dict[str, Any]],
    span_by_id: dict[str, dict[str, Any]],
    record_by_id: dict[str, dict[str, Any]],
) -> None:
    """Render provenance starting from an evidence item."""

    if not evidence:
        st.info(translate("rq_provenance_no_evidence"))
        return

    options = {e.get("evidence_id", ""): e for e in evidence}
    selected_id = st.selectbox(
        translate("rq_provenance_select_evidence"),
        options=list(options.keys()),
        format_func=lambda eid: f"{eid}: {options[eid].get('concept', '')[:50]}",
    )
    if not selected_id:
        return

    ev = options[selected_id]
    st.write(f"**{translate('col_concept')}:** {ev.get('concept', '')}")
    st.write(f"**{translate('col_value')}:** {ev.get('value', '')}")
    if ev.get("units"):
        st.write(f"**{translate('col_unit')}:** {ev.get('units')}")
    if ev.get("population"):
        st.write(f"**{translate('col_population')}:** {ev.get('population')}")
    if ev.get("evidence_type"):
        st.caption(f"{translate('rq_evidence_type')}: {ev.get('evidence_type', '')}")

    # Source spans
    st.markdown(f"### {translate('section_source_spans')}")
    _render_span_chain(ev.get("source_span_ids", []), span_by_id, record_by_id)

    # Reverse: which claims cite this evidence?
    claim_ids = {
        s.get("claim_id", "")
        for s in supports
        if s.get("source_id") == selected_id
        and s.get("support_type") == "evidence_item"
    }
    if claim_ids:
        st.markdown(f"### {translate('rq_provenance_claims_using')}")
        for c in claims:
            if c.get("claim_id") in claim_ids:
                st.markdown(f"- `{c.get('claim_id', '')}`: {c.get('text', '')[:80]}")


def _provenance_for_result(
    results: list[dict[str, Any]],
    supports: list[dict[str, Any]],
    claims: list[dict[str, Any]],
    analysis_run: dict[str, Any] | None,
) -> None:
    """Render provenance starting from a statistical result."""

    if not results:
        st.info(translate("rq_provenance_no_results"))
        return

    options = {r.get("result_id", ""): r for r in results}
    selected_id = st.selectbox(
        translate("rq_provenance_select_result"),
        options=list(options.keys()),
        format_func=lambda rid: f"{rid}: {options[rid].get('estimand', '')[:50]}",
    )
    if not selected_id:
        return

    res = options[selected_id]
    st.write(f"**{translate('col_estimate')}:** {res.get('estimate', '')}")
    ci = res.get("uncertainty_lower")
    cj = res.get("uncertainty_upper")
    if ci is not None and cj is not None:
        st.write(f"**{translate('col_ci')}:** {ci} - {cj}")
    st.write(f"**{translate('col_p_value')}:** {res.get('p_value', '')}")
    st.write(f"**{translate('col_method')}:** {res.get('method', '')}")
    st.write(f"**{translate('rq_analysis_class')}:** {res.get('analysis_class', '')}")

    if res.get("exploratory"):
        st.warning(translate("rq_exploratory_result_flag"))

    if analysis_run:
        st.markdown(f"### {translate('rq_provenance_analysis_run')}")
        col1, col2, col3 = st.columns(3)
        col1.metric(translate("rq_run_id"), analysis_run.get("run_id", "")[:12])
        col2.metric(
            translate("rq_provenance_status"),
            analysis_run.get("status", ""),
        )
        col3.metric(
            translate("rq_reproducible"),
            translate("label_yes")
            if analysis_run.get("is_reproducible")
            else translate("label_no"),
        )

    # Reverse: which claims cite this result?
    claim_ids = {
        s.get("claim_id", "")
        for s in supports
        if s.get("source_id") == selected_id
        and s.get("support_type") == "statistical_result"
    }
    if claim_ids:
        st.markdown(f"### {translate('rq_provenance_claims_using')}")
        for c in claims:
            if c.get("claim_id") in claim_ids:
                st.markdown(f"- `{c.get('claim_id', '')}`: {c.get('text', '')[:80]}")
