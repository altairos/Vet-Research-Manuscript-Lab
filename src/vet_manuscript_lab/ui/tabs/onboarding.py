"""Empty-state / onboarding entry points shown when no pipeline run exists.

Three entry cards:
- **Golden Project** — one-click synthetic data demo (primary CTA)
- **New project** — start from scratch
- **Import** — load existing artifacts
"""

from __future__ import annotations

import streamlit as st

from vet_manuscript_lab.ui.application import Application
from vet_manuscript_lab.ui.components import empty_state_card
from vet_manuscript_lab.ui.golden import (
    run_golden_workspace_pipeline,
)
from vet_manuscript_lab.ui.i18n import translate
from vet_manuscript_lab.ui.tabs.intake import bump_search_form_version


def render_onboarding(app: Application) -> None:
    """Render the three-card onboarding layout.

    Called when no active thread exists for the current project, replacing
    the usual "info_start_pipeline" empty message.
    """

    st.markdown(f"### {translate('onboard_welcome')}")

    col_golden, col_new, col_import = st.columns(3, gap="large")

    with col_golden:
        empty_state_card(
            icon="\U0001f3c6",
            title=translate("onboard_golden_title"),
            body=translate("onboard_golden_body"),
        )
        if st.button(
            translate("onboard_golden_button"),
            type="primary",
            width="stretch",
            key="onboard_run_golden",
        ):
            with st.spinner(translate("golden_workspace_loading")):
                try:
                    pid, _tid = run_golden_workspace_pipeline(
                        app, bump_search_form_version
                    )
                    st.session_state["project_id"] = pid
                    st.rerun()
                except (ValueError, OSError) as exc:
                    st.error(str(exc))

    with col_new:
        empty_state_card(
            icon="\U0001f4dd",
            title=translate("onboard_new_title"),
            body=translate("onboard_new_body"),
        )
        if st.button(
            translate("onboard_new_button"),
            width="stretch",
            key="onboard_new_project",
        ):
            # Switch to the Study Setup workspace by setting a hint
            st.session_state["_onboarding_target"] = "setup"
            st.rerun()

    with col_import:
        empty_state_card(
            icon="\U0001f4e5",
            title=translate("onboard_import_title"),
            body=translate("onboard_import_body"),
        )
        st.button(
            translate("onboard_import_button"),
            width="stretch",
            disabled=True,
            key="onboard_import",
            help=translate("onboard_import_body"),
        )
