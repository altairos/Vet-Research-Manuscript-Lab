"""Pipeline status, approval gates, and timeline (tab: Pipeline Control)."""

from __future__ import annotations

from typing import Any

import streamlit as st
from langgraph.types import Command

from vet_manuscript_lab.ui.application import Application
from vet_manuscript_lab.ui.golden import (
    prepare_golden_workspace,
    run_golden_workspace_pipeline,
)
from vet_manuscript_lab.ui.i18n import gate_field, stage_label, translate
from vet_manuscript_lab.ui.state import (
    start_workflow,
)
from vet_manuscript_lab.ui.tabs.intake import bump_search_form_version
from vet_manuscript_lab.ui.tabs.literature import render_search_strategy_detail
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
            translate("readiness_search"): bool(
                intake.get("search_strategy_input")
            ),
            translate("readiness_literature"): bool(
                intake.get("literature_record_drafts")
            ),
            translate("readiness_dataset"): bool(
                intake.get("dataset_summary")
            ),
        }
        status_cols = st.columns(4)
        for col, (label, complete) in zip(
            status_cols, requirements.items(), strict=True
        ):
            col.metric(
                label,
                translate("label_ready")
                if complete
                else translate("label_incomplete"),
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
            render_run_metrics(state, thread_id)
            next_nodes = (
                ", ".join(snapshot.next) if snapshot.next else "-"
            )
            st.caption(f"{translate('label_next')}: {next_nodes}")
            if pending:
                render_pending_approval(app, config, pending[0])
            render_search_strategy_detail(state)
            with st.expander(
                translate("expander_artifact_refs"), expanded=False
            ):
                st.json(state.get("artifacts", {}))
            with st.expander(
                translate("expander_approvals_locks"), expanded=False
            ):
                st.json(
                    {
                        "approvals": state.get("approvals", {}),
                        "locks": state.get("locks", {}),
                    }
                )
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
        role_options.index(required_role)
        if required_role in role_options
        else 0
    )

    decision_options = ["accept", "reject", "defer"]
    decision_labels = {
        d: translate(f"decision_{d}") for d in decision_options
    }

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
                    st.caption(
                        f"{translate('col_location')}: {loc}"
                    )
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
            app.governance.sync_state(
                app.graph.get_state(config).values
            )
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
            app.governance.sync_state(
                app.graph.get_state(config).values
            )
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
        translate("pending_action_caption", stage=stage_label(gate_name))
    )
    st.write(
        {
            translate("pending_action_gate"): gate_field(
                gate_name, "title"
            ),
            translate("pending_action_next"): stage_label(
                gate.get("proposed_next_stage")
            ),
        }
    )
    st.caption(gate_field(gate_name, "summary"))

    role_options = ["investigator", "statistician"]
    required_role = gate.get("required_reviewer_role", "investigator")
    default_index = (
        role_options.index(required_role)
        if required_role in role_options
        else 0
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
            app.governance.sync_state(
                app.graph.get_state(config).values
            )
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
        events.append(
            {
                "sort_key": ap.get("decided_at", ""),
                translate("col_event_type"): translate(
                    "col_decision"
                ),
                translate("col_gate"): stage_label(gate_key),
                translate("col_decision"): ap.get("decision", ""),
                translate("col_reviewer"): (
                    f"{ap.get('reviewer_id', '')} "
                    f"({ap.get('reviewer_role', '')})"
                ),
                translate("col_decided_at"): ap.get(
                    "decided_at", ""
                ),
                translate("col_message"): ap.get("comment", ""),
            }
        )

    for lock_key, lk in locks.items():
        events.append(
            {
                "sort_key": lk.get("locked_at", ""),
                translate("col_event_type"): translate(
                    "col_lock_type"
                ),
                translate("col_gate"): lk.get(
                    "lock_type", lock_key
                ),
                translate("col_decision"): "locked",
                translate("col_reviewer"): lk.get("locked_by", ""),
                translate("col_decided_at"): lk.get(
                    "locked_at", ""
                ),
                translate("col_message"): (
                    f"version: "
                    f"{str(lk.get('subject_version_id', ''))[:16]}"
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


def render_workspace_actions(app: Application) -> None:
    """Render the Golden workspace load/run buttons in the sidebar."""

    notice = st.session_state.pop("golden_workspace_notice", None)
    if isinstance(notice, str):
        st.success(notice)

    st.subheader(translate("workspace_actions_header"))
    st.caption(translate("workspace_actions_caption"))
    col_load, col_run = st.columns(2)
    load_clicked = col_load.button(
        translate("golden_workspace_load"),
        use_container_width=True,
    )
    run_clicked = col_run.button(
        translate("golden_workspace_run"),
        type="primary",
        use_container_width=True,
    )

    if load_clicked:
        try:
            with st.spinner(translate("golden_workspace_loading")):
                pid = prepare_golden_workspace(
                    app, bump_search_form_version
                )
        except (OSError, ValueError) as exc:
            st.error(
                translate("golden_demo_load_error", error=str(exc))
            )
        else:
            st.session_state["golden_workspace_notice"] = translate(
                "golden_workspace_loaded", id=pid[:8]
            )
            st.rerun()

    if run_clicked:
        try:
            with st.spinner(translate("golden_workspace_running")):
                pid, _tid = run_golden_workspace_pipeline(
                    app, bump_search_form_version
                )
        except (OSError, ValueError) as exc:
            st.error(
                translate("golden_demo_load_error", error=str(exc))
            )
        else:
            st.session_state["golden_workspace_notice"] = translate(
                "golden_workspace_finished", id=pid[:8]
            )
            st.rerun()
