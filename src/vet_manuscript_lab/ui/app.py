"""Minimal Foundation Streamlit UI.

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
from vet_manuscript_lab.workflow.foundation_graph import build_foundation_graph
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
    graph = build_foundation_graph(checkpointer)
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


def _render_workflow(app: Application, project_id: str) -> None:
    st.subheader(translate("workflow_header"))
    if st.button(translate("button_start_run")):
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

    with st.expander(translate("expander_artifact_refs"), expanded=False):
        st.json(state.get("artifacts", {}))
    with st.expander(translate("expander_approvals_locks"), expanded=False):
        st.json(
            {
                "approvals": state.get("approvals", {}),
                "locks": state.get("locks", {}),
            }
        )

    pending = _interrupt_values(snapshot)
    if not pending:
        if state.get("run_status") == "complete":
            st.success(translate("success_protocol_locked"))
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
    st.caption(translate("app_caption"))
    app = get_application()
    _render_project_creation(app)
    st.divider()
    _render_projects(app)
    project_id = st.session_state.get("project_id")
    if isinstance(project_id, str):
        _render_workflow(app, project_id)


if __name__ == "__main__":
    main()
