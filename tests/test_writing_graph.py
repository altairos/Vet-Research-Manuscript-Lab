"""Integration and adversarial tests for the writing + review + revision pipeline.

Covers the full ``PROJECT_INIT -> REVISION`` flow, including the
claim-audit → review → revision cycle, revision-limit escalation,
checkpoint resume, and adversarial claim-quality checks.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any

from langgraph.types import Command

from vet_manuscript_lab.domain.policies import extract_referenced_numbers
from vet_manuscript_lab.infrastructure.checkpoints import open_sqlite_checkpointer
from vet_manuscript_lab.services.writing import (
    FindingCategory,
    FindingSeverity,
    MockSectionWriter,
    ReviewInput,
    ReviewOutput,
    SectionDraft,
    SectionType,
    WritingInput,
    WritingOutput,
)
from vet_manuscript_lab.services.writing.types import (
    ClaimDraft,
    ReviewFindingDraft,
)
from vet_manuscript_lab.workflow.state import (
    new_workflow_state,
)
from vet_manuscript_lab.workflow.writing_graph import (
    WritingPipeline,
    build_writing_pipeline_graph,
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


def _run_to_results_approval(graph: Any, config: dict, initial: dict) -> None:
    """Run through foundation + literature + analysis to results_approval."""
    graph.invoke(initial, config)  # -> question_approval
    graph.invoke(_approve(), config)  # -> protocol_approval
    graph.invoke(_approve(), config)  # -> search_approval
    graph.invoke(_approve(), config)  # -> analysis_plan_approval
    graph.invoke(_approve(), config)  # -> results_approval


def _run_past_argument_spine(graph: Any, config: dict, initial: dict) -> None:
    """Run through results_approval AND argument_spine_approval.

    After Phase E, the pipeline inserts an argument_spine interrupt
    between results_approval and section_writing.  This helper runs
    through both so tests can proceed to the writing/review stages.
    """
    _run_to_results_approval(graph, config, initial)
    graph.invoke(_approve(), config)  # results -> argument_spine -> spine_approval
    graph.invoke(_approve(), config)  # spine_approval -> section_writing -> ...


# ---------------------------------------------------------------------------
# Custom test implementations
# ---------------------------------------------------------------------------


def _content_hash(text: str) -> str:
    import hashlib

    return f"sha256:{hashlib.sha256(text.encode()).hexdigest()}"


class _OverstatementWriter:
    """Section writer that includes absolute language ('all', 'always')."""

    def write_sections(self, inputs: WritingInput) -> WritingOutput:
        mock = MockSectionWriter()
        output = mock.write_sections(inputs)

        discussion_text = (
            "All cases responded to treatment. The association is "
            "always strong in veterinary patients."
        )
        d_hash = _content_hash(discussion_text)

        sections = list(output.sections)
        claims = list(output.claims)
        for i, s in enumerate(sections):
            if s.section_type == SectionType.DISCUSSION.value:
                sections[i] = SectionDraft(
                    section_id=s.section_id,
                    section_type=s.section_type,
                    content=discussion_text,
                    content_hash=d_hash,
                    order=s.order,
                    word_count=len(discussion_text.split()),
                    claim_ids=s.claim_ids,
                )
                break
        for i, c in enumerate(claims):
            if c.section_id and "discussion" in c.section_id:
                claims[i] = ClaimDraft(
                    claim_id=c.claim_id,
                    claim_type=c.claim_type,
                    text=discussion_text,
                    certainty=c.certainty,
                    section_id=c.section_id,
                    referenced_numbers=extract_referenced_numbers(discussion_text),
                )
                break

        manuscript_hash = _content_hash("".join(s.content for s in sections))
        return WritingOutput(
            sections=tuple(sections),
            claims=tuple(claims),
            supports=output.supports,
            citations=output.citations,
            manuscript_hash=manuscript_hash,
        )


class _OverstatementReviewer:
    """Reviewer that flags absolute language as overstatement."""

    def __init__(self) -> None:
        self._call_count = 0

    def review(self, inputs: ReviewInput) -> ReviewOutput:
        self._call_count += 1
        findings: list[ReviewFindingDraft] = []
        for cd in inputs.claims:
            text_lower = cd.text.lower()
            if "all " in text_lower or "always" in text_lower:
                findings.append(
                    ReviewFindingDraft(
                        finding_id=f"finding-{cd.claim_id}-overstatement",
                        category=FindingCategory.OVERSTATEMENT.value,
                        severity=FindingSeverity.WARNING.value,
                        location=cd.claim_id,
                        rationale="Claim uses absolute language.",
                        recommendation="Hedge with 'most' or 'usually'.",
                    )
                )
        return ReviewOutput(
            findings=tuple(findings),
            manuscript_hash_unchanged=True,
        )


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


class WritingPipelineIntegrationTests(unittest.TestCase):
    def initial_state(self, thread_id: str) -> dict[str, Any]:
        return new_workflow_state(
            project_id="project-writing",
            workflow_run_id="run-writing",
            thread_id=thread_id,
            now="2026-07-06T00:00:00Z",
        )

    def test_full_pipeline_completes_with_no_findings(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            connection, saver = open_sqlite_checkpointer(
                Path(temporary) / "checkpoints.sqlite"
            )
            graph = build_writing_pipeline_graph(saver)
            config = {"configurable": {"thread_id": "happy-path"}}

            _run_past_argument_spine(graph, config, self.initial_state("happy-path"))

            # Verify argument spine was generated
            snapshot = graph.get_state(config)
            spine = snapshot.values.get("argument_spine")
            self.assertIsNotNone(spine)
            self.assertTrue(spine["must_not_claim"])

            # review interrupt with no findings → END
            result = graph.get_state(config).values
            self.assertEqual(result["current_stage"], "review")

            snapshot = graph.get_state(config)
            manuscript = snapshot.values.get("manuscript_summary")
            self.assertIsNotNone(manuscript)
            self.assertGreater(manuscript["section_count"], 0)
            self.assertGreater(manuscript["claim_count"], 0)

            sections = snapshot.values.get("section_drafts", [])
            self.assertGreater(len(sections), 0)

            claims = snapshot.values.get("claim_drafts", [])
            self.assertGreater(len(claims), 0)

            findings = snapshot.values.get("review_findings", [])
            self.assertEqual(len(findings), 0)
            connection.close()

    def test_manuscript_artifacts_generated(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            connection, saver = open_sqlite_checkpointer(
                Path(temporary) / "checkpoints.sqlite"
            )
            graph = build_writing_pipeline_graph(saver)
            config = {"configurable": {"thread_id": "artifacts"}}
            _run_past_argument_spine(graph, config, self.initial_state("artifacts"))

            snapshot = graph.get_state(config)
            vals = snapshot.values

            self.assertIn("manuscript", vals.get("artifacts", {}))
            self.assertIn("claim_audit", vals.get("artifacts", {}))

            audit = vals["artifacts"]["claim_audit"]
            self.assertEqual(audit["status"], "audit_passed")

            supports = vals.get("support_drafts", [])
            self.assertGreater(len(supports), 0)

            connection.close()

    def test_checkpoint_resume_across_instances(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            checkpoint_path = Path(temporary) / "checkpoints.sqlite"
            config = {"configurable": {"thread_id": "resume-writing"}}

            connection, saver = open_sqlite_checkpointer(checkpoint_path)
            graph = build_writing_pipeline_graph(saver)
            _run_to_results_approval(
                graph, config, self.initial_state("resume-writing")
            )
            # Approve results → argument_spine → argument_spine_approval interrupt
            graph.invoke(_approve(), config)
            connection.close()

            connection, saver = open_sqlite_checkpointer(checkpoint_path)
            resumed = build_writing_pipeline_graph(saver)
            snapshot = resumed.get_state(config)
            self.assertEqual(
                interrupt_payloads(snapshot)[0]["gate"],
                "argument_spine",
            )
            # Approve spine → writing → claim_audit → review
            result = resumed.invoke(_approve(), config)
            self.assertEqual(result["current_stage"], "review")
            connection.close()

    def test_mock_writer_determinism(self) -> None:
        writer = MockSectionWriter()
        inputs = WritingInput(
            project_id="test-project",
            evidence_summary={"summary": "test"},
            result_drafts=[
                {
                    "result_id": "r1",
                    "estimand": "test",
                    "estimate": 1.5,
                    "p_value": 0.03,
                }
            ],
            literature_records=[],
        )
        out1 = writer.write_sections(inputs)
        out2 = writer.write_sections(inputs)
        self.assertEqual(out1.manuscript_hash, out2.manuscript_hash)


class WritingPipelineRevisionTests(unittest.TestCase):
    def initial_state(self, thread_id: str, *, max_rounds: int = 3) -> dict[str, Any]:
        state = new_workflow_state(
            project_id="project-revision",
            workflow_run_id="run-revision",
            thread_id=thread_id,
            now="2026-07-06T00:00:00Z",
        )
        state["max_revision_rounds"] = max_rounds
        return state

    def test_revision_cycle_resolves_overstatement(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            connection, saver = open_sqlite_checkpointer(
                Path(temporary) / "checkpoints.sqlite"
            )
            pipeline = WritingPipeline(
                writer=_OverstatementWriter(),
                reviewer=_OverstatementReviewer(),
            )
            graph = build_writing_pipeline_graph(saver, writing_pipeline=pipeline)
            config = {"configurable": {"thread_id": "revision-cycle"}}

            _run_past_argument_spine(
                graph, config, self.initial_state("revision-cycle")
            )

            # review_approval interrupt with findings
            snapshot = graph.get_state(config)
            payloads = interrupt_payloads(snapshot)
            self.assertTrue(len(payloads) > 0)
            self.assertEqual(payloads[0]["gate"], "review")
            self.assertGreater(len(payloads[0].get("findings", [])), 0)

            # Accept all findings
            finding_ids = [f["finding_id"] for f in payloads[0]["findings"]]
            resume_data = Command(
                resume={
                    "reviewer_id": "reviewer-1",
                    "reviewer_role": "reviewer",
                    "decisions": [
                        {
                            "finding_id": fid,
                            "decision": "accept",
                            "reason": "Agreed",
                        }
                        for fid in finding_ids
                    ],
                }
            )
            graph.invoke(resume_data, config)

            # After revision → claim_audit → review → END (no more findings)
            vals = graph.get_state(config).values
            revision_summary = vals.get("revision_summary")
            self.assertIsNotNone(revision_summary)
            self.assertGreater(revision_summary["accepted_count"], 0)
            connection.close()

    def test_all_findings_rejected_goes_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            connection, saver = open_sqlite_checkpointer(
                Path(temporary) / "checkpoints.sqlite"
            )
            pipeline = WritingPipeline(
                writer=_OverstatementWriter(),
                reviewer=_OverstatementReviewer(),
            )
            graph = build_writing_pipeline_graph(saver, writing_pipeline=pipeline)
            config = {"configurable": {"thread_id": "reject-findings"}}

            _run_past_argument_spine(
                graph, config, self.initial_state("reject-findings")
            )

            snapshot = graph.get_state(config)
            payloads = interrupt_payloads(snapshot)
            finding_ids = [f["finding_id"] for f in payloads[0]["findings"]]

            resume_data = Command(
                resume={
                    "reviewer_id": "reviewer-1",
                    "reviewer_role": "reviewer",
                    "decisions": [
                        {"finding_id": fid, "decision": "reject", "reason": "No"}
                        for fid in finding_ids
                    ],
                }
            )
            graph.invoke(resume_data, config)

            # Should reach END (no accepted findings)
            vals = graph.get_state(config).values
            self.assertEqual(vals.get("revision_round", 0), 0)
            connection.close()

    def test_revision_limit_triggers_escalation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            connection, saver = open_sqlite_checkpointer(
                Path(temporary) / "checkpoints.sqlite"
            )
            pipeline = WritingPipeline(
                writer=_OverstatementWriter(),
                reviewer=_OverstatementReviewer(),
            )
            graph = build_writing_pipeline_graph(saver, writing_pipeline=pipeline)
            config = {"configurable": {"thread_id": "revision-limit"}}

            # max_rounds = 1: only one revision allowed
            _run_past_argument_spine(
                graph,
                config,
                self.initial_state("revision-limit", max_rounds=1),
            )

            # First revision
            snapshot = graph.get_state(config)
            payloads = interrupt_payloads(snapshot)
            finding_ids = [f["finding_id"] for f in payloads[0]["findings"]]
            resume_data = Command(
                resume={
                    "reviewer_id": "reviewer-1",
                    "reviewer_role": "reviewer",
                    "decisions": [
                        {"finding_id": fid, "decision": "accept", "reason": "Fix"}
                        for fid in finding_ids
                    ],
                }
            )
            graph.invoke(resume_data, config)

            # revision_round should be 1, and route_revision_decision
            # should return END (1 >= 1)
            vals = graph.get_state(config).values
            self.assertEqual(vals.get("revision_round"), 1)
            connection.close()


class WritingPipelineAdversarialTests(unittest.TestCase):
    def initial_state(self, thread_id: str) -> dict[str, Any]:
        return new_workflow_state(
            project_id="project-adversarial",
            workflow_run_id="run-adversarial",
            thread_id=thread_id,
            now="2026-07-06T00:00:00Z",
        )

    def test_claim_audit_catches_unsupported_factual_claim(self) -> None:
        """Inject an unsupported factual claim and verify audit fails."""
        from vet_manuscript_lab.workflow.writing_graph import claim_audit_node

        state: dict[str, Any] = {
            **self.initial_state("adversarial-1"),
            "claim_drafts": [
                {
                    "claim_id": "c-unsupported",
                    "claim_type": "factual",
                    "text": "Dogs are the most common patients.",
                    "certainty": "high",
                    "section_id": "sec-1",
                    "referenced_numbers": [],
                }
            ],
            "support_drafts": [],
            "result_drafts": [],
            "artifacts": {},
        }
        result = claim_audit_node(state)
        audit = result["artifacts"]["claim_audit"]
        self.assertEqual(audit["status"], "audit_failed")

    def test_claim_audit_catches_causal_overreach(self) -> None:
        """Inject a causal claim without hedging and verify audit fails."""
        from vet_manuscript_lab.workflow.writing_graph import claim_audit_node

        state: dict[str, Any] = {
            **self.initial_state("adversarial-2"),
            "claim_drafts": [
                {
                    "claim_id": "c-causal",
                    "claim_type": "factual",
                    "text": "Treatment causes improved survival.",
                    "certainty": "high",
                    "section_id": "sec-1",
                    "referenced_numbers": [],
                }
            ],
            "support_drafts": [
                {
                    "claim_id": "c-causal",
                    "support_type": "evidence",
                    "source_id": "ev-1",
                    "relation": "supports",
                    "audit_status": "verified",
                }
            ],
            "result_drafts": [],
            "artifacts": {},
        }
        result = claim_audit_node(state)
        audit = result["artifacts"]["claim_audit"]
        self.assertEqual(audit["status"], "audit_failed")

    def test_claim_audit_catches_numeric_mismatch(self) -> None:
        """Inject a statistical claim with wrong numbers."""
        from vet_manuscript_lab.workflow.writing_graph import claim_audit_node

        state: dict[str, Any] = {
            **self.initial_state("adversarial-3"),
            "claim_drafts": [
                {
                    "claim_id": "c-numeric",
                    "claim_type": "statistical",
                    "text": "The estimate was 9.99.",
                    "certainty": "high",
                    "section_id": "sec-1",
                    "referenced_numbers": [9.99],
                }
            ],
            "support_drafts": [
                {
                    "claim_id": "c-numeric",
                    "support_type": "statistical_result",
                    "source_id": "r1",
                    "relation": "supports",
                    "audit_status": "verified",
                }
            ],
            "result_drafts": [
                {
                    "result_id": "r1",
                    "estimand": "test",
                    "estimate": 1.5,
                    "p_value": 0.03,
                }
            ],
            "artifacts": {},
        }
        result = claim_audit_node(state)
        audit = result["artifacts"]["claim_audit"]
        self.assertEqual(audit["status"], "audit_failed")

    def test_claim_audit_passes_clean_claims(self) -> None:
        """Clean claims with support and matching numbers pass audit."""
        from vet_manuscript_lab.workflow.writing_graph import claim_audit_node

        state: dict[str, Any] = {
            **self.initial_state("adversarial-4"),
            "claim_drafts": [
                {
                    "claim_id": "c-clean",
                    "claim_type": "statistical",
                    "text": "The estimate was 1.5 with p-value 0.03.",
                    "certainty": "high",
                    "section_id": "sec-1",
                    "referenced_numbers": [1.5, 0.03],
                }
            ],
            "support_drafts": [
                {
                    "claim_id": "c-clean",
                    "support_type": "statistical_result",
                    "source_id": "r1",
                    "relation": "supports",
                    "audit_status": "verified",
                }
            ],
            "result_drafts": [
                {
                    "result_id": "r1",
                    "estimand": "test",
                    "estimate": 1.5,
                    "p_value": 0.03,
                }
            ],
            "artifacts": {},
        }
        result = claim_audit_node(state)
        audit = result["artifacts"]["claim_audit"]
        self.assertEqual(audit["status"], "audit_passed")


if __name__ == "__main__":
    unittest.main()
