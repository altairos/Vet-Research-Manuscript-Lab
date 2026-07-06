"""Tests for the workflow node and artifact payload schemas."""

from __future__ import annotations

import unittest
from typing import Any

from vet_manuscript_lab.domain.conventions import ArtifactType, ErrorCode
from vet_manuscript_lab.workflow.state import WorkflowStage
from vet_manuscript_lab.workflow.state_schema import (
    ARTIFACT_PAYLOAD_SCHEMAS,
    NODE_INPUT_SCHEMAS,
    NODE_OUTPUT_SCHEMAS,
    make_node_failure,
    validate_node_output,
    validate_payload,
)


class ArtifactPayloadSchemaTests(unittest.TestCase):
    """Tests for validate_payload across artifact types."""

    def test_valid_research_question_payload(self) -> None:
        payload: dict[str, Any] = {
            "study_type": "retrospective_observational_clinical_study",
            "species_scope": ["canine", "feline"],
            "pico": {
                "population": "canine CKD patients",
                "comparator": "standard care",
                "outcomes": ["survival time"],
            },
            "primary_objective": "Describe survival in canine CKD",
            "version": 1,
        }
        violations = validate_payload(payload, ArtifactType.RESEARCH_QUESTION)
        self.assertEqual(violations, [])

    def test_missing_required_fields_reported(self) -> None:
        violations = validate_payload({}, ArtifactType.RESEARCH_QUESTION)
        self.assertIn(
            "Missing required field 'pico' for research_question payload",
            violations,
        )
        self.assertIn(
            "Missing required field 'study_type' for research_question payload",
            violations,
        )

    def test_valid_search_strategy_payload(self) -> None:
        payload: dict[str, Any] = {
            "databases": ["PubMed"],
            "query": "canine AND CKD",
            "date_range": "2018-01-01/2026-06-30",
            "species_scope": ["canine"],
            "record_count": 42,
            "version": 1,
        }
        violations = validate_payload(payload, ArtifactType.SEARCH_STRATEGY)
        self.assertEqual(violations, [])

    def test_valid_screening_result_payload(self) -> None:
        payload: dict[str, Any] = {
            "total": 3,
            "included": 2,
            "excluded": 1,
            "decisions": [
                {"record_id": "r1", "decision": "included"},
                {"record_id": "r2", "decision": "included"},
                {"record_id": "r3", "decision": "excluded"},
            ],
            "version": 1,
        }
        violations = validate_payload(payload, ArtifactType.SCREENING_RESULT)
        self.assertEqual(violations, [])

    def test_unregistered_artifact_type(self) -> None:
        violations = validate_payload({}, ArtifactType.AUDIT_REPORT)
        self.assertTrue(any("No payload schema registered" in v for v in violations))


class NodeOutputSchemaTests(unittest.TestCase):
    """Tests for validate_node_output."""

    def test_valid_research_question_output(self) -> None:
        artifact = {
            "artifact_id": "a1",
            "version_id": "v1",
            "artifact_type": "research_question",
            "version": 1,
            "status": "in_review",
            "content_hash": "sha256:abc",
            "uri": "mock://a1/1",
            "media_type": "application/json",
            "created_at": "2026-07-06T00:00:00Z",
        }
        output = {
            "current_stage": "research_question",
            "updated_at": "2026-07-06T00:00:00Z",
            "audit_events": [],
            "research_question_artifact": artifact,
        }
        violations = validate_node_output(output, WorkflowStage.RESEARCH_QUESTION)
        self.assertEqual(violations, [])

    def test_missing_artifact_ref_in_output(self) -> None:
        output = {
            "current_stage": "research_question",
            "updated_at": "2026-07-06T00:00:00Z",
            "audit_events": [],
        }
        violations = validate_node_output(output, WorkflowStage.RESEARCH_QUESTION)
        self.assertTrue(any("research_question_artifact" in v for v in violations))

    def test_unregistered_stage(self) -> None:
        violations = validate_node_output({}, WorkflowStage.BLOCKED)
        self.assertTrue(any("No output schema registered" in v for v in violations))


class SchemaRegistryTests(unittest.TestCase):
    """Tests for the schema registry mappings."""

    def test_every_artifact_type_has_payload_schema(self) -> None:
        # AUDIT_REPORT is intentionally unregistered (it is a free-form report)
        registered = set(ARTIFACT_PAYLOAD_SCHEMAS.keys())
        self.assertIn(ArtifactType.RESEARCH_QUESTION, registered)
        self.assertIn(ArtifactType.EXPORT_PACKAGE, registered)
        self.assertNotIn(ArtifactType.AUDIT_REPORT, registered)

    def test_every_non_terminal_stage_has_output_schema(self) -> None:
        for stage in [
            WorkflowStage.PROJECT_INIT,
            WorkflowStage.WRITING,
            WorkflowStage.EXPORT,
        ]:
            self.assertIn(stage, NODE_OUTPUT_SCHEMAS)

    def test_every_producing_stage_has_input_schema(self) -> None:
        for stage in [
            WorkflowStage.PROJECT_INIT,
            WorkflowStage.LITERATURE_SEARCH,
            WorkflowStage.STATISTICS_EXECUTION,
            WorkflowStage.EXPORT,
        ]:
            self.assertIn(stage, NODE_INPUT_SCHEMAS)

    def test_approval_stages_have_no_input_schema(self) -> None:
        """Approval interrupt nodes are passthrough; no input schema needed."""
        for stage in [
            WorkflowStage.QUESTION_APPROVAL,
            WorkflowStage.PROTOCOL_APPROVAL,
            WorkflowStage.SEARCH_APPROVAL,
        ]:
            self.assertNotIn(stage, NODE_INPUT_SCHEMAS)


class NodeFailureTests(unittest.TestCase):
    """Tests for make_node_failure helper."""

    def test_basic_failure(self) -> None:
        failure = make_node_failure(
            error_code=ErrorCode.VALIDATION_ERROR,
            message="Schema check failed",
            stage=WorkflowStage.EVIDENCE_EXTRACTION,
        )
        self.assertEqual(failure["error_code"], ErrorCode.VALIDATION_ERROR)
        self.assertFalse(failure["retryable"])
        self.assertEqual(failure["stage"], "evidence_extraction")
        self.assertNotIn("details", failure)

    def test_failure_with_details(self) -> None:
        failure = make_node_failure(
            error_code=ErrorCode.TRANSIENT_SERVICE_ERROR,
            message="Timeout",
            stage=WorkflowStage.LITERATURE_SEARCH,
            retryable=True,
            details={"timeout_ms": 30000},
        )
        self.assertTrue(failure["retryable"])
        self.assertEqual(failure["details"], {"timeout_ms": 30000})


if __name__ == "__main__":
    unittest.main()
