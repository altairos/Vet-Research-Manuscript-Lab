"""Unit tests for writing domain policies (pure functions).

Covers normal path, invalid input, and policy-bypass attempts for each
of the 7 writing policy functions.
"""

from __future__ import annotations

import unittest

from vet_manuscript_lab.domain.policies import (
    AuditContext,
    ClaimSnapshot,
    PolicyViolation,
    StatisticalResultSnapshot,
    extract_referenced_numbers,
    require_factual_claim_has_support,
    require_finding_before_revision,
    require_no_causal_overreach,
    require_numeric_consistency,
    require_reviewer_readonly,
    require_revision_within_limit,
    require_writing_inputs_approved,
)


def _claim(
    *,
    claim_id: str = "c1",
    claim_type: str = "factual",
    text: str = "test claim",
    certainty: str = "high",
    has_support: bool = True,
    support_count: int = 1,
    referenced_numbers: tuple[float, ...] = (),
) -> ClaimSnapshot:
    return ClaimSnapshot(
        claim_id=claim_id,
        claim_type=claim_type,
        text=text,
        certainty=certainty,
        has_support=has_support,
        support_count=support_count,
        referenced_numbers=referenced_numbers,
    )


def _result(
    *,
    result_id: str = "r1",
    estimate: float | None = 1.5,
    p_value: float | None = 0.03,
) -> StatisticalResultSnapshot:
    return StatisticalResultSnapshot(
        result_id=result_id, estimate=estimate, p_value=p_value
    )


class RequireWritingInputsApprovedTests(unittest.TestCase):
    def test_accepts_all_approved(self) -> None:
        ctx = AuditContext(
            protocol_locked=True,
            evidence_audited=True,
            results_approved=True,
        )
        result = require_writing_inputs_approved(ctx)
        self.assertIs(result, ctx)

    def test_rejects_unlocked_protocol(self) -> None:
        with self.assertRaises(PolicyViolation):
            require_writing_inputs_approved(
                AuditContext(
                    protocol_locked=False,
                    evidence_audited=True,
                    results_approved=True,
                )
            )

    def test_rejects_unaudited_evidence(self) -> None:
        with self.assertRaises(PolicyViolation):
            require_writing_inputs_approved(
                AuditContext(
                    protocol_locked=True,
                    evidence_audited=False,
                    results_approved=True,
                )
            )

    def test_rejects_unapproved_results(self) -> None:
        with self.assertRaises(PolicyViolation):
            require_writing_inputs_approved(
                AuditContext(
                    protocol_locked=True,
                    evidence_audited=True,
                    results_approved=False,
                )
            )


class RequireFactualClaimHasSupportTests(unittest.TestCase):
    def test_accepts_factual_claim_with_support(self) -> None:
        c = _claim(claim_type="factual", has_support=True, support_count=1)
        result = require_factual_claim_has_support(c)
        self.assertIs(result, c)

    def test_rejects_factual_claim_without_support(self) -> None:
        with self.assertRaises(PolicyViolation):
            require_factual_claim_has_support(
                _claim(claim_type="factual", has_support=False, support_count=0)
            )

    def test_rejects_statistical_claim_with_zero_support_count(self) -> None:
        with self.assertRaises(PolicyViolation):
            require_factual_claim_has_support(
                _claim(
                    claim_type="statistical",
                    has_support=True,
                    support_count=0,
                )
            )

    def test_accepts_interpretation_claim_without_support(self) -> None:
        c = _claim(claim_type="interpretation", has_support=False, support_count=0)
        result = require_factual_claim_has_support(c)
        self.assertIs(result, c)

    def test_accepts_recommendation_claim_without_support(self) -> None:
        c = _claim(claim_type="recommendation", has_support=False, support_count=0)
        result = require_factual_claim_has_support(c)
        self.assertIs(result, c)


