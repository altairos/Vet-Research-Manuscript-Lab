"""Streamlit UI for the Foundation + Literature & Evidence pipeline.

Run with: streamlit run src/vet_manuscript_lab/ui/app.py
"""

from __future__ import annotations

from typing import Any

import streamlit as st

from vet_manuscript_lab.ui.application import Application, get_application
from vet_manuscript_lab.ui.golden import (
    ensure_golden_project_exists,
    prepare_golden_workspace,
)
from vet_manuscript_lab.ui.i18n import translate
from vet_manuscript_lab.ui.sidebar import (
    render_language_switch,
    render_project_creation,
    render_projects,
    render_sidebar_header,
    render_sidebar_project_management,
)
from vet_manuscript_lab.ui.state import (
    compute_intake_ready,
    get_active_thread,
    inject_beforeunload,
    interrupt_values,
    is_intake_dirty,
    snapshot_intake,
)
from vet_manuscript_lab.ui.tabs.compliance import (
    render_ai_disclosure,
    render_compliance_findings,
    render_export,
)
from vet_manuscript_lab.ui.tabs.intake import (
    bump_search_form_version,
    render_intake_materials,
    render_intake_question,
)
from vet_manuscript_lab.ui.tabs.literature import (
    render_evidence_items,
    render_literature_records,
)
from vet_manuscript_lab.ui.tabs.methodology import (
    render_analysis_plan,
    render_analysis_provenance,
    render_effect_plots,
    render_guideline_mapping,
    render_methodology_findings,
    render_statistical_results,
    render_usage_summary,
)
from vet_manuscript_lab.ui.tabs.pipeline import (
    render_pipeline_bar,
    render_workspace_actions,
)
from vet_manuscript_lab.ui.tabs.writing import (
    render_citations,
    render_claim_audit,
    render_claim_traceability,
    render_manuscript,
    render_review,
    render_revision_diff,
)
from vet_manuscript_lab.ui.theme import (
    apply_theme,
    inject_auto_grow_textareas,
    render_hero,
)


def render_workflow(app: Application, project_id: str) -> None:
    """Render the full workspace: pipeline bar + seven content tabs."""

    intake: dict[str, Any] = st.session_state.setdefault(
        f"analysis_intake:{project_id}", {}
    )

    # Auto-populate intake data when the Golden Project is selected
    # but hasn't been loaded yet (fixture data not in session state).
    golden_pid = st.session_state.get("_golden_project_id")
    if golden_pid == project_id and not compute_intake_ready(intake):
        prepare_golden_workspace(app, bump_search_form_version)
        intake = st.session_state.setdefault(f"analysis_intake:{project_id}", {})
        snapshot_intake(project_id)

    ready = compute_intake_ready(intake)

    thread_id = get_active_thread(project_id)
    state: dict[str, Any] = {}
    pending: list[dict[str, Any]] = []
    config: dict[str, Any] | None = None
    snapshot: Any = None
    if thread_id is not None:
        config = {"configurable": {"thread_id": thread_id}}
        snapshot = app.graph.get_state(config)
        state = snapshot.values
        pending = interrupt_values(snapshot)

    # Two-column layout: main content (tabs) on the left, pipeline control
    # panel docked as a sticky sidebar on the far right.
    main_col, pipeline_col = st.columns([0.6, 0.4], gap="medium")

    with pipeline_col:
        # Hidden marker so the CSS ``:has()`` rule can pin this column.
        st.markdown(
            '<div class="pipeline-sidebar-marker"></div>',
            unsafe_allow_html=True,
        )
        # Pipeline bar (now lives in the right sidebar)
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

        # Golden workspace actions (only for Golden Project)
        if golden_pid == project_id:
            render_workspace_actions(app)

    with main_col:
        (
            tab_design,
            tab_data,
            tab_lit,
            tab_method,
            tab_manuscript,
            tab_review,
            tab_export,
        ) = st.tabs(
            [
                translate("tab_intake_question"),
                translate("tab_intake_data"),
                translate("tab_lit_evidence"),
                translate("tab_method_stats"),
                translate("tab_manuscript"),
                translate("tab_review_compliance"),
                translate("tab_export"),
            ]
        )

        with tab_design:
            render_intake_question(intake)

        with tab_data:
            render_intake_materials(app, project_id, intake)

        with tab_lit:
            if state:
                render_literature_records(state)
                render_evidence_items(state)
            else:
                st.info(translate("info_start_pipeline"))

        with tab_method:
            if state:
                render_guideline_mapping(state)
                render_methodology_findings(state)
                render_analysis_plan(state)
                render_statistical_results(state)
                render_effect_plots(state)
                render_analysis_provenance(state)
            else:
                st.info(translate("info_start_pipeline"))

        with tab_manuscript:
            if state:
                render_manuscript(state)
                render_claim_traceability(state)
                render_citations(state)
                render_claim_audit(state)
            else:
                st.info(translate("info_start_pipeline"))

        with tab_review:
            if state:
                render_review(state)
                render_revision_diff(state)
                render_compliance_findings(state)
            else:
                st.info(translate("info_start_pipeline"))

        with tab_export:
            if state:
                render_export(state)
                render_usage_summary(state)
                render_ai_disclosure(state)
            else:
                st.info(translate("info_start_pipeline"))


def main() -> None:
    st.set_page_config(
        page_title=translate("page_title"),
        page_icon=":microscope:",
        layout="wide",
    )
    apply_theme()
    render_sidebar_header()
    app = get_application()

    ensure_golden_project_exists(app)

    render_projects(app)

    project_id = st.session_state.get("project_id")
    active_project_id = project_id if isinstance(project_id, str) else None

    if active_project_id is None:
        all_projects = app.repository.list_projects()
        if all_projects:
            active_project_id = all_projects[0].id
            st.session_state["project_id"] = active_project_id
            snapshot_intake(active_project_id)
    elif not st.session_state.get(f"intake_baseline:{active_project_id}"):
        snapshot_intake(active_project_id)

    render_sidebar_project_management(app)
    render_project_creation(app)
    render_language_switch()

    inject_beforeunload(is_intake_dirty(active_project_id))

    render_hero()
    if active_project_id is not None:
        render_workflow(app, active_project_id)

    # Auto-grow every textarea so long text is always fully visible.
    inject_auto_grow_textareas()


if __name__ == "__main__":
    main()
