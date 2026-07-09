"""Tests for Phase F — Statistical credibility hardening.

Covers:
- F1: analysis_result_validator (categorical-as-continuous,
  binary-outcome-linear-model, sample-size mismatch,
  exploratory-not-marked)
- F2: requirements_hash in RunResult (environment locking)
- F3: exploratory-in-abstract warnings in claim_audit
"""

from __future__ import annotations

import unittest

from vet_manuscript_lab.domain.policies import PolicyViolation
from vet_manuscript_lab.services.analysis import (
    AnalysisClass,
    AnalysisSpec,
    DatasetSpec,
    MockStatisticsRunner,
    ResultSpec,
    ValidationFinding,
    VariableRole,
    VariableSpec,
    VariableType,
    require_no_blocking_findings,
    validate_analysis_results,
)
from vet_manuscript_lab.workflow.state import new_workflow_state

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def _make_dataset(
    *,
    variables: tuple[VariableSpec, ...] | None = None,
    row_count: int = 100,
) -> DatasetSpec:
    if variables is None:
        variables = (
            VariableSpec(
                name="age",
                var_type=VariableType.CONTINUOUS,
                role=VariableRole.COVARIATE,
                unit="years",
            ),
            VariableSpec(
                name="outcome",
                var_type=VariableType.BINARY,
                role=VariableRole.OUTCOME,
            ),
            VariableSpec(
                name="treatment",
                var_type=VariableType.BINARY,
                role=VariableRole.EXPOSURE,
            ),
            VariableSpec(
                name="breed",
                var_type=VariableType.CATEGORICAL,
                role=VariableRole.COVARIATE,
            ),
        )
    return DatasetSpec(
        dataset_id="ds-1",
        name="test_dataset",
        row_count=row_count,
        column_count=len(variables),
        content_hash="sha256:abc123",
        uri="file:///test.csv",
        variables=variables,
    )


# ──────────────────────────────────────────────────────────────────────────────
# F1: validate_analysis_results — categorical-as-continuous
# ──────────────────────────────────────────────────────────────────────────────


class CategoricalAsContinuousTests(unittest.TestCase):
    def test_continuous_variable_with_linear_model_passes(self) -> None:
        dataset = _make_dataset()
        analyses = (
            AnalysisSpec(
                name="linear_age",
                estimand="mean_age",
                model_type="linear_regression",
                variable_names=("age",),
            ),
        )
        results: tuple[ResultSpec, ...] = ()
        findings = validate_analysis_results(
            analyses=analyses,
            results=results,
            dataset=dataset,
        )
        cat_findings = [f for f in findings if f.check == "categorical_as_continuous"]
        self.assertEqual(len(cat_findings), 0)

    def test_categorical_variable_with_linear_model_fails(self) -> None:
        dataset = _make_dataset()
        analyses = (
            AnalysisSpec(
                name="linear_breed",
                estimand="breed_effect",
                model_type="linear_regression",
                variable_names=("breed",),
            ),
        )
        findings = validate_analysis_results(
            analyses=analyses,
            results=(),
            dataset=dataset,
        )
        cat_findings = [f for f in findings if f.check == "categorical_as_continuous"]
        self.assertEqual(len(cat_findings), 1)
        self.assertEqual(cat_findings[0].severity, "error")
        self.assertEqual(cat_findings[0].variable_name, "breed")

    def test_binary_variable_with_t_test_fails(self) -> None:
        dataset = _make_dataset()
        analyses = (
            AnalysisSpec(
                name="ttest_treatment",
                estimand="treatment_effect",
                model_type="t_test",
                variable_names=("treatment",),
            ),
        )
        findings = validate_analysis_results(
            analyses=analyses,
            results=(),
            dataset=dataset,
        )
        cat_findings = [f for f in findings if f.check == "categorical_as_continuous"]
        self.assertEqual(len(cat_findings), 1)


# ──────────────────────────────────────────────────────────────────────────────
# F1: validate_analysis_results — binary-outcome-linear-model
# ──────────────────────────────────────────────────────────────────────────────


