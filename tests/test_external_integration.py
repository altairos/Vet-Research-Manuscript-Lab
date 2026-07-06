"""Tests for Phase 3 external integration layer.

Covers:
1. SubprocessStatisticsRunner: deterministic execution, policy enforcement,
   reproducibility, failure handling, and Protocol compliance.
2. Methodology critic structured findings parsing from gateway output.
3. UI i18n entries for analysis-stage labels.
"""

from __future__ import annotations

import json
import unittest
from typing import Any, ClassVar

from vet_manuscript_lab.domain.policies import (
    AnalysisPlanSnapshot,
    DatasetVersionSnapshot,
    PolicyViolation,
)
from vet_manuscript_lab.infrastructure.model_gateway.gateway import (
    ModelGateway,
)
from vet_manuscript_lab.services.analysis.subprocess_runner import (
    SubprocessStatisticsRunner,
)
from vet_manuscript_lab.services.analysis.types import (
    AnalysisClass,
    AnalysisSpec,
    DatasetSpec,
    ResultSpec,
    VariableRole,
    VariableSpec,
    VariableType,
)
from vet_manuscript_lab.ui.i18n import STRINGS, translate
from vet_manuscript_lab.workflow.analysis_graph import _parse_gateway_findings

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


def _make_plan() -> AnalysisPlanSnapshot:
    return AnalysisPlanSnapshot(
        version_id="plan-v1",
        content_hash="sha256:abc123",
        status="locked",
        variable_names=frozenset({"survival_months", "treatment_group", "age_years"}),
        model_specifications=("log_rank", "cox"),
        exclusion_criteria=("Exclude short follow-up",),
    )


def _make_dataset() -> DatasetVersionSnapshot:
    return DatasetVersionSnapshot(
        version_id="ds-v1",
        content_hash="sha256:def456",
        status="locked",
    )


def _make_dataset_spec() -> DatasetSpec:
    return DatasetSpec(
        dataset_id="ds-001",
        name="Test dataset",
        row_count=30,
        column_count=5,
        content_hash="sha256:def456",
        uri="mock://ds-001",
        media_type="text/csv",
        variables=(
            VariableSpec(
                name="case_id",
                var_type=VariableType.CATEGORICAL,
                role=VariableRole.ID,
            ),
            VariableSpec(
                name="species",
                var_type=VariableType.CATEGORICAL,
                role=VariableRole.COVARIATE,
            ),
            VariableSpec(
                name="age_years",
                var_type=VariableType.CONTINUOUS,
                role=VariableRole.COVARIATE,
                unit="years",
            ),
            VariableSpec(
                name="treatment_group",
                var_type=VariableType.BINARY,
                role=VariableRole.EXPOSURE,
            ),
            VariableSpec(
                name="survival_months",
                var_type=VariableType.CONTINUOUS,
                role=VariableRole.OUTCOME,
                unit="months",
            ),
        ),
    )


def _make_analyses() -> tuple[AnalysisSpec, ...]:
    return (
        AnalysisSpec(
            name="primary_survival",
            estimand="Survival difference",
            model_type="log_rank",
            variable_names=("survival_months", "treatment_group"),
            analysis_class=AnalysisClass.PRIMARY,
            exclusion_criteria=("Exclude short follow-up",),
            population="All cases",
        ),
        AnalysisSpec(
            name="age_adjusted",
            estimand="Age-adjusted effect",
            model_type="cox",
            variable_names=(
                "survival_months",
                "treatment_group",
                "age_years",
            ),
            analysis_class=AnalysisClass.SECONDARY,
            exclusion_criteria=(),
            population="All cases",
        ),
    )


_AVAILABLE_VARS = frozenset(
    {"case_id", "species", "age_years", "treatment_group", "survival_months"}
)


# ---------------------------------------------------------------------------
# SubprocessStatisticsRunner tests
# ---------------------------------------------------------------------------


