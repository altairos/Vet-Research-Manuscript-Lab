"""Dashboard workspace — the project command center.

Shown as the default first workspace. Summarises current pipeline status,
next action, risk counts, cost, recent artifacts, and audit log into a
glanceable layout so the researcher immediately knows "what to do next".
"""

from __future__ import annotations

import html
from datetime import datetime
from typing import Any

import streamlit as st

from vet_manuscript_lab.ui.application import Application
from vet_manuscript_lab.ui.components import (
    Metric,
    artifact_card,
    empty_state_card,
    metric_strip,
    next_action_hero,
    severity_pill,
)
from vet_manuscript_lab.ui.i18n import (
    gate_field,
    stage_label,
    translate,
)
from vet_manuscript_lab.ui.tabs.review_queue import _SEVERITY_RANK, collect_review_items

# Mapping of raw artifact role keys to i18n keys.
_ARTIFACT_ROLE_I18N: dict[str, str] = {
    "guideline_mapping": "section_guideline",
    "protocol": "label_protocol_version",
    "search_strategy": "section_search_strategy",
    "evidence_ledger": "section_evidence",
    "analysis_plan": "section_analysis_plan",
    "analysis_run": "label_analysis_run",
    "manuscript": "section_manuscript",
    "claim_audit": "section_claim_audit",
    "revision_plan": "section_revision",
    "ai_usage_log": "section_usage",
    "audit_report": "dash_audit_log",
    "compliance_audit": "section_compliance",
    "export_package": "section_export",
    "argument_spine": "label_argument_spine",
}

# Mapping of raw event type strings to i18n keys.
_EVENT_TYPE_I18N: dict[str, str] = {
    "stage_started": "audit_stage_started",
    "stage_completed": "audit_stage_completed",
    "gate_approved": "audit_gate_approved",
    "gate_rejected": "audit_gate_rejected",
    "artifact_created": "audit_artifact_created",
    "artifact_locked": "audit_artifact_locked",
    "run_started": "audit_run_started",
    "run_completed": "audit_run_completed",
}


def _format_cost(state: dict[str, Any]) -> str:
    """Return a human-readable cost string from model usage summary."""

    usage = state.get("model_usage_summary")
    if not isinstance(usage, dict):
        return "$0.00"
    total_cents = usage.get("total_cost_cents", 0)
    try:
        return f"${total_cents / 100:.2f}"
    except (TypeError, ValueError):
        return "$0.00"


def _artifact_role_label(role: str) -> str:
    """Translate a raw artifact role key into a user-friendly label."""

    i18n_key = _ARTIFACT_ROLE_I18N.get(role)
    if i18n_key:
        text = translate(i18n_key)
        if text != i18n_key:
            return text
    # Fallback: prettify the raw key
    return role.replace("_", " ").title()


def _event_type_label(event_type: str) -> str:
    """Translate a raw audit event type into a user-friendly label."""

    i18n_key = _EVENT_TYPE_I18N.get(event_type)
    if i18n_key:
        text = translate(i18n_key)
        if text != i18n_key:
            return text
    return event_type.replace("_", " ").title()


def _format_timestamp(raw: str) -> str:
    """Convert ISO-8601 timestamp to readable 'YYYY-MM-DD HH:MM:SS' format."""

    if not raw:
        return "-"
    try:
        # Handle 'Z' suffix and fractional seconds
        ts = raw.replace("Z", "+00:00")
        dt = datetime.fromisoformat(ts)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return raw


def _artifact_status_label(status: str) -> str:
    key = f"artifact_status_{status}"
    text = translate(key)
    return text if text != key else status


def render_dashboard(
    state: dict[str, Any],
    pending: list[dict[str, Any]],
    thread_id: str | None,
    app: Application | None = None,
) -> None:
    """Render the Dashboard command center.

    Parameters mirror what ``render_workflow`` already computes so the
    dashboard can show live pipeline state without re-fetching.
    When *app* is provided and no thread exists, an onboarding empty-state
    with Golden Project entry is shown instead of a plain message.
    """

    # -- When no pipeline run yet, show onboarding empty state ------
    if not state and not thread_id:
        if app is not None:
            from vet_manuscript_lab.ui.tabs.onboarding import render_onboarding

            render_onboarding(app)
        else:
            st.info(translate("dash_pipeline_idle"))
        return

    if not state:
        st.info(translate("dash_no_thread"))
        return

    # -- Metric strip (thin horizontal bar, replaces 4 large metric cards) --
    items = collect_review_items(state)
    critical = [i for i in items if i.severity in ("critical", "error")]
    warnings = [i for i in items if i.severity in ("warning", "high", "medium")]
    risk_tone = "danger" if critical else "warning" if warnings else "success"
    risk_value = (
        f"{len(critical)} {translate('rq_critical_items')} "
        f"\u00b7 {len(warnings)} {translate('rq_warning_items')}"
    )
    metric_strip([
        Metric(label=translate("dash_risk_summary"), value=risk_value, tone=risk_tone),
        Metric(label=translate("rq_total_items"), value=len(items)),
        Metric(label=translate("label_total_cost"), value=_format_cost(state)),
    ])

    # -- Main two-column area ---------------------------------------------
    main_col, side_col = st.columns([0.65, 0.35], gap="large")

    with main_col:
        # Next action hero — the visual centerpiece of the page
        if pending:
            gate = pending[0]
            gate_name = gate.get("gate", "")
            _render_next_action_hero(gate, gate_name)
        elif state.get("run_status") == "complete":
            st.success(translate("success_pipeline_complete"))

        # Risk summary (actionable)
        _render_risk_summary_actionable(items)

        # Artifacts (empty-state or list)
        _render_artifact_list(state)

    with side_col:
        # Audit log (collapsed) — moved here from bottom for better balance
        _render_audit_log(state)