class BinaryOutcomeLinearModelTests(unittest.TestCase):
    def test_binary_outcome_with_linear_regression_fails(self) -> None:
        dataset = _make_dataset()
        analyses = (
            AnalysisSpec(
                name="linear_outcome",
                estimand="outcome_effect",
                model_type="linear_regression",
                variable_names=("outcome", "age"),
            ),
        )
        findings = validate_analysis_results(
            analyses=analyses,
            results=(),
            dataset=dataset,
        )
        bo_findings = [f for f in findings if f.check == "binary_outcome_linear_model"]
        self.assertEqual(len(bo_findings), 1)
        self.assertEqual(bo_findings[0].severity, "error")
        self.assertIn("logistic", bo_findings[0].message.lower())

    def test_binary_outcome_with_logistic_regression_passes(self) -> None:
        dataset = _make_dataset()
        analyses = (
            AnalysisSpec(
                name="logistic_outcome",
                estimand="outcome_effect",
                model_type="logistic",
                variable_names=("outcome", "age"),
            ),
        )
        findings = validate_analysis_results(
            analyses=analyses,
            results=(),
            dataset=dataset,
        )
        bo_findings = [f for f in findings if f.check == "binary_outcome_linear_model"]
        self.assertEqual(len(bo_findings), 0)

    def test_continuous_outcome_with_linear_passes(self) -> None:
        variables = (
            VariableSpec(
                name="survival_time",
                var_type=VariableType.CONTINUOUS,
                role=VariableRole.OUTCOME,
                unit="days",
            ),
            VariableSpec(
                name="age",
                var_type=VariableType.CONTINUOUS,
                role=VariableRole.COVARIATE,
                unit="years",
            ),
        )
        dataset = _make_dataset(variables=variables)
        analyses = (
            AnalysisSpec(
                name="linear_survival",
                estimand="survival_effect",
                model_type="linear_regression",
                variable_names=("survival_time", "age"),
            ),
        )
        findings = validate_analysis_results(
            analyses=analyses,
            results=(),
            dataset=dataset,
        )
        bo_findings = [f for f in findings if f.check == "binary_outcome_linear_model"]
        self.assertEqual(len(bo_findings), 0)


# ──────────────────────────────────────────────────────────────────────────────
# F1: validate_analysis_results — sample-size mismatch
# ──────────────────────────────────────────────────────────────────────────────


class SampleSizeMismatchTests(unittest.TestCase):
    def test_matching_sample_size_no_finding(self) -> None:
        dataset = _make_dataset(row_count=100)
        findings = validate_analysis_results(
            analyses=(),
            results=(),
            dataset=dataset,
            expected_sample_size=100,
        )
        ss_findings = [f for f in findings if f.check == "sample_size_mismatch"]
        self.assertEqual(len(ss_findings), 0)

    def test_mismatched_sample_size_warns(self) -> None:
        dataset = _make_dataset(row_count=50)
        findings = validate_analysis_results(
            analyses=(),
            results=(),
            dataset=dataset,
            expected_sample_size=100,
        )
        ss_findings = [f for f in findings if f.check == "sample_size_mismatch"]
        self.assertEqual(len(ss_findings), 1)
        self.assertEqual(ss_findings[0].severity, "warning")

    def test_no_expected_size_skips_check(self) -> None:
        dataset = _make_dataset(row_count=50)
        findings = validate_analysis_results(
            analyses=(),
            results=(),
            dataset=dataset,
        )
        ss_findings = [f for f in findings if f.check == "sample_size_mismatch"]
        self.assertEqual(len(ss_findings), 0)


# ──────────────────────────────────────────────────────────────────────────────
# F1: validate_analysis_results — exploratory not marked
# ──────────────────────────────────────────────────────────────────────────────


class ExploratoryNotMarkedTests(unittest.TestCase):
    def test_exploratory_result_without_marking_warns(self) -> None:
        results = (
            ResultSpec(
                estimand="exploratory_outcome",
                estimate=1.5,
                estimate_units=None,
                uncertainty_type="95% CI",
                uncertainty_lower=0.8,
                uncertainty_upper=2.2,
                p_value=0.03,
                method="cox",  # no "exploratory" in method
                population="all",
                analysis_class=AnalysisClass.EXPLORATORY,
            ),
        )
        findings = validate_analysis_results(
            analyses=(),
            results=results,
            dataset=_make_dataset(),
        )
        em_findings = [f for f in findings if f.check == "exploratory_not_marked"]
        self.assertEqual(len(em_findings), 1)
        self.assertEqual(em_findings[0].severity, "warning")

    def test_exploratory_result_with_marking_passes(self) -> None:
        results = (
            ResultSpec(
                estimand="exploratory_outcome",
                estimate=1.5,
                estimate_units=None,
                uncertainty_type="95% CI",
                uncertainty_lower=0.8,
                uncertainty_upper=2.2,
                p_value=0.03,
                method="exploratory-cox",
                population="all",
                analysis_class=AnalysisClass.EXPLORATORY,
            ),
        )
        findings = validate_analysis_results(
            analyses=(),
            results=results,
            dataset=_make_dataset(),
        )
        em_findings = [f for f in findings if f.check == "exploratory_not_marked"]
        self.assertEqual(len(em_findings), 0)


# ──────────────────────────────────────────────────────────────────────────────
# F1: require_no_blocking_findings
# ──────────────────────────────────────────────────────────────────────────────


