"""Type definitions for the compliance and audit service layer."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ChecklistCategory(StrEnum):
    """STROBE-Vet checklist section categories."""

    TITLE_ABSTRACT = "title_abstract"
    INTRODUCTION = "introduction"
    METHODS = "methods"
    RESULTS = "results"
    DISCUSSION = "discussion"
    OTHER = "other"


class ComplianceSeverity(StrEnum):
    """Severity levels for compliance findings."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    BLOCKING = "blocking"


class ComplianceStatus(StrEnum):
    """Status of a checklist item or finding."""

    PASS = "pass"
    FAIL = "fail"
    NOT_APPLICABLE = "not_applicable"
    NEEDS_REVIEW = "needs_review"


class ExportReadiness(StrEnum):
    """Overall export readiness after compliance audit."""

    READY = "ready"
    NOT_READY = "not_ready"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class STROBEItem:
    """A single STROBE-Vet checklist item."""

    item_number: int
    title: str
    requirement: str
    category: ChecklistCategory
    required: bool = True


@dataclass(frozen=True, slots=True)
class ComplianceFindingDraft:
    """A finding from the compliance auditor."""

    finding_id: str
    rule_id: str
    category: str
    severity: str
    status: str = ComplianceStatus.NEEDS_REVIEW.value
    evidence: str = ""
    recommendation: str = ""


@dataclass(frozen=True, slots=True)
class ChecklistSummary:
    """Aggregate summary of checklist evaluation."""

    total_items: int
    passed: int
    failed: int
    not_applicable: int
    needs_review: int


__all__ = [
    "ChecklistCategory",
    "ChecklistSummary",
    "ComplianceFindingDraft",
    "ComplianceSeverity",
    "ComplianceStatus",
    "ExportReadiness",
    "STROBEItem",
]
