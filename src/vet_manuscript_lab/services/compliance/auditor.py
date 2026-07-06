"""Compliance auditor service.

The ``ComplianceAuditor`` Protocol defines the contract;
``MockComplianceAuditor`` provides a deterministic implementation that
checks basic manuscript completeness against the STROBE-Vet checklist.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from vet_manuscript_lab.services.compliance.strobe_checklist import (
    build_strobe_checklist,
)
from vet_manuscript_lab.services.compliance.types import (
    ChecklistSummary,
    ComplianceFindingDraft,
    ComplianceSeverity,
    ComplianceStatus,
    ExportReadiness,
)


@dataclass(frozen=True, slots=True)
class ComplianceInput:
    """Inputs provided to the compliance auditor."""

    sections: tuple[dict[str, Any], ...]
    claims: tuple[dict[str, Any], ...]
    results: tuple[dict[str, Any], ...]
    citations: tuple[dict[str, Any], ...]
    guideline_mapping: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ComplianceOutput:
    """Output from the compliance auditor."""

    findings: tuple[ComplianceFindingDraft, ...]
    checklist_summary: ChecklistSummary
    readiness: str


class ComplianceAuditor(Protocol):
    """Protocol for compliance audit backends."""

    def audit(self, inputs: ComplianceInput) -> ComplianceOutput: ...


class MockComplianceAuditor:
    """Deterministic mock compliance auditor.

    Checks:
    - All required section types are present (introduction, methods,
      results, discussion).
    - Each statistical result is referenced by at least one claim.
    - Each claim has at least one citation.
    - The manuscript has a title.
    """

    REQUIRED_SECTIONS: tuple[str, ...] = (
        "introduction",
        "methods",
        "results",
        "discussion",
    )

    def audit(self, inputs: ComplianceInput) -> ComplianceOutput:
        findings: list[ComplianceFindingDraft] = []
        passed_count = 0
        total_items = len(build_strobe_checklist())

        # Check: required sections present
        section_types = {s.get("section_type", "") for s in inputs.sections}
        for req in self.REQUIRED_SECTIONS:
            if req not in section_types:
                findings.append(
                    ComplianceFindingDraft(
                        finding_id=f"compliance-section-{req}",
                        rule_id=f"required_section:{req}",
                        category="checklist",
                        severity=ComplianceSeverity.ERROR.value,
                        status=ComplianceStatus.FAIL.value,
                        evidence=f"Required section '{req}' is missing.",
                        recommendation=f"Add a '{req}' section.",
                    )
                )
            else:
                passed_count += 1

        # Check: each statistical result referenced by at least one claim
        result_ids = {r.get("result_id", "") for r in inputs.results}
        referenced_result_ids: set[str] = set()
        for claim in inputs.claims:
            for num in claim.get("referenced_numbers", []):
                for r in inputs.results:
                    est = r.get("estimate")
                    pv = r.get("p_value")
                    if est is not None and abs(est - num) < 1e-6:
                        referenced_result_ids.add(r.get("result_id", ""))
                    if pv is not None and abs(pv - num) < 1e-6:
                        referenced_result_ids.add(r.get("result_id", ""))
        unreferenced = result_ids - referenced_result_ids
        if unreferenced:
            findings.append(
                ComplianceFindingDraft(
                    finding_id="compliance-unreferenced-results",
                    rule_id="all_results_cited",
                    category="checklist",
                    severity=ComplianceSeverity.WARNING.value,
                    status=ComplianceStatus.FAIL.value,
                    evidence=(
                        f"{len(unreferenced)} statistical result(s) "
                        f"not referenced in any claim."
                    ),
                    recommendation=(
                        "Ensure every statistical result is mentioned "
                        "in the results or discussion section."
                    ),
                )
            )
        else:
            passed_count += 1

        # Check: each claim has a citation
        claim_ids_without_citation: list[str] = []
        citation_claim_ids = {
            c.get("claim_id", "") for c in inputs.citations if c.get("claim_id")
        }
        for claim in inputs.claims:
            cid = claim.get("claim_id", "")
            if cid and cid not in citation_claim_ids:
                claim_ids_without_citation.append(cid)
        if claim_ids_without_citation:
            findings.append(
                ComplianceFindingDraft(
                    finding_id="compliance-missing-citations",
                    rule_id="all_claims_cited",
                    category="checklist",
                    severity=ComplianceSeverity.WARNING.value,
                    status=ComplianceStatus.FAIL.value,
                    evidence=(
                        f"{len(claim_ids_without_citation)} claim(s) without citations."
                    ),
                    recommendation="Add citations to all claims.",
                )
            )
        else:
            passed_count += 1

        # Check: manuscript has a title
        guideline = inputs.guideline_mapping or {}
        if not guideline.get("title"):
            findings.append(
                ComplianceFindingDraft(
                    finding_id="compliance-no-title",
                    rule_id="manuscript_title",
                    category="checklist",
                    severity=ComplianceSeverity.WARNING.value,
                    status=ComplianceStatus.FAIL.value,
                    evidence="Manuscript title is missing.",
                    recommendation="Provide a manuscript title.",
                )
            )
        else:
            passed_count += 1

        # Determine readiness
        has_blocking = any(
            f.severity
            in (ComplianceSeverity.ERROR.value, ComplianceSeverity.BLOCKING.value)
            and f.status == ComplianceStatus.FAIL.value
            for f in findings
        )
        has_fail = any(f.status == ComplianceStatus.FAIL.value for f in findings)
        if has_blocking:
            readiness = ExportReadiness.BLOCKED.value
        elif has_fail:
            readiness = ExportReadiness.NOT_READY.value
        else:
            readiness = ExportReadiness.READY.value

        failed_count = sum(
            1 for f in findings if f.status == ComplianceStatus.FAIL.value
        )
        needs_review_count = sum(
            1 for f in findings if f.status == ComplianceStatus.NEEDS_REVIEW.value
        )

        summary = ChecklistSummary(
            total_items=total_items,
            passed=passed_count,
            failed=failed_count,
            not_applicable=0,
            needs_review=needs_review_count,
        )

        return ComplianceOutput(
            findings=tuple(findings),
            checklist_summary=summary,
            readiness=readiness,
        )


__all__ = [
    "ComplianceAuditor",
    "ComplianceInput",
    "ComplianceOutput",
    "MockComplianceAuditor",
]
