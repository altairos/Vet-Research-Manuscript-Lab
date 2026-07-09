"""Tests for the Phase G review-queue aggregation logic.

Only the pure function :func:`collect_review_items` is unit-tested.
Streamlit rendering functions are exercised visually.
"""

from __future__ import annotations

from typing import Any

import pytest

from vet_manuscript_lab.ui.tabs.review_queue import (
    ReviewItem,
    collect_review_items,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state(**overrides: Any) -> dict[str, Any]:
    """Return a minimal workflow state dict."""

    state: dict[str, Any] = {
        "evidence_drafts": [],
        "source_span_drafts": [],
        "claim_drafts": [],
        "support_drafts": [],
        "citation_drafts": [],
        "methodology_findings": [],
        "review_findings": [],
        "compliance_findings": [],
        "section_drafts": [],
        "result_drafts": [],
        "artifacts": {},
        "literature_record_drafts": [],
    }
    state.update(overrides)
    return state


# ---------------------------------------------------------------------------
# Empty state
# ---------------------------------------------------------------------------


class TestEmptyState:
    def test_empty_state_returns_no_items(self) -> None:
        assert collect_review_items(_make_state()) == []


# ---------------------------------------------------------------------------
# Evidence items
# ---------------------------------------------------------------------------


class TestEvidenceNoSpan:
    def test_evidence_without_spans_is_critical(self) -> None:
        state = _make_state(
            evidence_drafts=[
                {
                    "evidence_id": "ev-1",
                    "concept": "Prevalence of disease X",
                    "source_span_ids": [],
                }
            ]
        )
        items = collect_review_items(state)
        assert len(items) == 1
        assert items[0].category == "evidence_no_span"
        assert items[0].severity == "critical"
        assert items[0].source_id == "ev-1"

    def test_evidence_with_all_missing_spans(self) -> None:
        state = _make_state(
            evidence_drafts=[
                {
                    "evidence_id": "ev-2",
                    "concept": "Mean age",
                    "source_span_ids": ["span-a", "span-b"],
                }
            ],
            source_span_drafts=[
                {"span_id": "span-x"},
            ],
        )
        items = collect_review_items(state)
        no_span = [i for i in items if i.category == "evidence_no_span"]
        assert len(no_span) == 1
        assert no_span[0].severity == "warning"
        assert set(no_span[0].related_ids) == {"span-a", "span-b"}

    def test_evidence_with_partial_missing_spans(self) -> None:
        state = _make_state(
            evidence_drafts=[
                {
                    "evidence_id": "ev-3",
                    "concept": "Treatment response",
                    "source_span_ids": ["span-1", "span-2"],
                }
            ],
            source_span_drafts=[{"span_id": "span-1"}],
        )
        items = collect_review_items(state)
        no_span = [i for i in items if i.category == "evidence_no_span"]
        assert len(no_span) == 1
        assert "span-2" in no_span[0].related_ids

    def test_evidence_with_all_spans_present_no_issue(self) -> None:
        state = _make_state(
            evidence_drafts=[
                {
                    "evidence_id": "ev-ok",
                    "concept": "OK evidence",
                    "source_span_ids": ["span-1"],
                }
            ],
            source_span_drafts=[{"span_id": "span-1"}],
        )
        items = collect_review_items(state)
        assert not any(i.category == "evidence_no_span" for i in items)


class TestEvidenceNeedsReview:
    def test_requires_human_review_flag(self) -> None:
        state = _make_state(
            evidence_drafts=[
                {
                    "evidence_id": "ev-rev",
                    "concept": "Needs review",
                    "source_span_ids": ["span-ok"],
                    "requires_human_review": True,
                    "extraction_status": "needs_review",
                }
            ],
            source_span_drafts=[{"span_id": "span-ok"}],
        )
        items = collect_review_items(state)
        review_items = [i for i in items if i.category == "evidence_needs_review"]
        assert len(review_items) == 1
        assert review_items[0].source_id == "ev-rev"

    def test_extraction_status_needs_review(self) -> None:
        state = _make_state(
            evidence_drafts=[
                {
                    "evidence_id": "ev-status",
                    "concept": "Status check",
                    "source_span_ids": ["span-ok"],
                    "requires_human_review": False,
                    "extraction_status": "needs_review",
                }
            ],
            source_span_drafts=[{"span_id": "span-ok"}],
        )
        items = collect_review_items(state)
        assert any(i.category == "evidence_needs_review" for i in items)


class TestEvidenceLowConfidence:
    def test_low_certainty_in_metadata(self) -> None:
        state = _make_state(
            evidence_drafts=[
                {
                    "evidence_id": "ev-low",
                    "concept": "Low certainty",
                    "source_span_ids": ["span-ok"],
                    "metadata": {"certainty": "low"},
                }
            ],
            source_span_drafts=[{"span_id": "span-ok"}],
        )
        items = collect_review_items(state)
        assert any(i.category == "evidence_low_confidence" for i in items)

    def test_uncertain_certainty_in_metadata(self) -> None:
        state = _make_state(
            evidence_drafts=[
                {
                    "evidence_id": "ev-unc",
                    "concept": "Uncertain",
                    "source_span_ids": ["span-ok"],
                    "metadata": {"certainty": "uncertain"},
                }
            ],
            source_span_drafts=[{"span_id": "span-ok"}],
        )
        items = collect_review_items(state)
        assert any(i.category == "evidence_low_confidence" for i in items)

    def test_high_certainty_no_warning(self) -> None:
        state = _make_state(
            evidence_drafts=[
                {
                    "evidence_id": "ev-high",
                    "concept": "High certainty",
                    "source_span_ids": ["span-ok"],
                    "metadata": {"certainty": "high"},
                }
            ],
            source_span_drafts=[{"span_id": "span-ok"}],
        )
        items = collect_review_items(state)
        assert not any(i.category == "evidence_low_confidence" for i in items)


# ---------------------------------------------------------------------------
# Claims
# ---------------------------------------------------------------------------


class TestClaimUnsupported:
    def test_factual_claim_without_support(self) -> None:
        state = _make_state(
            claim_drafts=[
                {
                    "claim_id": "claim-1",
                    "claim_type": "factual",
                    "text": "Dogs are more affected.",
                    "certainty": "medium",
                    "section_id": "results",
                }
            ],
        )
        items = collect_review_items(state)
        unsup = [i for i in items if i.category == "claim_unsupported"]
        assert len(unsup) == 1
        assert unsup[0].severity == "critical"

    def test_result_claim_without_support(self) -> None:
        state = _make_state(
            claim_drafts=[
                {
                    "claim_id": "claim-r",
                    "claim_type": "result",
                    "text": "p < 0.001",
                    "certainty": "medium",
                    "section_id": "results",
                }
            ],
        )
        items = collect_review_items(state)
        assert any(i.category == "claim_unsupported" for i in items)

    def test_factual_claim_with_support_no_issue(self) -> None:
        state = _make_state(
            claim_drafts=[
                {
                    "claim_id": "claim-supported",
                    "claim_type": "factual",
                    "text": "Supported claim",
                    "certainty": "medium",
                    "section_id": "results",
                }
            ],
            support_drafts=[
                {"claim_id": "claim-supported", "support_type": "evidence_item"},
            ],
        )
        items = collect_review_items(state)
        assert not any(i.category == "claim_unsupported" for i in items)


class TestClaimHypothesisInAbstract:
    def test_hypothesis_in_abstract(self) -> None:
        state = _make_state(
            claim_drafts=[
                {
                    "claim_id": "claim-hyp",
                    "claim_type": "hypothesis",
                    "text": "We hypothesise X",
                    "certainty": "medium",
                    "section_id": "abstract",
                }
            ],
        )
        items = collect_review_items(state)
        assert any(i.category == "claim_high_risk" for i in items)

    def test_hypothesis_in_results_no_issue(self) -> None:
        state = _make_state(
            claim_drafts=[
                {
                    "claim_id": "claim-hyp-r",
                    "claim_type": "hypothesis",
                    "text": "We hypothesise X",
                    "certainty": "medium",
                    "section_id": "results",
                }
            ],
        )
        items = collect_review_items(state)
        assert not any(
            i.category == "claim_high_risk" and i.source_id == "claim-hyp-r"
            for i in items
        )


class TestClaimOvercertain:
    def test_high_certainty_without_support(self) -> None:
        state = _make_state(
            claim_drafts=[
                {
                    "claim_id": "claim-oc",
                    "claim_type": "background",
                    "text": "Very certain background",
                    "certainty": "high",
                    "section_id": "introduction",
                }
            ],
        )
        items = collect_review_items(state)
        assert any(i.category == "claim_high_risk" for i in items)


# ---------------------------------------------------------------------------
# Methodology / review / compliance findings
# ---------------------------------------------------------------------------


class TestMethodologyFindings:
    def test_open_methodology_finding(self) -> None:
        state = _make_state(
            methodology_findings=[
                {
                    "finding_id": "mf-1",
                    "severity": "warning",
                    "rationale": "Missing power calculation",
                    "recommendation": "Add power analysis",
                    "status": "open",
                }
            ],
        )
        items = collect_review_items(state)
        mf = [i for i in items if i.category == "methodology_finding"]
        assert len(mf) == 1
        assert mf[0].severity == "warning"

    def test_addressed_methodology_finding_skipped(self) -> None:
        state = _make_state(
            methodology_findings=[
                {
                    "finding_id": "mf-2",
                    "severity": "warning",
                    "rationale": "Fixed",
                    "recommendation": "Done",
                    "status": "addressed",
                }
            ],
        )
        items = collect_review_items(state)
        assert not any(i.category == "methodology_finding" for i in items)


class TestReviewFindings:
    def test_open_review_finding(self) -> None:
        state = _make_state(
            review_findings=[
                {
                    "finding_id": "rf-1",
                    "severity": "critical",
                    "rationale": "Unsupported conclusion",
                    "recommendation": "Add evidence",
                    "status": "open",
                }
            ],
        )
        items = collect_review_items(state)
        rf = [i for i in items if i.category == "review_finding"]
        assert len(rf) == 1
        assert rf[0].severity == "critical"

    def test_accepted_review_finding_skipped(self) -> None:
        state = _make_state(
            review_findings=[
                {
                    "finding_id": "rf-2",
                    "severity": "info",
                    "rationale": "OK",
                    "recommendation": "OK",
                    "status": "accepted",
                }
            ],
        )
        items = collect_review_items(state)
        assert not any(i.category == "review_finding" for i in items)

    def test_rejected_review_finding_skipped(self) -> None:
        state = _make_state(
            review_findings=[
                {
                    "finding_id": "rf-3",
                    "severity": "info",
                    "rationale": "Nope",
                    "recommendation": "Nope",
                    "status": "rejected",
                }
            ],
        )
        items = collect_review_items(state)
        assert not any(i.category == "review_finding" for i in items)


class TestComplianceFindings:
    def test_critical_compliance_finding(self) -> None:
        state = _make_state(
            compliance_findings=[
                {
                    "finding_id": "cf-1",
                    "severity": "critical",
                    "evidence": "Missing STROBE item 9",
                    "recommendation": "Report bias",
                }
            ],
        )
        items = collect_review_items(state)
        cf = [i for i in items if i.category == "compliance_finding"]
        assert len(cf) == 1

    def test_info_compliance_finding_skipped(self) -> None:
        state = _make_state(
            compliance_findings=[
                {
                    "finding_id": "cf-2",
                    "severity": "info",
                    "evidence": "Minor note",
                    "recommendation": "Consider",
                }
            ],
        )
        items = collect_review_items(state)
        assert not any(i.category == "compliance_finding" for i in items)


# ---------------------------------------------------------------------------
# Claim-audit warnings (exploratory in abstract)
# ---------------------------------------------------------------------------


class TestAuditWarnings:
    def test_exploratory_in_abstract_warning(self) -> None:
        state = _make_state(
            artifacts={
                "claim_audit": {
                    "warnings": [
                        {
                            "warning_id": "warn-1",
                            "message": "Exploratory result in abstract",
                            "detail": "Result r1 is exploratory",
                        }
                    ]
                }
            }
        )
        items = collect_review_items(state)
        warn_items = [i for i in items if i.category == "exploratory_in_abstract"]
        assert len(warn_items) == 1
        assert warn_items[0].source_type == "audit_warning"

    def test_no_warnings_no_items(self) -> None:
        state = _make_state(artifacts={"claim_audit": {"warnings": []}})
        items = collect_review_items(state)
        assert not any(i.category == "exploratory_in_abstract" for i in items)


# ---------------------------------------------------------------------------
# Section over limit
# ---------------------------------------------------------------------------


class TestSectionOverLimit:
    def test_abstract_over_limit(self) -> None:
        state = _make_state(
            section_drafts=[
                {
                    "section_id": "sec-1",
                    "section_type": "abstract",
                    "word_count": 500,
                }
            ]
        )
        items = collect_review_items(state)
        assert any(i.category == "section_over_limit" for i in items)

    def test_abstract_within_limit(self) -> None:
        state = _make_state(
            section_drafts=[
                {
                    "section_id": "sec-2",
                    "section_type": "abstract",
                    "word_count": 300,
                }
            ]
        )
        items = collect_review_items(state)
        assert not any(i.category == "section_over_limit" for i in items)

    def test_results_over_limit(self) -> None:
        state = _make_state(
            section_drafts=[
                {
                    "section_id": "sec-3",
                    "section_type": "results",
                    "word_count": 3000,
                }
            ]
        )
        items = collect_review_items(state)
        assert any(i.category == "section_over_limit" for i in items)


# ---------------------------------------------------------------------------
# Sorting
# ---------------------------------------------------------------------------


class TestSorting:
    def test_critical_before_warning(self) -> None:
        state = _make_state(
            evidence_drafts=[
                {
                    "evidence_id": "ev-crit",
                    "concept": "No span",
                    "source_span_ids": [],
                }
            ],
            methodology_findings=[
                {
                    "finding_id": "mf-warn",
                    "severity": "warning",
                    "rationale": "warn",
                    "recommendation": "fix",
                    "status": "open",
                }
            ],
        )
        items = collect_review_items(state)
        assert items[0].severity in ("critical", "error")
        assert items[-1].severity in ("warning", "info")

    def test_deterministic_ordering_same_input(self) -> None:
        state = _make_state(
            evidence_drafts=[
                {
                    "evidence_id": f"ev-{i}",
                    "concept": f"Evidence {i}",
                    "source_span_ids": [],
                }
                for i in range(5)
            ]
        )
        first = collect_review_items(state)
        second = collect_review_items(state)
        assert [i.item_id for i in first] == [i.item_id for i in second]


# ---------------------------------------------------------------------------
# Integration / combined scenarios
# ---------------------------------------------------------------------------


class TestCombinedScenario:
    def test_multiple_categories(self) -> None:
        state = _make_state(
            evidence_drafts=[
                {
                    "evidence_id": "ev-1",
                    "concept": "No span evidence",
                    "source_span_ids": [],
                },
                {
                    "evidence_id": "ev-2",
                    "concept": "Low conf evidence",
                    "source_span_ids": ["span-ok"],
                    "metadata": {"certainty": "low"},
                },
            ],
            source_span_drafts=[{"span_id": "span-ok"}],
            claim_drafts=[
                {
                    "claim_id": "claim-1",
                    "claim_type": "factual",
                    "text": "Unsupported",
                    "certainty": "medium",
                    "section_id": "results",
                }
            ],
            methodology_findings=[
                {
                    "finding_id": "mf-1",
                    "severity": "warning",
                    "rationale": "Power",
                    "recommendation": "Add",
                    "status": "open",
                }
            ],
        )
        items = collect_review_items(state)
        categories = {i.category for i in items}
        assert "evidence_no_span" in categories
        assert "evidence_low_confidence" in categories
        assert "claim_unsupported" in categories
        assert "methodology_finding" in categories

    def test_all_items_are_review_item_instances(self) -> None:
        state = _make_state(
            evidence_drafts=[
                {
                    "evidence_id": "ev-1",
                    "concept": "Test",
                    "source_span_ids": [],
                }
            ]
        )
        items = collect_review_items(state)
        for item in items:
            assert isinstance(item, ReviewItem)
            assert item.item_id
            assert item.category
            assert item.severity
            assert item.source_type
            assert item.source_id


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
