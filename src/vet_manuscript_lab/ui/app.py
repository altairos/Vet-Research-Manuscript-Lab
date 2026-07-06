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


def _render_project_creation(app: Application) -> None:
    st.subheader("Create project")
    with st.form("create_project", clear_on_submit=True):
        title = st.text_input("Project title")
        owner_id = st.text_input("Owner ID")
        species = st.multiselect(
            "Species scope", ["canine", "feline"], default=["canine"]
        )
        submitted = st.form_submit_button("Create")
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
            st.success(f"Created project {project.id}")
            st.rerun()


def _render_projects(app: Application) -> None:
    projects = app.repository.list_projects()
    if not projects:
        st.info("No projects yet.")
        return
    labels = {project.id: f"{project.title} ({project.id[:8]})" for project in projects}
    selected = st.selectbox(
        "Active project",
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
    st.subheader("Foundation workflow")
    if st.button("Start new Foundation run"):
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
            "thread_id": thread_id,
            "stage": state.get("current_stage"),
            "status": state.get("run_status"),
            "next": snapshot.next,
        }
    )

    with st.expander("Artifact references", expanded=False):
        st.json(state.get("artifacts", {}))
    with st.expander("Approvals and locks", expanded=False):
        st.json(
            {
                "approvals": state.get("approvals", {}),
                "locks": state.get("locks", {}),
            }
        )

    pending = _interrupt_values(snapshot)
    if not pending:
        if state.get("run_status") == "complete":
            st.success("Protocol is approved and locked.")
        return

    gate = pending[0]
    st.warning(gate["title"])
    st.caption(gate["summary"])
    with st.form(f"approval_{gate['gate']}"):
        reviewer_id = st.text_input("Reviewer ID")
        reviewer_role = st.selectbox("Reviewer role", ["investigator", "statistician"])
        decision = st.selectbox("Decision", gate["allowed_decisions"])
        comment = st.text_area("Comment")
        submitted = st.form_submit_button("Submit decision")
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
    st.set_page_config(page_title="Vet Research Manuscript Lab", layout="wide")
    st.title("Vet Research Manuscript Lab")
    st.caption("Foundation MVP: project setup, approval gates, and protocol lock")
    app = get_application()
    _render_project_creation(app)
    st.divider()
    _render_projects(app)
    project_id = st.session_state.get("project_id")
    if isinstance(project_id, str):
        _render_workflow(app, project_id)


if __name__ == "__main__":
    main()
