"""Type definitions for the manuscript writing, review, and revision service.

All enums and dataclasses are plain Python types with no external
dependencies, enabling deterministic mock implementations and easy
testing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class SectionType(StrEnum):
    """Standard manuscript section types."""

    INTRODUCTION = "introduction"
    METHODS = "methods"
    RESULTS = "results"
    DISCUSSION = "discussion"
    CONCLUSION = "conclusion"


class ClaimType(StrEnum):
    """Categories of manuscript claims with different support rules."""

    FACTUAL = "factual"
    STATISTICAL = "statistical"
    INTERPRETATION = "interpretation"
    RECOMMENDATION = "recommendation"


class ClaimCertainty(StrEnum):
    """Calibrated certainty levels for manuscript claims."""

    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"


class SupportRelation(StrEnum):
    """How a support source relates to a claim."""

    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    PARTIALLY_SUPPORTS = "partially_supports"


class SupportType(StrEnum):
    """Type of evidence backing a claim."""

    EVIDENCE = "evidence"
    STATISTICAL_RESULT = "statistical_result"


class FindingCategory(StrEnum):
    """Categories of review findings."""

    UNSUPPORTED_CLAIM = "unsupported_claim"
    NUMERIC_MISMATCH = "numeric_mismatch"
    CAUSAL_OVERREACH = "causal_overreach"
    MISSING_CITATION = "missing_citation"
    OVERSTATEMENT = "overstatement"
    SCOPE_DRIFT = "scope_drift"


class FindingSeverity(StrEnum):
    """Severity levels for review findings."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class FindingStatus(StrEnum):
    """Dispositional status of a review finding."""

    OPEN = "open"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    DEFERRED = "deferred"


class RevisionDecisionType(StrEnum):
    """Human disposition types for review findings."""

    ACCEPT = "accept"
    REJECT = "reject"
    DEFER = "defer"


@dataclass(frozen=True, slots=True)
class ClaimDraft:
    """A claim extracted from a manuscript section."""

    claim_id: str
    claim_type: str
    text: str
    certainty: str = ClaimCertainty.HIGH.value
    span_start: int | None = None
    span_end: int | None = None
    section_id: str = ""
    referenced_numbers: tuple[float, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class ClaimSupportDraft:
    """A support link connecting a claim to its source."""

    claim_id: str
    support_type: str
    source_id: str
    relation: str = SupportRelation.SUPPORTS.value
    audit_status: str = "verified"


@dataclass(frozen=True, slots=True)
class CitationDraft:
    """A citation occurrence in a manuscript section."""

    citation_key: str
    literature_record_id: str
    section_id: str
    claim_id: str | None = None
    locator: str | None = None


@dataclass(frozen=True, slots=True)
class SectionDraft:
    """A generated manuscript section with its claims and citations."""

    section_id: str
    section_type: str
    content: str
    content_hash: str
    order: int
    word_count: int = 0
    claim_ids: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class ReviewFindingDraft:
    """A finding produced by the Reviewer Agent."""

    finding_id: str
    category: str
    severity: str
    location: str = ""
    rationale: str = ""
    recommendation: str = ""
    status: str = FindingStatus.OPEN.value


@dataclass(frozen=True, slots=True)
class RevisionDecisionDraft:
    """A human disposition of a review finding."""

    finding_id: str
    decision: str
    reason: str = ""
    reviewer_id: str = ""


@dataclass(frozen=True, slots=True)
class SectionDiff:
    """Structured diff of a section before and after revision."""

    section_id: str
    section_type: str
    before_hash: str
    after_hash: str
    before_content: str
    after_content: str
    resolved_finding_ids: tuple[str, ...] = field(default_factory=tuple)


__all__ = [
    "CitationDraft",
    "ClaimCertainty",
    "ClaimDraft",
    "ClaimSupportDraft",
    "ClaimType",
    "FindingCategory",
    "FindingSeverity",
    "FindingStatus",
    "RevisionDecisionDraft",
    "RevisionDecisionType",
    "SectionDiff",
    "SectionDraft",
    "SectionType",
    "SupportRelation",
    "SupportType",
]
