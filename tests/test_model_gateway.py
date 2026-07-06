"""Tests for the Model Gateway: Router, pricing, invocation, and usage log.

Covers the full chain: RoutingDecision → ModelInvocation →
TokenUsageRecord → UsageLog (AI_USAGE_LOG artifact), using MockProvider.

Adversarial tests verify: budget enforcement (no silent downgrade),
model routing bypass prevention, and fallback provenance.
"""

from __future__ import annotations

import unittest

from vet_manuscript_lab.infrastructure.model_gateway.gateway import (
    GatewayResult,
    MockProvider,
    ModelGateway,
    ProviderError,
)
from vet_manuscript_lab.infrastructure.model_gateway.pricing import (
    default_catalog,
)
from vet_manuscript_lab.infrastructure.model_gateway.router import (
    BudgetExhaustedError,
    NoEligibleModelError,
    RouterAgent,
    route_task,
)
from vet_manuscript_lab.infrastructure.model_gateway.types import (
    AgentTaskSpec,
    BudgetLimit,
    ModelInvocation,
    ModelTier,
    RoutingDecision,
    TaskKind,
)


def _spec(
    task_kind: TaskKind = TaskKind.SECTION_WRITING,
    *,
    risk_level: int = 0,
    input_tokens: int = 1000,
    output_tokens: int = 500,
    required_capabilities: frozenset[str] | None = None,
) -> AgentTaskSpec:
    return AgentTaskSpec(
        task_kind=task_kind,
        estimated_input_tokens=input_tokens,
        estimated_output_tokens=output_tokens,
        required_capabilities=required_capabilities or frozenset(),
        risk_level=risk_level,
    )


# ===========================================================================
# Pricing tests
# ===========================================================================


class PricingCatalogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = default_catalog()

    def test_estimate_cost_cheap_model(self) -> None:
        cost = self.catalog.estimate_cost_cents(
            "deepseek-v4-flash",
            input_tokens=1_000_000,
            output_tokens=500_000,
        )
        # 1M input * 14c/M = 14c; 500K output * 28c/M = 14c → 28c
        self.assertEqual(cost, 28)

    def test_estimate_cost_high_model(self) -> None:
        cost = self.catalog.estimate_cost_cents(
            "glm-5.2",
            input_tokens=1_000_000,
            output_tokens=500_000,
        )
        # 1M input * 200c/M = 200c; 500K output * 600c/M = 300c → 500c
        self.assertEqual(cost, 500)

    def test_estimate_cost_zero_tokens(self) -> None:
        cost = self.catalog.estimate_cost_cents(
            "deepseek-v4-flash",
            input_tokens=0,
            output_tokens=0,
        )
        self.assertEqual(cost, 0)

    def test_estimate_cost_truncates_downward(self) -> None:
        # 1 token * 14c/M should floor to 0
        cost = self.catalog.estimate_cost_cents(
            "deepseek-v4-flash",
            input_tokens=1,
            output_tokens=0,
        )
        self.assertEqual(cost, 0)

    def test_get_profile_returns_capabilities(self) -> None:
        profile = self.catalog.get_profile("glm-5.2")
        self.assertIn("json_mode", profile.capabilities)
        self.assertIn("vision", profile.capabilities)

    def test_unknown_model_raises(self) -> None:
        from vet_manuscript_lab.infrastructure.model_gateway.pricing import (
            UnknownModelError,
        )

        with self.assertRaises(UnknownModelError):
            self.catalog.get_pricing("nonexistent-model")

    def test_fallback_chain_for_tier(self) -> None:
        chain = self.catalog.get_fallback_chain(ModelTier.BALANCED_WRITE)
        self.assertEqual(chain[0], "deepseek-v4-pro")
        self.assertIn("glm-5.2", chain)

    def test_models_by_tier(self) -> None:
        cheap = self.catalog.models_by_tier(ModelTier.CHEAP_BATCH)
        self.assertEqual(len(cheap), 1)
        self.assertEqual(cheap[0].model_id, "deepseek-v4-flash")


