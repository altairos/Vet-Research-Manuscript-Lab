"""Tests for Phase E — ArgumentSpine (argument skeleton layer).

Covers:
- argument_spine_node generates a valid spine from results
- must_not_claim constraints derived from result characteristics
- argument_spine_approval_node interrupt gate
- route_argument_spine_decision routing logic
- section_writing_node consumes must_not_claim constraints
- Non-significant / exploratory results generate stricter constraints
"""

from __future__ import annotations

import unittest
from typing import Any

from vet_manuscript_lab.workflow.state import (
    ArgumentSpineDraft,
    new_workflow_state,
)
from vet_manuscript_lab.workflow.writing_graph import (
    argument_spine_node,
    route_argument_spine_decision,
    section_writing_node,
)


def _base_state(thread_id: str = "spine-test") -> dict[str, Any]:
    """Create a minimal state with results for spine generation."""
    state = new_workflow_state(
        project_id="project-spine",
        workflow_run_id="run-spine",
        thread_id=thread_id,
        now="2026-07-09T00:00:00Z",
    )
    state["study_type"] = "retrospective_observational_clinical_study"
    state["species_scope"] = ["canine"]
    state["artifacts"] = {}
    state["approvals"] = {}
    state["result_drafts"] = [
        {
            "result_id": "r1",
            "label": "primary",
            "is_primary": True,
            "variable": "mortality_rate",
            "estimate": 1.5,
            "p_value": 0.03,
            "ci_low": 0.8,
            "ci_high": 2.2,
        }
    ]
    state["evidence_summary"] = {
        "total_evidence": 2,
        "items": [
            {"evidence_id": "ev-1", "concept": "finding_1"},
            {"evidence_id": "ev-2", "concept": "finding_2"},
        ],
    }
    return state


# ──────────────────────────────────────────────────────────────────────────────
# argument_spine_node tests
# ──────────────────────────────────────────────────────────────────────────────


class ArgumentSpineNodeTests(unittest.TestCase):
    def test_generates_spine_with_required_fields(self) -> None:
        result = argument_spine_node(_base_state())
        spine = result["argument_spine"]
        self.assertIsInstance(spine, dict)
        self.assertIn("spine_id", spine)
        self.assertIn("main_finding", spine)
        self.assertIn("clinical_relevance", spine)
        self.assertIn("primary_evidence", spine)
        self.assertIn("boundary_conditions", spine)
        self.assertIn("must_not_claim", spine)
        self.assertIn("discussion_blueprint", spine)
        self.assertIn("target_journal_angle", spine)

    def test_main_finding_includes_estimate_and_p_value(self) -> None:
        result = argument_spine_node(_base_state())
        finding = result["argument_spine"]["main_finding"]
        self.assertIn("1.5", finding)
        self.assertIn("0.03", finding)

    def test_main_finding_includes_ci(self) -> None:
        result = argument_spine_node(_base_state())
        finding = result["argument_spine"]["main_finding"]
        self.assertIn("0.8", finding)
        self.assertIn("2.2", finding)

    def test_primary_evidence_ids_extracted(self) -> None:
        result = argument_spine_node(_base_state())
        evidence_ids = result["argument_spine"]["primary_evidence"]
        self.assertIn("ev-1", evidence_ids)
        self.assertIn("ev-2", evidence_ids)

    def test_must_not_claim_always_non_empty(self) -> None:
        """Every spine must have at least one must_not_claim constraint."""
        result = argument_spine_node(_base_state())
        constraints = result["argument_spine"]["must_not_claim"]
        self.assertGreater(len(constraints), 0)

    def test_observational_study_generates_causal_constraint(self) -> None:
        result = argument_spine_node(_base_state())
        constraints = result["argument_spine"]["must_not_claim"]
        joined = " ".join(constraints).lower()
        self.assertIn("caus", joined)

    def test_non_significant_result_generates_significance_constraint(
        self,
    ) -> None:
        state = _base_state()
        state["result_drafts"] = [
            {
                "result_id": "r1",
                "is_primary": True,
                "variable": "survival",
                "estimate": 1.2,
                "p_value": 0.15,
                "ci_low": 0.7,
                "ci_high": 1.8,
            }
        ]
        result = argument_spine_node(state)
        constraints = result["argument_spine"]["must_not_claim"]
        joined = " ".join(constraints).lower()
        self.assertIn("significan", joined)

    def test_exploratory_result_generates_confirmatory_constraint(
        self,
    ) -> None:
        state = _base_state()
        state["result_drafts"] = [
            {
                "result_id": "r1",
                "is_primary": True,
                "variable": "survival",
                "estimate": 2.0,
                "p_value": 0.01,
                "ci_low": 1.5,
                "ci_high": 2.5,
                "exploratory": True,
            }
        ]
        result = argument_spine_node(state)
        constraints = result["argument_spine"]["must_not_claim"]
        joined = " ".join(constraints).lower()
        self.assertIn("confirmatory", joined)
        self.assertIn("definitive", joined)

    def test_wide_ci_generates_precision_constraint(self) -> None:
        state = _base_state()
        state["result_drafts"] = [
            {
                "result_id": "r1",
                "is_primary": True,
                "variable": "survival",
                "estimate": 2.0,
                "p_value": 0.01,
                "ci_low": 0.5,
                "ci_high": 5.0,
            }
        ]
        result = argument_spine_node(state)
        constraints = result["argument_spine"]["must_not_claim"]
        joined = " ".join(constraints).lower()
        self.assertIn("precise", joined)

    def test_generates_artifact(self) -> None:
        result = argument_spine_node(_base_state())
        artifacts = result["artifacts"]
        self.assertIn("argument_spine", artifacts)
        spine_artifact = artifacts["argument_spine"]
        self.assertEqual(spine_artifact["artifact_type"], "argument_spine")

    def test_boundary_conditions_non_empty(self) -> None:
        result = argument_spine_node(_base_state())
        conditions = result["argument_spine"]["boundary_conditions"]
        self.assertGreater(len(conditions), 0)

    def test_clinical_relevance_mentions_species(self) -> None:
        result = argument_spine_node(_base_state())
        relevance = result["argument_spine"]["clinical_relevance"]
        self.assertIn("canine", relevance)

    def test_no_results_state(self) -> None:
        """Spine with no results should still produce a valid structure."""
        state = _base_state()
        state["result_drafts"] = []
        result = argument_spine_node(state)
        spine = result["argument_spine"]
        self.assertIn("No primary result", spine["main_finding"])
        self.assertGreater(len(spine["must_not_claim"]), 0)

    def test_audit_event_emitted(self) -> None:
        result = argument_spine_node(_base_state())
        events = result.get("audit_events", [])
        self.assertTrue(any("argument_spine" in str(e) for e in events))


