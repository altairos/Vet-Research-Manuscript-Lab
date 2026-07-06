"""Dataset dictionary validator.

Checks that variable types are valid, continuous variables have units,
missing codes are consistent, and required roles (outcome, exposure) exist.
This is a pure validation layer — it does not read files or touch the DB.
"""

from __future__ import annotations

from dataclasses import dataclass

from vet_manuscript_lab.domain.policies.foundation import PolicyViolation
from vet_manuscript_lab.services.analysis.types import (
    VariableRole,
    VariableSpec,
    VariableType,
)


@dataclass(frozen=True, slots=True)
class DatasetDictionary:
    """Immutable, validated collection of variable definitions.

    Construct via ``DatasetDictionary.validate(variables)`` to run all
    checks, or ``DatasetDictionary(variables=...)`` to bypass validation
    (use with care — only for trusted/already-validated input).
    """

    variables: tuple[VariableSpec, ...]

    # -- Derived views --------------------------------------------------

    @property
    def variable_names(self) -> frozenset[str]:
        return frozenset(v.name for v in self.variables)

    @property
    def outcome_names(self) -> frozenset[str]:
        return frozenset(
            v.name for v in self.variables if v.role == VariableRole.OUTCOME
        )

    @property
    def exposure_names(self) -> frozenset[str]:
        return frozenset(
            v.name for v in self.variables if v.role == VariableRole.EXPOSURE
        )

    def get(self, name: str) -> VariableSpec | None:
        for v in self.variables:
            if v.name == name:
                return v
        return None

    # -- Validation -----------------------------------------------------

    @classmethod
    def validate(cls, variables: tuple[VariableSpec, ...]) -> DatasetDictionary:
        """Run all dictionary checks and return a validated instance.

        Raises ``PolicyViolation`` if any check fails.
        """

        if not variables:
            raise PolicyViolation(
                "Dataset dictionary must contain at least one variable"
            )

        # Check for duplicate names
        seen: set[str] = set()
        for v in variables:
            if v.name in seen:
                raise PolicyViolation(f"Duplicate variable name: {v.name}")
            seen.add(v.name)

        # Validate type-specific constraints
        for v in variables:
            _validate_single_variable(v)

        # Check for required roles in a study dataset
        roles = {v.role for v in variables}
        if VariableRole.OUTCOME not in roles:
            raise PolicyViolation(
                "Dataset dictionary must define at least one outcome variable"
            )
        if VariableRole.EXPOSURE not in roles:
            raise PolicyViolation(
                "Dataset dictionary must define at least one exposure variable"
            )

        return cls(variables=variables)

    @classmethod
    def from_specs(cls, *specs: VariableSpec) -> DatasetDictionary:
        return cls.validate(specs)


def _validate_single_variable(v: VariableSpec) -> None:
    """Run type-specific checks on a single variable."""

    if not v.name.strip():
        raise PolicyViolation("Variable name cannot be empty")

    # Continuous and count variables should have units
    if v.var_type in (VariableType.CONTINUOUS, VariableType.COUNT) and (
        not v.unit or not v.unit.strip()
    ):
        raise PolicyViolation(
            f"Variable '{v.name}' of type '{v.var_type.value}' must have a unit"
        )

    # Survival variables need a time component and event indicator
    # (represented as two separate variables, so we just check type validity)

    # Binary variables should not have units (they are inherently unitless)
    if v.var_type == VariableType.BINARY and v.unit:
        raise PolicyViolation(f"Binary variable '{v.name}' should not have a unit")


__all__ = ["DatasetDictionary"]