# ===========================================================================
# Router tests (deterministic policy)
# ===========================================================================


class RouterAgentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.router = RouterAgent()

    def test_default_tier_for_cheap_task(self) -> None:
        decision = self.router.route(
            _spec(TaskKind.FORMAT_CONVERSION, input_tokens=100, output_tokens=50)
        )
        self.assertEqual(decision.tier, ModelTier.CHEAP_BATCH)
        self.assertEqual(decision.model_id, "deepseek-v4-flash")

    def test_default_tier_for_balanced_task(self) -> None:
        decision = self.router.route(
            _spec(TaskKind.SECTION_WRITING, input_tokens=2000, output_tokens=1000)
        )
        self.assertEqual(decision.tier, ModelTier.BALANCED_WRITE)
        self.assertEqual(decision.model_id, "deepseek-v4-pro")

    def test_default_tier_for_high_task(self) -> None:
        decision = self.router.route(
            _spec(TaskKind.METHODOLOGY_CRITIC, input_tokens=5000, output_tokens=2000)
        )
        self.assertEqual(decision.tier, ModelTier.HIGH_REASONING)
        self.assertEqual(decision.model_id, "glm-5.2")

    def test_risk_upgrade_to_high_reasoning(self) -> None:
        # FORMAT_CONVERSION is cheap_batch by default...
        decision = self.router.route(_spec(TaskKind.FORMAT_CONVERSION, risk_level=2))
        # ...but risk_level=2 forces high_reasoning
        self.assertEqual(decision.tier, ModelTier.HIGH_REASONING)
        self.assertIn("triggers upgrade", decision.rationale)

    def test_risk_level_1_does_not_upgrade(self) -> None:
        decision = self.router.route(_spec(TaskKind.FORMAT_CONVERSION, risk_level=1))
        self.assertEqual(decision.tier, ModelTier.CHEAP_BATCH)

    def test_deterministic_same_spec_same_decision(self) -> None:
        spec = _spec(TaskKind.SECTION_WRITING, input_tokens=3000, output_tokens=800)
        d1 = self.router.route(spec)
        d2 = self.router.route(spec)
        self.assertEqual(d1, d2)

    def test_capability_filter_skips_model(self) -> None:
        # deepseek-v4-flash doesn't have "vision"; requiring it should
        # force upgrade to balanced or high tier
        decision = self.router.route(
            _spec(
                TaskKind.FORMAT_CONVERSION,
                required_capabilities=frozenset({"vision"}),
            )
        )
        self.assertEqual(decision.model_id, "glm-5.2")

    def test_context_window_too_small_raises(self) -> None:
        with self.assertRaises(NoEligibleModelError):
            self.router.route(
                _spec(TaskKind.FORMAT_CONVERSION, input_tokens=999_999_999)
            )

    def test_budget_ok_when_sufficient(self) -> None:
        budget = BudgetLimit(scope="run", limit_cents=10_000, spent_cents=0)
        decision = self.router.route(_spec(), budget=budget)
        self.assertTrue(decision.budget_ok)

    def test_budget_warning_when_insufficient(self) -> None:
        budget = BudgetLimit(scope="run", limit_cents=1, spent_cents=0)
        decision = self.router.route(
            _spec(
                TaskKind.SECTION_WRITING,
                input_tokens=20_000,
                output_tokens=5_000,
            ),
            budget=budget,
        )
        self.assertFalse(decision.budget_ok)
        self.assertIn("BUDGET WARNING", decision.rationale)

    def test_budget_exhausted_raises(self) -> None:
        budget = BudgetLimit(scope="run", limit_cents=100, spent_cents=100)
        with self.assertRaises(BudgetExhaustedError):
            self.router.route(_spec(), budget=budget)

    def test_rationale_contains_task_and_tier(self) -> None:
        decision = self.router.route(_spec(TaskKind.CITATION_AUDIT))
        self.assertIn("citation_audit", decision.rationale)
        self.assertIn("balanced_write", decision.rationale)

    def test_fallback_chain_in_decision(self) -> None:
        decision = self.router.route(_spec(TaskKind.METHODOLOGY_CRITIC))
        self.assertTrue(len(decision.fallback_chain) >= 1)
        self.assertIn("deepseek-v4-pro", decision.fallback_chain)

    def test_route_task_convenience_function(self) -> None:
        decision = route_task(_spec(TaskKind.SCREENING))
        self.assertEqual(decision.tier, ModelTier.CHEAP_BATCH)