class SubprocessRunnerTests(unittest.TestCase):
    """Tests for the subprocess-isolated statistics runner."""

    def test_executes_and_returns_deterministic_results(self) -> None:
        runner = SubprocessStatisticsRunner()
        result = runner.execute(
            plan=_make_plan(),
            dataset=_make_dataset(),
            analyses=_make_analyses(),
            dataset_spec=_make_dataset_spec(),
            available_variables=_AVAILABLE_VARS,
            run_id="test-run-1",
            seed=42,
        )

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(len(result.results), 2)
        for r in result.results:
            self.assertIsInstance(r, ResultSpec)
            self.assertIsNotNone(r.estimate)
            self.assertIsNotNone(r.p_value)
        self.assertTrue(result.script_hash.startswith("sha256:"))
        self.assertEqual(result.seed, 42)
        self.assertIn("python_version", result.environment)

    def test_results_are_reproducible(self) -> None:
        runner = SubprocessStatisticsRunner()

        run1 = runner.execute(
            plan=_make_plan(),
            dataset=_make_dataset(),
            analyses=_make_analyses(),
            dataset_spec=_make_dataset_spec(),
            available_variables=_AVAILABLE_VARS,
            run_id="test-run-2a",
            seed=42,
        )
        run2 = runner.execute(
            plan=_make_plan(),
            dataset=_make_dataset(),
            analyses=_make_analyses(),
            dataset_spec=_make_dataset_spec(),
            available_variables=_AVAILABLE_VARS,
            run_id="test-run-2b",
            seed=42,
        )

        self.assertEqual(run1.script_hash, run2.script_hash)
        for r1, r2 in zip(run1.results, run2.results, strict=True):
            self.assertEqual(r1.estimate, r2.estimate)
            self.assertEqual(r1.p_value, r2.p_value)
            self.assertEqual(r1.uncertainty_lower, r2.uncertainty_lower)

    def test_rejects_unlocked_plan(self) -> None:
        runner = SubprocessStatisticsRunner()
        unlocked_plan = AnalysisPlanSnapshot(
            version_id="plan-v1",
            content_hash="sha256:abc123",
            status="approved",
            variable_names=frozenset({"survival_months"}),
            model_specifications=("log_rank",),
            exclusion_criteria=(),
        )
        with self.assertRaises(PolicyViolation):
            runner.execute(
                plan=unlocked_plan,
                dataset=_make_dataset(),
                analyses=_make_analyses(),
                dataset_spec=_make_dataset_spec(),
                available_variables=_AVAILABLE_VARS,
                run_id="test-run-3",
            )

    def test_rejects_unlocked_dataset(self) -> None:
        runner = SubprocessStatisticsRunner()
        unlocked_ds = DatasetVersionSnapshot(
            version_id="ds-v1",
            content_hash="sha256:def456",
            status="draft",
        )
        with self.assertRaises(PolicyViolation):
            runner.execute(
                plan=_make_plan(),
                dataset=unlocked_ds,
                analyses=_make_analyses(),
                dataset_spec=_make_dataset_spec(),
                available_variables=_AVAILABLE_VARS,
                run_id="test-run-4",
            )

    def test_stdout_contains_analysis_output(self) -> None:
        runner = SubprocessStatisticsRunner()
        result = runner.execute(
            plan=_make_plan(),
            dataset=_make_dataset(),
            analyses=_make_analyses(),
            dataset_spec=_make_dataset_spec(),
            available_variables=_AVAILABLE_VARS,
            run_id="test-run-5",
            seed=42,
        )
        self.assertIn("primary_survival", result.stdout)
        self.assertIn("age_adjusted", result.stdout)

    def test_satisfies_statistics_runner_protocol(self) -> None:
        """SubprocessStatisticsRunner must satisfy the StatisticsRunner Protocol."""

        from vet_manuscript_lab.services.analysis.runner import (
            StatisticsRunner,
        )

        runner: StatisticsRunner = SubprocessStatisticsRunner()
        self.assertIsNotNone(runner)


# ---------------------------------------------------------------------------
# Gateway findings parser tests
# ---------------------------------------------------------------------------


class GatewayFindingsParserTests(unittest.TestCase):
    """Tests for _parse_gateway_findings."""

    def test_parses_valid_json_findings(self) -> None:
        text = json.dumps(
            {
                "findings": [
                    {
                        "category": "confounding",
                        "severity": "warning",
                        "rationale": "Age imbalance detected",
                        "recommendation": "Adjust for age",
                    },
                    {
                        "category": "missing_data",
                        "severity": "info",
                        "rationale": "Some missing values",
                        "recommendation": "Report missingness",
                    },
                ]
            }
        )
        findings = _parse_gateway_findings(text, "proj-1", "inv-1")

        self.assertEqual(len(findings), 2)
        self.assertEqual(findings[0]["category"], "confounding")
        self.assertEqual(findings[0]["severity"], "warning")
        self.assertIn("Age imbalance", findings[0]["rationale"])
        self.assertEqual(findings[1]["category"], "missing_data")

    def test_falls_back_on_non_json(self) -> None:
        text = "This is plain text review with no JSON structure."
        findings = _parse_gateway_findings(text, "proj-1", "inv-1")

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["category"], "other")
        self.assertIn("plain text", findings[0]["rationale"])

    def test_falls_back_on_empty_text(self) -> None:
        findings = _parse_gateway_findings("", "proj-1", "inv-1")

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["severity"], "info")

    def test_normalizes_invalid_severity(self) -> None:
        text = json.dumps(
            {
                "findings": [
                    {
                        "category": "confounding",
                        "severity": "CRITICAL",
                        "rationale": "test",
                    }
                ]
            }
        )
        findings = _parse_gateway_findings(text, "proj-1", "inv-1")

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["severity"], "info")

    def test_normalizes_unknown_category(self) -> None:
        text = json.dumps(
            {
                "findings": [
                    {
                        "category": "totally_unknown_thing",
                        "severity": "warning",
                        "rationale": "test",
                    }
                ]
            }
        )
        findings = _parse_gateway_findings(text, "proj-1", "inv-1")

        self.assertEqual(findings[0]["category"], "other")

    def test_handles_empty_findings_list(self) -> None:
        text = json.dumps({"findings": []})
        findings = _parse_gateway_findings(text, "proj-1", "inv-1")

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["category"], "other")

    def test_each_finding_has_unique_id(self) -> None:
        text = json.dumps(
            {
                "findings": [
                    {"category": "confounding", "severity": "info", "rationale": "1"},
                    {"category": "missing_data", "severity": "info", "rationale": "2"},
                    {"category": "sample_size", "severity": "info", "rationale": "3"},
                ]
            }
        )
        findings = _parse_gateway_findings(text, "proj-1", "inv-1")

        ids = {f["finding_id"] for f in findings}
        self.assertEqual(len(ids), 3)