class RequireNoBlockingFindingsTests(unittest.TestCase):
    def test_no_findings_passes(self) -> None:
        require_no_blocking_findings([])

    def test_only_warnings_passes(self) -> None:
        findings = [
            ValidationFinding(
                severity="warning",
                check="sample_size_mismatch",
                message="Mismatch",
            )
        ]
        require_no_blocking_findings(findings)

    def test_error_finding_raises(self) -> None:
        findings = [
            ValidationFinding(
                severity="error",
                check="categorical_as_continuous",
                message="Bad model",
                analysis_name="a1",
                variable_name="breed",
            )
        ]
        with self.assertRaises(PolicyViolation) as ctx:
            require_no_blocking_findings(findings)
        self.assertIn("categorical_as_continuous", str(ctx.exception))

    def test_mixed_findings_only_errors_block(self) -> None:
        findings = [
            ValidationFinding(
                severity="warning",
                check="sample_size_mismatch",
                message="Mismatch",
            ),
            ValidationFinding(
                severity="error",
                check="binary_outcome_linear_model",
                message="Use logistic",
            ),
        ]
        with self.assertRaises(PolicyViolation):
            require_no_blocking_findings(findings)


# ──────────────────────────────────────────────────────────────────────────────
# F2: requirements_hash in RunResult
# ──────────────────────────────────────────────────────────────────────────────


class RequirementsHashTests(unittest.TestCase):
    def test_mock_runner_produces_requirements_hash(self) -> None:
        """RunResult should have a non-empty requirements_hash."""
        from vet_manuscript_lab.domain.policies import (
            AnalysisPlanSnapshot,
            DatasetVersionSnapshot,
        )

        plan = AnalysisPlanSnapshot(
            version_id="plan-v1",
            content_hash="sha256:plan123",
            status="locked",
            variable_names=frozenset({"age", "outcome"}),
        )
        dataset = DatasetVersionSnapshot(
            version_id="ds-v1",
            content_hash="sha256:ds123",
            status="locked",
        )
        dataset_spec = _make_dataset()
        analyses = (
            AnalysisSpec(
                name="primary",
                estimand="outcome_effect",
                model_type="logistic",
                variable_names=("age", "outcome"),
            ),
        )

        runner = MockStatisticsRunner()
        result = runner.execute(
            plan=plan,
            dataset=dataset,
            analyses=analyses,
            dataset_spec=dataset_spec,
            available_variables=frozenset({"age", "outcome"}),
            run_id="run-1",
            seed=42,
        )

        self.assertTrue(result.requirements_hash)
        self.assertTrue(result.requirements_hash.startswith("sha256:"))

    def test_requirements_hash_deterministic(self) -> None:
        """Same packages → same hash."""
        from vet_manuscript_lab.services.analysis.runner import (
            _compute_requirements_hash,
        )

        h1 = _compute_requirements_hash({"a": "1.0", "b": "2.0"})
        h2 = _compute_requirements_hash({"a": "1.0", "b": "2.0"})
        self.assertEqual(h1, h2)

    def test_different_packages_different_hash(self) -> None:
        from vet_manuscript_lab.services.analysis.runner import (
            _compute_requirements_hash,
        )

        h1 = _compute_requirements_hash({"a": "1.0"})
        h2 = _compute_requirements_hash({"a": "2.0"})
        self.assertNotEqual(h1, h2)

    def test_key_order_does_not_matter(self) -> None:
        """JSON serialization with sort_keys ensures order-independence."""
        from vet_manuscript_lab.services.analysis.runner import (
            _compute_requirements_hash,
        )

        h1 = _compute_requirements_hash({"a": "1.0", "b": "2.0"})
        h2 = _compute_requirements_hash({"b": "2.0", "a": "1.0"})
        self.assertEqual(h1, h2)


# ──────────────────────────────────────────────────────────────────────────────
# F3: exploratory-in-abstract warning in claim_audit
# ──────────────────────────────────────────────────────────────────────────────