# ===========================================================================
# Gateway integration tests
# ===========================================================================


class ModelGatewayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.gateway = ModelGateway()

    def test_invoke_returns_text_and_invocation(self) -> None:
        result = self.gateway.invoke(
            _spec(TaskKind.SECTION_WRITING),
            prompt="Write an introduction about canine CKD.",
        )
        self.assertIsInstance(result, GatewayResult)
        self.assertTrue(result.text)
        self.assertIsInstance(result.invocation, ModelInvocation)
        self.assertEqual(result.invocation.status, "success")
        self.assertIsNone(result.invocation.fallback_from)

    def test_invoke_records_usage(self) -> None:
        # Use a very long prompt to ensure token count is high enough for
        # integer-cent cost to be non-zero (>10K input tokens).
        long_prompt = "Check these citations carefully. " * 2000
        self.gateway.invoke(
            _spec(TaskKind.CITATION_AUDIT),
            prompt=long_prompt,
        )
        log = self.gateway.usage_log
        self.assertEqual(len(log.invocations), 1)
        self.assertGreater(log.total_input_tokens, 0)
        self.assertGreater(log.total_output_tokens, 0)
        self.assertGreater(log.total_cost_cents, 0)

    def test_invoke_records_input_hash(self) -> None:
        result = self.gateway.invoke(
            _spec(TaskKind.FORMAT_CONVERSION),
            prompt="Convert this to JSON.",
        )
        self.assertTrue(result.invocation.input_hash.startswith("sha256:"))

    def test_multiple_invocations_accumulate(self) -> None:
        for i in range(3):
            self.gateway.invoke(
                _spec(TaskKind.SCREENING),
                prompt=f"Screen record {i}.",
            )
        log = self.gateway.usage_log
        self.assertEqual(len(log.invocations), 3)
        self.assertEqual(log.fallback_count, 0)
        self.assertEqual(log.failure_count, 0)

    def test_usage_log_to_dict(self) -> None:
        self.gateway.invoke(
            _spec(TaskKind.SECTION_WRITING),
            prompt="Draft methods section.",
        )
        data = self.gateway.usage_log.to_dict()
        self.assertEqual(data["total_invocations"], 1)
        self.assertIn("invocations", data)
        self.assertEqual(data["invocations"][0]["task_kind"], "section_writing")
        self.assertEqual(data["invocations"][0]["status"], "success")

    def test_budget_exhausted_blocks_invocation(self) -> None:
        budget = BudgetLimit(scope="run", limit_cents=1, spent_cents=1)
        with self.assertRaises(BudgetExhaustedError):
            self.gateway.invoke(
                _spec(TaskKind.SECTION_WRITING),
                prompt="This should be blocked.",
                budget=budget,
            )
        # No invocation should be recorded
        self.assertEqual(len(self.gateway.usage_log.invocations), 0)

    def test_fallback_on_primary_failure(self) -> None:
        gateway = ModelGateway(provider=MockProvider(fail_first=1))
        result = gateway.invoke(
            _spec(TaskKind.METHODOLOGY_CRITIC),
            prompt="Critique this methodology.",
        )
        self.assertEqual(result.invocation.status, "fallback")
        self.assertIsNotNone(result.invocation.fallback_from)

    def test_all_models_fail_records_failure(self) -> None:
        gateway = ModelGateway(provider=MockProvider(fail_first=99))
        with self.assertRaises(ProviderError):
            gateway.invoke(
                _spec(TaskKind.FORMAT_CONVERSION),
                prompt="This will fail all models.",
            )
        log = gateway.usage_log
        self.assertEqual(log.failure_count, 1)
        self.assertEqual(log.invocations[0].status, "failed")

    def test_cost_recorded_matches_catalog(self) -> None:
        catalog = default_catalog()
        gateway = ModelGateway(catalog=catalog)
        result = gateway.invoke(
            _spec(TaskKind.SCREENING, input_tokens=100, output_tokens=50),
            prompt="x" * 400,  # ~100 tokens
        )
        expected = catalog.estimate_cost_cents(
            result.invocation.model_id,
            input_tokens=result.invocation.usage.input_tokens,
            output_tokens=result.invocation.usage.output_tokens,
        )
        self.assertEqual(result.invocation.usage.cost_cents, expected)

    def test_prompt_template_version_recorded(self) -> None:
        gateway = ModelGateway(prompt_template_version="v2-test")
        result = gateway.invoke(
            _spec(TaskKind.EVIDENCE_AUDIT),
            prompt="Audit evidence.",
        )
        self.assertEqual(result.invocation.prompt_template_version, "v2-test")