# ──────────────────────────────────────────────────────────────────────────────
# route_argument_spine_decision tests
# ──────────────────────────────────────────────────────────────────────────────


class RouteArgumentSpineTests(unittest.TestCase):
    def test_routes_to_writing_when_approved(self) -> None:
        state = _base_state()
        state["approvals"] = {"argument_spine": {"decision": "approved"}}
        self.assertEqual(route_argument_spine_decision(state), "section_writing")

    def test_routes_back_to_spine_when_changes_requested(self) -> None:
        state = _base_state()
        state["approvals"] = {"argument_spine": {"decision": "changes_requested"}}
        self.assertEqual(route_argument_spine_decision(state), "argument_spine")

    def test_routes_to_spine_when_no_approval(self) -> None:
        state = _base_state()
        state["approvals"] = {}
        self.assertEqual(route_argument_spine_decision(state), "argument_spine")


# ──────────────────────────────────────────────────────────────────────────────
# section_writing consumes must_not_claim tests
# ──────────────────────────────────────────────────────────────────────────────


class SectionWritingConsumesSpineTests(unittest.TestCase):
    def test_spine_constraints_passed_to_writing_input(self) -> None:
        """Verify section_writing_node reads argument_spine from state."""
        from vet_manuscript_lab.services.writing import (
            MockSectionWriter,
            WritingInput,
        )

        captured_inputs: list[WritingInput] = []

        class _CapturingWriter(MockSectionWriter):
            def write_sections(self, inputs: WritingInput) -> Any:
                captured_inputs.append(inputs)
                return super().write_sections(inputs)

        state = _base_state()
        # Set up state for writing
        state["approvals"] = {
            "results_interpretation": {"decision": "approved"},
            "argument_spine": {"decision": "approved"},
        }
        state["locks"] = {"protocol": {"locked": True}}
        state["evidence_summary"] = {"total_evidence": 0}
        state["argument_spine"] = ArgumentSpineDraft(
            spine_id="spine-1",
            main_finding="Test finding",
            clinical_relevance="Relevant",
            primary_evidence=["ev-1"],
            boundary_conditions=["Condition 1"],
            must_not_claim=["Do not claim causation"],
            discussion_blueprint="Discuss",
            target_journal_angle="Angle",
        )

        # Need protocol lock + evidence summary for the writing precondition
        section_writing_node(state, writer=_CapturingWriter())

        self.assertEqual(len(captured_inputs), 1)
        self.assertIn(
            "Do not claim causation",
            captured_inputs[0].must_not_claim,
        )
        self.assertEqual(
            captured_inputs[0].argument_spine_finding,
            "Test finding",
        )

    def test_no_spine_produces_empty_constraints(self) -> None:
        """When no spine exists, must_not_claim should be empty tuple."""
        from vet_manuscript_lab.services.writing import (
            MockSectionWriter,
            WritingInput,
        )

        captured_inputs: list[WritingInput] = []

        class _CapturingWriter(MockSectionWriter):
            def write_sections(self, inputs: WritingInput) -> Any:
                captured_inputs.append(inputs)
                return super().write_sections(inputs)

        state = _base_state()
        state["approvals"] = {
            "results_interpretation": {"decision": "approved"},
        }
        state["locks"] = {"protocol": {"locked": True}}
        state["evidence_summary"] = {"total_evidence": 0}
        # No argument_spine in state

        section_writing_node(state, writer=_CapturingWriter())

        self.assertEqual(len(captured_inputs), 1)
        self.assertEqual(captured_inputs[0].must_not_claim, ())
        self.assertEqual(captured_inputs[0].argument_spine_finding, "")


if __name__ == "__main__":
    unittest.main()