class ExploratoryInAbstractTests(unittest.TestCase):
    def test_exploratory_in_abstract_generates_warning(self) -> None:
        from vet_manuscript_lab.workflow.writing_graph import claim_audit_node

        state = {
            **new_workflow_state(
                project_id="p1",
                workflow_run_id="r1",
                thread_id="t1",
                now="2026-07-09T00:00:00Z",
            ),
            "claim_drafts": [
                {
                    "claim_id": "c-expl",
                    "claim_type": "statistical",
                    "text": "The estimate was 1.5.",
                    "certainty": "high",
                    "section_id": "sec-abstract",
                    "referenced_numbers": [1.5],
                }
            ],
            "support_drafts": [
                {
                    "claim_id": "c-expl",
                    "support_type": "statistical_result",
                    "source_id": "r-exploratory",
                    "relation": "supports",
                    "audit_status": "verified",
                }
            ],
            "result_drafts": [
                {
                    "result_id": "r-exploratory",
                    "estimand": "test",
                    "estimate": 1.5,
                    "p_value": 0.03,
                    "exploratory": True,
                }
            ],
            "artifacts": {},
        }
        result = claim_audit_node(state)
        audit = result["artifacts"]["claim_audit"]
        warnings = audit.get("warnings", [])
        self.assertGreater(len(warnings), 0)
        self.assertEqual(warnings[0]["check"], "exploratory_in_abstract")

    def test_exploratory_in_results_section_no_warning(self) -> None:
        from vet_manuscript_lab.workflow.writing_graph import claim_audit_node

        state = {
            **new_workflow_state(
                project_id="p1",
                workflow_run_id="r1",
                thread_id="t1",
                now="2026-07-09T00:00:00Z",
            ),
            "claim_drafts": [
                {
                    "claim_id": "c-expl",
                    "claim_type": "statistical",
                    "text": "The estimate was 1.5.",
                    "certainty": "high",
                    "section_id": "sec-results",  # Not abstract
                    "referenced_numbers": [1.5],
                }
            ],
            "support_drafts": [
                {
                    "claim_id": "c-expl",
                    "support_type": "statistical_result",
                    "source_id": "r-exploratory",
                    "relation": "supports",
                    "audit_status": "verified",
                }
            ],
            "result_drafts": [
                {
                    "result_id": "r-exploratory",
                    "estimand": "test",
                    "estimate": 1.5,
                    "p_value": 0.03,
                    "exploratory": True,
                }
            ],
            "artifacts": {},
        }
        result = claim_audit_node(state)
        audit = result["artifacts"]["claim_audit"]
        warnings = audit.get("warnings", [])
        expl_warnings = [w for w in warnings if w["check"] == "exploratory_in_abstract"]
        self.assertEqual(len(expl_warnings), 0)

    def test_non_exploratory_in_abstract_no_warning(self) -> None:
        from vet_manuscript_lab.workflow.writing_graph import claim_audit_node

        state = {
            **new_workflow_state(
                project_id="p1",
                workflow_run_id="r1",
                thread_id="t1",
                now="2026-07-09T00:00:00Z",
            ),
            "claim_drafts": [
                {
                    "claim_id": "c-primary",
                    "claim_type": "statistical",
                    "text": "The estimate was 1.5.",
                    "certainty": "high",
                    "section_id": "sec-abstract",
                    "referenced_numbers": [1.5],
                }
            ],
            "support_drafts": [
                {
                    "claim_id": "c-primary",
                    "support_type": "statistical_result",
                    "source_id": "r-primary",  # Not exploratory
                    "relation": "supports",
                    "audit_status": "verified",
                }
            ],
            "result_drafts": [
                {
                    "result_id": "r-primary",
                    "estimand": "test",
                    "estimate": 1.5,
                    "p_value": 0.03,
                    # No exploratory flag
                }
            ],
            "artifacts": {},
        }
        result = claim_audit_node(state)
        audit = result["artifacts"]["claim_audit"]
        warnings = audit.get("warnings", [])
        expl_warnings = [w for w in warnings if w["check"] == "exploratory_in_abstract"]
        self.assertEqual(len(expl_warnings), 0)

    def test_warnings_do_not_fail_audit(self) -> None:
        """Warnings should not change audit status to failed."""
        from vet_manuscript_lab.workflow.writing_graph import claim_audit_node

        state = {
            **new_workflow_state(
                project_id="p1",
                workflow_run_id="r1",
                thread_id="t1",
                now="2026-07-09T00:00:00Z",
            ),
            "claim_drafts": [
                {
                    "claim_id": "c-expl",
                    "claim_type": "statistical",
                    "text": "The estimate was 1.5.",
                    "certainty": "high",
                    "section_id": "sec-abstract",
                    "referenced_numbers": [1.5],
                }
            ],
            "support_drafts": [
                {
                    "claim_id": "c-expl",
                    "support_type": "statistical_result",
                    "source_id": "r-exploratory",
                    "relation": "supports",
                    "audit_status": "verified",
                }
            ],
            "result_drafts": [
                {
                    "result_id": "r-exploratory",
                    "estimand": "test",
                    "estimate": 1.5,
                    "p_value": 0.03,
                    "exploratory": True,
                }
            ],
            "artifacts": {},
        }
        result = claim_audit_node(state)
        audit = result["artifacts"]["claim_audit"]
        # Warnings present but audit still passes
        self.assertEqual(audit["status"], "audit_passed")
        self.assertGreater(audit.get("warning_count", 0), 0)


if __name__ == "__main__":
    unittest.main()
