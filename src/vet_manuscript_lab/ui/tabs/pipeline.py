"""Pipeline status, approval gates, and timeline (tab: Pipeline Control)."""

from __future__ import annotations

from typing import Any

import streamlit as st
from langgraph.types import Command

from vet_manuscript_lab.ui.application import Application
from vet_manuscript_lab.ui.components import (
    collapsible_details,
)
from vet_manuscript_lab.ui.i18n import (
    gate_field,
    gate_stage_label,
    stage_label,
    translate,
)
from vet_manuscript_lab.ui.state import (
    start_workflow,
)
from vet_manuscript_lab.ui.theme import render_phase_tracker, render_run_metrics


def render_pipeline_bar(
    app: Application,
    project_id: str,
    intake: dict[str, Any],
    ready: bool,
    state: dict[str, Any],
    pending: list[dict[str, Any]],
    config: dict[str, Any] | None,
    snapshot: Any,
    thread_id: str | None,
) -> None:
    """Render the pipeline-control section as a standalone bar."""

    with st.container(border=True):
        st.markdown(
            f"""<div class="pipeline-bar-header">
            <strong>{translate("tab_pipeline_control")}</strong>
            </div>""",
            unsafe_allow_html=True,
        )

        requirements = {
            translate("tab_research_question"): bool(
                intake.get("research_question_input")
            ),
            translate("readiness_search"): bool(intake.get("search_strategy_input")),
            translate("readiness_literature"): bool(
                intake.get("literature_record_drafts")
            ),
            translate("readiness_dataset"): bool(intake.get("dataset_summary")),
        }
        status_cols = st.columns(4)
        for col, (label, complete) in zip(
            status_cols, requirements.items(), strict=True
        ):
            col.metric(
                label,
                translate("label_ready") if complete else translate("label_incomplete"),
            )

        if st.button(
            translate("button_start_full_run"),
            type="primary",
            disabled=not ready,
            help=None if ready else translate("start_disabled_help"),
        ):
            start_workflow(app, project_id)
            st.rerun()

        if thread_id is not None and config is not None:
            render_phase_tracker(state.get("current_stage"))
            if snapshot.next:
                next_labels = ", ".join(
                    stage_label(n) for n in snapshot.next
                )
            else:
                next_labels = "-"
            st.caption(f"{translate('label_next')}: {next_labels}")
            if pending:
                render_pending_approval(app, config, pending[0])
            # Technical details (run metrics, artifacts, timeline) collapsed
            with st.expander(translate("show_details"), expanded=False):
                render_run_metrics(state, thread_id)
                render_artifact_summary(state)
                render_approval_timeline(state)
            if not pending and state.get("run_status") == "complete":
                st.success(translate("success_pipeline_complete"))


def render_review_disposition(
    app: Application,
    config: dict[str, Any],
    gate: dict[str, Any],
) -> None:
    """Render the per-finding review disposition form."""

    findings = gate.get("findings", [])
    if not findings:
        st.info(translate("review_no_findings"))
        return

    st.subheader(translate("review_disposition_header"))
    st.caption(translate("review_disposition_caption"))

    role_options = ["reviewer", "investigator"]
    required_role = gate.get("required_reviewer_role", "reviewer")
    default_index = (
        role_options.index(required_role) if required_role in role_options else 0
    )

    decision_options = ["accept", "reject", "defer"]
    decision_labels = {d: translate(f"decision_{d}") for d in decision_options}

    decisions: list[dict[str, str]] = []

    with st.form("review_disposition_form"):
        col_id, col_role = st.columns(2)
        reviewer_id = col_id.text_input(
            translate("field_reviewer_id"),
            value=st.session_state.get("default_reviewer_id", "Mona"),
        )
        reviewer_role = col_role.selectbox(
            translate("field_reviewer_role"),
            role_options,
            index=default_index,
            format_func=lambda role: translate(f"role_{role}"),
        )

        st.divider()
        for f in findings:
            fid = f.get("finding_id", "")
            with st.container(border=True):
                sev = f.get("severity", "")
                cat = f.get("category", "")
                loc = f.get("location", "")
                st.markdown(
                    f"**{translate('label_finding_id')}:** `{fid}` "
                    f"| **{translate('col_severity')}:** {sev} "
                    f"| **{translate('col_category')}:** {cat}"
                )
                if loc:
                    st.caption(f"{translate('col_location')}: {loc}")
                st.write(f.get("rationale", ""))
                rec = f.get("recommendation", "")
                if rec:
                    st.info(rec)

                choice = st.radio(
                    translate("field_decision"),
                    decision_options,
                    format_func=lambda d: decision_labels[d],
                    horizontal=True,
                    key=f"rev_decision_{fid}",
                )
                reason = st.text_input(
                    translate("field_finding_reason"),
                    key=f"rev_reason_{fid}",
                )
                decisions.append(
                    {
                        "finding_id": fid,
                        "decision": choice,
                        "reason": reason,
                    }
                )

        submitted = st.form_submit_button(
            translate("button_submit_review"),
            type="primary",
            use_container_width=True,
        )

    if submitted:
        st.session_state["default_reviewer_id"] = reviewer_id
        try:
            app.graph.invoke(
                Command(
                    resume={
                        "reviewer_id": reviewer_id,
                        "reviewer_role": reviewer_role,
                        "decisions": decisions,
                    }
                ),
                config,
            )
            app.governance.sync_state(app.graph.get_state(config).values)
        except (LookupError, PermissionError, ValueError) as exc:
            st.error(str(exc))
        else:
            st.rerun()


