"""Design-system UI components for the Streamlit workspace.

This package provides reusable card, badge, and table primitives so that
tab modules share a consistent visual language instead of emitting
ad-hoc ``st.markdown`` / CSS everywhere.
"""

from __future__ import annotations

from vet_manuscript_lab.ui.components.badges import (
    badge,
    severity_pill,
    status_badge,
    status_to_tone,
)
from vet_manuscript_lab.ui.components.cards import (
    Metric,
    approval_gate_card,
    artifact_card,
    card,
    empty_state_card,
    finding_card,
    metric_strip,
    next_action_hero,
)
from vet_manuscript_lab.ui.components.tables import (
    clean_table,
    collapsible_details,
    copy_button_html,
    inject_copy_js,
    short_hash,
)

__all__ = [
    "Metric",
    "approval_gate_card",
    "artifact_card",
    "badge",
    "card",
    "clean_table",
    "collapsible_details",
    "copy_button_html",
    "empty_state_card",
    "finding_card",
    "inject_copy_js",
    "metric_strip",
    "next_action_hero",
    "severity_pill",
    "short_hash",
    "status_badge",
    "status_to_tone",
]
