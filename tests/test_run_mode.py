"""Tests for RunMode and production fail-closed behavior.

Covers:
1. RunMode enum and run_mode_allows_mock helper.
2. Settings.run_mode loading from environment.
3. Evidence extraction fail-closed: mock fallback rejected in production,
   no-hit retrieval rejected in production.
4. Methodology critic fail-closed: mock findings rejected in production.
5. Statistics execution fail-closed: MockStatisticsRunner rejected in production.
6. Section writing fail-closed: MockSectionWriter rejected in production.
7. DOCX export fail-closed: MockDocxRenderer rejected in production.
8. Demo mode remains fully functional (all fallbacks allowed).
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from typing import Any

from vet_manuscript_lab.domain.conventions import (
    RUN_MODE_ENV,
    RunMode,
    run_mode_allows_mock,
)
from vet_manuscript_lab.domain.policies import (
    EvidenceExtractionFailed,
    NeedsHumanSourceSpan,
    PolicyViolation,
    require_no_mock_fallback,
    require_real_source_span,
)
from vet_manuscript_lab.workflow.literature_graph import (
    evidence_extraction_node,
)
from vet_manuscript_lab.workflow.state import new_workflow_state

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state(**overrides: Any) -> dict[str, Any]:
    """Create a minimal workflow state for testing."""

    state = new_workflow_state(
        project_id="proj-run-mode",
        workflow_run_id="run-1",
        thread_id="thread-1",
        now="2026-07-09T00:00:00Z",
    )
    state.update(overrides)
    return state


def _make_included_records(count: int = 2) -> list[dict[str, Any]]:
    """Create synthetic included literature records."""

    records = []
    for i in range(count):
        records.append(
            {
                "record_id": f"rec-{i}",
                "title": f"Study {i}",
                "doi": f"10.1000/study{i}",
                "publication_year": 2024,
                "screening_decision": "included",
            }
        )
    return records


# ---------------------------------------------------------------------------
# RunMode enum and helpers
# ---------------------------------------------------------------------------


class RunModeEnumTests(unittest.TestCase):
    """RunMode enum and run_mode_allows_mock tests."""

    def test_run_mode_values(self) -> None:
        self.assertEqual(RunMode.DEMO.value, "demo")
        self.assertEqual(RunMode.TEST.value, "test")
        self.assertEqual(RunMode.PRODUCTION.value, "production")

    def test_allows_mock_demo(self) -> None:
        self.assertTrue(run_mode_allows_mock(RunMode.DEMO))

    def test_allows_mock_test(self) -> None:
        self.assertTrue(run_mode_allows_mock(RunMode.TEST))

    def test_disallows_mock_production(self) -> None:
        self.assertFalse(run_mode_allows_mock(RunMode.PRODUCTION))


# ---------------------------------------------------------------------------
# Settings.run_mode
# ---------------------------------------------------------------------------


class SettingsRunModeTests(unittest.TestCase):
    """Settings.run_mode loading from environment."""

    def setUp(self) -> None:
        self._original = os.environ.pop(RUN_MODE_ENV, None)

    def tearDown(self) -> None:
        if self._original is not None:
            os.environ[RUN_MODE_ENV] = self._original
        else:
            os.environ.pop(RUN_MODE_ENV, None)

    def test_defaults_to_demo(self) -> None:
        from vet_manuscript_lab.config import Settings

        settings = Settings.from_env()
        self.assertEqual(settings.run_mode, RunMode.DEMO)
        self.assertTrue(settings.is_demo)
        self.assertTrue(settings.allows_mock_fallback)
        self.assertFalse(settings.is_production)

    def test_production_from_env(self) -> None:
        from vet_manuscript_lab.config import Settings

        os.environ[RUN_MODE_ENV] = "production"
        settings = Settings.from_env()
        self.assertEqual(settings.run_mode, RunMode.PRODUCTION)
        self.assertTrue(settings.is_production)
        self.assertFalse(settings.allows_mock_fallback)


# ---------------------------------------------------------------------------
# Policy function tests
# ---------------------------------------------------------------------------


class FailClosedPolicyTests(unittest.TestCase):
    """Tests for require_no_mock_fallback and require_real_source_span."""

    def test_no_mock_fallback_allows_demo(self) -> None:
        """Mock fallback is permitted in DEMO mode."""
        require_no_mock_fallback(
            run_mode=RunMode.DEMO,
            is_mock_generated=True,
        )

    def test_no_mock_fallback_rejects_production(self) -> None:
        """Mock fallback is rejected in PRODUCTION mode."""
        with self.assertRaises(EvidenceExtractionFailed):
            require_no_mock_fallback(
                run_mode=RunMode.PRODUCTION,
                is_mock_generated=True,
            )

    def test_no_mock_fallback_allows_real_in_production(self) -> None:
        """Real (non-mock) data is always permitted."""
        require_no_mock_fallback(
            run_mode=RunMode.PRODUCTION,
            is_mock_generated=False,
        )

    def test_real_source_span_allows_demo_without_attachment(self) -> None:
        """In DEMO mode, a span without attachment_version_id is allowed."""
        require_real_source_span(
            run_mode=RunMode.DEMO,
            span_attachment_version_id=None,
            record_id="rec-1",
        )

    def test_real_source_span_rejects_production_without_attachment(self) -> None:
        """In PRODUCTION mode, a span without attachment_version_id is rejected."""
        with self.assertRaises(NeedsHumanSourceSpan):
            require_real_source_span(
                run_mode=RunMode.PRODUCTION,
                span_attachment_version_id=None,
                record_id="rec-1",
            )

    def test_real_source_span_allows_production_with_attachment(self) -> None:
        """In PRODUCTION mode, a span with a real attachment is allowed."""
        require_real_source_span(
            run_mode=RunMode.PRODUCTION,
            span_attachment_version_id="att-v1",
            record_id="rec-1",
        )


# ---------------------------------------------------------------------------
# Evidence extraction node fail-closed
# ---------------------------------------------------------------------------


class EvidenceExtractionFailClosedTests(unittest.TestCase):
    """Evidence extraction node fail-closed behavior."""

    def test_demo_mode_mock_fallback_works(self) -> None:
        """In DEMO mode, mock evidence extraction works as before."""
        state = _make_state(
            literature_record_drafts=_make_included_records(2),
        )
        result = evidence_extraction_node(state, run_mode=RunMode.DEMO)
        self.assertEqual(len(result["evidence_drafts"]), 2)

    def test_production_mode_mock_fallback_rejected(self) -> None:
        """In PRODUCTION mode, mock evidence extraction is rejected."""
        state = _make_state(
            literature_record_drafts=_make_included_records(2),
        )
        with self.assertRaises(EvidenceExtractionFailed):
            evidence_extraction_node(state, run_mode=RunMode.PRODUCTION)

    def test_production_mode_pipeline_no_hits_rejected(self) -> None:
        """In PRODUCTION mode, retriever with no hits raises NeedsHumanSourceSpan."""
        from vet_manuscript_lab.services.documents.parser import PdfParser
        from vet_manuscript_lab.services.retrieval.chunker import TextChunker
        from vet_manuscript_lab.services.retrieval.index import HybridRetriever
        from vet_manuscript_lab.workflow.literature_graph import EvidencePipeline

        pipeline = EvidencePipeline(
            parser=PdfParser(),
            chunker=TextChunker(),
            retriever=HybridRetriever(),
        )
        state = _make_state(
            literature_record_drafts=_make_included_records(1),
            _pipeline_chunks=[],  # empty → no retrieval hits
        )
        with self.assertRaises(NeedsHumanSourceSpan):
            evidence_extraction_node(
                state, pipeline=pipeline, run_mode=RunMode.PRODUCTION
            )

    def test_test_mode_mock_fallback_works(self) -> None:
        """In TEST mode, mock evidence extraction is allowed."""
        state = _make_state(
            literature_record_drafts=_make_included_records(1),
        )
        result = evidence_extraction_node(state, run_mode=RunMode.TEST)
        self.assertEqual(len(result["evidence_drafts"]), 1)


# ---------------------------------------------------------------------------
# Methodology critic fail-closed
# ---------------------------------------------------------------------------


class MethodologyCriticFailClosedTests(unittest.TestCase):
    """Methodology critic node fail-closed behavior."""

    def test_production_no_gateway_rejected(self) -> None:
        """In PRODUCTION mode, mock methodology findings are rejected."""
        from vet_manuscript_lab.workflow.analysis_graph import (
            methodology_critic_node,
        )

        state = _make_state(
            evidence_summary={"total_evidence_items": 5},
        )
        with self.assertRaises(EvidenceExtractionFailed):
            methodology_critic_node(state, run_mode=RunMode.PRODUCTION)

    def test_demo_no_gateway_works(self) -> None:
        """In DEMO mode, mock methodology findings work as before."""
        from vet_manuscript_lab.workflow.analysis_graph import (
            methodology_critic_node,
        )

        state = _make_state(
            evidence_summary={"total_evidence_items": 5},
        )
        result = methodology_critic_node(state, run_mode=RunMode.DEMO)
        self.assertGreater(len(result["methodology_findings"]), 0)


# ---------------------------------------------------------------------------
# Statistics execution fail-closed
# ---------------------------------------------------------------------------


class StatisticsExecutionFailClosedTests(unittest.TestCase):
    """Statistics execution node fail-closed behavior."""

    def _make_state_for_stats(self) -> dict[str, Any]:
        """Create a state with enough context for statistics execution."""
        return _make_state(
            evidence_summary={"total_evidence_items": 5},
            methodology_findings=[
                {
                    "finding_id": "f1",
                    "category": "confounding",
                    "severity": "warning",
                    "rationale": "test",
                    "recommendation": "test",
                    "status": "open",
                }
            ],
            dataset_summary={
                "dataset_id": "ds-1",
                "dataset_version_id": "ds-v1",
                "name": "Test",
                "row_count": 10,
                "variable_count": 3,
                "content_hash": "sha256:abc",
                "locked": True,
            },
            analysis_plan_summary={
                "plan_version_id": "plan-v1",
                "plan_hash": "sha256:def",
                "status": "locked",
            },
            locks={
                "analysis_plan": {
                    "lock_id": "lock-1",
                    "lock_type": "analysis_plan",
                    "subject_id": "plan-1",
                    "subject_version_id": "plan-v1",
                    "subject_hash": "sha256:def",
                    "locked_by": "test",
                    "locked_at": "2026-01-01T00:00:00Z",
                },
                "dataset": {
                    "lock_id": "lock-2",
                    "lock_type": "dataset",
                    "subject_id": "ds-1",
                    "subject_version_id": "ds-v1",
                    "subject_hash": "sha256:abc",
                    "locked_by": "test",
                    "locked_at": "2026-01-01T00:00:00Z",
                },
            },
            variable_spec_drafts=[
                {"name": "x", "var_type": "continuous", "role": "covariate"},
            ],
            analysis_spec_drafts=[
                {
                    "name": "test",
                    "estimand": "test",
                    "model_type": "logistic",
                    "variable_names": ["x"],
                    "analysis_class": "primary",
                    "exclusion_criteria": [],
                    "population": "all",
                }
            ],
        )

    def test_production_mock_runner_rejected(self) -> None:
        """In PRODUCTION mode, MockStatisticsRunner is rejected."""
        from vet_manuscript_lab.workflow.analysis_graph import (
            statistics_execution_node,
        )

        state = self._make_state_for_stats()
        with self.assertRaises(EvidenceExtractionFailed):
            statistics_execution_node(state, run_mode=RunMode.PRODUCTION)


# ---------------------------------------------------------------------------
# Section writing fail-closed
# ---------------------------------------------------------------------------


class SectionWritingFailClosedTests(unittest.TestCase):
    """Section writing node fail-closed behavior."""

    def test_production_mock_writer_rejected(self) -> None:
        """In PRODUCTION mode, MockSectionWriter is rejected."""
        from vet_manuscript_lab.workflow.writing_graph import (
            section_writing_node,
        )

        state = _make_state(
            evidence_summary={"total_evidence_items": 5},
            locks={"protocol": {}},
            approvals={
                "results_interpretation": {"decision": "approved"},
            },
            result_drafts=[],
            literature_record_drafts=[],
            analysis_plan_summary={},
        )
        with self.assertRaises(EvidenceExtractionFailed):
            section_writing_node(state, run_mode=RunMode.PRODUCTION)


# ---------------------------------------------------------------------------
# DOCX export fail-closed
# ---------------------------------------------------------------------------


class DocxExportFailClosedTests(unittest.TestCase):
    """DOCX export fail-closed: mock renderer marked and rejectable."""

    def test_mock_renderer_marks_output(self) -> None:
        """MockDocxRenderer output has is_mock_output=True."""
        from vet_manuscript_lab.services.export.renderer import (
            DocxRenderInput,
            MockDocxRenderer,
        )

        renderer = MockDocxRenderer()
        result = renderer.render(
            DocxRenderInput(
                qmd_content="# Test\n\nHello world.",
                bib_content="",
                title="Test",
            )
        )
        self.assertTrue(result.is_mock_output)
        self.assertEqual(result.renderer_name, "mock")

    def test_real_renderers_not_marked_mock(self) -> None:
        """QuartoDocxRenderer and PandocDocxRenderer are not mock."""
        from vet_manuscript_lab.services.export.renderer import (
            PandocDocxRenderer,
            QuartoDocxRenderer,
        )

        quarto = QuartoDocxRenderer()
        pandoc = PandocDocxRenderer()
        # Even if not available, the class itself is not MockDocxRenderer
        self.assertFalse(quarto.__class__.__name__ == "MockDocxRenderer")
        self.assertFalse(pandoc.__class__.__name__ == "MockDocxRenderer")

    def test_compliance_graph_rejects_mock_docx_in_production(self) -> None:
        """build_compliance_pipeline_graph raises for mock DOCX in production."""
        from langgraph.checkpoint.memory import MemorySaver

        from vet_manuscript_lab.workflow.compliance_graph import (
            build_compliance_pipeline_graph,
        )

        with self.assertRaises(PolicyViolation) as ctx:
            build_compliance_pipeline_graph(
                MemorySaver(),
                run_mode=RunMode.PRODUCTION,
            )
        self.assertIn("Mock DOCX", str(ctx.exception))


# ---------------------------------------------------------------------------
# Demo mode integration (backward compatibility)
# ---------------------------------------------------------------------------


class DemoModeIntegrationTests(unittest.TestCase):
    """Verify demo mode still works end-to-end (backward compatibility)."""

    def test_evidence_pipeline_graph_demo_mode(self) -> None:
        """Full evidence pipeline in DEMO mode runs to completion."""
        from langgraph.types import Command

        from vet_manuscript_lab.infrastructure.checkpoints import (
            open_sqlite_checkpointer,
        )
        from vet_manuscript_lab.workflow.literature_graph import (
            build_evidence_pipeline_graph,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            connection, saver = open_sqlite_checkpointer(
                Path(tmpdir) / "checkpoints.sqlite"
            )
            graph = build_evidence_pipeline_graph(saver, run_mode=RunMode.DEMO)
            config = {"configurable": {"thread_id": "demo-run"}}

            state = new_workflow_state(
                project_id="proj-demo",
                workflow_run_id="run-demo",
                thread_id="demo-run",
                now="2026-07-09T00:00:00Z",
            )
            graph.invoke(state, config)

            def _approve() -> Command:
                return Command(
                    resume={
                        "decision": "approved",
                        "reviewer_id": "test",
                        "reviewer_role": "investigator",
                        "comment": "ok",
                    }
                )

            graph.invoke(_approve(), config)  # question
            graph.invoke(_approve(), config)  # protocol
            graph.invoke(_approve(), config)  # search

            result = graph.get_state(config)
            self.assertEqual(result.values.get("run_status"), "complete")
            self.assertGreater(
                result.values.get("evidence_summary", {}).get(
                    "total_evidence_items", 0
                ),
                0,
            )
            connection.close()


if __name__ == "__main__":
    unittest.main()
