"""Dashboard workspace — the project command center.

Shown as the default first workspace. Summarises current pipeline status,
next action, risk counts, cost, recent artifacts, and audit log into a
glanceable layout so the researcher immediately knows "what to do next".
"""

from __future__ import annotations

from typing import Any

import streamlit as st

from vet_manuscript_lab.ui.components import (
    Metric,
    approval_gate_card,
    artifact_card,
    finding_card,
    metric_strip,
    short_hash,
)
from vet_manuscript_lab.ui.i18n import (
    gate_field,
    stage_label,
    status_label,
    translate,
)
from vet_manuscript_lab.ui.tabs.review_queue import collect_review_items
from vet_manuscript_lab.ui.theme import render_phase_tracker


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


def _artifact_status_label(status: str) -> str:
    key = f"artifact_status_{status}"
    text = translate(key)
    return text if text != key else status


def render_dashboard(
    state: dict[str, Any],
    pending: list[dict[str, Any]],
    thread_id: str | None,
) -> None:
    """Render the Dashboard command center.

    Parameters mirror what ``render_workflow`` already computes so the
    dashboard can show live pipeline state without re-fetching.
    """

    # -- When no pipeline run yet, show onboarding-style empty state ------
    if not state and not thread_id:
        st.info(translate("dash_pipeline_idle"))
        return

    if not state:
        st.info(translate("dash_no_thread"))
        return

    # -- Top: status sentence ---------------------------------------------
    current_stage = stage_label(state.get("current_stage"))
    run_status = status_label(state.get("run_status"))
    st.markdown(
        f"**{translate('dash_project_status')}:** "
        f"{current_stage or '-'} · {run_status or '-'}"
    )

    # -- Summary metric strip ---------------------------------------------
    items = collect_review_items(state)
    critical = sum(1 for i in items if i.severity in ("critical", "error"))
    artifacts_count = len(
        [a for a in state.get("artifacts", {}).values() if isinstance(a, dict)]
    )
    metric_strip(
        [
            Metric(
                translate("metric_current_stage"),
                current_stage or "-",
                tone="primary",
            ),
            Metric(
                translate("rq_total_items"),
                len(items),
                tone="danger" if critical else "neutral",
            ),
            Metric(
                translate("dash_recent_artifacts"),
                artifacts_count,
            ),
            Metric(
                translate("label_total_cost"),
                _format_cost(state),
            ),
        ]
    )

    st.markdown("")

    # -- Main two-column area ---------------------------------------------
    main_col, side_col = st.columns([0.65, 0.35], gap="large")

    with main_col:
        # Next action card (or idle)
        if pending:
            gate = pending[0]
            gate_name = gate.get("gate", "")
            _render_next_action_card(gate, gate_name)
        elif state.get("run_status") == "complete":
            st.success(translate("success_pipeline_complete"))

        # Risk summary
        _render_risk_summary(items)

        # Recent artifacts
        _render_recent_artifacts(state)

    with side_col:
        # Stage timeline
        st.markdown(f"#### {translate('metric_current_stage')}")
        render_phase_tracker(state.get("current_stage"))

        # Cost summary
        _render_cost_summary(state)

    # -- Bottom: audit log (collapsed) ------------------------------------
    _render_audit_log(state)


def _render_next_action_card(gate: dict[str, Any], gate_name: str) -> None:
    """Render the prominent "approval needed" card."""

    next_stage = stage_label(gate.get("proposed_next_stage"))
    approval_gate_card(
        title=gate_field(gate_name, "title"),
        summary=gate_field(gate_name, "summary"),
        next_stage=next_stage,
    )


def _render_risk_summary(items: list[Any]) -> None:
    """Render a compact risk-summary section with top findings."""

    st.markdown(f"#### {translate('dash_risk_summary')}")

    if not items:
        st.info(translate("dash_risk_none"))
        return

    critical = [i for i in items if i.severity in ("critical", "error")]
    warning = [i for i in items if i.severity in ("warning", "high", "medium")]

    col_c, col_w = st.columns(2)
    col_c.metric(translate("rq_critical_items"), len(critical))
    col_w.metric(translate("rq_warning_items"), len(warning))

    # Show top 3 critical items as finding cards
    for item in critical[:3]:
        finding_card(
            severity=item.severity,
            title=item.title,
            detail=item.detail,
        )

    if len(items) > 3:
        st.caption(
            translate("rq_items_showing").format(
                shown=min(3, len(critical)), total=len(items)
            )
        )


def _render_recent_artifacts(state: dict[str, Any]) -> None:
    """Render the 3 most recent artifacts as cards."""

    st.markdown(f"#### {translate('dash_recent_artifacts')}")

    artifacts = state.get("artifacts", {})
    if not artifacts:
        st.caption(translate("label_no_artifacts"))
        return

    # Show last 3 artifacts as cards
    recent = list(artifacts.items())[-3:]
    for role, art in recent:
        if not isinstance(art, dict):
            continue
        artifact_card(
            title=role,
            version=str(art.get("version", "-")),
            status=_artifact_status_label(art.get("status", "")),
            hash_short=short_hash(art.get("content_hash", "")),
            artifact_type=art.get("artifact_type", ""),
        )


def _render_cost_summary(state: dict[str, Any]) -> None:
    """Render cost and invocation summary."""

    st.markdown(f"#### {translate('dash_cost_summary')}")

    usage = state.get("model_usage_summary")
    if not isinstance(usage, dict):
        st.caption(translate("dash_no_cost"))
        return

    total_cents = usage.get("total_cost_cents", 0)
    total_invocations = usage.get("total_invocations", 0)
    fallbacks = usage.get("total_fallbacks", 0)
    failures = usage.get("total_failures", 0)

    cost_str = f"${total_cents / 100:.2f}" if total_cents else "$0.00"

    col1, col2 = st.columns(2)
    col1.metric(translate("label_total_cost"), cost_str)
    col2.metric(translate("label_total_invocations"), total_invocations)

    if fallbacks or failures:
        st.caption(
            f"{translate('label_fallbacks')}: {fallbacks} | "
            f"{translate('label_failures')}: {failures}"
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
                    translate("col_occurred_at"): ev.get("occurred_at", ""),
                    translate("col_event_type"): ev.get("event_type", ""),
                    translate("col_stage"): stage_label(ev.get("stage")),
                    translate("col_message"): ev.get("message", ""),
                }
            )
        rows.reverse()  # newest first
        if rows:
            st.dataframe(rows, use_container_width=True, hide_index=True)
