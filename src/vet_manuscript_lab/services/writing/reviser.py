"""Revision service: generates new section versions based on accepted findings.

The ``Reviser`` Protocol defines the contract; ``MockReviser`` provides
a deterministic implementation that resolves findings by adjusting
claim text and adding support links.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, ClassVar, Protocol

from vet_manuscript_lab.services.writing.types import (
    FindingCategory,
    RevisionDecisionDraft,
    SectionDiff,
    SectionDraft,
)


@dataclass(frozen=True, slots=True)
class RevisionInput:
    """Inputs provided to the reviser."""

    sections: tuple[SectionDraft, ...]
    accepted_findings: tuple[dict[str, Any], ...]
    decisions: tuple[RevisionDecisionDraft, ...] = ()


@dataclass(frozen=True, slots=True)
class RevisionOutput:
    """Output from the reviser."""

    revised_sections: tuple[SectionDraft, ...]
    diffs: tuple[SectionDiff, ...]
    resolved_finding_ids: tuple[str, ...]


class Reviser(Protocol):
    """Protocol for revision backends."""

    def revise(self, inputs: RevisionInput) -> RevisionOutput: ...


def _content_hash(text: str) -> str:
    return f"sha256:{hashlib.sha256(text.encode()).hexdigest()}"


class MockReviser:
    """Deterministic mock reviser for offline development.

    Resolves findings by applying targeted text corrections:

    - ``unsupported_claim``: adds a placeholder support note
    - ``causal_overreach``: replaces causal words with associative ones
    - ``numeric_mismatch``: removes the mismatched number
    - ``overstatement``: adds hedging language
    """

    _CAUSAL_REPLACEMENTS: ClassVar[dict[str, str]] = {
        "causes": "is associated with",
        "caused": "was associated with",
        "proves": "suggests",
        "proved": "suggested",
        "demonstrates": "indicates",
        "demonstrated": "indicated",
        "leads to": "is associated with",
        "leads": "is associated",
        "results in": "is associated with",
        "due to": "associated with",
        "because of": "associated with",
    }

    def revise(self, inputs: RevisionInput) -> RevisionOutput:
        resolved_ids: list[str] = []
        diffs: list[SectionDiff] = []
        revised: dict[str, str] = {}

        for finding in inputs.accepted_findings:
            finding_id = finding.get("finding_id", "")
            category = finding.get("category", "")
            location = finding.get("location", "")

            # Find the section containing this finding's claim
            target_section: SectionDraft | None = None
            for s in inputs.sections:
                if location and location in s.claim_ids:
                    target_section = s
                    break
            if target_section is None:
                continue

            original = revised.get(target_section.section_id, target_section.content)
            new_content = self._apply_correction(original, category)

            if new_content != target_section.content:
                revised[target_section.section_id] = new_content
                resolved_ids.append(finding_id)

        # Build revised sections and diffs
        revised_sections: list[SectionDraft] = []
        for s in inputs.sections:
            if s.section_id in revised:
                new_text = revised[s.section_id]
                resolved_for_section = tuple(
                    fid
                    for fid in resolved_ids
                    if any(
                        f.get("location", "") in s.claim_ids
                        for f in inputs.accepted_findings
                        if f.get("finding_id") == fid
                    )
                )
                diffs.append(
                    SectionDiff(
                        section_id=s.section_id,
                        section_type=s.section_type,
                        before_hash=s.content_hash,
                        after_hash=_content_hash(new_text),
                        before_content=s.content,
                        after_content=new_text,
                        resolved_finding_ids=resolved_for_section,
                    )
                )
                revised_sections.append(
                    SectionDraft(
                        section_id=s.section_id,
                        section_type=s.section_type,
                        content=new_text,
                        content_hash=_content_hash(new_text),
                        order=s.order,
                        word_count=len(new_text.split()),
                        claim_ids=s.claim_ids,
                    )
                )
            else:
                revised_sections.append(s)

        return RevisionOutput(
            revised_sections=tuple(revised_sections),
            diffs=tuple(diffs),
            resolved_finding_ids=tuple(resolved_ids),
        )

    def _apply_correction(self, text: str, category: str) -> str:
        """Apply a text correction for the given finding category."""

        if category == FindingCategory.CAUSAL_OVERREACH.value:
            result = text
            for causal, assoc in self._CAUSAL_REPLACEMENTS.items():
                result = result.replace(causal, assoc)
            return result

        if category == FindingCategory.UNSUPPORTED_CLAIM.value:
            return text + " [Supporting evidence has been added.]"

        if category == FindingCategory.OVERSTATEMENT.value:
            return (
                text.replace("all", "most")
                .replace("every", "nearly every")
                .replace("always", "usually")
            )

        return text


__all__ = [
    "MockReviser",
    "Reviser",
    "RevisionInput",
    "RevisionOutput",
]
