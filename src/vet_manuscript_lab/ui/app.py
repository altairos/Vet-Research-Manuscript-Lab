"""Streamlit UI for the Foundation + Literature & Evidence pipeline.

Run with: streamlit run src/vet_manuscript_lab/ui/app.py
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import streamlit as st
from langgraph.types import Command

from vet_manuscript_lab.config import Settings
from vet_manuscript_lab.domain.conventions import utc_now
from vet_manuscript_lab.infrastructure.checkpoints import open_checkpointer
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
from vet_manuscript_lab.workflow.compliance_graph import build_compliance_pipeline_graph
from vet_manuscript_lab.workflow.state import new_workflow_state

GOLDEN_FIXTURE_ROOT = (
    Path(__file__).resolve().parents[3] / "fixtures" / "golden_project"
)


@st.cache_data(show_spinner=False)
def _load_golden_fixture() -> dict[str, Any] | None:
    """Load all golden project fixture JSON files (cached).

    Returns ``None`` and records the error in session state when the
    fixture directory cannot be read so the UI can show a helpful message.
    """

    try:

        def _read_json(rel: str) -> dict[str, Any]:
            return json.loads(  # type: ignore[no-any-return]
                (GOLDEN_FIXTURE_ROOT / rel).read_text(encoding="utf-8")
            )

        return {
            "project": _read_json("project.json"),
            "literature": _read_json("literature/records.json"),
            "methodology": _read_json("methodology/findings.json"),
            "dictionary": _read_json("dictionary/variables.json"),
            "analysis_plan": _read_json("analysis_plan/analyses.json"),
        }
    except (OSError, ValueError) as exc:
        st.session_state["golden_fixture_error"] = str(exc)
        return None


@dataclass(slots=True)
class Application:
    repository: FoundationRepository
    governance: GovernanceRepository
    graph: Any
    checkpoint_connection: Any


@st.cache_resource
def get_application() -> Application:
    settings = Settings.from_env()
    database = create_database(
        settings.database_url,
        pool_config=settings.pool_config,
    )
    database.create_schema()
    repository = FoundationRepository(database.sessions)
    governance = GovernanceRepository(database.sessions)
    connection, checkpointer = open_checkpointer(
        database_url=settings.database_url,
        checkpoint_path=settings.checkpoint_path,
    )
    graph = build_compliance_pipeline_graph(checkpointer)
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


def _render_view_mode_switch() -> str:
    """Render the main view mode switcher in the sidebar.

    Returns either ``'workflow'`` (default project/run view) or
    ``'golden_demo'`` (Golden Project fixture browser + demo run).
    """

    options = ["workflow", "golden_demo"]
    current = st.session_state.get("view_mode", "workflow")
    if current not in options:
        current = "workflow"

    def _label(code: str) -> str:
        return (
            translate("view_workflow")
            if code == "workflow"
            else translate("view_golden_demo")
        )

    selected = st.sidebar.radio(
        translate("view_mode_label"),
        options=options,
        format_func=_label,
        index=options.index(current),
        horizontal=True,
    )
    st.session_state["view_mode"] = selected
    return selected


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


# ---------------------------------------------------------------------------
# Golden Project demo view
# ---------------------------------------------------------------------------


def _render_golden_overview(fixture: dict[str, Any]) -> None:
    """Render the project overview card from project.json."""

    st.subheader(translate("golden_section_overview"))
    project = fixture["project"]["project"]
    rq = fixture["project"].get("research_question", {})
    dataset_meta = fixture["project"].get("dataset", {})

    col1, col2 = st.columns(2)
    with col1:
        st.write(
            f"**{translate('golden_label_project_id')}**: "
            f"`{project.get('project_id', '')}`"
        )
        st.write(f"**{translate('golden_label_title')}**: {project.get('title', '')}")
        st.write(
            f"**{translate('golden_label_study_type')}**: "
            f"`{project.get('study_type', '')}`"
        )
        species = project.get("species_scope", [])
        st.write(f"**{translate('golden_label_species')}**: {', '.join(species)}")
        st.write(
            f"**{translate('golden_label_guideline')}**: "
            f"{project.get('reporting_guideline', '')}"
        )
    with col2:
        synthetic = fixture["project"].get("synthetic")
        st.write(
            f"**{translate('golden_label_synthetic')}**: "
            f"{translate('label_yes') if synthetic else translate('label_no')}"
        )
        st.write(
            f"**{translate('golden_label_classification')}**: "
            f"{fixture['project'].get('data_classification', '')}"
        )
        st.write(
            f"**{translate('golden_label_rows')}**: {dataset_meta.get('rows', '')}"
        )
        st.write(
            f"**{translate('golden_label_columns')}**: "
            f"{dataset_meta.get('columns', '')}"
        )

    if rq:
        with st.expander(translate("golden_label_peco"), expanded=False):
            st.write(
                f"**{translate('golden_label_population')}**: "
                f"{rq.get('population', '')}"
            )
            st.write(
                f"**{translate('golden_label_exposure')}**: {rq.get('exposure', '')}"
            )
            st.write(
                f"**{translate('golden_label_comparator')}**: "
                f"{rq.get('comparator', '')}"
            )
            st.write(
                f"**{translate('golden_label_outcome')}**: {rq.get('outcome', '')}"
            )


def _render_golden_literature(fixture: dict[str, Any]) -> None:
    """Render the literature records table from records.json."""

    records = fixture["literature"].get("records", [])
    if not records:
        st.info(translate("info_no_literature"))
        return

    st.subheader(translate("golden_section_literature"))
    st.caption(f"{len(records)} records")

    rows = []
    for rec in records:
        rows.append(
            {
                translate("col_record_id"): rec.get("literature_id", ""),
                translate("col_title"): rec.get("title", ""),
                translate("col_authors"): ", ".join(rec.get("authors", [])),
                translate("col_year"): rec.get("year", ""),
                translate("col_journal"): rec.get("journal", ""),
                translate("col_doi"): rec.get("doi", ""),
                translate("col_tags"): ", ".join(rec.get("tags", [])),
            }
        )
    st.dataframe(rows, use_container_width=True, hide_index=True)

    for rec in records:
        abstract = rec.get("abstract", "")
        if abstract:
            label = f"{rec.get('literature_id', '')} \u2014 {rec.get('title', '')[:60]}"
            with st.expander(label):
                st.write(abstract)


def _render_golden_methodology(fixture: dict[str, Any]) -> None:
    """Render the methodology findings table from findings.json."""

    findings = fixture["methodology"].get("findings", [])
    if not findings:
        st.info(translate("info_no_methodology"))
        return

    st.subheader(translate("golden_section_methodology"))
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
                translate("col_status"): f.get("status", ""),
                translate("col_rationale"): f.get("rationale", ""),
                translate("col_recommendation"): f.get("recommendation", ""),
            }
        )
    st.dataframe(rows, use_container_width=True, hide_index=True)


def _render_golden_dictionary(fixture: dict[str, Any]) -> None:
    """Render the data dictionary table from variables.json."""

    variables = fixture["dictionary"].get("variables", [])
    if not variables:
        return

    st.subheader(translate("golden_section_dictionary"))
    rows = []
    for v in variables:
        rows.append(
            {
                translate("col_var_name"): v.get("name", ""),
                translate("col_var_type"): v.get("var_type", ""),
                translate("col_var_role"): v.get("role", ""),
                translate("col_unit"): v.get("unit") or "\u2014",
                translate("col_missing_code"): v.get("missing_code") or "\u2014",
                translate("col_description"): v.get("description", ""),
            }
        )
    st.dataframe(rows, use_container_width=True, hide_index=True)


def _render_golden_analysis_plan(fixture: dict[str, Any]) -> None:
    """Render the analysis plan table from analyses.json."""

    analyses = fixture["analysis_plan"].get("plan", {}).get("analyses", [])
    if not analyses:
        st.info(translate("info_no_analysis_plan"))
        return

    st.subheader(translate("golden_section_analysis_plan"))
    rows = []
    for a in analyses:
        rows.append(
            {
                translate("col_analysis_name"): a.get("name", ""),
                translate("col_estimand"): a.get("estimand", ""),
                translate("col_method"): a.get("model_type", ""),
                translate("col_class"): a.get("analysis_class", ""),
                translate("col_variables"): ", ".join(a.get("variable_names", [])),
                translate("col_population"): a.get("population", "") or "\u2014",
            }
        )
    st.dataframe(rows, use_container_width=True, hide_index=True)

    rows2 = []
    for a in analyses:
        for crit in a.get("exclusion_criteria", []):
            rows2.append(
                {
                    translate("col_analysis_name"): a.get("name", ""),
                    translate("col_exclusion"): crit,
                }
            )
    if rows2:
        with st.expander(translate("col_exclusion"), expanded=False):
            st.dataframe(rows2, use_container_width=True, hide_index=True)


def _render_golden_dataset() -> None:
    """Render the synthetic CSV dataset preview using stdlib csv."""

    import csv

    st.subheader(translate("golden_section_dataset"))
    try:
        csv_path = GOLDEN_FIXTURE_ROOT / "data" / "cases_synthetic.csv"
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        if rows:
            st.dataframe(rows, use_container_width=True, hide_index=True)
            st.caption(f"{len(rows)} {translate('golden_label_rows').lower()}")
        else:
            st.info(translate("golden_section_dataset"))
    except OSError as exc:
        st.error(translate("golden_demo_load_error", error=str(exc)))


def _auto_resume_payload(interrupt: dict[str, Any]) -> dict[str, Any]:
    """Build a resume payload matching the interrupt's gate type.

    The compliance pipeline has three interrupt shapes:
    - Standard approval gates (question/protocol/search/analysis_plan/results):
      ``{decision, reviewer_id, reviewer_role}``
    - Review disposition gate: ``{reviewer_id, reviewer_role, decisions: [...]}``
    - Final sign-off gate: ``{decision, authoriser_id, authoriser_role}``
    """

    gate = interrupt.get("gate", "")
    if gate == "review":
        findings = interrupt.get("findings", [])
        decisions = [
            {"finding_id": f.get("finding_id", ""), "decision": "reject"}
            for f in findings
        ]
        return {
            "reviewer_id": "golden-demo",
            "reviewer_role": "reviewer",
            "decisions": decisions,
        }
    if gate == "final_sign_off":
        return {
            "decision": "approved",
            "authoriser_id": "golden-demo-pi",
            "authoriser_role": "principal_investigator",
            "reason": "Auto-approved for golden project demo",
        }
    # Standard approval gate
    return {
        "decision": "approved",
        "reviewer_id": "golden-demo",
        "reviewer_role": "investigator",
    }


def _fixture_to_literature_drafts(fixture: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert golden fixture literature records to WorkflowState drafts."""

    records = fixture.get("literature", {}).get("records", [])
    return [
        {
            "record_id": rec.get("literature_id", ""),
            "title": rec.get("title", ""),
            "doi": rec.get("doi"),
            "pmid": None,
            "journal": rec.get("journal"),
            "publication_year": rec.get("year"),
        }
        for rec in records
    ]