def _render_next_action_hero(gate: dict[str, Any], gate_name: str) -> None:
    """Render the *Next Action* hero card — the page visual centerpiece.

    Displays the gate title, summary, optional lock items, and a three-button
    action row: ``View details`` / ``Request changes`` / ``Approve & continue``.
    Only the *Approve* button uses ``type="primary"`` so there is exactly one
    green button on the page.
    """

    title = gate_field(gate_name, "title")
    summary = gate_field(gate_name, "summary")
    next_stage = stage_label(gate.get("proposed_next_stage"))

    # Build lock items from gate data (if available)
    lock_items: list[str] = []
    # Common lock-able fields surfaced from state — these are informational
    # hints so the user understands what they are committing to.
    proposed_stage = gate.get("proposed_next_stage", "")
    if proposed_stage:
        stage_text = stage_label(proposed_stage)
        if stage_text and stage_text != proposed_stage:
            lock_items.append(stage_text)

    next_action_hero(
        title=title,
        summary=summary,
        lock_items=lock_items if lock_items else None,
        next_stage=next_stage,
    )

    # Action button row — exactly one primary button
    col_view, col_modify, col_approve = st.columns([1, 1, 1.4])
    col_view.button(
        translate("button_view_details"),
        width="stretch",
        key=f"dash_view_{gate_name}",
    )
    col_modify.button(
        translate("button_request_changes"),
        width="stretch",
        key=f"dash_modify_{gate_name}",
    )
    col_approve.button(
        translate("button_approve_continue"),
        type="primary",
        width="stretch",
        key=f"dash_approve_{gate_name}",
    )


def _render_risk_summary_actionable(items: list[Any]) -> None:
    """Render an actionable risk summary: counts + top-2 items inline."""

    st.markdown(f"#### {translate('dash_risk_summary')}")

    if not items:
        st.success(translate("dash_risk_none"))
        return

    critical = [i for i in items if i.severity in ("critical", "error")]
    warnings = [i for i in items if i.severity in ("warning", "high", "medium")]

    # Inline count (not large metric cards)
    st.markdown(
        f"**{len(critical)} {translate('rq_critical_items')} "
        f"\u00b7 {len(warnings)} {translate('rq_warning_items')}**"
    )

    # Show top-2 highest-priority items inline
    top = sorted(
        items, key=lambda i: -_SEVERITY_RANK.get(i.severity, 0)
    )[:2]
    for item in top:
        st.markdown(
            f"{severity_pill(item.severity)} "
            f'<span class="risk-inline-title">{html.escape(item.title[:65])}</span>',
            help=item.detail if item.detail else None,
            unsafe_allow_html=True,
        )

    if len(items) > 2:
        st.caption(
            translate("rq_items_showing").format(
                shown=min(2, len(items)), total=len(items)
            )
        )


def _render_artifact_list(state: dict[str, Any]) -> None:
    """Render recent artifacts, or a meaningful empty state when none exist."""

    st.markdown(f"#### {translate('dash_recent_artifacts')}")

    artifacts = state.get("artifacts", {})
    artifact_dicts = {
        k: v for k, v in artifacts.items() if isinstance(v, dict)
    }
    if not artifact_dicts:
        empty_state_card(
            icon="\U0001f4c4",
            title=translate("artifacts_empty_title"),
            body=translate("artifacts_empty_body"),
        )
        return

    # Show last 3 artifacts as cards
    recent = list(artifact_dicts.items())[-3:]
    for role, art in recent:
        artifact_card(
            title=_artifact_role_label(role),
            version=str(art.get("version", "-")),
            status=_artifact_status_label(art.get("status", "")),
            artifact_type=art.get("artifact_type", ""),
        )


def _render_audit_log(state: dict[str, Any]) -> None:
    """Render the audit event log in a collapsed expander."""

    events = state.get("audit_events", [])
    if not events:
        return

    with st.expander(
        f"{translate('dash_audit_log')} ({len(events)})", expanded=False
    ):
        rows: list[dict[str, Any]] = []
        for ev in events[-20:]:  # last 20 events
            if not isinstance(ev, dict):
                continue
            rows.append(
                {
                    translate("col_occurred_at"): _format_timestamp(
                        ev.get("occurred_at", "")
                    ),
                    translate("col_event_type"): _event_type_label(
                        ev.get("event_type", "")
                    ),
                    translate("col_stage"): stage_label(ev.get("stage")),
                    translate("col_message"): ev.get("message", ""),
                }
            )
        rows.reverse()  # newest first
        if rows:
            st.dataframe(rows, width="stretch", hide_index=True)
