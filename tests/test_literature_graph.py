"""Integration and adversarial tests for the mock literature-and-evidence pipeline.

Covers the full ``PROJECT_INIT -> EVIDENCE_AUDIT`` flow, cross-instance
checkpoint resume, search-strategy rejection with version bump, and every
Phase 2 exit-gate invariant (source-span linkage, search-gate precondition,
hash verification, adversarial citation).
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any

from langgraph.types import Command

from vet_manuscript_lab.domain.policies import PolicyViolation
from vet_manuscript_lab.infrastructure.checkpoints import open_sqlite_checkpointer
from vet_manuscript_lab.workflow.literature_graph import (
    build_evidence_pipeline_graph,
    evidence_audit_node,
    screening_node,
)
from vet_manuscript_lab.workflow.state import (
    EvidenceDraft,
    LiteratureRecordDraft,
    SourceSpanDraft,
    new_workflow_state,
)


def interrupt_payloads(snapshot: Any) -> list[dict[str, Any]]:
    return [
        pending.value
        for task in snapshot.tasks
        for pending in task.interrupts
        if isinstance(pending.value, dict)
    ]


def _approve(reviewer: str = "investigator-1") -> Command:
    return Command(
        resume={
            "decision": "approved",
            "reviewer_id": reviewer,
            "reviewer_role": "investigator",
        }
    )


def _reject(reviewer: str = "investigator-1") -> Command:
    return Command(
        resume={
            "decision": "changes_requested",
            "reviewer_id": reviewer,
            "reviewer_role": "investigator",
            "comment": "Broaden the query to include CAB Abstracts",
        }
    )


class EvidencePipelineIntegrationTests(unittest.TestCase):
    def initial_state(self, thread_id: str) -> dict[str, Any]:
        return new_workflow_state(
            project_id="project-lit",
            workflow_run_id="run-lit",
            thread_id=thread_id,
            now="2026-07-06T00:00:00Z",
        )

    def test_full_pipeline_runs_to_evidence_audit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            connection, saver = open_sqlite_checkpointer(
                Path(temporary) / "checkpoints.sqlite"
            )
            graph = build_evidence_pipeline_graph(saver)
            config = {"configurable": {"thread_id": "full-run"}}

            graph.invoke(self.initial_state("full-run"), config)
            self.assertEqual(
                interrupt_payloads(graph.get_state(config))[0]["gate"], "question"
            )

            graph.invoke(_approve(), config)
            self.assertEqual(
                interrupt_payloads(graph.get_state(config))[0]["gate"], "protocol"
            )

            graph.invoke(_approve(), config)
            snapshot = graph.get_state(config)
            self.assertEqual(interrupt_payloads(snapshot)[0]["gate"], "search_strategy")
            self.assertIn("search_strategy", snapshot.values.get("artifacts", {}))

            result = graph.invoke(_approve(), config)
            self.assertEqual(result["run_status"], "complete")
            self.assertEqual(result["current_stage"], "evidence_audit")
            # Two in-scope records (canine + feline), one excluded (bovine).
            self.assertEqual(result["literature_summary"]["included_count"], 2)
            self.assertEqual(result["literature_summary"]["excluded_count"], 1)
            self.assertEqual(result["evidence_summary"]["total_evidence_items"], 2)
            self.assertIn("evidence_ledger", result["artifacts"])
            self.assertIn("citation_audit", result["artifacts"])
            # Each evidence item must trace to at least one source span.
            for draft in result["evidence_drafts"]:
                self.assertTrue(draft["source_span_ids"])
            connection.close()

    def test_pipeline_resumes_across_graph_instances(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            checkpoint_path = Path(temporary) / "checkpoints.sqlite"
            config = {"configurable": {"thread_id": "resume-lit"}}

            connection, saver = open_sqlite_checkpointer(checkpoint_path)
            graph = build_evidence_pipeline_graph(saver)
            graph.invoke(self.initial_state("resume-lit"), config)
            graph.invoke(_approve(), config)  # question approval
            connection.close()

            connection, saver = open_sqlite_checkpointer(checkpoint_path)
            resumed_graph = build_evidence_pipeline_graph(saver)
            snapshot = resumed_graph.get_state(config)
            self.assertEqual(interrupt_payloads(snapshot)[0]["gate"], "protocol")
            resumed_graph.invoke(_approve(), config)  # protocol approval
            resumed_graph.invoke(_approve(), config)  # search approval
            result = resumed_graph.invoke(_approve(), config)
            # Last invoke resumes search-approval and auto-runs to evidence_audit.
            self.assertEqual(result["run_status"], "complete")
            self.assertEqual(
                result["approvals"]["search_strategy"]["reviewer_id"],
                "investigator-1",
            )
            connection.close()

    def test_rejected_search_creates_new_version(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            connection, saver = open_sqlite_checkpointer(
                Path(temporary) / "checkpoints.sqlite"
            )
            graph = build_evidence_pipeline_graph(saver)
            config = {"configurable": {"thread_id": "revision-search"}}
            graph.invoke(self.initial_state("revision-search"), config)
            graph.invoke(_approve(), config)  # question
            graph.invoke(_approve(), config)  # protocol
            # Search strategy exists at version 1.
            first_version = graph.get_state(config).values["artifacts"][
                "search_strategy"
            ]["version"]
            self.assertEqual(first_version, 1)

            graph.invoke(_reject(), config)  # reject search
            snapshot = graph.get_state(config)
            self.assertEqual(interrupt_payloads(snapshot)[0]["gate"], "search_strategy")
            second_version = snapshot.values["artifacts"]["search_strategy"]["version"]
            self.assertEqual(second_version, 2)
            connection.close()


class EvidencePipelineAdversarialTests(unittest.TestCase):
    """Verify Phase 2 exit-gate invariants cannot be bypassed."""

    def _base_state(self) -> dict[str, Any]:
        return new_workflow_state(
            project_id="project-adv",
            workflow_run_id="run-adv",
            thread_id="adv-thread",
            now="2026-07-06T00:00:00Z",
        )

    # -- search-gate precondition -----------------------------------------

    def test_screening_without_search_approval_raises(self) -> None:
        state = self._base_state()
        state["literature_record_drafts"] = [
            LiteratureRecordDraft(record_id="lit-1", title="Canine CKD study"),
        ]
        with self.assertRaises(PermissionError):
            screening_node(state)

    def test_screening_with_no_records_raises(self) -> None:
        state = self._base_state()
        state["approvals"] = {
            "search_strategy": {
                "approval_id": "a1",
                "gate": "search_strategy",
                "subject_id": "s1",
                "subject_version_id": "sv1",
                "subject_hash": "sha256:abc",
                "decision": "approved",
                "reviewer_id": "inv-1",
                "reviewer_role": "investigator",
                "decided_at": "2026-07-06T00:00:00Z",
            }
        }
        state["literature_record_drafts"] = []
        with self.assertRaises(PolicyViolation):
            screening_node(state)

    # -- source-span linkage ----------------------------------------------

    def test_audit_rejects_evidence_without_source_spans(self) -> None:
        state = self._base_state()
        state["evidence_drafts"] = [
            EvidenceDraft(
                evidence_id="ev-1",
                concept="sample_size",
                literature_record_id="lit-1",
                source_span_ids=[],
            ),
        ]
        with self.assertRaisesRegex(PolicyViolation, "no source spans"):
            evidence_audit_node(state)

    def test_audit_rejects_unknown_span_reference(self) -> None:
        state = self._base_state()
        state["evidence_drafts"] = [
            EvidenceDraft(
                evidence_id="ev-1",
                concept="sample_size",
                literature_record_id="lit-1",
                source_span_ids=["nonexistent-span"],
            ),
        ]
        with self.assertRaisesRegex(PolicyViolation, "unknown source span"):
            evidence_audit_node(state)

    def test_audit_rejects_corrupted_quote_hash(self) -> None:
        state = self._base_state()
        state["source_span_drafts"] = [
            SourceSpanDraft(
                span_id="span-1",
                literature_record_id="lit-1",
                page=3,
                section_label="Results",
                quote_hash="md5:corrupted",
            ),
        ]
        state["evidence_drafts"] = [
            EvidenceDraft(
                evidence_id="ev-1",
                concept="sample_size",
                literature_record_id="lit-1",
                source_span_ids=["span-1"],
            ),
        ]
        with self.assertRaisesRegex(PolicyViolation, "invalid quote hash"):
            evidence_audit_node(state)

    def test_audit_passes_with_valid_evidence_chain(self) -> None:
        state = self._base_state()
        state["source_span_drafts"] = [
            SourceSpanDraft(
                span_id="span-1",
                literature_record_id="lit-1",
                page=5,
                section_label="Results",
                quote_hash="sha256:abcdef0123456789",
            ),
        ]
        state["evidence_drafts"] = [
            EvidenceDraft(
                evidence_id="ev-1",
                concept="sample_size",
                value="42",
                units="dogs",
                literature_record_id="lit-1",
                source_span_ids=["span-1"],
                requires_human_review=False,
                extraction_status="draft",
            ),
        ]
        result = evidence_audit_node(state)
        self.assertIn("citation_audit", result["artifacts"])
        self.assertEqual(result["evidence_summary"]["items_requiring_review"], 0)


if __name__ == "__main__":
    unittest.main()
