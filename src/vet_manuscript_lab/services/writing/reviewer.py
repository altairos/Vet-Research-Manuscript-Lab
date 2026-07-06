"""Reviewer service: scans manuscript claims and produces structured findings.

The ``Reviewer`` Protocol defines the contract; ``MockReviewer`` provides
a deterministic implementation that applies the same checks as the
policy layer to produce actionable findings.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from vet_manuscript_lab.domain.policies import (
    ClaimSnapshot,
    StatisticalResultSnapshot,
    require_factual_claim_has_support,
    require_no_causal_overreach,
    require_numeric_consistency,
)
from vet_manuscript_lab.domain.policies.foundation import PolicyViolation
from vet_manuscript_lab.services.writing.types import (
    FindingCategory,
    FindingSeverity,
    ReviewFindingDraft,
)


@dataclass(frozen=True, slots=True)
class ReviewInput:
    """Inputs provided to the reviewer."""

    manuscript_hash: str
    claims: tuple[ClaimDraftData, ...]
    results: tuple[dict[str, Any], ...]


@dataclass(frozen=True, slots=True)
class ClaimDraftData:
    """Claim data extracted for review (plain dict-like)."""

    claim_id: str
    claim_type: str
    text: str
    certainty: str
    has_support: bool
    support_count: int
    referenced_numbers: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class ReviewOutput:
    """Output from the reviewer."""

    findings: tuple[ReviewFindingDraft, ...]
    manuscript_hash_unchanged: bool


class Reviewer(Protocol):
    """Protocol for review backends."""

    def review(self, inputs: ReviewInput) -> ReviewOutput: ...


class MockReviewer:
    """Deterministic mock reviewer for offline development.

    Applies the same policy checks used in claim_audit to produce
    structured findings. Does not modify the manuscript.
    """

    def review(self, inputs: ReviewInput) -> ReviewOutput:
        findings: list[ReviewFindingDraft] = []

        # Build statistical result snapshots for numeric consistency
        result_snaps = tuple(
            StatisticalResultSnapshot(
                result_id=r.get("result_id", ""),
                estimate=r.get("estimate"),
                p_value=r.get("p_value"),
            )
            for r in inputs.results
        )

        for cd in inputs.claims:
            snap = ClaimSnapshot(
                claim_id=cd.claim_id,
                claim_type=cd.claim_type,
                text=cd.text,
                certainty=cd.certainty,
                has_support=cd.has_support,
                support_count=cd.support_count,
                referenced_numbers=cd.referenced_numbers,
            )

            # Check: factual/statistical claim without support
            try:
                require_factual_claim_has_support(snap)
            except PolicyViolation as exc:
                findings.append(
                    ReviewFindingDraft(
                        finding_id=f"finding-{cd.claim_id}-unsupported",
                        category=FindingCategory.UNSUPPORTED_CLAIM.value,
                        severity=FindingSeverity.ERROR.value,
                        location=cd.claim_id,
                        rationale=str(exc),
                        recommendation=(
                            "Add a ClaimSupport link to an EvidenceItem "
                            "or StatisticalResult."
                        ),
                    )
                )

            # Check: causal overreach
            try:
                require_no_causal_overreach(snap)
            except PolicyViolation as exc:
                findings.append(
                    ReviewFindingDraft(
                        finding_id=f"finding-{cd.claim_id}-causal",
                        category=FindingCategory.CAUSAL_OVERREACH.value,
                        severity=FindingSeverity.ERROR.value,
                        location=cd.claim_id,
                        rationale=str(exc),
                        recommendation=(
                            "Use associative language: 'associated', "
                            "'correlated', or hedge with 'may'."
                        ),
                    )
                )

        # Check: numeric consistency across all claims
        claim_snaps = tuple(
            ClaimSnapshot(
                claim_id=cd.claim_id,
                claim_type=cd.claim_type,
                text=cd.text,
                certainty=cd.certainty,
                has_support=cd.has_support,
                support_count=cd.support_count,
                referenced_numbers=cd.referenced_numbers,
            )
            for cd in inputs.claims
        )
        try:
            require_numeric_consistency(claim_snaps, results=result_snaps)
        except PolicyViolation as exc:
            findings.append(
                ReviewFindingDraft(
                    finding_id="finding-numeric-mismatch",
                    category=FindingCategory.NUMERIC_MISMATCH.value,
                    severity=FindingSeverity.ERROR.value,
                    rationale=str(exc),
                    recommendation=(
                        "Ensure all numbers in claims match the official "
                        "statistical results."
                    ),
                )
            )

        return ReviewOutput(
            findings=tuple(findings),
            manuscript_hash_unchanged=True,
        )


__all__ = [
    "ClaimDraftData",
    "MockReviewer",
    "ReviewInput",
    "ReviewOutput",
    "Reviewer",
]
