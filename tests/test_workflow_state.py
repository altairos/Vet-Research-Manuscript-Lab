from __future__ import annotations

import math
import unittest

from vet_manuscript_lab.workflow.state import (
    WorkflowStage,
    assert_json_serializable,
    new_workflow_state,
    validate_stage_preconditions,
    validate_transition,
)


class WorkflowStateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.state = new_workflow_state(
            project_id="project-test",
            workflow_run_id="run-test",
            thread_id="thread-test",
            now="2026-07-06T00:00:00Z",
        )

    def test_initial_state_is_serializable(self) -> None:
        assert_json_serializable(self.state)
        self.assertEqual(self.state["schema_version"], "1.0.0")
        self.assertEqual(self.state["current_stage"], "project_init")

    def test_valid_forward_transition(self) -> None:
        validate_transition("project_init", "research_question")

    def test_invalid_transition_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "Invalid workflow transition"):
            validate_transition("project_init", "writing")

    def test_terminal_stage_cannot_be_left(self) -> None:
        with self.assertRaisesRegex(ValueError, "Cannot leave terminal stage"):
            validate_transition("complete", "project_init")

    def test_missing_approval_blocks_protected_stage(self) -> None:
        with self.assertRaisesRegex(PermissionError, "Missing required approval"):
            validate_stage_preconditions(
                self.state, WorkflowStage.GUIDELINE_MAPPING.value
            )

    def test_approved_exact_gate_allows_protected_stage(self) -> None:
        self.state["approvals"] = {
            "question": {
                "approval_id": "approval-1",
                "gate": "question",
                "subject_id": "question-1",
                "subject_version_id": "question-version-1",
                "subject_hash": "sha256:abc",
                "decision": "approved",
                "reviewer_id": "human-1",
                "reviewer_role": "investigator",
                "decided_at": "2026-07-06T00:00:00Z",
            }
        }
        validate_stage_preconditions(self.state, WorkflowStage.GUIDELINE_MAPPING.value)

    def test_non_finite_numbers_are_not_serializable(self) -> None:
        with self.assertRaisesRegex(ValueError, "strictly JSON serializable"):
            assert_json_serializable({"invalid": math.nan})

    def test_revision_limit_is_enforced(self) -> None:
        self.state["revision_round"] = 3
        self.state["max_revision_rounds"] = 3
        with self.assertRaisesRegex(PermissionError, "revision limit"):
            validate_stage_preconditions(self.state, WorkflowStage.REVISION.value)


if __name__ == "__main__":
    unittest.main()
