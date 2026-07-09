"""Session-state, thread, and workflow helpers shared across the UI."""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any, cast

import streamlit as st
from langgraph.types import Command

from vet_manuscript_lab.domain.conventions import utc_now
from vet_manuscript_lab.ui.application import Application
from vet_manuscript_lab.workflow.state import new_workflow_state

# ---------------------------------------------------------------------------
# Interrupts & resume payloads
# ---------------------------------------------------------------------------


def interrupt_values(snapshot: Any) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    for task in snapshot.tasks:
        for pending in task.interrupts:
            if isinstance(pending.value, dict):
                values.append(pending.value)
    return values


def auto_resume_payload(interrupt: dict[str, Any]) -> dict[str, Any]:
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


# ---------------------------------------------------------------------------
# Intake dirty tracking
# ---------------------------------------------------------------------------


def intake_snapshot(intake: dict[str, Any]) -> str:
    """Return a stable hash of the current intake data for dirty tracking."""

    payload = json.dumps(intake, sort_keys=True, default=str)
    return hashlib.md5(payload.encode()).hexdigest()


def snapshot_intake(project_id: str) -> None:
    intake = st.session_state.get(f"analysis_intake:{project_id}", {})
    st.session_state[f"intake_baseline:{project_id}"] = intake_snapshot(intake)


def is_intake_dirty(project_id: str | None) -> bool:
    if project_id is None:
        return False
    intake = st.session_state.get(f"analysis_intake:{project_id}", {})
    baseline = st.session_state.get(f"intake_baseline:{project_id}")
    if baseline is None:
        return False
    return bool(intake_snapshot(intake) != baseline)


def compute_intake_ready(intake: dict[str, Any]) -> bool:
    """Return *True* when all four intake requirements are satisfied."""

    return all(
        [
            bool(intake.get("research_question_input")),
            bool(intake.get("search_strategy_input")),
            bool(intake.get("literature_record_drafts")),
            bool(intake.get("dataset_summary")),
        ]
    )


def inject_beforeunload(is_dirty: bool) -> None:
    """Inject JS to warn on page leave when there are unsaved changes."""

    flag = "true" if is_dirty else "false"
    st.iframe(
        f"""
<script>
(function() {{
  window.onbeforeunload = function(e) {{
    if ({flag}) {{
      e.preventDefault();
      return '';
    }}
  }};
}})();
</script>
""",
        height=1,
    )


# ---------------------------------------------------------------------------
# Thread / workflow management
# ---------------------------------------------------------------------------


def thread_session_key(project_id: str) -> str:
    return f"thread_id:{project_id}"


def set_active_thread(project_id: str, thread_id: str) -> None:
    st.session_state[thread_session_key(project_id)] = thread_id
    st.session_state["thread_id"] = thread_id


def get_active_thread(project_id: str) -> str | None:
    thread_id = st.session_state.get(thread_session_key(project_id))
    return thread_id if isinstance(thread_id, str) else None


def drive_pipeline_to_completion(
    app: Application, state: dict[str, Any], thread_id: str
) -> None:
    config = {"configurable": {"thread_id": thread_id}}
    app.graph.invoke(state, config)
    for _ in range(50):
        snapshot = app.graph.get_state(config)
        pending = interrupt_values(snapshot)
        if not pending:
            break
        app.graph.invoke(Command(resume=auto_resume_payload(pending[0])), config)


def start_workflow(app: Application, project_id: str) -> None:
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
        cast(dict[str, Any], state).update(intake)
    config = {"configurable": {"thread_id": thread_id}}
    app.graph.invoke(state, config)
    app.governance.sync_state(app.graph.get_state(config).values)
    set_active_thread(project_id, thread_id)
