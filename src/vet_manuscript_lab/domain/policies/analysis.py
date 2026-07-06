"""Pure policy checks for the dataset and statistics aggregate.

These functions enforce the invariants described in domain_model.md section
("Dataset and statistics aggregate") and the Phase 3 exit criteria in
DEVELOPMENT.md.

Core invariants:

1. A runner may start only when the analysis plan is approved + locked and
   the dataset version is locked.
2. Plan-referenced variables must exist in the dataset dictionary.
3. Analyses not in the locked plan must be flagged ``exploratory``.
4. The execution phase is immutable: the runner cannot modify models,
   variables, or exclusion rules after the plan is locked.
5. A failed run must never produce an ``approved`` result.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from vet_manuscript_lab.domain.policies.foundation import PolicyViolation

# ---------------------------------------------------------------------------
# Snapshot dataclasses (mirror the DB record fields but are pure values)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DatasetVersionSnapshot:
    """Compact representation of a locked dataset version."""

    version_id: str
    content_hash: str
    status: str  # "draft", "locked", etc.


@dataclass(frozen=True, slots=True)
class AnalysisPlanSnapshot:
    """Compact representation of an analysis plan version."""

    version_id: str
    content_hash: str
    status: str  # "draft", "approved", "locked", etc.
    is_exploratory: bool = False
    variable_names: frozenset[str] = field(default_factory=frozenset)
    model_specifications: tuple[str, ...] = ()
    exclusion_criteria: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AnalysisRunSnapshot:
    """Compact representation of an analysis run outcome."""

    run_id: str
    plan_version_id: str
    plan_hash: str
    dataset_version_id: str
    dataset_hash: str
    exit_code: int
    status: str  # "running", "completed", "failed"
    has_approved_result: bool = False


@dataclass(frozen=True, slots=True)
class ExecutionInput:
    """Inputs checked before a statistics runner is allowed to start."""

    plan: AnalysisPlanSnapshot
    dataset: DatasetVersionSnapshot
    requested_variable_names: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True, slots=True)
class ExecutionContext:
    """Runtime context captured during execution for immutability checks."""

    plan_hash_at_start: str
    variable_names_at_start: frozenset[str]
    exclusion_criteria_at_start: tuple[str, ...]
    model_specifications_at_start: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AnalysisSpecSnapshot:
    """Specification of a single analysis to be executed."""

    name: str
    variable_names: frozenset[str]
    is_exploratory: bool = False
    is_in_locked_plan: bool = True


# ---------------------------------------------------------------------------
# Policy functions
# ---------------------------------------------------------------------------


def require_locked_dataset(dataset: DatasetVersionSnapshot) -> DatasetVersionSnapshot:
    """A runner may only consume a locked dataset version.

    Draft or unapproved datasets must not enter statistical execution
    because their content may still change.
    """

    if dataset.status != "locked":
        raise PolicyViolation(
            f"Dataset version {dataset.version_id} is not locked "
            f"(status='{dataset.status}')"
        )
    return dataset


def require_locked_plan(plan: AnalysisPlanSnapshot) -> AnalysisPlanSnapshot:
    """A runner may only execute an approved + locked analysis plan.

    This is the dual of the protocol-lock invariant: once locked, the
    endpoints, variables, models, and exclusion rules cannot change.
    """

    if plan.status != "locked":
        raise PolicyViolation(
            f"Analysis plan {plan.version_id} is not locked (status='{plan.status}')"
        )
    return plan


def require_plan_variables_in_dataset(
    spec: ExecutionInput,
    *,
    available_variables: frozenset[str],
) -> None:
    """Every variable referenced by the plan must exist in the dataset dictionary.

    A plan that references a non-existent variable is either stale or
    malformed and must be rejected before execution.
    """

    missing = spec.requested_variable_names - available_variables
    if missing:
        raise PolicyViolation(
            f"Plan references variables not in dataset dictionary: {sorted(missing)}"
        )


def require_exploratory_marking(spec: AnalysisSpecSnapshot) -> None:
    """Analyses not in the locked plan must be flagged exploratory.

    Exploratory results carry ``analysis_class=exploratory`` through writing
    and audit so they are never confused with prespecified findings.
    """

    if not spec.is_in_locked_plan and not spec.is_exploratory:
        raise PolicyViolation(
            f"Analysis '{spec.name}' is not in the locked plan but is not "
            f"marked as exploratory"
        )


def require_execution_immutability(
    start: ExecutionContext,
    *,
    plan_hash_now: str,
    variable_names_now: frozenset[str],
    exclusion_criteria_now: tuple[str, ...],
    model_specifications_now: tuple[str, ...],
) -> None:
    """The execution phase must not modify models, variables, or exclusions.

    This prevents a statistics Agent from silently broadening scope or
    changing the analysis after the plan is locked.
    """

    if plan_hash_now != start.plan_hash_at_start:
        raise PolicyViolation(
            "Plan hash changed during execution: the runner attempted to "
            "modify the analysis plan"
        )
    if variable_names_now != start.variable_names_at_start:
        added = variable_names_now - start.variable_names_at_start
        removed = start.variable_names_at_start - variable_names_now
        parts: list[str] = []
        if added:
            parts.append(f"added={sorted(added)}")
        if removed:
            parts.append(f"removed={sorted(removed)}")
        raise PolicyViolation(
            f"Variable set changed during execution ({', '.join(parts)})"
        )
    if exclusion_criteria_now != start.exclusion_criteria_at_start:
        raise PolicyViolation(
            "Exclusion criteria changed during execution: the runner "
            "attempted to modify eligibility"
        )
    if model_specifications_now != start.model_specifications_at_start:
        raise PolicyViolation(
            "Model specifications changed during execution: the runner "
            "attempted to modify the statistical model"
        )


def require_no_approved_result_on_failure(run: AnalysisRunSnapshot) -> None:
    """A failed run must never produce an approved result.

    The run may retain logs and partial output for debugging, but the
    result status must not be ``approved``.
    """

    if run.status == "failed" and run.has_approved_result:
        raise PolicyViolation(
            f"Run {run.run_id} failed but has an approved result — "
            f"this violates the failure-safety invariant"
        )
    if run.exit_code != 0 and run.has_approved_result:
        raise PolicyViolation(
            f"Run {run.run_id} exited with code {run.exit_code} but has "
            f"an approved result"
        )


def require_hash_match(
    *,
    expected_hash: str,
    actual_hash: str,
    subject: str,
) -> None:
    """A content hash mismatch invalidates the version and blocks downstream use.

    Used to verify that the locked plan/dataset has not been tampered with
    between locking and execution.
    """

    if expected_hash != actual_hash:
        raise PolicyViolation(
            f"Hash mismatch for {subject}: expected {expected_hash}, got {actual_hash}"
        )


__all__ = [
    "AnalysisPlanSnapshot",
    "AnalysisRunSnapshot",
    "AnalysisSpecSnapshot",
    "DatasetVersionSnapshot",
    "ExecutionContext",
    "ExecutionInput",
    "require_execution_immutability",
    "require_exploratory_marking",
    "require_hash_match",
    "require_locked_dataset",
    "require_locked_plan",
    "require_no_approved_result_on_failure",
    "require_plan_variables_in_dataset",
]
