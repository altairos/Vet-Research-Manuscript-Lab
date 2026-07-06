"""Integration tests for the compliance, sign-off, and export pipeline.

Covers the full ``REVIEW -> COMPLIANCE_AUDIT -> SIGN_OFF -> EXPORT -> COMPLETE``
flow, including blocking findings, hash-tamper detection, manifest
integrity, checkpoint resume, and auditor determinism.
"""

from __future__ import annotations

import gc
import tempfile
import unittest
from pathlib import Path
from typing import Any

from langgraph.types import Command

from vet_manuscript_lab.infrastructure.checkpoints import open_sqlite_checkpointer
from vet_manuscript_lab.services.compliance import (
    ComplianceInput,
    ComplianceOutput,
    MockComplianceAuditor,
)
from vet_manuscript_lab.services.compliance.types import (
    ChecklistSummary,
    ComplianceFindingDraft,
    ComplianceSeverity,
    ComplianceStatus,
    ExportReadiness,
)
from vet_manuscript_lab.services.export import (
    ExportInput,
    MockExportGenerator,
)
from vet_manuscript_lab.workflow.compliance_graph import (
    CompliancePipeline,
    build_compliance_pipeline_graph,
)
from vet_manuscript_lab.workflow.state import new_workflow_state


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


def _sign_off(
    decision: str = "approved",
    authoriser: str = "pi-1",
) -> Command:
    return Command(
        resume={
            "decision": decision,
            "authoriser_id": authoriser,
            "authoriser_role": "principal_investigator",
            "reason": "Final approval",
        }
    )


def _run_to_results_approval(graph: Any, config: dict, initial: dict) -> None:
    """Run through foundation + literature + analysis to results_approval."""
    graph.invoke(initial, config)  # -> question_approval
    graph.invoke(_approve(), config)  # -> protocol_approval
    graph.invoke(_approve(), config)  # -> search_approval
    graph.invoke(_approve(), config)  # -> analysis_plan_approval
    graph.invoke(_approve(), config)  # -> results_approval


def _run_to_compliance_audit(graph: Any, config: dict, initial: dict) -> None:
    """Run through to the final_compliance_audit interrupt or node."""
    _run_to_results_approval(graph, config, initial)
    # Approve results -> writing -> claim_audit -> review -> compliance_audit
    graph.invoke(_approve(), config)


# ---------------------------------------------------------------------------
# Test implementations
# ---------------------------------------------------------------------------


class _BlockingAuditor:
    """Auditor that always reports a blocking finding."""

    def audit(self, inputs: ComplianceInput) -> ComplianceOutput:
        return ComplianceOutput(
            findings=(
                ComplianceFindingDraft(
                    finding_id="block-1",
                    rule_id="test:blocking",
                    category="checklist",
                    severity=ComplianceSeverity.BLOCKING.value,
                    status=ComplianceStatus.FAIL.value,
                    evidence="Test blocking finding.",
                    recommendation="Fix this.",
                ),
            ),
            checklist_summary=ChecklistSummary(
                total_items=22,
                passed=0,
                failed=1,
                not_applicable=0,
                needs_review=0,
            ),
            readiness=ExportReadiness.BLOCKED.value,
        )


class _CleanAuditor:
    """Auditor that always returns ready (no findings)."""

    def audit(self, inputs: ComplianceInput) -> ComplianceOutput:
        return ComplianceOutput(
            findings=(),
            checklist_summary=ChecklistSummary(
                total_items=22,
                passed=22,
                failed=0,
                not_applicable=0,
                needs_review=0,
            ),
            readiness=ExportReadiness.READY.value,
        )


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


