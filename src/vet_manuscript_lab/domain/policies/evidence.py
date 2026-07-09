"""Pure policy checks for the literature and evidence aggregate.

These functions enforce the invariants described in domain_model.md section 2
("Literature and evidence aggregate") and IDEA.md ("every claim must be
traceable to an evidence item or statistical result").
"""

from __future__ import annotations

from dataclasses import dataclass

from vet_manuscript_lab.domain.conventions import RunMode, run_mode_allows_mock
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


__all__ = [
    "EvidenceCandidate",
    "ScreeningSummary",
    "SearchGateSnapshot",
    "require_no_mock_fallback",
    "require_non_duplicate_reference",
    "require_real_source_span",
    "require_screening_complete",
    "require_search_approved",
    "require_source_span_for_evidence",
]
