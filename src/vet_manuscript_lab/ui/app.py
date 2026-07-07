"""Streamlit UI for the Foundation + Literature & Evidence pipeline.

Run with: streamlit run src/vet_manuscript_lab/ui/app.py
"""

from __future__ import annotations

import csv
import io
import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import streamlit as st
from langgraph.types import Command

from vet_manuscript_lab.config import Settings
from vet_manuscript_lab.domain.conventions import utc_now
from vet_manuscript_lab.infrastructure.artifacts import LocalArtifactStore
from vet_manuscript_lab.infrastructure.checkpoints import open_checkpointer
from vet_manuscript_lab.infrastructure.database import create_database
from vet_manuscript_lab.infrastructure.database.governance import GovernanceRepository
from vet_manuscript_lab.infrastructure.database.literature import (
    LiteratureInput,
    LiteratureRepository,
)
from vet_manuscript_lab.infrastructure.database.repository import (
    FoundationRepository,
    ProjectInput,
)
from vet_manuscript_lab.services.documents import DocumentImporter
from vet_manuscript_lab.services.zotero import (
    ZoteroClient,
    ZoteroConfig,
    ZoteroSynchroniser,
)
from vet_manuscript_lab.ui.i18n import (
    DEFAULT_LANGUAGE,
    LANGUAGE_LABELS,
    SUPPORTED_LANGUAGES,
    gate_field,
    stage_label,
    translate,
)
from vet_manuscript_lab.ui.theme import (
    apply_theme,
    render_hero,
    render_phase_tracker,
    render_run_metrics,
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
    literature_repository: LiteratureRepository
    document_importer: DocumentImporter
    governance: GovernanceRepository
    settings: Settings
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
    literature_repository = LiteratureRepository(database.sessions)
    document_importer = DocumentImporter(
        LocalArtifactStore(settings.artifact_root), literature_repository
    )
    governance = GovernanceRepository(database.sessions)
    connection, checkpointer = open_checkpointer(
        database_url=settings.database_url,
        checkpoint_path=settings.checkpoint_path,
    )
    graph = build_compliance_pipeline_graph(checkpointer)
    return Application(
        repository=repository,
        literature_repository=literature_repository,
        document_importer=document_importer,
        governance=governance,
        settings=settings,
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


# Ordered workflow stages for sidebar progress tracking.
_STAGE_ORDER = [
    "project_init",
    "research_question",
    "question_approval",
    "guideline_mapping",
    "protocol_approval",
    "protocol_lock",
    "literature_search",
    "search_approval",
    "screening",
    "evidence_extraction",
    "evidence_audit",
    "methodology_critic",
    "analysis_plan_approval",
    "analysis_plan_lock",
    "statistics_execution",
    "results_approval",
    "writing",
    "claim_audit",
    "review",
    "revision",
    "final_compliance_audit",
    "final_sign_off",
    "export",
    "complete",
]


def _render_sidebar_header() -> None:
    st.sidebar.markdown(
        f"""<div class="sidebar-brand"><strong>{translate("app_title")}</strong>
        <span>{translate("sidebar_tagline")}</span></div>""",
        unsafe_allow_html=True,
    )


def _render_sidebar_context(app: Application, project_id: str | None) -> None:
    """Render the *Production flow* checklist in the sidebar."""
    if project_id is None:
        return

    intake = st.session_state.get(f"analysis_intake:{project_id}", {})
    stage_idx = -1
    run_complete = False
    thread_id = _get_active_thread(project_id)
    if thread_id is not None:
        snapshot = app.graph.get_state(
            {"configurable": {"thread_id": thread_id}}
        )
        current = snapshot.values.get("current_stage", "project_init")
        run_complete = snapshot.values.get("run_status") == "complete"
        if current in _STAGE_ORDER:
            stage_idx = _STAGE_ORDER.index(current)

    def _past(stage_name: str) -> bool:
        return stage_idx >= _STAGE_ORDER.index(stage_name)

    steps = [
        (translate("flow_study_design"), bool(intake.get("research_question_input"))),
        (
            translate("flow_data_prep"),
            bool(intake.get("dataset_summary"))
            and bool(intake.get("literature_record_drafts")),
        ),
        (translate("flow_protocol_approval"), _past("protocol_lock")),
        (translate("flow_evidence_extraction"), _past("evidence_audit")),
        (translate("flow_statistical_analysis"), _past("results_approval")),
        (translate("flow_manuscript_review"), _past("review")),
        (translate("flow_compliance_export"), _past("export") or run_complete),
    ]

    st.sidebar.divider()
    st.sidebar.markdown(f"#### {translate('sidebar_production_flow')}")
    for label, done in steps:
        marker = "[x]" if done else "[ ]"
        st.sidebar.markdown(
            f'<div class="side-step">{marker}&nbsp;&nbsp;{label}</div>',
            unsafe_allow_html=True,
        )


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
    with st.sidebar.expander(
        translate("sidebar_new_project"), expanded=False
    ):
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
            submitted = st.form_submit_button(
                translate("button_create"), type="primary", use_container_width=True
            )
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
                st.session_state["project_created_notice"] = translate(
                    "success_project_created", id=project.id
                )
                st.rerun()


def _render_projects(app: Application) -> None:
    """Render project selector in the sidebar (without showing IDs)."""

    projects = app.repository.list_projects()
    notice = st.session_state.pop("project_created_notice", None)
    if isinstance(notice, str):
        st.sidebar.success(notice)
    if not projects:
        st.sidebar.info(translate("info_no_projects"))
        return
    labels = {project.id: project.title for project in projects}
    project_ids = list(labels)
    current_project_id = st.session_state.get("project_id")
    selected_index = (
        project_ids.index(current_project_id)
        if current_project_id in project_ids
        else 0
    )
    selected = st.sidebar.selectbox(
        translate("field_active_project"),
        options=project_ids,
        format_func=lambda project_id: labels[project_id],
        index=selected_index,
    )
    st.session_state["project_id"] = selected


def _render_sidebar_project_management(
    app: Application, project_id: str
) -> None:
    """Render rename / delete buttons for the active project in the sidebar."""

    with st.sidebar.expander(
        translate("sidebar_project_management"), expanded=False
    ):
        with st.form("rename_project"):
            new_title = st.text_input(
                translate("field_new_title"),
            )
            rename_clicked = st.form_submit_button(
                translate("button_rename_project"), use_container_width=True
            )
        if rename_clicked:
            try:
                app.repository.rename_project(project_id, new_title)
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.session_state["project_renamed_notice"] = translate(
                    "success_project_renamed"
                )
                st.rerun()

        if st.button(
            translate("button_delete_project"),
            use_container_width=True,
            type="secondary",
        ):
            st.session_state["confirm_delete"] = project_id

    confirm = st.session_state.get("confirm_delete")
    if confirm == project_id:
        st.sidebar.warning(translate("confirm_delete_project"))
        c_del, c_cancel = st.sidebar.columns(2)
        if c_del.button(
            "OK", type="primary", use_container_width=True, key="confirm_del"
        ):
            try:
                app.repository.delete_project(project_id)
            except (ValueError, OSError) as exc:
                st.error(str(exc))
            else:
                st.session_state.pop("confirm_delete", None)
                st.session_state.pop("project_id", None)
                st.session_state["project_deleted_notice"] = translate(
                    "success_project_deleted"
                )
                st.rerun()
        if c_cancel.button(
            translate("label_no"), use_container_width=True, key="cancel_del"
        ):
            st.session_state.pop("confirm_delete", None)
            st.rerun()

    deleted_notice = st.session_state.pop("project_deleted_notice", None)
    renamed_notice = st.session_state.pop("project_renamed_notice", None)
    if isinstance(deleted_notice, str):
        st.sidebar.success(deleted_notice)
    if isinstance(renamed_notice, str):
        st.sidebar.success(renamed_notice)


def _literature_draft(record: Any) -> dict[str, Any]:
    return {
        "record_id": record.id,
        "title": record.title,
        "doi": record.doi,
        "pmid": record.pmid,
        "journal": record.journal,
        "publication_year": record.publication_year,
        "screening_decision": "pending",
    }


def _render_intake_question(intake: dict[str, Any]) -> None:
    """Render the PECO research-question form."""

    question = dict(intake.get("research_question_input", {}))
    with st.form("analysis-question"):
        objective = st.text_area(
            translate("field_objective"), value=question.get("objective", ""),
            height=68,
        )
        peco_cols = st.columns(4)
        population = peco_cols[0].text_input(
            translate("field_population"), value=question.get("population", "")
        )
        exposure = peco_cols[1].text_input(
            translate("field_exposure"), value=question.get("exposure", "")
        )
        comparator = peco_cols[2].text_input(
            translate("field_comparator"), value=question.get("comparator", "")
        )
        outcome = peco_cols[3].text_input(
            translate("field_outcome"), value=question.get("outcome", "")
        )
        hypothesis = st.text_input(
            translate("field_hypothesis"), value=question.get("hypothesis", "")
        )
        if st.form_submit_button(translate("button_save_question"), type="primary"):
            required = (objective, population, exposure, outcome)
            if not all(value.strip() for value in required):
                st.error(translate("error_required_fields"))
            else:
                intake["research_question_input"] = {
                    "objective": objective.strip(),
                    "population": population.strip(),
                    "exposure": exposure.strip(),
                    "comparator": comparator.strip(),
                    "outcome": outcome.strip(),
                    "hypothesis": hypothesis.strip(),
                }
                st.success(translate("success_question_saved"))


def _render_intake_materials(
    app: Application, project_id: str, intake: dict[str, Any]
) -> None:
    """Render literature search and dataset forms."""

    # ---- Literature / search strategy ----------------------------------
    search = dict(intake.get("search_strategy_input", {}))
    with st.form("search-strategy"):
        query = st.text_area(
            translate("field_search_query"), value=search.get("query", ""),
            height=68,
        )
        date_col, db_col = st.columns([1, 2])
        date_range = date_col.text_input(
            translate("field_date_range"),
            value=search.get("date_range", "2018-01-01/2026-12-31"),
        )
        databases = db_col.multiselect(
            translate("field_databases"),
            ["PubMed", "CAB Abstracts", "Web of Science", "Scopus"],
            default=search.get("databases", ["PubMed", "CAB Abstracts"]),
        )
        if st.form_submit_button(translate("button_save_search")):
            if not query.strip():
                st.error(translate("error_search_required"))
            else:
                intake["search_strategy_input"] = {
                    "query": query.strip(),
                    "databases": databases,
                    "date_range": date_range.strip(),
                }
                st.success(translate("success_search_saved"))

    col_zotero, col_manual = st.columns(2)
    with col_zotero:
        st.markdown("##### Zotero")
        if app.settings.zotero_enabled:
            if st.button(translate("button_sync_zotero"), type="primary"):
                try:
                    client = ZoteroClient(
                        ZoteroConfig(
                            library_id=app.settings.zotero_library_id,
                            api_key=app.settings.zotero_api_key,
                            library_type=app.settings.zotero_library_type,
                        )
                    )
                    result = ZoteroSynchroniser(
                        client, app.literature_repository
                    ).sync_library(project_id=project_id, fetch_attachments=True)
                except Exception as exc:
                    st.error(translate("error_zotero_sync", error=exc))
                else:
                    st.success(
                        translate(
                            "success_zotero_sync",
                            fetched=result.fetched,
                            created=result.created,
                        )
                    )
        else:
            st.info(translate("info_zotero_config"))
    with col_manual:
        st.markdown(f"##### {translate('manual_entry_header')}")
        with st.form("manual-literature", clear_on_submit=True):
            lit_title = st.text_input(translate("field_literature_title"))
            lit_doi = st.text_input("DOI", placeholder="10.1038/...")
            if st.form_submit_button(translate("button_add_literature")):
                try:
                    app.literature_repository.create_literature_record(
                        project_id=project_id,
                        data=LiteratureInput(
                            title=lit_title, doi=lit_doi.strip() or None
                        ),
                    )
                except (ValueError, PermissionError) as exc:
                    st.error(str(exc))
                else:
                    st.success(translate("success_literature_added"))

    records = app.literature_repository.list_literature_records(project_id)
    if records:
        intake["literature_record_drafts"] = [
            _literature_draft(record) for record in records
        ]
        st.dataframe(
            [
                {
                    translate("col_title"): r.title,
                    "DOI": r.doi or "",
                    translate("col_year"): r.publication_year or "",
                }
                for r in records
            ],
            use_container_width=True,
            hide_index=True,
        )
        record_labels = {r.id: r.title for r in records}
        target_id = st.selectbox(
            translate("field_pdf_record"),
            list(record_labels),
            format_func=lambda value: record_labels[value],
        )
        pdf = st.file_uploader(translate("field_import_pdf"), type=["pdf"])
        if pdf is not None and st.button(translate("button_archive_pdf")):
            result = app.document_importer.import_bytes(
                project_id=project_id,
                literature_record_id=target_id,
                attachment_key=pdf.name,
                pdf_bytes=pdf.getvalue(),
            )
            st.success(
                translate("success_pdf_archived", hash=result.content_hash[:20])
            )
    else:
        st.warning(translate("warning_no_literature"))

    # ---- Dataset -------------------------------------------------------
    st.markdown(f"##### {translate('tab_dataset_variables')}")
    uploaded = st.file_uploader(
        translate("field_upload_csv"), type=["csv"], key="analysis-dataset"
    )
    if uploaded is not None:
        content = uploaded.getvalue()
        rows = list(csv.reader(io.StringIO(content.decode("utf-8-sig"))))
        if not rows or not rows[0]:
            st.error(translate("error_empty_csv"))
        else:
            columns = rows[0]
            st.caption(
                translate(
                    "dataset_dimensions",
                    rows=len(rows) - 1,
                    columns=len(columns),
                    names=", ".join(columns),
                )
            )
            outcome_var = st.selectbox(translate("field_outcome_variable"), columns)
            exposure_var = st.selectbox(
                translate("field_exposure_variable"), columns
            )
            id_var = st.selectbox(
                translate("field_id_variable"), [translate("option_none"), *columns]
            )
            if st.button(translate("button_save_dataset"), type="primary"):
                from vet_manuscript_lab.domain.conventions import sha256_bytes

                dataset_id = str(uuid.uuid4())
                intake["dataset_summary"] = {
                    "dataset_id": dataset_id,
                    "dataset_version_id": str(uuid.uuid4()),
                    "name": uploaded.name,
                    "row_count": len(rows) - 1,
                    "variable_count": len(columns),
                    "content_hash": sha256_bytes(content),
                    "locked": False,
                }
                intake["variable_spec_drafts"] = [
                    {
                        "name": name,
                        "var_type": "continuous",
                        "role": (
                            "outcome"
                            if name == outcome_var
                            else "exposure"
                            if name == exposure_var
                            else "id"
                            if name == id_var
                            else "covariate"
                        ),
                        "unit": None,
                        "missing_code": None,
                    }
                    for name in columns
                ]
                st.success(translate("success_dataset_saved"))
    elif intake.get("dataset_summary"):
        dataset = intake["dataset_summary"]
        st.success(
            translate(
                "success_dataset_ready",
                name=dataset["name"],
                rows=dataset["row_count"],
            )
        )


def _compute_intake_ready(intake: dict[str, Any]) -> bool:
    """Return *True* when all four intake requirements are satisfied."""

    return all(
        [
            bool(intake.get("research_question_input")),
            bool(intake.get("search_strategy_input")),
            bool(intake.get("literature_record_drafts")),
            bool(intake.get("dataset_summary")),
        ]
    )


def _thread_session_key(project_id: str) -> str:
    return f"thread_id:{project_id}"


def _set_active_thread(project_id: str, thread_id: str) -> None:
    st.session_state[_thread_session_key(project_id)] = thread_id
    st.session_state["thread_id"] = thread_id


def _get_active_thread(project_id: str) -> str | None:
    thread_id = st.session_state.get(_thread_session_key(project_id))
    return thread_id if isinstance(thread_id, str) else None


def _drive_pipeline_to_completion(
    app: Application, state: dict[str, Any], thread_id: str
) -> None:
    config = {"configurable": {"thread_id": thread_id}}
    app.graph.invoke(state, config)
    for _ in range(50):
        snapshot = app.graph.get_state(config)
        pending = _interrupt_values(snapshot)
        if not pending:
            break
        app.graph.invoke(Command(resume=_auto_resume_payload(pending[0])), config)


def _start_workflow(app: Application, project_id: str) -> None:
    thread_id = str(uuid.uuid4())
    run = app.repository.create_run(project_id, thread_id)
    state = new_workflow_state(
        project_id=project_id,
        workflow_run_id=run.id,
        thread_id=thread_id,
        now=utc_now(),
    )
    intake = st.session_state.get(f"analysis_intake:{project_id}", {})
    if isinstance(intake, dict):
        state.update(intake)
    config = {"configurable": {"thread_id": thread_id}}
    app.graph.invoke(state, config)
    app.governance.sync_state(app.graph.get_state(config).values)
    _set_active_thread(project_id, thread_id)


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


def _golden_research_question(fixture: dict[str, Any]) -> dict[str, str]:
    rq = fixture.get("project", {}).get("research_question", {})
    return {
        "objective": (
            "Assess the association between synthetic treatment A and overall "
            "survival in a retrospective canine/feline referral cohort."
        ),
        "population": rq.get("population", ""),
        "exposure": rq.get("exposure", ""),
        "comparator": rq.get("comparator", ""),
        "outcome": rq.get("outcome", ""),
        "hypothesis": (
            "Synthetic treatment A is associated with improved overall survival "
            "after adjusting for age and species."
        ),
    }


def _golden_search_strategy() -> dict[str, Any]:
    return {
        "query": (
            "(veterinary OR canine OR feline) AND (survival OR \"time-to-event\") "
            "AND (retrospective OR observational) AND (treatment OR exposure)"
        ),
        "databases": ["PubMed", "CAB Abstracts", "Web of Science"],
        "date_range": "2021-01-01/2026-12-31",
    }


def _golden_dataset_summary(fixture: dict[str, Any]) -> dict[str, Any]:
    from vet_manuscript_lab.domain.conventions import sha256_bytes

    dictionary = fixture.get("dictionary", {})
    dataset = dictionary.get("dataset", {})
    csv_bytes = (GOLDEN_FIXTURE_ROOT / "data" / "cases_synthetic.csv").read_bytes()
    return {
        "dataset_id": "golden-dataset",
        "dataset_version_id": "golden-dataset-v1",
        "name": dataset.get("name", "Golden Project dataset"),
        "row_count": dataset.get("row_count", 0),
        "variable_count": dataset.get("column_count", 0),
        "content_hash": sha256_bytes(csv_bytes),
        "locked": False,
    }


def _build_golden_workspace_intake(fixture: dict[str, Any]) -> dict[str, Any]:
    return {
        "research_question_input": _golden_research_question(fixture),
        "search_strategy_input": _golden_search_strategy(),
        "literature_record_drafts": _fixture_to_literature_drafts(fixture),
        "dataset_summary": _golden_dataset_summary(fixture),
        "variable_spec_drafts": _fixture_to_variable_drafts(fixture),
        "analysis_spec_drafts": _fixture_to_analysis_drafts(fixture),
        "methodology_findings": _fixture_to_methodology_findings(fixture),
    }


def _ensure_golden_workspace_project(app: Application, fixture: dict[str, Any]) -> str:
    project_meta = fixture.get("project", {}).get("project", {})
    title = str(project_meta.get("title", "Golden Project")).strip()
    for project in app.repository.list_projects():
        if project.title == title:
            return project.id

    project = app.repository.create_project(
        ProjectInput(
            title=title,
            study_type=str(
                project_meta.get(
                    "study_type", "retrospective_observational_clinical_study"
                )
            ),
            species_scope=list(project_meta.get("species_scope", ["canine", "feline"])),
            owner_id="golden-demo",
        )
    )
    return project.id


def _seed_golden_literature_records(
    app: Application, project_id: str, fixture: dict[str, Any]
) -> None:
    for record in fixture.get("literature", {}).get("records", []):
        doi = record.get("doi")
        if isinstance(doi, str) and doi and app.literature_repository.find_by_doi(
            project_id, doi
        ):
            continue
        app.literature_repository.create_literature_record(
            project_id=project_id,
            data=LiteratureInput(
                title=str(record.get("title", "")),
                doi=doi if isinstance(doi, str) and doi else None,
                publication_year=record.get("year"),
                journal=record.get("journal"),
                creators=[{"name": author} for author in record.get("authors", [])],
                metadata_json={
                    "tags": record.get("tags", []),
                    "abstract": record.get("abstract", ""),
                    "fixture": "golden_project",
                },
            ),
        )


def _prepare_golden_workspace(app: Application) -> str:
    fixture = _load_golden_fixture()
    if fixture is None:
        raise ValueError("golden fixture not found")

    project_id = _ensure_golden_workspace_project(app, fixture)
    _seed_golden_literature_records(app, project_id, fixture)
    st.session_state[f"analysis_intake:{project_id}"] = (
        _build_golden_workspace_intake(fixture)
    )
    st.session_state["project_id"] = project_id
    st.session_state.pop(_thread_session_key(project_id), None)
    st.session_state.pop("thread_id", None)
    return project_id


def _run_golden_workspace_pipeline(app: Application) -> tuple[str, str]:
    fixture = _load_golden_fixture()
    if fixture is None:
        raise ValueError("golden fixture not found")

    project_id = _ensure_golden_workspace_project(app, fixture)
    _seed_golden_literature_records(app, project_id, fixture)
    intake = _build_golden_workspace_intake(fixture)
    st.session_state[f"analysis_intake:{project_id}"] = intake
    st.session_state["project_id"] = project_id

    thread_id = f"golden-workspace-{uuid.uuid4().hex[:8]}"
    run = app.repository.create_run(project_id, thread_id)
    state = new_workflow_state(
        project_id=project_id,
        workflow_run_id=run.id,
        thread_id=thread_id,
        now=utc_now(),
        species_scope=list(
            fixture.get("project", {})
            .get("project", {})
            .get("species_scope", ["canine", "feline"])
        ),
    )
    state.update(intake)
    _drive_pipeline_to_completion(app, state, thread_id)
    _set_active_thread(project_id, thread_id)
    return project_id, thread_id


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


def _render_workspace_actions(app: Application) -> None:
    notice = st.session_state.pop("golden_workspace_notice", None)
    if isinstance(notice, str):
        st.success(notice)

    st.subheader(translate("workspace_actions_header"))
    st.caption(translate("workspace_actions_caption"))
    col_load, col_run = st.columns(2)
    load_clicked = col_load.button(
        translate("golden_workspace_load"), use_container_width=True
    )
    run_clicked = col_run.button(
        translate("golden_workspace_run"),
        type="primary",
        use_container_width=True,
    )

    if load_clicked:
        try:
            with st.spinner(translate("golden_workspace_loading")):
                project_id = _prepare_golden_workspace(app)
        except (OSError, ValueError) as exc:
            st.error(translate("golden_demo_load_error", error=str(exc)))
        else:
            st.session_state["golden_workspace_notice"] = translate(
                "golden_workspace_loaded", id=project_id[:8]
            )
            st.rerun()

    if run_clicked:
        try:
            with st.spinner(translate("golden_workspace_running")):
                project_id, _thread_id = _run_golden_workspace_pipeline(app)
        except (OSError, ValueError) as exc:
            st.error(translate("golden_demo_load_error", error=str(exc)))
        else:
            st.session_state["golden_workspace_notice"] = translate(
                "golden_workspace_finished", id=project_id[:8]
            )
            st.rerun()


def _render_pending_approval(
    app: Application,
    config: dict[str, Any],
    gate: dict[str, Any],
) -> None:
    gate_name = gate["gate"]
    st.markdown('<div class="approval-card">', unsafe_allow_html=True)
    st.subheader(translate("pending_action_header"))
    st.caption(translate("pending_action_caption", stage=stage_label(gate_name)))
    st.write(
        {
            translate("pending_action_gate"): gate_field(gate_name, "title"),
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
    st.markdown('</div>', unsafe_allow_html=True)

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


def _render_workflow(app: Application, project_id: str) -> None:
    intake = st.session_state.setdefault(f"analysis_intake:{project_id}", {})
    ready = _compute_intake_ready(intake)

    thread_id = _get_active_thread(project_id)
    state: dict[str, Any] = {}
    pending: list[dict[str, Any]] = []
    config: dict[str, Any] | None = None
    if thread_id is not None:
        config = {"configurable": {"thread_id": thread_id}}
        snapshot = app.graph.get_state(config)
        state = snapshot.values
        pending = _interrupt_values(snapshot)

    (
        tab_design,
        tab_data,
        tab_control,
        tab_lit,
        tab_method,
        tab_manuscript,
        tab_review,
        tab_export,
    ) = st.tabs(
        [
            translate("tab_intake_question"),
            translate("tab_intake_data"),
            translate("tab_pipeline_control"),
            translate("tab_lit_evidence"),
            translate("tab_method_stats"),
            translate("tab_manuscript"),
            translate("tab_review_compliance"),
            translate("tab_export"),
        ]
    )

    # ---- Tab: Study design --------------------------------------------
    with tab_design:
        _render_intake_question(intake)

    # ---- Tab: Data preparation ----------------------------------------
    with tab_data:
        _render_intake_materials(app, project_id, intake)

    # ---- Tab: Pipeline & approval -------------------------------------
    with tab_control:
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
            translate("readiness_dataset"): bool(intake.get("dataset_summary")),
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
            _start_workflow(app, project_id)
            st.rerun()

        if thread_id is not None and config is not None:
            render_phase_tracker(state.get("current_stage"))
            render_run_metrics(state, thread_id)
            next_nodes = ", ".join(snapshot.next) if snapshot.next else "-"
            st.caption(f"{translate('label_next')}: {next_nodes}")
            if pending:
                _render_pending_approval(app, config, pending[0])
            _render_search_strategy_detail(state)
            with st.expander(translate("expander_artifact_refs"), expanded=False):
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
            if not pending and state.get("run_status") == "complete":
                st.success(translate("success_pipeline_complete"))

    # ---- Result tabs (guarded by state availability) ------------------
    with tab_lit:
        if state:
            _render_literature_records(state)
            _render_evidence_items(state)
        else:
            st.info(translate("info_start_pipeline"))
    with tab_method:
        if state:
            _render_methodology_findings(state)
            _render_analysis_plan(state)
            _render_statistical_results(state)
        else:
            st.info(translate("info_start_pipeline"))
    with tab_manuscript:
        if state:
            _render_manuscript(state)
            _render_claims(state)
            _render_citations(state)
            _render_claim_audit(state)
        else:
            st.info(translate("info_start_pipeline"))
    with tab_review:
        if state:
            _render_review(state)
            _render_compliance(state)
        else:
            st.info(translate("info_start_pipeline"))
    with tab_export:
        if state:
            _render_export(state)
            _render_usage_summary(state)
        else:
            st.info(translate("info_start_pipeline"))


def main() -> None:
    st.set_page_config(
        page_title=translate("page_title"), page_icon=":microscope:", layout="wide"
    )
    apply_theme()
    _render_sidebar_header()
    app = get_application()

    # Sidebar: project selector
    _render_projects(app)

    project_id = st.session_state.get("project_id")
    active_project_id = project_id if isinstance(project_id, str) else None

    # Sidebar: project management (rename / delete)
    if active_project_id is not None:
        _render_sidebar_project_management(app, active_project_id)

    # Sidebar: new project creation
    _render_project_creation(app)

    # Sidebar: workspace context (readiness + progress)
    _render_sidebar_context(app, active_project_id)

    # Sidebar: language switch (at bottom)
    _render_language_switch()

    # Main area
    render_hero()
    if active_project_id is not None:
        _render_workflow(app, active_project_id)


if __name__ == "__main__":
    main()
