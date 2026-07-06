"""Integration and adversarial tests for the methodology + statistics pipeline.

Covers the full ``PROJECT_INIT -> RESULTS_APPROVAL`` flow, cross-instance
checkpoint resume, analysis-plan rejection with re-drafting, and every
Phase 3 exit-gate invariant (locked dataset + locked plan, exploratory
marking, execution immutability, failure safety, reproducibility).
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any

from langgraph.types import Command

from vet_manuscript_lab.domain.policies import PolicyViolation
from vet_manuscript_lab.infrastructure.checkpoints import open_sqlite_checkpointer
from vet_manuscript_lab.services.analysis.runner import MockStatisticsRunner
from vet_manuscript_lab.services.analysis.types import (
    AnalysisClass,
    AnalysisSpec,
    VariableRole,
    VariableSpec,
    VariableType,
)
from vet_manuscript_lab.workflow.analysis_graph import (
    AnalysisPipeline,
    build_analysis_pipeline_graph,
)
from vet_manuscript_lab.workflow.state import (
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
            "comment": "Plan needs revision",
        }
    )


def _run_to_evidence(graph: Any, config: dict, initial: dict) -> None:
    """Helper: run the graph through foundation + literature stages."""
    graph.invoke(initial, config)  # project_init -> question_approval interrupt
    graph.invoke(_approve(), config)  # question -> protocol
    graph.invoke(_approve(), config)  # protocol -> search
    graph.invoke(_approve(), config)  # search -> evidence audit
    # After evidence_audit: methodology -> plan -> approval interrupt


class AnalysisPipelineIntegrationTests(unittest.TestCase):
    def initial_state(self, thread_id: str) -> dict[str, Any]:
        return new_workflow_state(
            project_id="project-analysis",
            workflow_run_id="run-analysis",
            thread_id=thread_id,
            now="2026-07-06T00:00:00Z",
        )

    def test_full_pipeline_runs_to_results_approval(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            connection, saver = open_sqlite_checkpointer(
                Path(temporary) / "checkpoints.sqlite"
            )
            graph = build_analysis_pipeline_graph(saver)
            config = {"configurable": {"thread_id": "full-analysis"}}

            graph.invoke(self.initial_state("full-analysis"), config)
            # question approval
            self.assertEqual(
                interrupt_payloads(graph.get_state(config))[0]["gate"], "question"
            )
            graph.invoke(_approve(), config)
            # protocol approval
            self.assertEqual(
                interrupt_payloads(graph.get_state(config))[0]["gate"], "protocol"
            )
            graph.invoke(_approve(), config)
            # search approval
            self.assertEqual(
                interrupt_payloads(graph.get_state(config))[0]["gate"],
                "search_strategy",
            )
            graph.invoke(_approve(), config)
            # After search: screening -> audit -> methodology -> plan
            # Reaches analysis_plan_approval
            self.assertEqual(
                interrupt_payloads(graph.get_state(config))[0]["gate"],
                "analysis_plan",
            )

            # Verify methodology findings were generated
            snapshot = graph.get_state(config)
            self.assertIn("methodology_findings", snapshot.values)
            self.assertGreater(len(snapshot.values.get("methodology_findings", [])), 0)

            # Approve analysis plan
            graph.invoke(_approve(), config)
            # statistics execution + results approval interrupt
            self.assertEqual(
                interrupt_payloads(graph.get_state(config))[0]["gate"],
                "results_interpretation",
            )

            # Verify statistics execution completed
            snapshot = graph.get_state(config)
            run_summary = snapshot.values.get("analysis_run_summary")
            self.assertIsNotNone(run_summary)
            self.assertEqual(run_summary["status"], "completed")
            self.assertEqual(run_summary["exit_code"], 0)
            self.assertGreater(run_summary["result_count"], 0)

            # Verify plan and dataset are locked
            locks = snapshot.values.get("locks", {})
            self.assertIn("analysis_plan", locks)
            self.assertIn("dataset", locks)

            # Approve results
            result = graph.invoke(_approve(), config)
            self.assertEqual(result["run_status"], "complete")
            self.assertEqual(result["current_stage"], "results_approval")
            connection.close()

    def test_pipeline_resumes_across_graph_instances(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            checkpoint_path = Path(temporary) / "checkpoints.sqlite"
            config = {"configurable": {"thread_id": "resume-analysis"}}

            connection, saver = open_sqlite_checkpointer(checkpoint_path)
            graph = build_analysis_pipeline_graph(saver)
            graph.invoke(self.initial_state("resume-analysis"), config)
            graph.invoke(_approve(), config)  # question
            graph.invoke(_approve(), config)  # protocol
            connection.close()

            # Resume with a new graph instance
            connection, saver = open_sqlite_checkpointer(checkpoint_path)
            resumed_graph = build_analysis_pipeline_graph(saver)
            snapshot = resumed_graph.get_state(config)
            self.assertEqual(interrupt_payloads(snapshot)[0]["gate"], "search_strategy")
            resumed_graph.invoke(_approve(), config)  # search
            # Reaches analysis_plan_approval
            self.assertEqual(
                interrupt_payloads(resumed_graph.get_state(config))[0]["gate"],
                "analysis_plan",
            )
            resumed_graph.invoke(_approve(), config)  # analysis plan
            resumed_graph.invoke(_approve(), config)  # results
            result = resumed_graph.get_state(config).values
            self.assertEqual(result["run_status"], "complete")
            connection.close()

    def test_analysis_plan_rejection_returns_to_methodology(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            connection, saver = open_sqlite_checkpointer(
                Path(temporary) / "checkpoints.sqlite"
            )
            graph = build_analysis_pipeline_graph(saver)
            config = {"configurable": {"thread_id": "reject-plan"}}

            _run_to_evidence(graph, config, self.initial_state("reject-plan"))
            self.assertEqual(
                interrupt_payloads(graph.get_state(config))[0]["gate"],
                "analysis_plan",
            )

            # Reject the plan
            graph.invoke(_reject(), config)
            # Should go back to methodology_critic -> analysis_plan -> approval again
            self.assertEqual(
                interrupt_payloads(graph.get_state(config))[0]["gate"],
                "analysis_plan",
            )

            # Verify version was bumped (re-drafted after rejection)
            snapshot = graph.get_state(config)
            plan = snapshot.values["artifacts"]["analysis_plan"]
            self.assertGreaterEqual(plan["version"], 2)

            # Approve the re-drafted plan
            graph.invoke(_approve(), config)
            graph.invoke(_approve(), config)
            connection.close()

    def test_statistics_results_are_deterministic(self) -> None:
        """Same plan + dataset + seed must produce same results."""
        with tempfile.TemporaryDirectory() as temporary:
            connection1, saver1 = open_sqlite_checkpointer(
                Path(temporary) / "cp1.sqlite"
            )
            connection2, saver2 = open_sqlite_checkpointer(
                Path(temporary) / "cp2.sqlite"
            )

            for i, (conn, saver) in enumerate(
                [(connection1, saver1), (connection2, saver2)]
            ):
                graph = build_analysis_pipeline_graph(saver)
                config = {"configurable": {"thread_id": f"repro-{i}"}}
                _run_to_evidence(graph, config, self.initial_state(f"repro-{i}"))
                graph.invoke(_approve(), config)  # analysis plan
                graph.invoke(_approve(), config)  # results

                snapshot = graph.get_state(config)
                results = snapshot.values.get("result_drafts", [])
                self.assertGreater(len(results), 0)
                if i == 0:
                    first_estimates = tuple(r["estimate"] for r in results)
                else:
                    second_estimates = tuple(r["estimate"] for r in results)
                    self.assertEqual(first_estimates, second_estimates)
                conn.close()

    def test_failed_run_does_not_produce_approved_result(self) -> None:
        """A runner that fails must not produce approved results."""
        with tempfile.TemporaryDirectory() as temporary:
            connection, saver = open_sqlite_checkpointer(
                Path(temporary) / "checkpoints.sqlite"
            )
            graph = build_analysis_pipeline_graph(
                saver,
                analysis_pipeline=AnalysisPipeline(
                    runner=MockStatisticsRunner(fail_on_analysis="primary_survival"),
                ),
            )
            config = {"configurable": {"thread_id": "fail-run"}}

            _run_to_evidence(graph, config, self.initial_state("fail-run"))
            graph.invoke(_approve(), config)  # analysis plan

            snapshot = graph.get_state(config)
            run_summary = snapshot.values.get("analysis_run_summary")
            self.assertIsNotNone(run_summary)
            self.assertEqual(run_summary["status"], "failed")
            self.assertEqual(run_summary["exit_code"], 1)
            self.assertEqual(run_summary["result_count"], 0)
            connection.close()

    def test_runner_requires_locked_plan(self) -> None:
        """Runner must reject an unlocked plan."""
        from vet_manuscript_lab.domain.policies import (
            AnalysisPlanSnapshot,
            DatasetVersionSnapshot,
        )
        from vet_manuscript_lab.services.analysis.runner import MockStatisticsRunner
        from vet_manuscript_lab.services.analysis.types import DatasetSpec

        runner = MockStatisticsRunner()
        plan = AnalysisPlanSnapshot(
            version_id="plan-1",
            content_hash="sha256:abc",
            status="draft",  # NOT locked
            variable_names=frozenset({"x"}),
            model_specifications=("logistic",),
            exclusion_criteria=(),
        )
        dataset = DatasetVersionSnapshot(
            version_id="ds-1",
            content_hash="sha256:def",
            status="locked",
        )
        analyses = (
            AnalysisSpec(
                name="test",
                estimand="test",
                model_type="logistic",
                variable_names=("x",),
            ),
        )
        dataset_spec = DatasetSpec(
            dataset_id="ds-1",
            name="test",
            row_count=10,
            column_count=1,
            content_hash="sha256:def",
            uri="mock://ds-1",
        )
        with self.assertRaises(PolicyViolation):
            runner.execute(
                plan=plan,
                dataset=dataset,
                analyses=analyses,
                dataset_spec=dataset_spec,
                available_variables=frozenset({"x"}),
                run_id="run-1",
            )

    def test_runner_requires_locked_dataset(self) -> None:
        """Runner must reject an unlocked dataset."""
        from vet_manuscript_lab.domain.policies import (
            AnalysisPlanSnapshot,
            DatasetVersionSnapshot,
        )
        from vet_manuscript_lab.services.analysis.runner import MockStatisticsRunner
        from vet_manuscript_lab.services.analysis.types import DatasetSpec

        runner = MockStatisticsRunner()
        plan = AnalysisPlanSnapshot(
            version_id="plan-1",
            content_hash="sha256:abc",
            status="locked",
            variable_names=frozenset({"x"}),
            model_specifications=("logistic",),
            exclusion_criteria=(),
        )
        dataset = DatasetVersionSnapshot(
            version_id="ds-1",
            content_hash="sha256:def",
            status="draft",  # NOT locked
        )
        analyses = (
            AnalysisSpec(
                name="test",
                estimand="test",
                model_type="logistic",
                variable_names=("x",),
            ),
        )
        dataset_spec = DatasetSpec(
            dataset_id="ds-1",
            name="test",
            row_count=10,
            column_count=1,
            content_hash="sha256:def",
            uri="mock://ds-1",
        )
        with self.assertRaises(PolicyViolation):
            runner.execute(
                plan=plan,
                dataset=dataset,
                analyses=analyses,
                dataset_spec=dataset_spec,
                available_variables=frozenset({"x"}),
                run_id="run-1",
            )

    def test_runner_rejects_unknown_variable(self) -> None:
        """Runner must reject a plan referencing non-existent variables."""
        from vet_manuscript_lab.domain.policies import (
            AnalysisPlanSnapshot,
            DatasetVersionSnapshot,
        )
        from vet_manuscript_lab.services.analysis.runner import MockStatisticsRunner
        from vet_manuscript_lab.services.analysis.types import DatasetSpec

        runner = MockStatisticsRunner()
        plan = AnalysisPlanSnapshot(
            version_id="plan-1",
            content_hash="sha256:abc",
            status="locked",
            variable_names=frozenset({"x"}),
            model_specifications=("logistic",),
            exclusion_criteria=(),
        )
        dataset = DatasetVersionSnapshot(
            version_id="ds-1",
            content_hash="sha256:def",
            status="locked",
        )
        analyses = (
            AnalysisSpec(
                name="test",
                estimand="test",
                model_type="logistic",
                variable_names=("x", "nonexistent"),
            ),
        )
        dataset_spec = DatasetSpec(
            dataset_id="ds-1",
            name="test",
            row_count=10,
            column_count=1,
            content_hash="sha256:def",
            uri="mock://ds-1",
        )
        with self.assertRaises(PolicyViolation) as ctx:
            runner.execute(
                plan=plan,
                dataset=dataset,
                analyses=analyses,
                dataset_spec=dataset_spec,
                available_variables=frozenset({"x"}),
                run_id="run-1",
            )
        self.assertIn("nonexistent", str(ctx.exception))

    def test_runner_rejects_unflagged_exploratory(self) -> None:
        """Analysis not in plan but not flagged exploratory must be rejected."""
        from vet_manuscript_lab.domain.policies import (
            AnalysisPlanSnapshot,
            DatasetVersionSnapshot,
        )
        from vet_manuscript_lab.services.analysis.runner import MockStatisticsRunner
        from vet_manuscript_lab.services.analysis.types import DatasetSpec

        runner = MockStatisticsRunner()
        plan = AnalysisPlanSnapshot(
            version_id="plan-1",
            content_hash="sha256:abc",
            status="locked",
            variable_names=frozenset({"x"}),
            model_specifications=("logistic",),
            exclusion_criteria=(),
        )
        dataset = DatasetVersionSnapshot(
            version_id="ds-1",
            content_hash="sha256:def",
            status="locked",
        )
        # Analysis references 'z' which is NOT in plan's variable set
        # and is NOT marked exploratory
        analyses = (
            AnalysisSpec(
                name="sneaky",
                estimand="test",
                model_type="logistic",
                variable_names=("x", "z"),
                analysis_class=AnalysisClass.PRIMARY,
            ),
        )
        dataset_spec = DatasetSpec(
            dataset_id="ds-1",
            name="test",
            row_count=10,
            column_count=2,
            content_hash="sha256:def",
            uri="mock://ds-1",
            variables=(
                VariableSpec(name="x", var_type=VariableType.CONTINUOUS, unit="mg"),
                VariableSpec(
                    name="z",
                    var_type=VariableType.CONTINUOUS,
                    unit="ml",
                    role=VariableRole.OUTCOME,
                ),
            ),
        )
        with self.assertRaises(PolicyViolation) as ctx:
            runner.execute(
                plan=plan,
                dataset=dataset,
                analyses=analyses,
                dataset_spec=dataset_spec,
                available_variables=frozenset({"x", "z"}),
                run_id="run-1",
            )
        self.assertIn("exploratory", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
