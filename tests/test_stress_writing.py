"""Stress tests for writing and claim audit on borderline results.

Tests that the claim audit policies correctly handle:
- Non-significant trends (p > 0.05) that should not be inflated
- Very small samples with wide confidence intervals
- Marginal significance with clinically meaningless lower bounds
- Exploratory subgroup analyses entering primary conclusions

The key invariant: the writing policy must catch causal overreach,
numeric inconsistency, and unsupported claims before they enter the
formal manuscript.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from vet_manuscript_lab.domain.policies.foundation import PolicyViolation
from vet_manuscript_lab.domain.policies.writing import (
    ClaimSnapshot,
    StatisticalResultSnapshot,
    extract_referenced_numbers,
    require_no_causal_overreach,
    require_numeric_consistency,
)

_FIXTURE_ROOT = Path(__file__).resolve().parent.parent / "fixtures" / "stress_projects"


class NonSignificantTrendStressTests(unittest.TestCase):
    """Tests for non-significant trends being inflated to significant claims."""

    @classmethod
    def setUpClass(cls) -> None:
        path = _FIXTURE_ROOT / "writing_stress" / "scenarios.json"
        cls.fixture = json.loads(path.read_text(encoding="utf-8"))
        cls.scenario = next(
            s
            for s in cls.fixture["scenarios"]
            if s["scenario_id"] == "nonsignificant_trend"
        )

    def test_dangerous_claim_caught_by_causal_overreach(self) -> None:
        """A claim that inflates a trend to 'demonstrates' must be caught."""

        dangerous = self.scenario["dangerous_claims"][0]
        claim = ClaimSnapshot(
            claim_id="claim-001",
            claim_type="interpretation",
            text=dangerous,
            certainty="high",
            has_support=True,
            support_count=1,
        )
        # "demonstrates" is a causal word that should be caught
        with self.assertRaises(PolicyViolation) as ctx:
            require_no_causal_overreach(claim)
        self.assertIn("causal", str(ctx.exception).lower())

    def test_dangerous_claim_with_significantly_caught(self) -> None:
        """A claim using 'significantly' with causal words must be caught."""

        dangerous = self.scenario["dangerous_claims"][1]
        claim = ClaimSnapshot(
            claim_id="claim-002",
            claim_type="interpretation",
            text=dangerous,
            certainty="high",
            has_support=True,
            support_count=1,
        )
        with self.assertRaises(PolicyViolation):
            require_no_causal_overreach(claim)

    def test_safe_claim_passes_audit(self) -> None:
        """A carefully hedged claim about non-significance should pass."""

        safe = self.scenario["safe_claims"][2]
        claim = ClaimSnapshot(
            claim_id="claim-003",
            claim_type="interpretation",
            text=safe,
            certainty="low",
            has_support=True,
            support_count=1,
        )
        # Should NOT raise (no causal words, properly hedged)
        require_no_causal_overreach(claim)

    def test_numeric_consistency_with_result(self) -> None:
        """Claim referencing the p-value must match the statistical result."""

        result = self.scenario["result"]
        stats_result = StatisticalResultSnapshot(
            result_id="result-001",
            estimate=result["estimate"],
            p_value=result["p_value"],
        )
        # A claim that references the correct p-value should pass
        claim = ClaimSnapshot(
            claim_id="claim-004",
            claim_type="statistical",
            text=f"The p-value was {result['p_value']}.",
            certainty="moderate",
            has_support=True,
            support_count=1,
            referenced_numbers=(result["p_value"],),
        )
        # Should not raise
        require_numeric_consistency((claim,), results=(stats_result,))

    def test_fabricated_number_caught(self) -> None:
        """A claim referencing a fabricated number must be caught."""

        result = self.scenario["result"]
        stats_result = StatisticalResultSnapshot(
            result_id="result-001",
            estimate=result["estimate"],
            p_value=result["p_value"],
        )
        # Claim references p = 0.001 but actual p = 0.12
        claim = ClaimSnapshot(
            claim_id="claim-005",
            claim_type="statistical",
            text="The result was significant with p = 0.001.",
            certainty="high",
            has_support=True,
            support_count=1,
            referenced_numbers=(0.001,),
        )
        with self.assertRaises(PolicyViolation) as ctx:
            require_numeric_consistency((claim,), results=(stats_result,))
        self.assertIn("0.001", str(ctx.exception))


class SmallSampleStressTests(unittest.TestCase):
    """Tests for overconfident claims from tiny samples."""

    @classmethod
    def setUpClass(cls) -> None:
        path = _FIXTURE_ROOT / "writing_stress" / "scenarios.json"
        cls.fixture = json.loads(path.read_text(encoding="utf-8"))
        cls.scenario = next(
            s for s in cls.fixture["scenarios"] if s["scenario_id"] == "small_sample"
        )

    def test_dangerous_claim_caught(self) -> None:
        """'Treatment leads to reduced risk' from n=8 with HR=2.1 is dangerous."""

        # Use a claim with an actual causal word from the policy list
        dangerous = "Treatment leads to a strong protective effect in this population."
        claim = ClaimSnapshot(
            claim_id="claim-010",
            claim_type="factual",
            text=dangerous,
            certainty="high",
            has_support=True,
            support_count=1,
        )
        with self.assertRaises(PolicyViolation):
            require_no_causal_overreach(claim)

    def test_safe_hedged_claim_passes(self) -> None:
        """Hedged claim about wide CI and small sample should pass."""

        safe = self.scenario["safe_claims"][0]
        claim = ClaimSnapshot(
            claim_id="claim-011",
            claim_type="interpretation",
            text=safe,
            certainty="low",
            has_support=True,
            support_count=1,
        )
        require_no_causal_overreach(claim)


class WideCIStressTests(unittest.TestCase):
    """Tests for nominally significant results with clinically meaningless bounds."""

    @classmethod
    def setUpClass(cls) -> None:
        path = _FIXTURE_ROOT / "writing_stress" / "scenarios.json"
        cls.fixture = json.loads(path.read_text(encoding="utf-8"))
        cls.scenario = next(
            s for s in cls.fixture["scenarios"] if s["scenario_id"] == "wide_ci"
        )

    def test_dangerous_claim_caught(self) -> None:
        """'effect of treatment' from HR=0.55 with wide CI 0.08-3.80."""

        # Use a claim with an actual causal word from the policy list
        dangerous = "The effect of treatment on mortality is a 45% reduction."
        claim = ClaimSnapshot(
            claim_id="claim-020",
            claim_type="factual",
            text=dangerous,
            certainty="high",
            has_support=True,
            support_count=1,
        )
        with self.assertRaises(PolicyViolation):
            require_no_causal_overreach(claim)

    def test_safe_claim_with_hedging_passes(self) -> None:
        """A properly hedged claim about wide CI should pass."""

        safe = self.scenario["safe_claims"][0]
        claim = ClaimSnapshot(
            claim_id="claim-021",
            claim_type="interpretation",
            text=safe,
            certainty="low",
            has_support=True,
            support_count=1,
        )
        require_no_causal_overreach(claim)


class ExploratoryAnalysisStressTests(unittest.TestCase):
    """Tests for exploratory analyses entering primary conclusions."""

    @classmethod
    def setUpClass(cls) -> None:
        path = _FIXTURE_ROOT / "writing_stress" / "scenarios.json"
        cls.fixture = json.loads(path.read_text(encoding="utf-8"))
        cls.scenario = next(
            s
            for s in cls.fixture["scenarios"]
            if s["scenario_id"] == "exploratory_misuse"
        )

    def test_scenario_is_marked_exploratory(self) -> None:
        """The fixture scenario must be marked as exploratory."""

        self.assertTrue(self.scenario["result"].get("is_exploratory"))

    def test_dangerous_claim_caught(self) -> None:
        """'Treatment is especially effective' from exploratory n=7 subgroup."""

        dangerous = self.scenario["dangerous_claims"][0]
        claim = ClaimSnapshot(
            claim_id="claim-030",
            claim_type="factual",
            text=dangerous,
            certainty="high",
            has_support=True,
            support_count=1,
        )
        with self.assertRaises(PolicyViolation):
            require_no_causal_overreach(claim)

    def test_safe_exploratory_claim_passes(self) -> None:
        """A claim properly labeling the analysis as exploratory should pass."""

        safe = self.scenario["safe_claims"][0]
        claim = ClaimSnapshot(
            claim_id="claim-031",
            claim_type="interpretation",
            text=safe,
            certainty="low",
            has_support=True,
            support_count=1,
        )
        require_no_causal_overreach(claim)


class NumberExtractionTests(unittest.TestCase):
    """Tests for the numeric extraction helper used in consistency checks."""

    def test_extracts_decimals(self) -> None:
        """extract_referenced_numbers should handle decimal numbers."""

        numbers = extract_referenced_numbers("The HR was 0.55 with p = 0.048.")
        self.assertIn(0.55, numbers)
        self.assertIn(0.048, numbers)

    def test_extracts_integers(self) -> None:
        """extract_referenced_numbers should handle integers."""

        numbers = extract_referenced_numbers("Median survival was 285 days.")
        self.assertIn(285.0, numbers)

    def test_extracts_negative_numbers(self) -> None:
        """extract_referenced_numbers should handle negative values."""

        numbers = extract_referenced_numbers("CI: -12 to 102")
        self.assertIn(-12.0, numbers)
        self.assertIn(102.0, numbers)

    def test_empty_text_returns_empty(self) -> None:
        """Empty text should produce no numbers."""

        self.assertEqual(extract_referenced_numbers(""), ())


if __name__ == "__main__":
    unittest.main()
