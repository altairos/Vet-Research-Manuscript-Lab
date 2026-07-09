"""Pure policy checks used by services, graph nodes, and tests."""

from __future__ import annotations

from dataclasses import dataclass


class PolicyViolation(PermissionError):
    pass


class EvidenceExtractionFailed(PolicyViolation):
    """Raised when evidence extraction cannot produce real evidence.

    In ``RunMode.PRODUCTION`` the system must **not** fall back to mock
    spans.  Instead it raises this exception so the workflow fails
    closed, forcing human resolution.
    """


class NeedsHumanSourceSpan(PolicyViolation):
    """A retriever returned no hits in production mode.

    Rather than generating a synthetic source span to maintain the
    source-span invariant, the node flags this as requiring human
    attention.  The record is marked ``requires_human_review`` and
    excluded from the formal evidence ledger.
    """


@dataclass(frozen=True, slots=True)
class ApprovalSnapshot:
    gate: str
    subject_version_id: str
    subject_hash: str
    decision: str
    reviewer_id: str
    reviewer_role: str


@dataclass(frozen=True, slots=True)
class LockSnapshot:
    lock_type: str
    subject_version_id: str
    subject_hash: str


def require_approved_subject(
    approval: ApprovalSnapshot | None,
    *,
    gate: str,
    subject_version_id: str,
    subject_hash: str,
    allowed_roles: frozenset[str],
) -> ApprovalSnapshot:
    if approval is None:
        raise PolicyViolation(f"Missing approval for gate: {gate}")
    if approval.gate != gate:
        raise PolicyViolation("Approval belongs to a different gate")
    if approval.decision != "approved":
        raise PolicyViolation("Approval decision is not approved")
    if approval.subject_version_id != subject_version_id:
        raise PolicyViolation("Approval is stale or belongs to another version")
    if approval.subject_hash != subject_hash:
        raise PolicyViolation("Approval hash does not match subject content")
    if approval.reviewer_role not in allowed_roles:
        raise PolicyViolation("Reviewer role is not authorized for this gate")
    if not approval.reviewer_id.strip():
        raise PolicyViolation("Reviewer identity is required")
    return approval


def require_unlocked_subject(
    locks: list[LockSnapshot], *, subject_version_id: str
) -> None:
    if any(lock.subject_version_id == subject_version_id for lock in locks):
        raise PolicyViolation("Locked artifact versions are immutable")
