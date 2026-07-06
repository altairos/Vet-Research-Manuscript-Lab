"""Streamlit UI for the Foundation + Literature & Evidence pipeline.

Run with: streamlit run src/vet_manuscript_lab/ui/app.py
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

import streamlit as st
from langgraph.types import Command

from vet_manuscript_lab.config import Settings
from vet_manuscript_lab.domain.conventions import utc_now
from vet_manuscript_lab.infrastructure.checkpoints import open_sqlite_checkpointer
from vet_manuscript_lab.infrastructure.database import create_database
from vet_manuscript_lab.infrastructure.database.governance import GovernanceRepository
from vet_manuscript_lab.infrastructure.database.repository import (
    FoundationRepository,
    ProjectInput,
)
from vet_manuscript_lab.ui.i18n import (
    DEFAULT_LANGUAGE,
    LANGUAGE_LABELS,
    SUPPORTED_LANGUAGES,
    gate_field,
    stage_label,
    status_label,
    translate,
)
from vet_manuscript_lab.workflow.analysis_graph import build_analysis_pipeline_graph
from vet_manuscript_lab.workflow.state import new_workflow_state


@dataclass(slots=True)
class Application:
    repository: FoundationRepository
    governance: GovernanceRepository
    graph: Any
    checkpoint_connection: Any


@st.cache_resource
def get_application() -> Application:
    settings = Settings.from_env()
    database = create_database(settings.database_url)
    database.create_schema()
    repository = FoundationRepository(database.sessions)
    governance = GovernanceRepository(database.sessions)
    connection, checkpointer = open_sqlite_checkpointer(settings.checkpoint_path)
    graph = build_analysis_pipeline_graph(checkpointer)
    return Application(
        repository=repository,
        governance=governance,
        graph=graph,
        checkpoint_connection=connection,
    )


def _interrupt_values(snapshot: Any) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    for task in snapshot.tasks:
        for pending in task.interrupts:
            if isinstance(pending.value, dict):
                values.append(pending.value)
    return values


def _render_language_switch() -> None:
    """Persist the active UI language (English / Chinese) in session state."""

    options = list(SUPPORTED_LANGUAGES)
    current = st.session_state.get("language", DEFAULT_LANGUAGE)
    if current not in options:
        current = DEFAULT_LANGUAGE
    selected = st.sidebar.selectbox(
        translate("language_label"),
        options=options,
        format_func=lambda code: LANGUAGE_LABELS[code],
        index=options.index(current),
    )
    st.session_state["language"] = selected


def _render_project_creation(app: Application) -> None:
    st.subheader(translate("create_project_header"))
    species_options = ["canine", "feline"]
    with st.form("create_project", clear_on_submit=True):
        title = st.text_input(translate("field_project_title"))
        owner_id = st.text_input(translate("field_owner_id"))
        species = st.multiselect(
            translate("field_species_scope"),
            species_options,
            format_func=lambda code: translate(f"species_{code}"),
            default=["canine"],
        )
        submitted = st.form_submit_button(translate("button_create"))
    if submitted:
        try:
            project = app.repository.create_project(
                ProjectInput(
                    title=title,
                    study_type="retrospective_observational_clinical_study",
                    species_scope=species,
                    owner_id=owner_id,
                )
            )
        except ValueError as exc:
            st.error(str(exc))
        else:
            st.session_state["project_id"] = project.id
            st.success(translate("success_project_created", id=project.id))
            st.rerun()


def _render_projects(app: Application) -> None:
    projects = app.repository.list_projects()
    if not projects:
        st.info(translate("info_no_projects"))
        return
    labels = {project.id: f"{project.title} ({project.id[:8]})" for project in projects}
    selected = st.selectbox(
        translate("field_active_project"),
        options=list(labels),
        format_func=lambda project_id: labels[project_id],
        index=0,
    )
    st.session_state["project_id"] = selected


def _start_workflow(app: Application, project_id: str) -> None:
    thread_id = str(uuid.uuid4())
    run = app.repository.create_run(project_id, thread_id)
    state = new_workflow_state(
        project_id=project_id,
        workflow_run_id=run.id,
        thread_id=thread_id,
        now=utc_now(),
    )
    config = {"configurable": {"thread_id": thread_id}}
    app.graph.invoke(state, config)
    app.governance.sync_state(app.graph.get_state(config).values)
    st.session_state["thread_id"] = thread_id


# ---------------------------------------------------------------------------
# Literature + Evidence renderers
# ---------------------------------------------------------------------------


def _render_literature_records(state: dict[str, Any]) -> None:
    """Display the literature record drafts in a table."""

    records = state.get("literature_record_drafts", [])
    if not records:
        st.info(translate("info_no_literature"))
        return

    st.subheader(translate("section_literature"))

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

    rows = []
    for rec in records:
        rows.append(
            {
                translate("col_record_id"): rec.get("record_id", "")[:12],
                translate("col_title"): rec.get("title", ""),
                translate("col_doi"): rec.get("doi", ""),
                translate("col_decision"): rec.get("screening_decision", ""),
            }
        )
    st.dataframe(rows, use_container_width=True, hide_index=True)


def _render_evidence_items(state: dict[str, Any]) -> None:
    """Display extracted evidence drafts and their source spans."""

    drafts = state.get("evidence_drafts", [])
    spans = state.get("source_span_drafts", [])
    if not drafts:
        st.info(translate("info_no_evidence"))
        return

    st.subheader(translate("section_evidence"))

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
    st.dataframe(rows, use_container_width=True, hide_index=True)

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
            st.dataframe(span_rows, use_container_width=True, hide_index=True)
        else:
            st.info(translate("info_no_evidence"))


def _render_search_strategy_detail(state: dict[str, Any]) -> None:
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


def _render_methodology_findings(state: dict[str, Any]) -> None:
    """Display methodology critic findings in a table."""

    findings = state.get("methodology_findings", [])
    if not findings:
        st.info(translate("info_no_methodology"))
        return

    st.subheader(translate("section_methodology"))

    warning_count = sum(1 for f in findings if f.get("severity") == "warning")
    col1, col2 = st.columns(2)
    col1.metric(translate("label_findings_count"), len(findings))
    col2.metric(translate("label_warnings_count"), warning_count)

    rows = []
    for f in findings:
        rows.append(
            {
                translate("col_category"): f.get("category", ""),
                translate("col_severity"): f.get("severity", ""),
                translate("col_rationale"): f.get("rationale", ""),
                translate("col_recommendation"): f.get("recommendation", ""),
            }
        )
    st.dataframe(rows, use_container_width=True, hide_index=True)


def _render_analysis_plan(state: dict[str, Any]) -> None:
    """Display analysis plan summary and variable specs."""

    plan_summary = state.get("analysis_plan_summary")
    if plan_summary is None:
        st.info(translate("info_no_analysis_plan"))
        return

    st.subheader(translate("section_analysis_plan"))

    col1, col2, col3 = st.columns(3)
    col1.metric(
        translate("label_analysis_count"),
        plan_summary.get("analysis_count", 0),
    )
    col2.metric(
        translate("label_findings_count"),
        plan_summary.get("findings_count", 0),
    )
    plan_locked = plan_summary.get("locked", False)
    col3.metric(
        translate("label_plan_locked"),
        translate("label_yes") if plan_locked else translate("label_no"),
    )

    locks = state.get("locks", {})
    dataset_locked = "dataset" in locks
    if dataset_locked:
        st.caption(translate("label_dataset_locked"))

    analyses = state.get("analysis_spec_drafts", [])
    if analyses:
        rows = []
        for a in analyses:
            rows.append(
                {
                    translate("col_analysis_name"): a.get("name", ""),
                    translate("col_estimand"): a.get("estimand", ""),
                    translate("col_method"): a.get("model_type", ""),
                    translate("col_class"): a.get("analysis_class", ""),
                }
            )
        st.dataframe(rows, use_container_width=True, hide_index=True)


def _render_statistical_results(state: dict[str, Any]) -> None:
    """Display statistical results from the analysis run."""

    run_summary = state.get("analysis_run_summary")
    drafts = state.get("result_drafts", [])
    if not drafts and run_summary is None:
        st.info(translate("info_no_results"))
        return

    st.subheader(translate("section_results"))

    if run_summary:
        col1, col2, col3 = st.columns(3)
        col1.metric(
            translate("label_run_status"),
            run_summary.get("status", ""),
        )
        col2.metric(
            translate("label_result_count"),
            run_summary.get("result_count", 0),
        )
        col3.metric(
            translate("label_reproducible"),
            translate("label_yes")
            if run_summary.get("is_reproducible")
            else translate("label_no"),
        )

    if drafts:
        rows = []
        for d in drafts:
            lower = d.get("uncertainty_lower")
            upper = d.get("uncertainty_upper")
            ci = f"{lower} - {upper}" if lower is not None and upper is not None else ""
            rows.append(
                {
                    translate("col_analysis_name"): d.get("estimand", ""),
                    translate("col_estimate"): str(d.get("estimate", "")),
                    translate("col_ci"): ci,
                    translate("col_p_value"): str(d.get("p_value", "")),
                    translate("col_method"): d.get("method", ""),
                    translate("col_class"): d.get("analysis_class", ""),
                }
            )
        st.dataframe(rows, use_container_width=True, hide_index=True)


def _render_usage_summary(state: dict[str, Any]) -> None:
    """Display AI model usage and cost breakdown if available."""

    usage = state.get("ai_usage")
    if not usage:
        return

    st.subheader(translate("section_usage"))

    col1, col2, col3, col4 = st.columns(4)
    col1.metric(
        translate("label_total_invocations"),
        usage.get("total_invocations", 0),
    )
    col2.metric(
        translate("label_total_cost"),
        f"${usage.get('total_cost_cents', 0) / 100:.2f}",
    )
    col3.metric(
        translate("label_input_tokens"),
        usage.get("total_input_tokens", 0),
    )
    col4.metric(
        translate("label_output_tokens"),
        usage.get("total_output_tokens", 0),
    )

    fallback = usage.get("fallback_count", 0)
    failure = usage.get("failure_count", 0)
    if fallback or failure:
        st.caption(
            f"{translate('label_fallbacks')}: {fallback} | "
            f"{translate('label_failures')}: {failure}"
        )

    cost_by_stage = usage.get("cost_by_stage", {})
    if cost_by_stage:
        stage_rows = []
        for task_kind, data in cost_by_stage.items():
            if task_kind == "__total__":
                continue
            stage_rows.append(
                {
                    translate("col_task_kind"): task_kind,
                    translate("col_invocations"): data.get("invocations", 0),
                    translate("col_cost_cents"): (
                        f"${data.get('cost_cents', 0) / 100:.2f}"
                    ),
                    translate("col_tokens"): (
                        data.get("input_tokens", 0) + data.get("output_tokens", 0)
                    ),
                }
            )
        if stage_rows:
            st.dataframe(stage_rows, use_container_width=True, hide_index=True)


def _render_workflow(app: Application, project_id: str) -> None:
    st.subheader(translate("workflow_header_full"))
    if st.button(translate("button_start_full_run")):
        _start_workflow(app, project_id)
        st.rerun()

    thread_id = st.session_state.get("thread_id")
    if not isinstance(thread_id, str):
        return
    config = {"configurable": {"thread_id": thread_id}}
    snapshot = app.graph.get_state(config)
    state = snapshot.values
    st.write(
        {
            translate("label_thread_id"): thread_id,
            translate("label_stage"): stage_label(state.get("current_stage")),
            translate("label_status"): status_label(state.get("run_status")),
            translate("label_next"): snapshot.next,
        }
    )

    _render_search_strategy_detail(state)

    with st.expander(translate("expander_artifact_refs"), expanded=False):
        st.json(state.get("artifacts", {}))
    with st.expander(translate("expander_approvals_locks"), expanded=False):
        st.json(
            {
                "approvals": state.get("approvals", {}),
                "locks": state.get("locks", {}),
            }
        )

    # Literature + evidence views (appear after screening / extraction stages)
    _render_literature_records(state)
    _render_evidence_items(state)

    # Methodology + analysis views (appear after methodology critic stage)
    _render_methodology_findings(state)
    _render_analysis_plan(state)
    _render_statistical_results(state)

    # AI usage / cost views (appear after any gateway call)
    _render_usage_summary(state)

    pending = _interrupt_values(snapshot)
    if not pending:
        if state.get("run_status") == "complete":
            st.success(translate("success_pipeline_complete"))
        return

    gate = pending[0]
    gate_name = gate["gate"]
    st.warning(gate_field(gate_name, "title"))
    st.caption(gate_field(gate_name, "summary"))
    role_options = ["investigator", "statistician"]
    with st.form(f"approval_{gate['gate']}"):
        reviewer_id = st.text_input(translate("field_reviewer_id"))
        reviewer_role = st.selectbox(
            translate("field_reviewer_role"),
            role_options,
            format_func=lambda role: translate(f"role_{role}"),
        )
        decision = st.selectbox(
            translate("field_decision"),
            gate["allowed_decisions"],
            format_func=lambda value: translate(f"decision.{value}"),
        )
        comment = st.text_area(translate("field_comment"))
        submitted = st.form_submit_button(translate("button_submit_decision"))
    if submitted:
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


def main() -> None:
    st.set_page_config(page_title=translate("page_title"), layout="wide")
    _render_language_switch()
    st.title(translate("app_title"))
    st.caption(translate("app_caption_full"))
    app = get_application()
    _render_project_creation(app)
    st.divider()
    _render_projects(app)
    project_id = st.session_state.get("project_id")
    if isinstance(project_id, str):
        _render_workflow(app, project_id)


if __name__ == "__main__":
    main()