class RequireNumericConsistencyTests(unittest.TestCase):
    def test_accepts_matching_numbers(self) -> None:
        claims = (
            _claim(
                claim_type="statistical",
                referenced_numbers=(1.5, 0.03),
            ),
        )
        results = (_result(estimate=1.5, p_value=0.03),)
        require_numeric_consistency(claims, results=results)

    def test_rejects_mismatched_number(self) -> None:
        claims = (
            _claim(
                claim_type="statistical",
                referenced_numbers=(9.99,),
            ),
        )
        results = (_result(estimate=1.5, p_value=0.03),)
        with self.assertRaises(PolicyViolation):
            require_numeric_consistency(claims, results=results)

    def test_skips_non_statistical_claims(self) -> None:
        claims = (
            _claim(
                claim_type="interpretation",
                referenced_numbers=(9.99,),
            ),
        )
        results = (_result(estimate=1.5),)
        # Should not raise — interpretation claims are not checked
        require_numeric_consistency(claims, results=results)

    def test_accepts_empty_claims(self) -> None:
        require_numeric_consistency((), results=(_result(),))


class RequireNoCausalOverreachTests(unittest.TestCase):
    def test_accepts_associative_language(self) -> None:
        c = _claim(text="Treatment is associated with survival.")
        require_no_causal_overreach(c)

    def test_rejects_unhedged_causal_language(self) -> None:
        bad_words = [
            "Treatment causes improved survival.",
            "The drug proved effective.",
            "Age demonstrates a significant effect.",
            "This leads to better outcomes.",
            "The results show a causal effect of treatment.",
        ]
        for text in bad_words:
            with self.subTest(text=text), self.assertRaises(PolicyViolation):
                require_no_causal_overreach(_claim(text=text))

    def test_accepts_hedged_causal_language(self) -> None:
        hedged = [
            "Treatment may cause improved survival in some patients.",
            "This might lead to better outcomes.",
            "The drug could demonstrate effectiveness.",
            "These results suggest a potential causal pathway.",
        ]
        for text in hedged:
            with self.subTest(text=text):
                require_no_causal_overreach(_claim(text=text))


class RequireFindingBeforeRevisionTests(unittest.TestCase):
    def test_accepts_with_accepted_finding(self) -> None:
        require_finding_before_revision(has_accepted_finding=True)

    def test_rejects_without_accepted_finding(self) -> None:
        with self.assertRaises(PolicyViolation):
            require_finding_before_revision(has_accepted_finding=False)


class RequireRevisionWithinLimitTests(unittest.TestCase):
    def test_accepts_within_limit(self) -> None:
        require_revision_within_limit(current_round=1, max_rounds=3)

    def test_rejects_at_limit(self) -> None:
        with self.assertRaises(PolicyViolation):
            require_revision_within_limit(current_round=3, max_rounds=3)

    def test_rejects_over_limit(self) -> None:
        with self.assertRaises(PolicyViolation):
            require_revision_within_limit(current_round=5, max_rounds=3)


class RequireReviewerReadonlyTests(unittest.TestCase):
    def test_accepts_unchanged_hash(self) -> None:
        require_reviewer_readonly(
            manuscript_hash_before="sha256:abc",
            manuscript_hash_after="sha256:abc",
        )

    def test_rejects_changed_hash(self) -> None:
        with self.assertRaises(PolicyViolation):
            require_reviewer_readonly(
                manuscript_hash_before="sha256:abc",
                manuscript_hash_after="sha256:def",
            )


class ExtractReferencedNumbersTests(unittest.TestCase):
    def test_extracts_integers(self) -> None:
        nums = extract_referenced_numbers("There were 42 cases.")
        self.assertIn(42.0, nums)

    def test_extracts_floats(self) -> None:
        nums = extract_referenced_numbers("Estimate: 3.14, P: 0.05")
        self.assertIn(3.14, nums)
        self.assertIn(0.05, nums)

    def test_extracts_negative_numbers(self) -> None:
        nums = extract_referenced_numbers("Difference: -2.5")
        self.assertIn(-2.5, nums)

    def test_returns_empty_for_no_numbers(self) -> None:
        nums = extract_referenced_numbers("No numbers here.")
        self.assertEqual(nums, ())


if __name__ == "__main__":
    unittest.main()
