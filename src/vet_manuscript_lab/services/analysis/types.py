"""Core types for the analysis and statistics domain.

All enums and dataclasses are immutable (frozen) so analysis specs,
dataset definitions, and result records are tamper-evident after creation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class VariableType(StrEnum):
    """Statistical variable type.

    Determines which analyses are valid for a given variable and drives
    automatic dictionary validation.
    """

    CONTINUOUS = "continuous"
    BINARY = "binary"
    CATEGORICAL = "categorical"
    ORDINAL = "ordinal"
    COUNT = "count"
    SURVIVAL = "survival"  # time-to-event with censoring


class VariableRole(StrEnum):
    """Analytic role of a variable within a study.

    The role constrains which positions a variable may occupy in an
    analysis model (e.g. an outcome variable cannot also be an exposure).
    """

    OUTCOME = "outcome"
    EXPOSURE = "exposure"
    COVARIATE = "covariate"
    CONFOUNDER = "confounder"
    ID = "id"  # subject/case identifier (not for modelling)
    STRATA = "strata"


class AnalysisClass(StrEnum):
    """Classification of an analysis relative to the locked plan.

    ``primary`` and ``secondary`` analyses are prespecified in the locked
    analysis plan.  ``exploratory`` analyses are conducted outside the
    plan and must be clearly labelled in all downstream artifacts.
    """

    PRIMARY = "primary"
    SECONDARY = "secondary"
    EXPLORATORY = "exploratory"


class RunStatus(StrEnum):
    """Status of an analysis run."""

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class VariableSpec:
    """Single variable definition in a dataset dictionary.

    ``missing_code`` is the value used to represent missing data (e.g.
    ``"NA"``, ``-99``).  ``unit`` is required for continuous variables.
    """

    name: str
    var_type: VariableType
    role: VariableRole = VariableRole.COVARIATE
    unit: str | None = None
    missing_code: str | None = None
    description: str | None = None


@dataclass(frozen=True, slots=True)
class DatasetSpec:
    """Dataset identity and its variable dictionary.

    ``content_hash`` is the SHA-256 of the underlying data file so the
    version can be verified before execution.
    """

    dataset_id: str
    name: str
    row_count: int
    column_count: int
    content_hash: str
    uri: str
    media_type: str = "text/csv"
    version: int = 1
    variables: tuple[VariableSpec, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class AnalysisSpec:
    """Specification of a single statistical analysis.

    ``variable_names`` lists the variables consumed by this analysis.
    ``model_type`` is a short tag like ``"logistic"`` or ``"cox"``.
    ``exclusion_criteria`` documents eligibility restrictions specific
    to this analysis (not dataset-wide).
    """

    name: str
    estimand: str
    model_type: str
    variable_names: tuple[str, ...]
    analysis_class: AnalysisClass = AnalysisClass.PRIMARY
    exclusion_criteria: tuple[str, ...] = ()
    population: str | None = None


@dataclass(frozen=True, slots=True)
class ResultSpec:
    """Typed statistical result produced by a runner.

    Carries the estimate, uncertainty interval, p-value, and provenance
    (method and run id) so downstream claim/citation audits can verify
    exact numerical consistency.
    """

    estimand: str
    estimate: float | None
    estimate_units: str | None
    uncertainty_type: str | None
    uncertainty_lower: float | None
    uncertainty_upper: float | None
    p_value: float | None
    method: str | None
    population: str | None
    analysis_class: AnalysisClass


@dataclass(frozen=True, slots=True)
class AnalysisPlanContent:
    """Full content of an analysis plan version (for hashing).

    This is the structured payload that gets hashed into ``content_hash``
    so any change to models, variables, or exclusions is detectable.
    """

    version: int
    analyses: tuple[AnalysisSpec, ...]
    methodology_version_id: str | None = None
    protocol_version_id: str | None = None
    is_exploratory: bool = False


__all__ = [
    "AnalysisClass",
    "AnalysisPlanContent",
    "AnalysisSpec",
    "DatasetSpec",
    "ResultSpec",
    "RunStatus",
    "VariableRole",
    "VariableSpec",
    "VariableType",
]
