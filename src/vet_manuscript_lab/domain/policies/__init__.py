"""Deterministic approval, lock, immutability, and evidence policies."""

from vet_manuscript_lab.domain.policies.evidence import (
    EvidenceCandidate,
    ScreeningSummary,
    SearchGateSnapshot,
    require_non_duplicate_reference,
    require_screening_complete,
    require_search_approved,
    require_source_span_for_evidence,
)
from vet_manuscript_lab.domain.policies.foundation import (
    ApprovalSnapshot,
    LockSnapshot,
    PolicyViolation,
    require_approved_subject,
    require_unlocked_subject,
)

__all__ = [
    "ApprovalSnapshot",
    "EvidenceCandidate",
    "LockSnapshot",
    "PolicyViolation",
    "ScreeningSummary",
    "SearchGateSnapshot",
    "require_approved_subject",
    "require_non_duplicate_reference",
    "require_screening_complete",
    "require_search_approved",
    "require_source_span_for_evidence",
    "require_unlocked_subject",
]
"""Deterministic approval, lock, and immutability policies."""


__all__ = [
    "ApprovalSnapshot",
    "LockSnapshot",
    "PolicyViolation",
    "require_approved_subject",
    "require_unlocked_subject",
]
