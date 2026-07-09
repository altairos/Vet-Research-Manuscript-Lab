"""Pure policy checks for the literature and evidence aggregate.

These functions enforce the invariants described in domain_model.md section 2
("Literature and evidence aggregate") and IDEA.md ("every claim must be
traceable to an evidence item or statistical result").
"""

from __future__ import annotations

from dataclasses import dataclass

from vet_manuscript_lab.domain.conventions import (
    EvidenceType,
    RunMode,
    run_mode_allows_mock,
)
from vet_manuscript_lab.domain.policies.foundation import (
    EvidenceExtractionFailed,
    NeedsHumanSourceSpan,
    PolicyViolation,
)


@dataclass(frozen=True, slots=True)
class EvidenceCandidate:
    concept: str
    source_span_ids: list[str]
    literature_record_id: str
    extraction_status: str
    requires_human_review: bool


@dataclass(frozen=True, slots=True)
class SearchGateSnapshot:
    """Compact summary of the search-strategy approval gate."""

    approved: bool
    subject_version_id: str


def require_source_span_for_evidence(evidence: EvidenceCandidate) -> None:
    """An EvidenceItem must trace to at least one SourceSpan.

    Without a source span the evidence is unverifiable and must not enter the
    formal evidence ledger.
    """

    if not evidence.source_span_ids:
        raise PolicyViolation(
            f"Evidence item for concept '{evidence.concept}' has no source spans"
        )


def require_search_approved(gate: SearchGateSnapshot | None) -> SearchGateSnapshot:
    """Screening may only proceed after the search strategy is approved."""

    if gate is None:
        raise PolicyViolation("Search strategy approval gate is missing")
    if not gate.approved:
        raise PolicyViolation("Search strategy has not been approved")
    return gate


@dataclass(frozen=True, slots=True)
class ScreeningSummary:
    total_records: int
    included_count: int
    excluded_count: int


def require_screening_complete(summary: ScreeningSummary) -> None:
    """Evidence extraction requires that every record has been screened.

    The counts must be positive and every record must have been accounted for.
    """

    if summary.total_records <= 0:
        raise PolicyViolation("No literature records to screen")
    if summary.included_count + summary.excluded_count != summary.total_records:
        raise PolicyViolation(
            "Screening is incomplete: "
            f"{summary.included_count + summary.excluded_count}/"
            f"{summary.total_records} records decided"
        )


def require_non_duplicate_reference(
    *,
    doi: str | None,
    pmid: str | None,
    existing_dois: frozenset[str],
    existing_pmids: frozenset[str],
) -> None:
    """Reject references that duplicate an existing DOI or PMID in the project."""

    if doi and doi in existing_dois:
        raise PolicyViolation(f"Duplicate DOI already in project: {doi}")
    if pmid and pmid in existing_pmids:
        raise PolicyViolation(f"Duplicate PMID already in project: {pmid}")


def require_no_mock_fallback(
    *,
    run_mode: RunMode,
    is_mock_generated: bool,
    context: str = "evidence extraction",
) -> None:
    """In production mode, mock-generated evidence must not be admitted.

    ``is_mock_generated`` is ``True`` when the span/evidence was produced by
    a deterministic stub rather than real retrieval.  In ``PRODUCTION`` this
    is a hard failure — the system must fail closed instead of fabricating
    evidence.
    """

    if is_mock_generated and not run_mode_allows_mock(run_mode):
        raise EvidenceExtractionFailed(
            f"Mock fallback used during {context} in {run_mode.value} mode; "
            "this is forbidden in production. "
            "Either provide a real retrieval pipeline or switch to DEMO/TEST mode."
        )


def require_real_source_span(
    *,
    run_mode: RunMode,
    span_attachment_version_id: str | None,
    record_id: str,
) -> None:
    """In production mode, every source span must trace to a real attachment.

    A source span without ``attachment_version_id`` is synthetic (generated
    to maintain the source-span invariant).  In production this is
    unacceptable — the record must be flagged for human resolution instead.
    """

    if span_attachment_version_id is None and not run_mode_allows_mock(run_mode):
        raise NeedsHumanSourceSpan(
            f"Record '{record_id}' has no real source span in {run_mode.value} "
            "mode; retrieval returned no hits. "
            "Human resolution is required to locate the source passage."
        )


@dataclass(frozen=True, slots=True)
class TypedEvidenceCandidate:
    """Evidence candidate with a structured ``evidence_type`` field.

    This extends ``EvidenceCandidate`` with a type classification that
    drives type-specific validation rules.  The ``metadata`` dict holds
    type-specific fields (e.g. variable, groups, effect_size for
    ``STATISTICAL_RESULT``).
    """

    concept: str
    evidence_type: EvidenceType
    source_span_ids: list[str]
    literature_record_id: str
    extraction_status: str
    requires_human_review: bool
    value: str | None = None
    units: str | None = None
    population: str | None = None
    metadata: dict[str, str] | None = None


# Required fields per evidence type.
#
# Keys in the metadata dict that must be non-empty for the type to be
# considered valid.  An empty tuple means the type has no extra
# required metadata beyond the base fields.
_REQUIRED_METADATA: dict[EvidenceType, tuple[str, ...]] = {
    EvidenceType.SAMPLE_CHARACTERISTIC: (),
    EvidenceType.DIAGNOSTIC_CRITERION: (),
    EvidenceType.EXPOSURE_OR_INTERVENTION: (),
    EvidenceType.OUTCOME_DEFINITION: (),
    EvidenceType.STATISTICAL_RESULT: (
        "variable",
        "groups",
        "effect_size",
    ),
    EvidenceType.ADVERSE_EVENT: ("event",),
    EvidenceType.LIMITATION: (),
    EvidenceType.MECHANISTIC_HYPOTHESIS: (),
    EvidenceType.GUIDELINE_REQUIREMENT: ("guideline",),
    EvidenceType.BACKGROUND_CLAIM: (),
}


def require_valid_evidence_type(candidate: TypedEvidenceCandidate) -> None:
    """Validate that a typed evidence item has all required fields.

    Different ``EvidenceType`` values require different metadata fields.
    For example, ``STATISTICAL_RESULT`` must specify ``variable``,
    ``groups``, and ``effect_size`` in its metadata dict.

    Raises ``PolicyViolation`` if required fields are missing or empty.
    """

    required = _REQUIRED_METADATA.get(candidate.evidence_type, ())
    if not required:
        return

    meta = candidate.metadata or {}
    missing: list[str] = []
    for field_name in required:
        val = meta.get(field_name, "")
        if not val or not str(val).strip():
            missing.append(field_name)

    if missing:
        raise PolicyViolation(
            f"Evidence item for concept '{candidate.concept}' with type "
            f"'{candidate.evidence_type.value}' is missing required "
            f"metadata fields: {', '.join(missing)}"
        )


def get_required_metadata_fields(
    evidence_type: EvidenceType,
) -> tuple[str, ...]:
    """Return the tuple of required metadata field names for a type."""

    return _REQUIRED_METADATA.get(evidence_type, ())


__all__ = [
    "EvidenceCandidate",
    "ScreeningSummary",
    "SearchGateSnapshot",
    "TypedEvidenceCandidate",
    "get_required_metadata_fields",
    "require_no_mock_fallback",
    "require_non_duplicate_reference",
    "require_real_source_span",
    "require_screening_complete",
    "require_search_approved",
    "require_source_span_for_evidence",
    "require_valid_evidence_type",
]
