"""Section writer service: generates manuscript sections from evidence and results.

The ``SectionWriter`` Protocol defines the contract; ``MockSectionWriter``
provides a deterministic implementation for offline development and testing.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Protocol

from vet_manuscript_lab.domain.policies import extract_referenced_numbers
from vet_manuscript_lab.services.writing.types import (
    CitationDraft,
    ClaimCertainty,
    ClaimDraft,
    ClaimSupportDraft,
    ClaimType,
    SectionDiff,
    SectionDraft,
    SectionType,
    SupportRelation,
    SupportType,
)


@dataclass(frozen=True, slots=True)
class WritingInput:
    """Inputs provided to the section writer."""

    project_id: str
    evidence_summary: dict[str, Any]
    result_drafts: list[dict[str, Any]]
    literature_records: list[dict[str, Any]]
    analysis_plan_summary: dict[str, Any] = field(default_factory=dict)
    must_not_claim: tuple[str, ...] = ()
    argument_spine_finding: str = ""


@dataclass(frozen=True, slots=True)
class WritingOutput:
    """Output from the section writer."""

    sections: tuple[SectionDraft, ...]
    claims: tuple[ClaimDraft, ...]
    supports: tuple[ClaimSupportDraft, ...]
    citations: tuple[CitationDraft, ...]
    manuscript_hash: str


class SectionWriter(Protocol):
    """Protocol for section generation backends."""

    def write_sections(self, inputs: WritingInput) -> WritingOutput: ...


def _content_hash(text: str) -> str:
    return f"sha256:{hashlib.sha256(text.encode()).hexdigest()}"


class MockSectionWriter:
    """Deterministic mock writer for offline development.

    Generates concise sections that reference evidence and statistical
    results with correct numeric values, ensuring claims pass the
    numeric consistency check.
    """

    def write_sections(self, inputs: WritingInput) -> WritingOutput:
        sections: list[SectionDraft] = []
        claims: list[ClaimDraft] = []
        supports: list[ClaimSupportDraft] = []
        citations: list[CitationDraft] = []

        project_id = inputs.project_id

        # --- Introduction ---
        intro_text = (
            "This retrospective observational study examines treatment "
            "outcomes in a synthetic canine and feline cohort. "
            "Survival analysis was performed using the prespecified "
            "analysis plan."
        )
        intro_hash = _content_hash(intro_text)
        intro_id = f"section-{project_id}-intro"
        intro_claim_id = f"claim-{project_id}-intro-1"
        sections.append(
            SectionDraft(
                section_id=intro_id,
                section_type=SectionType.INTRODUCTION.value,
                content=intro_text,
                content_hash=intro_hash,
                order=0,
                word_count=len(intro_text.split()),
                claim_ids=(intro_claim_id,),
            )
        )
        claims.append(
            ClaimDraft(
                claim_id=intro_claim_id,
                claim_type=ClaimType.INTERPRETATION.value,
                text=intro_text,
                certainty=ClaimCertainty.HIGH.value,
                section_id=intro_id,
                span_start=0,
                span_end=len(intro_text),
                referenced_numbers=extract_referenced_numbers(intro_text),
            )
        )

        # --- Methods ---
        method_text = (
            "Cases were enrolled from a fictional referral hospital. "
            "Treatment assignment was recorded as a binary variable. "
            "Survival time was measured in months from enrollment."
        )
        method_hash = _content_hash(method_text)
        method_id = f"section-{project_id}-methods"
        sections.append(
            SectionDraft(
                section_id=method_id,
                section_type=SectionType.METHODS.value,
                content=method_text,
                content_hash=method_hash,
                order=1,
                word_count=len(method_text.split()),
                claim_ids=(),
            )
        )

        # --- Results (with statistical claims) ---
        result_claims: list[ClaimDraft] = []
        result_supports: list[ClaimSupportDraft] = []
        result_parts: list[str] = []

        for i, rd in enumerate(inputs.result_drafts):
            estimate = rd.get("estimate")
            p_value = rd.get("p_value")

            # Build claim text using ONLY numbers from official results.
            # Any extra numbers (indices, IDs) would trigger numeric
            # mismatch in the claim audit.
            parts: list[str] = []
            if estimate is not None:
                parts.append(f"The estimate was {estimate}.")
            if p_value is not None:
                parts.append(f"The p-value was {p_value}.")
            claim_text = " ".join(parts) if parts else "No quantitative result."

            claim_id = f"claim-{project_id}-result-{i}"
            section_id = f"section-{project_id}-results"
            nums = extract_referenced_numbers(claim_text)

            result_claims.append(
                ClaimDraft(
                    claim_id=claim_id,
                    claim_type=ClaimType.STATISTICAL.value,
                    text=claim_text,
                    certainty=ClaimCertainty.HIGH.value,
                    section_id=section_id,
                    referenced_numbers=nums,
                )
            )

            # Link claim to its statistical result source
            result_id = rd.get("result_id", f"result-{i}")
            result_supports.append(
                ClaimSupportDraft(
                    claim_id=claim_id,
                    support_type=SupportType.STATISTICAL_RESULT.value,
                    source_id=result_id,
                    relation=SupportRelation.SUPPORTS.value,
                )
            )
            result_parts.append(claim_text)

        results_text = " ".join(result_parts) if result_parts else "No results."
        results_hash = _content_hash(results_text)
        results_id = f"section-{project_id}-results"
        result_claim_ids = tuple(c.claim_id for c in result_claims)
        sections.append(
            SectionDraft(
                section_id=results_id,
                section_type=SectionType.RESULTS.value,
                content=results_text,
                content_hash=results_hash,
                order=2,
                word_count=len(results_text.split()),
                claim_ids=result_claim_ids,
            )
        )
        claims.extend(result_claims)
        supports.extend(result_supports)

        # --- Discussion ---
        discussion_text = (
            "The results suggest an association between treatment and "
            "survival. These findings are consistent with the existing "
            "literature on canine and feline clinical outcomes."
        )
        discussion_hash = _content_hash(discussion_text)
        discussion_id = f"section-{project_id}-discussion"
        discussion_claim_id = f"claim-{project_id}-disc-1"
        sections.append(
            SectionDraft(
                section_id=discussion_id,
                section_type=SectionType.DISCUSSION.value,
                content=discussion_text,
                content_hash=discussion_hash,
                order=3,
                word_count=len(discussion_text.split()),
                claim_ids=(discussion_claim_id,),
            )
        )
        claims.append(
            ClaimDraft(
                claim_id=discussion_claim_id,
                claim_type=ClaimType.INTERPRETATION.value,
                text=discussion_text,
                certainty=ClaimCertainty.MODERATE.value,
                section_id=discussion_id,
                referenced_numbers=extract_referenced_numbers(discussion_text),
            )
        )

        # Citations from literature records
        for rec in inputs.literature_records:
            lit_id = rec.get("record_id", "")
            if not lit_id:
                continue
            citation_key = f"ref-{lit_id}"
            citations.append(
                CitationDraft(
                    citation_key=citation_key,
                    literature_record_id=lit_id,
                    section_id=discussion_id,
                )
            )

        manuscript_hash = _content_hash("".join(s.content for s in sections))

        return WritingOutput(
            sections=tuple(sections),
            claims=tuple(claims),
            supports=tuple(supports),
            citations=tuple(citations),
            manuscript_hash=manuscript_hash,
        )


def create_section_diff(
    section: SectionDraft,
    new_content: str,
    *,
    resolved_finding_ids: tuple[str, ...] = (),
) -> SectionDiff:
    """Create a structured diff for a revised section."""

    return SectionDiff(
        section_id=section.section_id,
        section_type=section.section_type,
        before_hash=section.content_hash,
        after_hash=_content_hash(new_content),
        before_content=section.content,
        after_content=new_content,
        resolved_finding_ids=resolved_finding_ids,
    )


__all__ = [
    "MockSectionWriter",
    "SectionWriter",
    "WritingInput",
    "WritingOutput",
    "create_section_diff",
]