def render_sign_off_approval(
    app: Application,
    config: dict[str, Any],
    gate: dict[str, Any],
) -> None:
    """Render the final sign-off form with authoriser identity."""

    st.markdown('<div class="approval-card">', unsafe_allow_html=True)
    st.subheader(translate("pending_action_header"))
    st.caption(
        translate(
            "pending_action_caption",
            stage=stage_label("final_sign_off"),
        )
    )
    st.caption(gate.get("summary", ""))

    role_options = ["principal_investigator", "corresponding_author"]
    with st.form("approval_final_sign_off"):
        col_id, col_role = st.columns(2)
        authoriser_id = col_id.text_input(
            translate("field_reviewer_id"),
            value=st.session_state.get("default_reviewer_id", "PI"),
        )
        authoriser_role = col_role.selectbox(
            translate("field_reviewer_role"),
            role_options,
            format_func=lambda r: translate(f"role_{r}"),
        )
        decision = st.selectbox(
            translate("field_decision"),
            ["approved", "rejected"],
            format_func=lambda v: translate(f"decision.{v}"),
        )
        reason = st.text_area(translate("field_comment"))
        submitted = st.form_submit_button(
            translate("button_submit_decision"),
            type="primary",
            use_container_width=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)

    if submitted:
        st.session_state["default_reviewer_id"] = authoriser_id
        try:
            app.graph.invoke(
                Command(
                    resume={
                        "decision": decision,
                        "authoriser_id": authoriser_id,
                        "authoriser_role": authoriser_role,
                        "reason": reason,
                    }
                ),
                config,
            )
            app.governance.sync_state(app.graph.get_state(config).values)
        except (LookupError, PermissionError, ValueError) as exc:
            st.error(str(exc))
        else:
            st.rerun()


def render_pending_approval(
    app: Application,
    config: dict[str, Any],
    gate: dict[str, Any],
) -> None:
    """Dispatch approval rendering based on gate type."""

    gate_name = gate.get("gate", "")

    if gate_name == "review":
        render_review_disposition(app, config, gate)
        return
    if gate_name == "final_sign_off":
        render_sign_off_approval(app, config, gate)
        return

    # Standard approval gates
    st.markdown('<div class="approval-card">', unsafe_allow_html=True)
    st.subheader(translate("pending_action_header"))
    st.caption(
        translate("pending_action_caption", stage=gate_stage_label(gate_name))
    )
    st.markdown(
        f"**{translate('pending_action_gate')}:** "
        f"{gate_field(gate_name, 'title')}"
    )
    next_stage = stage_label(gate.get("proposed_next_stage"))
    if next_stage:
        st.markdown(
            f"**{translate('pending_action_next')}:** {next_stage}"
        )
    st.caption(gate_field(gate_name, "summary"))

    role_options = ["investigator", "statistician"]
    required_role = gate.get("required_reviewer_role", "investigator")
    default_index = (
        role_options.index(required_role) if required_role in role_options else 0
    )
    with st.form(f"approval_{gate_name}"):
        reviewer_id = st.text_input(
            translate("field_reviewer_id"),
            value=st.session_state.get("default_reviewer_id", "Mona"),
        )
        reviewer_role = st.selectbox(
            translate("field_reviewer_role"),
            role_options,
            index=default_index,
            format_func=lambda role: translate(f"role_{role}"),
        )
        decision = st.selectbox(
            translate("field_decision"),
            gate["allowed_decisions"],
            format_func=lambda value: translate(f"decision.{value}"),
        )
        comment = st.text_area(translate("field_comment"))
        submitted = st.form_submit_button(
            translate("button_submit_decision"),
            type="primary",
            use_container_width=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)

    if submitted:
        st.session_state["default_reviewer_id"] = reviewer_id
        try:
            app.graph.invoke(
                Command(
                    resume={
                        "decision": decision,
                        "reviewer_id": reviewer_id,
                        "reviewer_role": reviewer_role,
                        "comment": comment,
                    }
                ),
                config,
            )
            app.governance.sync_state(app.graph.get_state(config).values)
        except (LookupError, PermissionError, ValueError) as exc:
            st.error(str(exc))
        else:
            st.rerun()