def _fixture_to_variable_drafts(fixture: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert golden fixture variables to WorkflowState drafts."""

    return list(fixture.get("dictionary", {}).get("variables", []))


def _fixture_to_analysis_drafts(fixture: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert golden fixture analyses to WorkflowState drafts."""

    return list(fixture.get("analysis_plan", {}).get("plan", {}).get("analyses", []))


def _fixture_to_methodology_findings(fixture: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert golden fixture methodology findings to WorkflowState entries."""

    return list(fixture.get("methodology", {}).get("findings", []))


def _run_golden_demo_pipeline(app: Application) -> str:
    """Run the full end-to-end pipeline with golden project fixture data.

    All approval gates are auto-approved (including review disposition and
    final sign-off) so the pipeline runs all the way through to DOCX export
    without manual intervention. Fixture literature records, variables,
    analysis specs, and methodology findings are injected into the initial
    state so that the pipeline output is consistent with the static fixture
    display. Returns the thread_id of the demo run.
    """

    thread_id = f"golden-demo-{uuid.uuid4().hex[:8]}"
    state = new_workflow_state(
        project_id="00000000-0000-4000-8000-000000000001",
        workflow_run_id=f"golden-demo-run-{thread_id[-8:]}",
        thread_id=thread_id,
        now=utc_now(),
        species_scope=["canine", "feline"],
    )

    # Inject golden fixture data so pipeline output matches the static
    # fixture display.  These pre-populated fields are respected by
    # literature_search_node, methodology_critic_node, and analysis_plan_node.
    fixture = _load_golden_fixture()
    if fixture:
        state["literature_record_drafts"] = _fixture_to_literature_drafts(fixture)  # type: ignore[typeddict-item]
        state["variable_spec_drafts"] = _fixture_to_variable_drafts(fixture)  # type: ignore[typeddict-item]
        state["analysis_spec_drafts"] = _fixture_to_analysis_drafts(fixture)  # type: ignore[typeddict-item]
        state["methodology_findings"] = _fixture_to_methodology_findings(fixture)  # type: ignore[typeddict-item]

    config = {"configurable": {"thread_id": thread_id}}

    # Run to the first interrupt, then auto-approve every gate until the
    # pipeline reaches a terminal stage or no more interrupts are pending.
    app.graph.invoke(state, config)
    for _ in range(50):  # safety bound on revision loops
        snapshot = app.graph.get_state(config)
        pending = _interrupt_values(snapshot)
        if not pending:
            break
        app.graph.invoke(
            Command(resume=_auto_resume_payload(pending[0])),
            config,
        )
    return thread_id


def _render_manuscript(state: dict[str, Any]) -> None:
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
        col2.metric(translate("label_section_count"), summary.get("section_count", 0))
        col3.metric(translate("label_claim_count"), summary.get("claim_count", 0))
        status = summary.get("status", "")
        col4.metric(translate("label_manuscript_status"), status)

    total_words = sum(s.get("word_count", 0) for s in sections)
    if total_words:
        st.caption(f"{translate('label_word_count')}: {total_words}")

    for section in sorted(sections, key=lambda s: s.get("order", 0)):
        stype = section.get("section_type", "section")
        content = section.get("content", "")
        with st.expander(stype.title(), expanded=False):
            st.write(content)


def _render_claims(state: dict[str, Any]) -> None:
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


def _render_citations(state: dict[str, Any]) -> None:
    """Display citation drafts linking claims to literature records."""

    citations = state.get("citation_drafts", [])
    if not citations:
        st.info(translate("info_no_citations"))
        return

    st.subheader(translate("section_citations"))
    rows = []
    for c in citations:
        rows.append(
            {
                translate("col_citation_key"): c.get("citation_key", ""),
                translate("col_lit_record"): c.get("literature_record_id", "")[:16],
                translate("col_section"): c.get("section_id", "")[:24],
                translate("col_claim_type"): c.get("claim_id", "")[:24],
            }
        )
    st.dataframe(rows, use_container_width=True, hide_index=True)


def _render_claim_audit(state: dict[str, Any]) -> None:
    """Display claim audit results (factual support, numeric consistency, etc.)."""

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


def _render_review(state: dict[str, Any]) -> None:
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


def _render_compliance(state: dict[str, Any]) -> None:
    """Display STROBE-Vet compliance audit findings and checklist summary."""

    findings = state.get("compliance_findings", [])
    checklist = state.get("checklist_summary")
    readiness = state.get("export_readiness")
    if not findings and checklist is None:
        st.info(translate("info_no_compliance"))
        return

    st.subheader(translate("section_compliance"))

    if readiness:
        st.metric(translate("label_export_readiness"), readiness)

    if checklist:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric(translate("label_passed"), checklist.get("passed", 0))
        col2.metric(translate("label_failed"), checklist.get("failed", 0))
        col3.metric(
            translate("label_not_applicable"),
            checklist.get("not_applicable", 0),
        )
        col4.metric(translate("label_needs_review"), checklist.get("needs_review", 0))

    if findings:
        rows = []
        for f in findings:
            rows.append(
                {
                    translate("col_rule_id"): f.get("rule_id", ""),
                    translate("col_category"): f.get("category", ""),
                    translate("col_severity"): f.get("severity", ""),
                    translate("col_status"): f.get("status", ""),
                    translate("col_evidence"): f.get("evidence", ""),
                    translate("col_recommendation"): f.get("recommendation", ""),
                }
            )
        st.dataframe(rows, use_container_width=True, hide_index=True)


@st.cache_data(show_spinner=False)
def _regenerate_export_package(_state_hash: str) -> tuple[Any, ...] | None:
    """Placeholder kept for potential future caching; current implementation
    regenerates inline in ``_render_export`` to access live state.
    """

    return None


def _render_export(state: dict[str, Any]) -> None:
    """Display export package summary with download buttons for components."""

    package = state.get("export_package")
    if package is None:
        st.info(translate("info_no_export"))
        return

    st.subheader(translate("section_export"))

    col1, col2 = st.columns(2)
    col1.metric(translate("col_components"), package.get("component_count", 0))
    col2.metric(
        translate("label_manuscript_status"),
        package.get("status", ""),
    )
    st.caption(f"{translate('col_package_uri')}: `{package.get('package_uri', '')}`")

    # Regenerate components for download from current state
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

    # Download buttons for each component
    import base64

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

        # DOCX content is base64; other components are plain text
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

    # Component table
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
        st.dataframe(comp_rows, use_container_width=True, hide_index=True)


def _render_golden_demo_run(app: Application) -> None:
    """Render the demo pipeline run controls (Run / Clear buttons)."""

    st.subheader(translate("golden_run_header"))
    st.caption(translate("golden_run_description_full"))

    col_run, col_clear = st.columns([1, 1])
    run_clicked = col_run.button(translate("golden_button_run"))
    clear_clicked = col_clear.button(translate("golden_button_clear"))

    if clear_clicked:
        st.session_state.pop("golden_demo_thread_id", None)
        st.rerun()

    if run_clicked:
        with st.spinner(translate("golden_run_header")):
            try:
                thread_id = _run_golden_demo_pipeline(app)
                st.session_state["golden_demo_thread_id"] = thread_id
                st.success(translate("golden_run_started"))
            except (LookupError, PermissionError, ValueError) as exc:
                st.error(str(exc))
                st.session_state.pop("golden_demo_thread_id", None)


def _render_golden_demo_status(app: Application) -> dict[str, Any] | None:
    """Return the pipeline state if a demo run exists, else ``None``.

    When a run exists, renders a 4-column status bar with thread id,
    stage, run status, and audit-event count.
    """

    thread_id = st.session_state.get("golden_demo_thread_id")
    if not isinstance(thread_id, str):
        return None

    config = {"configurable": {"thread_id": thread_id}}
    snapshot = app.graph.get_state(config)
    state: dict[str, Any] = snapshot.values

    col1, col2, col3, col4 = st.columns(4)
    col1.metric(translate("label_thread_id"), thread_id[:20])
    col2.metric(translate("label_stage"), stage_label(state.get("current_stage")))
    col3.metric(translate("label_status"), status_label(state.get("run_status")))
    audit_count = len(state.get("audit_events", []))
    col4.metric(translate("pipeline_stage_count"), audit_count)

    return state


def _render_golden_demo_results(
    state: dict[str, Any],
    fixture: dict[str, Any],
) -> None:
    """Render pipeline-derived results organised into navigable tabs."""

    st.subheader(translate("golden_pipeline_results"))

    tab_data, tab_lit, tab_method, tab_manuscript, tab_review, tab_export = st.tabs(
        [
            translate("tab_data_inputs"),
            translate("tab_lit_evidence"),
            translate("tab_method_stats"),
            translate("tab_manuscript"),
            translate("tab_review_compliance"),
            translate("tab_export"),
        ]
    )

    with tab_data:
        _render_golden_dataset()
        _render_golden_dictionary(fixture)

    with tab_lit:
        _render_literature_records(state)
        _render_evidence_items(state)

    with tab_method:
        _render_methodology_findings(state)
        _render_analysis_plan(state)
        _render_statistical_results(state)

    with tab_manuscript:
        _render_manuscript(state)
        _render_claims(state)
        _render_citations(state)
        _render_claim_audit(state)

    with tab_review:
        _render_review(state)
        _render_compliance(state)

    with tab_export:
        _render_export(state)
        _render_usage_summary(state)


def _render_golden_data_reference(fixture: dict[str, Any]) -> None:
    """Show static fixture data in expanders before the pipeline runs."""

    st.subheader(translate("golden_data_reference"))
    st.caption(translate("golden_data_reference_hint"))

    with st.expander(translate("golden_section_literature"), expanded=False):
        _render_golden_literature(fixture)

    with st.expander(translate("golden_section_dataset"), expanded=False):
        _render_golden_dataset()

    with st.expander(translate("golden_section_dictionary"), expanded=False):
        _render_golden_dictionary(fixture)

    with st.expander(translate("golden_section_analysis_plan"), expanded=False):
        _render_golden_analysis_plan(fixture)

    with st.expander(translate("golden_section_methodology"), expanded=False):
        _render_golden_methodology(fixture)


def _render_golden_demo(app: Application) -> None:
    """Render the full Golden Project demo view.

    Project overview and pipeline controls are always visible. Before the
    pipeline runs, static fixture data is shown in expanders as reference.
    After running, all derived outputs are organised into navigable tabs:
    Data inputs, Literature & evidence, Methodology & statistics,
    Manuscript, Review & compliance, and Export.
    """

    st.title(translate("golden_demo_title"))
    st.caption(translate("golden_demo_caption"))

    error = st.session_state.pop("golden_fixture_error", None)
    if error:
        st.error(translate("golden_demo_load_error", error=error))

    fixture = _load_golden_fixture()
    if fixture is None:
        st.error(translate("golden_demo_load_error", error="fixture not found"))
        return

    # Project overview (always visible)
    _render_golden_overview(fixture)
    st.divider()

    # Pipeline run controls
    _render_golden_demo_run(app)
    st.divider()

    # Results (if pipeline has run) or data reference (before running)
    state = _render_golden_demo_status(app)
    if state is not None:
        _render_golden_demo_results(state, fixture)
    else:
        _render_golden_data_reference(fixture)
        st.info(translate("golden_run_no_thread"))


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
    view_mode = _render_view_mode_switch()
    app = get_application()

    if view_mode == "golden_demo":
        _render_golden_demo(app)
        return

    st.title(translate("app_title"))
    st.caption(translate("app_caption_full"))
    _render_project_creation(app)
    st.divider()
    _render_projects(app)
    project_id = st.session_state.get("project_id")
    if isinstance(project_id, str):
        _render_workflow(app, project_id)


if __name__ == "__main__":
    main()