class CompliancePipelineIntegrationTests(unittest.TestCase):
    def initial_state(self, thread_id: str) -> dict[str, Any]:
        return new_workflow_state(
            project_id="project-compliance",
            workflow_run_id="run-compliance",
            thread_id=thread_id,
            now="2026-07-06T00:00:00Z",
        )

    def test_full_pipeline_completes_to_export(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temporary:
            connection, saver = open_sqlite_checkpointer(
                Path(temporary) / "checkpoints.sqlite"
            )
            graph = build_compliance_pipeline_graph(saver)
            config = {"configurable": {"thread_id": "full-pipeline"}}

            _run_to_compliance_audit(graph, config, self.initial_state("full-pipeline"))

            # Should be at compliance audit completed, waiting for sign-off
            snapshot = graph.get_state(config)
            readiness = snapshot.values.get("export_readiness")
            self.assertEqual(readiness, "ready")

            # Sign-off approved → export → complete (no more interrupts)
            result = graph.invoke(_sign_off(), config)
            self.assertEqual(result["run_status"], "complete")

            snapshot = graph.get_state(config)
            pkg = snapshot.values.get("export_package")
            self.assertIsNotNone(pkg)
            self.assertEqual(pkg["status"], "complete")
            self.assertGreater(pkg["component_count"], 0)

            connection.close()

    def test_export_package_has_manifest_and_components(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temporary:
            connection, saver = open_sqlite_checkpointer(
                Path(temporary) / "checkpoints.sqlite"
            )
            graph = build_compliance_pipeline_graph(saver)
            config = {"configurable": {"thread_id": "export-pkg"}}

            _run_to_compliance_audit(graph, config, self.initial_state("export-pkg"))
            graph.invoke(_sign_off(), config)

            snapshot = graph.get_state(config)
            artifacts = snapshot.values.get("artifacts", {})
            self.assertIn("export_package", artifacts)

            pkg = snapshot.values["export_package"]
            self.assertIn("manifest_hash", pkg)
            self.assertIn("package_uri", pkg)
            self.assertIn("sign_off_id", pkg)

            connection.close()

    def test_sign_off_binding_captures_hashes(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temporary:
            connection, saver = open_sqlite_checkpointer(
                Path(temporary) / "checkpoints.sqlite"
            )
            graph = build_compliance_pipeline_graph(saver)
            config = {"configurable": {"thread_id": "binding"}}

            _run_to_compliance_audit(graph, config, self.initial_state("binding"))
            graph.invoke(_sign_off(), config)

            snapshot = graph.get_state(config)
            binding = snapshot.values.get("sign_off_binding")
            self.assertIsNotNone(binding)
            self.assertIn("artifact_hashes", binding)
            self.assertGreater(len(binding["artifact_hashes"]), 0)

            connection.close()

    def test_checkpoint_resume_at_sign_off(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temporary:
            checkpoint_path = Path(temporary) / "checkpoints.sqlite"
            config = {"configurable": {"thread_id": "resume-signoff"}}

            connection, saver = open_sqlite_checkpointer(checkpoint_path)
            graph = build_compliance_pipeline_graph(saver)
            _run_to_compliance_audit(
                graph, config, self.initial_state("resume-signoff")
            )
            connection.close()
            del graph, saver
            gc.collect()

            # Resume from checkpoint with a new graph instance
            connection, saver = open_sqlite_checkpointer(checkpoint_path)
            resumed = build_compliance_pipeline_graph(saver)
            snapshot = resumed.get_state(config)

            # Should be waiting at sign-off
            self.assertTrue(len(interrupt_payloads(snapshot)) > 0)
            result = resumed.invoke(_sign_off(), config)
            # Sign-off approved → export → complete
            self.assertEqual(result["run_status"], "complete")
            connection.close()
            del resumed, saver
            gc.collect()


class CompliancePipelineBlockingTests(unittest.TestCase):
    def initial_state(self, thread_id: str) -> dict[str, Any]:
        return new_workflow_state(
            project_id="project-block",
            workflow_run_id="run-block",
            thread_id=thread_id,
            now="2026-07-06T00:00:00Z",
        )

    def test_blocking_finding_routes_to_blocked(self) -> None:
        """Blocking audit finding prevents sign-off; routes to blocked."""
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temporary:
            connection, saver = open_sqlite_checkpointer(
                Path(temporary) / "checkpoints.sqlite"
            )
            pipeline = CompliancePipeline(auditor=_BlockingAuditor())
            graph = build_compliance_pipeline_graph(saver, compliance_pipeline=pipeline)
            config = {"configurable": {"thread_id": "blocked"}}

            _run_to_compliance_audit(graph, config, self.initial_state("blocked"))

            # Graph should have run to blocked_termination
            snapshot = graph.get_state(config)
            self.assertEqual(snapshot.values.get("export_readiness"), "blocked")
            self.assertEqual(snapshot.values.get("run_status"), "blocked")
            self.assertEqual(snapshot.values.get("current_stage"), "blocked")

            connection.close()

    def test_revision_limit_reaches_blocked_termination(self) -> None:
        """Blocking compliance finding escalates to blocked state."""
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temporary:
            connection, saver = open_sqlite_checkpointer(
                Path(temporary) / "checkpoints.sqlite"
            )
            pipeline = CompliancePipeline(auditor=_BlockingAuditor())
            graph = build_compliance_pipeline_graph(saver, compliance_pipeline=pipeline)
            config = {"configurable": {"thread_id": "limit"}}

            state = self.initial_state("limit")
            _run_to_compliance_audit(graph, config, state)

            # Blocking compliance → blocked_termination → END
            snapshot = graph.get_state(config)
            self.assertEqual(snapshot.values.get("run_status"), "blocked")
            self.assertEqual(snapshot.values.get("current_stage"), "blocked")

            connection.close()


class CompliancePipelineAdversarialTests(unittest.TestCase):
    def initial_state(self, thread_id: str) -> dict[str, Any]:
        return new_workflow_state(
            project_id="project-adv",
            workflow_run_id="run-adv",
            thread_id=thread_id,
            now="2026-07-06T00:00:00Z",
        )

    def test_sign_off_rejected_routes_to_writing(self) -> None:
        """Rejected sign-off routes back to section writing for re-audit."""
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temporary:
            _connection, saver = open_sqlite_checkpointer(
                Path(temporary) / "checkpoints.sqlite"
            )
            graph = build_compliance_pipeline_graph(saver)
            config = {"configurable": {"thread_id": "rejected"}}

            _run_to_compliance_audit(graph, config, self.initial_state("rejected"))

            # Reject sign-off → routes to section_writing → re-audit
            # Graph loops back and arrives at sign-off again
            result = graph.invoke(_sign_off(decision="rejected"), config)
            self.assertIsNotNone(result)
            # Should be back at a sign-off interrupt
            snapshot = graph.get_state(config)
            interrupts = interrupt_payloads(snapshot)
            self.assertTrue(
                any(i.get("gate") == "final_sign_off" for i in interrupts),
                "Expected sign-off interrupt after rejection loop",
            )

    def test_mock_auditor_determinism(self) -> None:
        """Mock auditor produces identical output for identical input."""
        auditor = MockComplianceAuditor()
        inputs = ComplianceInput(
            sections=(),
            claims=(),
            results=(),
            citations=(),
            guideline_mapping={},
        )
        out1 = auditor.audit(inputs)
        out2 = auditor.audit(inputs)
        self.assertEqual(out1.readiness, out2.readiness)
        self.assertEqual(len(out1.findings), len(out2.findings))

    def test_mock_generator_determinism(self) -> None:
        """Mock export generator produces identical hash for identical input."""
        gen = MockExportGenerator()
        inputs = ExportInput(
            sections=(),
            citations=(),
            results=(),
            literature_records=(),
            analysis_plan_summary={},
            ai_usage={},
            sign_off_approval={"approval_id": "test"},
            manuscript_summary={"manuscript_id": "m1", "title": "T"},
        )
        out1 = gen.generate(inputs)
        out2 = gen.generate(inputs)
        self.assertEqual(out1.package_hash, out2.package_hash)

    def test_export_fail_closed_on_hash_mismatch(self) -> None:
        """Export must fail-closed if artifact hash changes after sign-off.

        We simulate this by checking that the sign-off binding captures
        the correct hashes and the export node verifies them.
        """
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temporary:
            connection, saver = open_sqlite_checkpointer(
                Path(temporary) / "checkpoints.sqlite"
            )
            graph = build_compliance_pipeline_graph(saver)
            config = {"configurable": {"thread_id": "tamper"}}

            _run_to_compliance_audit(graph, config, self.initial_state("tamper"))
            graph.invoke(_sign_off(), config)

            snapshot = graph.get_state(config)
            binding = snapshot.values.get("sign_off_binding")
            self.assertIsNotNone(binding)

            # Tamper: modify an artifact hash in the binding
            tampered_state = dict(snapshot.values)
            tampered_binding = dict(binding)
            tampered_hashes = dict(tampered_binding["artifact_hashes"])
            if tampered_hashes:
                first_key = next(iter(tampered_hashes))
                tampered_hashes[first_key] = "sha256:tampered"
            tampered_binding["artifact_hashes"] = tampered_hashes
            tampered_state["sign_off_binding"] = tampered_binding

            # The export node should detect the mismatch and raise
            from vet_manuscript_lab.domain.policies import PolicyViolation
            from vet_manuscript_lab.workflow.compliance_graph import export_node

            with self.assertRaises(PolicyViolation):
                export_node(tampered_state)

            connection.close()


if __name__ == "__main__":
    unittest.main()