class MethodologyCriticGatewayIntegrationTests(unittest.TestCase):
    """Integration test: methodology_critic_node with a real ModelGateway."""

    def test_gateway_produces_structured_findings(self) -> None:
        """When a gateway is supplied, the critic parses structured findings."""

        # Create a gateway with a custom provider that returns valid JSON
        class StructuredMockProvider:
            def invoke(
                self, model_id: str, prompt: str, *, max_tokens: int
            ) -> dict[str, Any]:
                return {
                    "text": json.dumps(
                        {
                            "findings": [
                                {
                                    "category": "confounding",
                                    "severity": "warning",
                                    "rationale": "Age is a confounder",
                                    "recommendation": "Adjust for age",
                                },
                                {
                                    "category": "sample_size",
                                    "severity": "info",
                                    "rationale": "Small sample",
                                    "recommendation": "Interpret with caution",
                                },
                            ]
                        }
                    ),
                    "input_tokens": 100,
                    "output_tokens": 50,
                }

        gateway = ModelGateway(provider=StructuredMockProvider())

        # Build minimal state with evidence_summary
        from vet_manuscript_lab.workflow.analysis_graph import (
            methodology_critic_node,
        )
        from vet_manuscript_lab.workflow.state import new_workflow_state

        state = new_workflow_state(
            project_id="proj-gateway-test",
            workflow_run_id="run-gateway",
            thread_id="thread-gateway",
            now="2026-01-01T00:00:00Z",
        )
        state["evidence_summary"] = {"total_evidence_items": 5}

        result = methodology_critic_node(state, gateway=gateway)

        findings = result.get("methodology_findings", [])
        self.assertEqual(len(findings), 2)
        self.assertEqual(findings[0]["category"], "confounding")
        self.assertEqual(findings[0]["severity"], "warning")
        artifact = result["artifacts"]["methodology_findings"]
        self.assertEqual(artifact["artifact_type"], "methodology_findings")
        self.assertTrue(artifact["content_hash"].startswith("sha256:"))


# ---------------------------------------------------------------------------
# i18n coverage tests
# ---------------------------------------------------------------------------


class I18nCoverageTests(unittest.TestCase):
    """Verify that analysis-stage i18n keys exist for all supported languages."""

    REQUIRED_KEYS: ClassVar[tuple[str, ...]] = (
        "section_methodology",
        "section_analysis_plan",
        "section_results",
        "section_usage",
        "col_category",
        "col_severity",
        "col_estimate",
        "col_p_value",
        "col_task_kind",
        "col_invocations",
        "col_cost_cents",
        "col_tokens",
        "label_total_invocations",
        "label_total_cost",
        "label_input_tokens",
        "label_output_tokens",
        "label_fallbacks",
        "label_failures",
        "gate.analysis_plan.title",
        "gate.analysis_plan.summary",
        "gate.results_interpretation.title",
        "gate.results_interpretation.summary",
        "info_no_methodology",
        "info_no_results",
    )

    def test_all_keys_have_en_and_zh(self) -> None:
        for key in self.REQUIRED_KEYS:
            self.assertIn(key, STRINGS, f"Missing i18n key: {key}")
            entry = STRINGS[key]
            self.assertIn("en", entry, f"Missing 'en' for key: {key}")
            self.assertIn("zh", entry, f"Missing 'zh' for key: {key}")

    def test_translate_fallback_for_unknown_key(self) -> None:
        self.assertEqual(translate("nonexistent.key"), "nonexistent.key")


if __name__ == "__main__":
    unittest.main()
