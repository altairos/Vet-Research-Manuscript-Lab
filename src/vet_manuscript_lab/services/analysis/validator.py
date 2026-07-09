"""Analysis result validator (Phase F — statistical credibility).

Validates analysis results against dataset specifications and analysis
plans to catch common statistical methodology errors:

1. **Categorical-as-continuous**: A categorical or binary variable used
   as a continuous predictor/outcome in a model that assumes continuity
   (e.g. linear regression).
2. **Binary-outcome-with-linear-model**: A binary outcome variable used
   with a linear regression model instead of logistic regression.
3. **Sample-size inconsistency**: The dataset row count differs from
   the stated inclusion criteria sample size.

These checks run *after* the runner produces results and *before* the
results are approved for writing.  They complement the existing policy
checks (locked plan, locked dataset, exploratory marking) by catching
semantic statistical errors that structural policies cannot detect.
"""

from __future__ import annotations

from dataclasses import dataclass

from vet_manuscript_lab.domain.policies.foundation import PolicyViolation
from vet_manuscript_lab.services.analysis.types import (
    AnalysisClass,
    AnalysisSpec,
    DatasetSpec,
    ResultSpec,
    VariableRole,
    VariableType,
)

# Models that assume a continuous outcome/predictor
_CONTINUOUS_MODEL_TYPES = frozenset(
    {
        "linear",
        "linear_regression",
        "ols",
        "t_test",
        "anova",
    }
)

# Models appropriate for binary outcomes
_BINARY_OUTCOME_MODELS = frozenset(
    {
        "logistic",
        "logistic_regression",
        "logit",
        "firth",
        "probit",
    }
)


@dataclass(frozen=True, slots=True)
class ValidationFinding:
    """A single validation finding from the analysis result validator."""

    severity: str  # "error" or "warning"
    check: str
    message: str
    analysis_name: str | None = None
    variable_name: str | None = None


def validate_analysis_results(
    *,
    analyses: tuple[AnalysisSpec, ...],
    results: tuple[ResultSpec, ...],
    dataset: DatasetSpec,
    expected_sample_size: int | None = None,
) -> list[ValidationFinding]:
    """Validate analysis results against dataset and plan specs.

    Returns a list of findings.  ``severity="error"`` findings should
    block result approval; ``severity="warning"`` findings should be
    flagged for human review.

    Parameters
    ----------
    analyses
        The analysis specifications that were executed.
    results
        The results produced by the runner.
    dataset
        The dataset specification with variable dictionary.
    expected_sample_size
        Optional sample size from inclusion criteria.  If provided,
        the validator checks it against ``dataset.row_count``.
    """

    findings: list[ValidationFinding] = []
    var_map = {v.name: v for v in dataset.variables}

    for analysis in analyses:
        for var_name in analysis.variable_names:
            var = var_map.get(var_name)
            if var is None:
                continue

            # Check 1: Categorical variable treated as continuous
            if (
                analysis.model_type in _CONTINUOUS_MODEL_TYPES
                and var.var_type
                in (
                    VariableType.CATEGORICAL,
                    VariableType.BINARY,
                )
                and var.role != VariableRole.STRATA
            ):
                findings.append(
                    ValidationFinding(
                        severity="error",
                        check="categorical_as_continuous",
                        message=(
                            f"Variable '{var_name}' is {var.var_type.value} "
                            f"but model '{analysis.model_type}' assumes "
                            f"continuous data. Use a model appropriate "
                            f"for {var.var_type.value} variables."
                        ),
                        analysis_name=analysis.name,
                        variable_name=var_name,
                    )
                )

            # Check 2: Binary outcome with linear model
            if (
                var.role == VariableRole.OUTCOME
                and var.var_type == VariableType.BINARY
                and analysis.model_type in _CONTINUOUS_MODEL_TYPES
            ):
                findings.append(
                    ValidationFinding(
                        severity="error",
                        check="binary_outcome_linear_model",
                        message=(
                            f"Binary outcome '{var_name}' used with "
                            f"'{analysis.model_type}'. Use logistic "
                            f"regression or similar instead."
                        ),
                        analysis_name=analysis.name,
                        variable_name=var_name,
                    )
                )

    # Check 3: Sample size consistency
    if expected_sample_size is not None and dataset.row_count != expected_sample_size:
        findings.append(
            ValidationFinding(
                severity="warning",
                check="sample_size_mismatch",
                message=(
                    f"Dataset has {dataset.row_count} rows but "
                    f"inclusion criteria specify "
                    f"{expected_sample_size} cases."
                ),
            )
        )

    # Check 4: Exploratory results without explicit marking
    for result in results:
        if (
            result.analysis_class == AnalysisClass.EXPLORATORY
            and result.method
            and "exploratory" not in result.method.lower()
        ):
            findings.append(
                ValidationFinding(
                    severity="warning",
                    check="exploratory_not_marked",
                    message=(
                        f"Exploratory result for '{result.estimand}' "
                        f"does not have 'exploratory' in its method label. "
                        f"Consider marking it explicitly."
                    ),
                )
            )

    return findings


def require_no_blocking_findings(
    findings: list[ValidationFinding],
) -> None:
    """Raise ``PolicyViolation`` if any finding has severity='error'.

    Warning-level findings do not block; they are advisory.
    """

    errors = [f for f in findings if f.severity == "error"]
    if errors:
        messages = "; ".join(f"[{f.check}] {f.message}" for f in errors)
        raise PolicyViolation(
            f"Analysis result validation found {len(errors)} error(s): {messages}"
        )


__all__ = [
    "ValidationFinding",
    "require_no_blocking_findings",
    "validate_analysis_results",
]
