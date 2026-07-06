"""Unit tests for analysis domain policies (pure functions).

Covers normal path, invalid input, and policy-bypass attempts for each
of the 7 analysis policy functions.
"""

from __future__ import annotations

import unittest

from vet_manuscript_lab.domain.policies import (
    AnalysisPlanSnapshot,
    AnalysisRunSnapshot,
    AnalysisSpecSnapshot,
    DatasetVersionSnapshot,
    ExecutionContext,
    ExecutionInput,
    PolicyViolation,
    require_execution_immutability,
    require_exploratory_marking,
    require_hash_match,
    require_locked_dataset,
    require_locked_plan,
    require_no_approved_result_on_failure,
    require_plan_variables_in_dataset,
)


def _plan(
    *,
    status: str = "locked",
    variables: frozenset[str] | None = None,
) -> AnalysisPlanSnapshot:
    return AnalysisPlanSnapshot(
        version_id="plan-v1",
        content_hash="sha256:abc",
        status=status,
        variable_names=variables or frozenset({"x", "y"}),
        model_specifications=("logistic",),
        exclusion_criteria=("exclude_missing",),
    )


def _dataset(*, status: str = "locked") -> DatasetVersionSnapshot:
    return DatasetVersionSnapshot(
        version_id="ds-v1",
        content_hash="sha256:def",
        status=status,
    )


class RequireLockedDatasetTests(unittest.TestCase):
    def test_accepts_locked_dataset(self) -> None:
        ds = _dataset(status="locked")
        result = require_locked_dataset(ds)
        self.assertIs(result, ds)

    def test_rejects_draft_dataset(self) -> None:
        with self.assertRaises(PolicyViolation):
            require_locked_dataset(_dataset(status="draft"))

    def test_rejects_none_status(self) -> None:
        with self.assertRaises(PolicyViolation):
            require_locked_dataset(_dataset(status=""))


class RequireLockedPlanTests(unittest.TestCase):
    def test_accepts_locked_plan(self) -> None:
        plan = _plan(status="locked")
        result = require_locked_plan(plan)
        self.assertIs(result, plan)

    def test_rejects_draft_plan(self) -> None:
        with self.assertRaises(PolicyViolation):
            require_locked_plan(_plan(status="draft"))

    def test_rejects_approved_but_not_locked(self) -> None:
        with self.assertRaises(PolicyViolation):
            require_locked_plan(_plan(status="approved"))


class RequirePlanVariablesInDatasetTests(unittest.TestCase):
    def test_accepts_matching_variables(self) -> None:
        spec = ExecutionInput(
            plan=_plan(),
            dataset=_dataset(),
            requested_variable_names=frozenset({"x", "y"}),
        )
        require_plan_variables_in_dataset(
            spec, available_variables=frozenset({"x", "y", "z"})
        )

    def test_rejects_missing_variable(self) -> None:
        spec = ExecutionInput(
            plan=_plan(),
            dataset=_dataset(),
            requested_variable_names=frozenset({"x", "w"}),
        )
        with self.assertRaises(PolicyViolation) as ctx:
            require_plan_variables_in_dataset(
                spec, available_variables=frozenset({"x", "y"})
            )
        self.assertIn("w", str(ctx.exception))

    def test_accepts_empty_request(self) -> None:
        spec = ExecutionInput(
            plan=_plan(),
            dataset=_dataset(),
            requested_variable_names=frozenset(),
        )
        require_plan_variables_in_dataset(spec, available_variables=frozenset())


class RequireExploratoryMarkingTests(unittest.TestCase):
    def test_accepts_in_plan_non_exploratory(self) -> None:
        spec = AnalysisSpecSnapshot(
            name="primary_analysis",
            variable_names=frozenset({"x"}),
            is_exploratory=False,
            is_in_locked_plan=True,
        )
        require_exploratory_marking(spec)

    def test_accepts_not_in_plan_exploratory(self) -> None:
        spec = AnalysisSpecSnapshot(
            name="post_hoc",
            variable_names=frozenset({"x"}),
            is_exploratory=True,
            is_in_locked_plan=False,
        )
        require_exploratory_marking(spec)

    def test_rejects_not_in_plan_not_exploratory(self) -> None:
        spec = AnalysisSpecSnapshot(
            name="sneaky_post_hoc",
            variable_names=frozenset({"x"}),
            is_exploratory=False,
            is_in_locked_plan=False,
        )
        with self.assertRaises(PolicyViolation) as ctx:
            require_exploratory_marking(spec)
        self.assertIn("exploratory", str(ctx.exception))


class RequireExecutionImmutabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ctx = ExecutionContext(
            plan_hash_at_start="sha256:abc",
            variable_names_at_start=frozenset({"x", "y"}),
            exclusion_criteria_at_start=("exclude_missing",),
            model_specifications_at_start=("logistic",),
        )

    def test_accepts_unchanged_context(self) -> None:
        require_execution_immutability(
            self.ctx,
            plan_hash_now="sha256:abc",
            variable_names_now=frozenset({"x", "y"}),
            exclusion_criteria_now=("exclude_missing",),
            model_specifications_now=("logistic",),
        )

    def test_rejects_plan_hash_change(self) -> None:
        with self.assertRaises(PolicyViolation) as ctx:
            require_execution_immutability(
                self.ctx,
                plan_hash_now="sha256:xyz",
                variable_names_now=frozenset({"x", "y"}),
                exclusion_criteria_now=("exclude_missing",),
                model_specifications_now=("logistic",),
            )
        self.assertIn("Plan hash changed", str(ctx.exception))

    def test_rejects_variable_addition(self) -> None:
        with self.assertRaises(PolicyViolation) as ctx:
            require_execution_immutability(
                self.ctx,
                plan_hash_now="sha256:abc",
                variable_names_now=frozenset({"x", "y", "z"}),
                exclusion_criteria_now=("exclude_missing",),
                model_specifications_now=("logistic",),
            )
        self.assertIn("Variable set changed", str(ctx.exception))

    def test_rejects_exclusion_change(self) -> None:
        with self.assertRaises(PolicyViolation) as ctx:
            require_execution_immutability(
                self.ctx,
                plan_hash_now="sha256:abc",
                variable_names_now=frozenset({"x", "y"}),
                exclusion_criteria_now=("different_criteria",),
                model_specifications_now=("logistic",),
            )
        self.assertIn("Exclusion criteria", str(ctx.exception))

    def test_rejects_model_change(self) -> None:
        with self.assertRaises(PolicyViolation) as ctx:
            require_execution_immutability(
                self.ctx,
                plan_hash_now="sha256:abc",
                variable_names_now=frozenset({"x", "y"}),
                exclusion_criteria_now=("exclude_missing",),
                model_specifications_now=("cox",),
            )
        self.assertIn("Model specifications", str(ctx.exception))


class RequireNoApprovedResultOnFailureTests(unittest.TestCase):
    def test_accepts_success_with_result(self) -> None:
        run = AnalysisRunSnapshot(
            run_id="run-1",
            plan_version_id="plan-v1",
            plan_hash="sha256:abc",
            dataset_version_id="ds-v1",
            dataset_hash="sha256:def",
            exit_code=0,
            status="completed",
            has_approved_result=True,
        )
        require_no_approved_result_on_failure(run)

    def test_accepts_failure_without_result(self) -> None:
        run = AnalysisRunSnapshot(
            run_id="run-1",
            plan_version_id="plan-v1",
            plan_hash="sha256:abc",
            dataset_version_id="ds-v1",
            dataset_hash="sha256:def",
            exit_code=1,
            status="failed",
            has_approved_result=False,
        )
        require_no_approved_result_on_failure(run)

    def test_rejects_failure_with_approved_result(self) -> None:
        run = AnalysisRunSnapshot(
            run_id="run-1",
            plan_version_id="plan-v1",
            plan_hash="sha256:abc",
            dataset_version_id="ds-v1",
            dataset_hash="sha256:def",
            exit_code=1,
            status="failed",
            has_approved_result=True,
        )
        with self.assertRaises(PolicyViolation):
            require_no_approved_result_on_failure(run)

    def test_rejects_nonzero_exit_with_approved_result(self) -> None:
        run = AnalysisRunSnapshot(
            run_id="run-1",
            plan_version_id="plan-v1",
            plan_hash="sha256:abc",
            dataset_version_id="ds-v1",
            dataset_hash="sha256:def",
            exit_code=2,
            status="completed",
            has_approved_result=True,
        )
        with self.assertRaises(PolicyViolation):
            require_no_approved_result_on_failure(run)


class RequireHashMatchTests(unittest.TestCase):
    def test_accepts_matching_hash(self) -> None:
        require_hash_match(
            expected_hash="sha256:abc",
            actual_hash="sha256:abc",
            subject="plan",
        )

    def test_rejects_mismatched_hash(self) -> None:
        with self.assertRaises(PolicyViolation) as ctx:
            require_hash_match(
                expected_hash="sha256:abc",
                actual_hash="sha256:xyz",
                subject="plan",
            )
        self.assertIn("Hash mismatch", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
