"""Golden Project fixture helpers for workspace seeding and pipeline demo."""

from __future__ import annotations

import uuid
from typing import Any, cast

import streamlit as st

from vet_manuscript_lab.domain.conventions import sha256_bytes, utc_now
from vet_manuscript_lab.infrastructure.database.literature import LiteratureInput
from vet_manuscript_lab.infrastructure.database.repository import ProjectInput
from vet_manuscript_lab.ui.application import (
    GOLDEN_FIXTURE_ROOT,
    Application,
    load_golden_fixture,
)
from vet_manuscript_lab.ui.state import (
    drive_pipeline_to_completion,
    set_active_thread,
    thread_session_key,
)
from vet_manuscript_lab.workflow.state import new_workflow_state


def fixture_to_literature_drafts(fixture: dict[str, Any]) -> list[dict[str, Any]]:
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


def fixture_to_variable_drafts(fixture: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert golden fixture variables to WorkflowState drafts."""

    return list(fixture.get("dictionary", {}).get("variables", []))


def fixture_to_analysis_drafts(fixture: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert golden fixture analyses to WorkflowState drafts."""

    return list(fixture.get("analysis_plan", {}).get("plan", {}).get("analyses", []))


def fixture_to_methodology_findings(fixture: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert golden fixture methodology findings to WorkflowState entries."""

    return list(fixture.get("methodology", {}).get("findings", []))


def golden_research_question(fixture: dict[str, Any]) -> dict[str, str]:
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


def golden_search_strategy() -> dict[str, Any]:
    return {
        "query": (
            '(veterinary OR canine OR feline) AND (survival OR "time-to-event") '
            "AND (retrospective OR observational) AND (treatment OR exposure)"
        ),
        "databases": ["PubMed", "CAB Abstracts", "Web of Science"],
        "date_range": "2021-01-01/2026-12-31",
    }


def golden_dataset_summary(fixture: dict[str, Any]) -> dict[str, Any]:
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


def build_golden_workspace_intake(fixture: dict[str, Any]) -> dict[str, Any]:
    return {
        "research_question_input": golden_research_question(fixture),
        "search_strategy_input": golden_search_strategy(),
        "literature_record_drafts": fixture_to_literature_drafts(fixture),
        "dataset_summary": golden_dataset_summary(fixture),
        "variable_spec_drafts": fixture_to_variable_drafts(fixture),
        "analysis_spec_drafts": fixture_to_analysis_drafts(fixture),
        "methodology_findings": fixture_to_methodology_findings(fixture),
    }


def ensure_golden_workspace_project(
    app: Application, fixture: dict[str, Any]
) -> str:
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
            species_scope=list(
                project_meta.get("species_scope", ["canine", "feline"])
            ),
            owner_id="golden-demo",
        )
    )
    return project.id


def seed_golden_literature_records(
    app: Application, project_id: str, fixture: dict[str, Any]
) -> None:
    for record in fixture.get("literature", {}).get("records", []):
        doi = record.get("doi")
        if (
            isinstance(doi, str)
            and doi
            and app.literature_repository.find_by_doi(project_id, doi)
        ):
            continue
        app.literature_repository.create_literature_record(
            project_id=project_id,
            data=LiteratureInput(
                title=str(record.get("title", "")),
                doi=doi if isinstance(doi, str) and doi else None,
                publication_year=record.get("year"),
                journal=record.get("journal"),
                creators=[
                    {"name": author} for author in record.get("authors", [])
                ],
                metadata_json={
                    "tags": record.get("tags", []),
                    "abstract": record.get("abstract", ""),
                    "fixture": "golden_project",
                },
            ),
        )


def prepare_golden_workspace(
    app: Application, bump_search_form_version: Any
) -> str:
    fixture = load_golden_fixture()
    if fixture is None:
        raise ValueError("golden fixture not found")

    project_id = ensure_golden_workspace_project(app, fixture)
    seed_golden_literature_records(app, project_id, fixture)
    st.session_state[f"analysis_intake:{project_id}"] = (
        build_golden_workspace_intake(fixture)
    )
    st.session_state["project_id"] = project_id
    st.session_state.pop(thread_session_key(project_id), None)
    st.session_state.pop("thread_id", None)
    # Force the search-strategy form to reinitialize from the freshly loaded
    # Golden inputs (otherwise Streamlit widget stickiness keeps old values).
    bump_search_form_version(project_id)
    return project_id


def run_golden_workspace_pipeline(
    app: Application, bump_search_form_version: Any
) -> tuple[str, str]:
    fixture = load_golden_fixture()
    if fixture is None:
        raise ValueError("golden fixture not found")

    project_id = ensure_golden_workspace_project(app, fixture)
    seed_golden_literature_records(app, project_id, fixture)
    intake = build_golden_workspace_intake(fixture)
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
    cast(dict[str, Any], state).update(intake)
    drive_pipeline_to_completion(app, cast(dict[str, Any], state), thread_id)
    set_active_thread(project_id, thread_id)
    return project_id, thread_id


def ensure_golden_project_exists(app: Application) -> None:
    """Ensure the Golden Project fixture is present in the project list."""

    if st.session_state.get("_golden_seeded"):
        return
    fixture = load_golden_fixture()
    if fixture is None:
        return
    project_id = ensure_golden_workspace_project(app, fixture)
    st.session_state["_golden_project_id"] = project_id
    st.session_state["_golden_seeded"] = True
