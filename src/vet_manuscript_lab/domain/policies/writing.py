"""Pure policy checks for the manuscript, claim, review, and revision aggregate.

These functions enforce the invariants described in domain_model.md section
("Manuscript aggregate") and the Phase 4 exit criteria in DEVELOPMENT.md.

Core invariants:

1. Writing requires approved protocol, evidence, and statistical results.
2. Every factual claim must trace back to an EvidenceItem or StatisticalResult.
3. Numbers in claims must match the official statistical results.
4. Associative language must not be rewritten as causal.
5. Revision must be based on accepted review findings.
6. Revision rounds must not exceed the configured limit.
7. The Reviewer Agent must not modify the manuscript (read-only).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from vet_manuscript_lab.domain.policies.foundation import PolicyViolation

# ---------------------------------------------------------------------------
# Snapshot dataclasses (mirror the DB record fields but are pure values)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ManuscriptVersionSnapshot:
    """Compact representation of a manuscript version."""

    version_id: str
    content_hash: str
    status: str  # "draft", "assembled", "under_review", etc.


@dataclass(frozen=True, slots=True)
class SectionSnapshot:
    """Compact representation of a manuscript section."""

    section_id: str
    section_type: str
    content_hash: str
    order: int


@dataclass(frozen=True, slots=True)
class ClaimSnapshot:
    """Compact representation of a manuscript claim."""

    claim_id: str
    claim_type: str  # "factual", "statistical", "interpretation", "recommendation"
    text: str
    certainty: str  # "high", "moderate", "low"
    has_support: bool = False
    support_count: int = 0
    referenced_numbers: tuple[float, ...] = field(default_factory=tuple)
    support_source_ids: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class ClaimSupportSnapshot:
    """Compact representation of a claim-to-source relation."""

    claim_id: str
    support_type: str  # "evidence", "statistical_result"
    source_id: str
    relation: str  # "supports", "contradicts", "partially_supports"
    audit_status: str  # "pending", "verified", "failed"


@dataclass(frozen=True, slots=True)
class StatisticalResultSnapshot:
    """Compact representation of a statistical result for numeric consistency."""

    result_id: str
    estimate: float | None = None
    p_value: float | None = None


@dataclass(frozen=True, slots=True)
class AuditContext:
    """Inputs checked before the writing stage may begin."""

    protocol_locked: bool
    evidence_audited: bool
    results_approved: bool


# ---------------------------------------------------------------------------
# Patterns for causal-overreach detection
# ---------------------------------------------------------------------------

# Words that imply causation — banned in claims based on observational data
# unless the study design supports causal inference.
_CAUSAL_WORDS: tuple[str, ...] = (
    "causes",
    "caused",
    "proves",
    "proved",
    "demonstrates",
    "demonstrated",
    "leads to",
    "leads",
    "results in",
    "results",
    "due to",
    "because of",
    "effect of",
    "effect",
)

# Words that indicate association — the correct register for observational
# studies.
_ASSOCIATION_WORDS: tuple[str, ...] = (
    "associated",
    "association",
    "correlated",
    "correlation",
    "related",
    "relationship",
    "linked",
    "link",
    "trend",
    "pattern",
)

_NUMBER_PATTERN = re.compile(r"-?\d+\.?\d*")


# ---------------------------------------------------------------------------
# Policy functions
# ---------------------------------------------------------------------------


def require_writing_inputs_approved(ctx: AuditContext) -> AuditContext:
    """Writing may start only when protocol, evidence, and results are approved.

    This prevents drafting a manuscript from preliminary or unverified
    scientific inputs.
    """

    if not ctx.protocol_locked:
        raise PolicyViolation("Writing requires an approved and locked protocol")
    if not ctx.evidence_audited:
        raise PolicyViolation("Writing requires completed evidence audit")
    if not ctx.results_approved:
        raise PolicyViolation("Writing requires approved statistical results")
    return ctx


def require_factual_claim_has_support(claim: ClaimSnapshot) -> ClaimSnapshot:
    """Every factual or statistical claim must have at least one support link.

    A factual claim without support is either fabricated or unsupported
    and must not enter a formal manuscript version.
    """

    if claim.claim_type in ("factual", "statistical") and not claim.has_support:
        raise PolicyViolation(
            f"Claim '{claim.claim_id}' of type '{claim.claim_type}' "
            f"has no supporting evidence or statistical result"
        )
    if claim.claim_type in ("factual", "statistical") and claim.support_count == 0:
        raise PolicyViolation(
            f"Claim '{claim.claim_id}' requires at least one support "
            f"link but found {claim.support_count}"
        )
    return claim


def require_numeric_consistency(
    claims: tuple[ClaimSnapshot, ...],
    *,
    results: tuple[StatisticalResultSnapshot, ...],
) -> None:
    """Numbers cited in claims must appear in the official statistical results.

    This prevents the manuscript from reporting figures that were never
    produced by the analysis pipeline.
    """

    valid_numbers: set[float] = set()
    for r in results:
        if r.estimate is not None:
            valid_numbers.add(round(r.estimate, 4))
        if r.p_value is not None:
            valid_numbers.add(round(r.p_value, 4))

    for claim in claims:
        if claim.claim_type not in ("factual", "statistical"):
            continue
        for num in claim.referenced_numbers:
            if round(num, 4) not in valid_numbers:
                raise PolicyViolation(
                    f"Claim '{claim.claim_id}' references number {num} "
                    f"which does not match any official statistical result"
                )


def require_no_causal_overreach(claim: ClaimSnapshot) -> None:
    """Claims must not upgrade associative language to causal language.

    In observational veterinary studies, associations cannot be claimed as
    causation. This check flags claims that use causal verbs without
    appropriate hedging.
    """

    text_lower = claim.text.lower()
    for word in _CAUSAL_WORDS:
        if word in text_lower:
            # Allow if explicitly hedged with "may", "might", "could",
            # "potential", or "suggests"
            hedged = any(
                hedge in text_lower
                for hedge in ("may ", "might ", "could ", "potential", "suggest")
            )
            if not hedged:
                raise PolicyViolation(
                    f"Claim '{claim.claim_id}' uses causal language "
                    f"'{word}' without hedging; observational data "
                    f"supports association, not causation"
                )


def require_finding_before_revision(
    *,
    has_accepted_finding: bool,
) -> None:
    """Revision must be triggered by at least one accepted review finding.

    A revision without an accepted finding is either speculative or
    addresses a rejected issue, both of which violate the controlled
    revision process.
    """

    if not has_accepted_finding:
        raise PolicyViolation("Revision requires at least one accepted review finding")


def require_revision_within_limit(
    *,
    current_round: int,
    max_rounds: int,
) -> None:
    """The revision round must not exceed the configured maximum.

    When the limit is reached, the workflow must escalate to a human
    rather than looping indefinitely.
    """

    if current_round >= max_rounds:
        raise PolicyViolation(
            f"Revision limit reached: round {current_round} >= "
            f"max {max_rounds}; human escalation required"
        )


def require_reviewer_readonly(
    *,
    manuscript_hash_before: str,
    manuscript_hash_after: str,
) -> None:
    """The Reviewer Agent must not modify the manuscript.

    The reviewer produces findings only; the manuscript content hash
    must be identical before and after the review stage.
    """

    if manuscript_hash_before != manuscript_hash_after:
        raise PolicyViolation(
            "Manuscript hash changed during review: the reviewer must be read-only"
        )


def extract_referenced_numbers(text: str) -> tuple[float, ...]:
    """Extract numeric values mentioned in a claim text.

    Used by the writing service to populate ``ClaimSnapshot.referenced_numbers``
    for the numeric consistency check.
    """

    matches = _NUMBER_PATTERN.findall(text)
    return tuple(float(m) for m in matches)


__all__ = [
    "AuditContext",
    "ClaimSnapshot",
    "ClaimSupportSnapshot",
    "ManuscriptVersionSnapshot",
    "SectionSnapshot",
    "StatisticalResultSnapshot",
    "extract_referenced_numbers",
    "require_factual_claim_has_support",
    "require_finding_before_revision",
    "require_no_causal_overreach",
    "require_numeric_consistency",
    "require_reviewer_readonly",
    "require_revision_within_limit",
    "require_writing_inputs_approved",
]