def render_approval_timeline(state: dict[str, Any]) -> None:
    """Render a chronological timeline of approvals and locks."""

    approvals = state.get("approvals", {})
    locks = state.get("locks", {})
    if not approvals and not locks:
        return

    st.subheader(translate("section_timeline"))

    events: list[dict[str, Any]] = []

    for gate_key, ap in approvals.items():
        decision_raw = ap.get("decision", "")
        events.append(
            {
                "sort_key": ap.get("decided_at", ""),
                translate("col_event_type"): translate("col_decision"),
                translate("col_gate"): gate_stage_label(gate_key),
                translate("col_decision"): translate(
                    f"decision.{decision_raw}",
                )
                if decision_raw
                else "",
                translate("col_reviewer"): (
                    f"{ap.get('reviewer_id', '')} "
                    f"({translate(f'role_{ap.get("reviewer_role", "")}')})"
                ),
                translate("col_decided_at"): ap.get("decided_at", ""),
                translate("col_message"): ap.get("comment", ""),
            }
        )

    for lock_key, lk in locks.items():
        events.append(
            {
                "sort_key": lk.get("locked_at", ""),
                translate("col_event_type"): translate("col_lock_type"),
                translate("col_gate"): lk.get("lock_type", lock_key),
                translate("col_decision"): translate("label_passed"),
                translate("col_reviewer"): lk.get("locked_by", ""),
                translate("col_decided_at"): lk.get("locked_at", ""),
                translate("col_message"): (
                    f"v{lk.get('subject_version_id', '')[:8]}"
                ),
            }
        )

    events.sort(key=lambda e: e["sort_key"])
    for e in events:
        del e["sort_key"]

    if events:
        st.dataframe(
            events,
            use_container_width=True,
            hide_index=True,
        )


def _artifact_status_label(status: str) -> str:
    """Translate a raw artifact status into a user-friendly label."""

    key = f"artifact_status_{status}"
    text = translate(key)
    # translate() falls back to the key itself when not found.
    return text if text != key else status


def render_artifact_summary(state: dict[str, Any]) -> None:
    """Render artifact references as a clean, readable table.

    Shows role, type, version, and status. Technical details (content_hash,
    version_id) are collapsed into a sub-expander per artifact.
    """

    artifacts = state.get("artifacts", {})
    if not artifacts:
        return

    with st.expander(translate("expander_artifact_refs"), expanded=False):
        rows: list[dict[str, Any]] = []
        tech_details: dict[str, Any] = {}
        for role, art in artifacts.items():
            if not isinstance(art, dict):
                continue
            rows.append(
                {
                    translate("col_artifact_role"): role,
                    translate("col_artifact_type"): art.get(
                        "artifact_type", "-"
                    ),
                    translate("col_artifact_version"): art.get("version", "-"),
                    translate("col_artifact_status"): _artifact_status_label(
                        art.get("status", "")
                    ),
                }
            )
            # Collect full technical details for collapsible display.
            # Values are stored UNTRUNCED so the user can copy them from
            # the expanded st.json view (which has a built-in copy button).
            version_id = art.get("version_id", "")
            content_hash = art.get("content_hash", "")
            if version_id or content_hash:
                tech_details[role] = {
                    "version_id": version_id or "-",
                    "content_hash": content_hash or "-",
                }
        if rows:
            st.dataframe(rows, use_container_width=True, hide_index=True)
        else:
            st.caption(translate("label_no_artifacts"))

        # Collapsed technical details
        if tech_details:
            collapsible_details(
                translate("show_technical_info"),
                tech_details,
            )


# ---------------------------------------------------------------------------
# Next Action Panel — the redesigned right sidebar
# ---------------------------------------------------------------------------


def render_next_action_panel(
    app: Application,
    project_id: str,
    intake: dict[str, Any],
    ready: bool,
    state: dict[str, Any],
    pending: list[dict[str, Any]],
    config: dict[str, Any] | None,
    snapshot: Any,
    thread_id: str | None,
) -> None:
    """Render the redesigned sticky right sidebar.

    Combines the classic pipeline bar (start button, phase tracker,
    approval gates) with a compact *Review Queue* summary so the user
    always sees risks at a glance.
    """

    # The core pipeline controls (start, phase tracker, approval gates)
    render_pipeline_bar(
        app,
        project_id,
        intake,
        ready,
        state,
        pending,
        config,
        snapshot,
        thread_id,
    )

    # Review Queue compact summary
    if state:
        render_review_queue_summary(state)


def render_review_queue_summary(state: dict[str, Any]) -> None:
    """Render a compact Review Queue summary for the right sidebar.

    Shows critical/warning counts and the top 3 critical items as
    severity pills so the user always sees risks at a glance.
    """

    from vet_manuscript_lab.ui.components import severity_pill
    from vet_manuscript_lab.ui.tabs.review_queue import collect_review_items

    items = collect_review_items(state)
    if not items:
        return

    st.markdown("---")
    st.markdown(f"**{translate('rq_header')}**")
    critical = [i for i in items if i.severity in ("critical", "error")]
    col_c, col_w = st.columns(2)
    col_c.metric(translate("rq_critical_items"), len(critical))
    col_w.metric(
        translate("rq_warning_items"),
        len(items) - len(critical),
    )
    # Show top 3 critical items as compact severity pills
    for item in critical[:3]:
        st.markdown(
            f"{severity_pill(item.severity)} "
            f"{item.title[:60]}",
            unsafe_allow_html=True,
        )
    if len(items) > 3:
        st.caption(
            translate("rq_items_showing").format(
                shown=min(3, len(critical)), total=len(items)
            )
        )