# ===========================================================================
# Adversarial tests
# ===========================================================================


class ModelGatewayAdversarialTests(unittest.TestCase):
    """Verify budget downgrade and routing bypass cannot happen."""

    def test_budget_does_not_silently_downgrade(self) -> None:
        """When budget is insufficient, the router must NOT pick a cheaper
        model that violates the tier requirement — it must signal
        ``budget_ok=False`` and the Gateway must raise."""

        # high_reasoning task with tiny budget
        budget = BudgetLimit(scope="project", limit_cents=5, spent_cents=0)
        router = RouterAgent()
        decision = router.route(
            _spec(
                TaskKind.METHODOLOGY_CRITIC,
                risk_level=2,
                input_tokens=20_000,
                output_tokens=5_000,
            ),
            budget=budget,
        )
        self.assertFalse(decision.budget_ok)
        self.assertEqual(decision.tier, ModelTier.HIGH_REASONING)
        # The router did NOT downgrade to a cheaper model
        self.assertEqual(decision.model_id, "glm-5.2")

        # Gateway raises instead of calling provider
        gateway = ModelGateway()
        with self.assertRaises(BudgetExhaustedError):
            gateway.invoke(
                _spec(
                    TaskKind.METHODOLOGY_CRITIC,
                    risk_level=2,
                    input_tokens=20_000,
                    output_tokens=5_000,
                ),
                prompt="This must be blocked.",
                budget=budget,
            )

    def test_no_provider_bypass(self) -> None:
        """Every invocation must go through the Gateway's provider,
        producing a ModelInvocation with routing_decision attached."""

        gateway = ModelGateway()
        result = gateway.invoke(
            _spec(TaskKind.CITATION_AUDIT),
            prompt="Verify citations.",
        )
        inv = result.invocation
        # Must have routing decision
        self.assertIsInstance(inv.routing_decision, RoutingDecision)
        # Must have usage record
        self.assertGreater(inv.usage.total_tokens, 0)
        # Must have timestamp
        self.assertTrue(inv.timestamp)

    def test_high_risk_task_never_uses_cheap_model(self) -> None:
        """Risk_level >= 2 must always route to high_reasoning tier."""

        router = RouterAgent()
        high_risk_tasks = [
            TaskKind.STATISTICS_CRITIC,
            TaskKind.FINAL_COMPLIANCE_AUDIT,
        ]
        for task_kind in high_risk_tasks:
            decision = router.route(_spec(task_kind, risk_level=3))
            self.assertEqual(
                decision.tier,
                ModelTier.HIGH_REASONING,
                f"{task_kind} should be high_reasoning at risk=3",
            )

    def test_usage_log_is_tamper_evident(self) -> None:
        """UsageLog is frozen — appended invocations are immutable."""

        gateway = ModelGateway()
        gateway.invoke(
            _spec(TaskKind.SECTION_WRITING),
            prompt="Write something.",
        )
        inv = gateway.usage_log.invocations[0]
        with self.assertRaises(AttributeError):
            inv.status = "tampered"  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
