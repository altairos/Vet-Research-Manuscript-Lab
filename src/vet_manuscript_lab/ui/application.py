"""Application container and initialisation for the Streamlit workspace."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import streamlit as st

from vet_manuscript_lab.config import Settings
from vet_manuscript_lab.infrastructure.artifacts import LocalArtifactStore
from vet_manuscript_lab.infrastructure.checkpoints import open_checkpointer
from vet_manuscript_lab.infrastructure.database import create_database
from vet_manuscript_lab.infrastructure.database.governance import GovernanceRepository
from vet_manuscript_lab.infrastructure.database.literature import LiteratureRepository
from vet_manuscript_lab.infrastructure.database.repository import FoundationRepository
from vet_manuscript_lab.services.documents import DocumentImporter
from vet_manuscript_lab.workflow.compliance_graph import build_compliance_pipeline_graph

GOLDEN_FIXTURE_ROOT = (
    Path(__file__).resolve().parents[3] / "fixtures" / "golden_project"
)


@st.cache_data(show_spinner=False)
def load_golden_fixture() -> dict[str, Any] | None:
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
