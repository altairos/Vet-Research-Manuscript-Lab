"""Deterministic Router Agent — model selection as a pure policy function.

The Router is **not** an LLM.  It is a deterministic, replayable policy
service that maps ``(task_kind, risk_level, context_length, budget,
required_capabilities, fallback_order)`` to a ``RoutingDecision``.

Design rules enforced here:

1. **Risk upgrade**: tasks with ``risk_level >= 2`` are always upgraded
   to ``high_reasoning``, regardless of their default tier.
2. **Capability filter**: if the caller requires capabilities (e.g.
   ``"json_mode"``) the router skips models that lack them.
3. **Context window**: models whose ``context_window`` is smaller than
   the estimated input are skipped.
4. **Budget hard-stop**: when the estimated cost exceeds the remaining
   budget, ``budget_ok`` is set to ``False`` — the caller must request
   human approval.  The router **never** silently downgrades to a
   cheaper model that violates tier requirements.
5. **Deterministic rationale**: the explanation string is built from
   the same inputs every time, so identical specs produce identical
   decisions and explanations.
"""

from __future__ import annotations

from vet_manuscript_lab.infrastructure.model_gateway.pricing import (
    PricingCatalog,
    default_catalog,
)
from vet_manuscript_lab.infrastructure.model_gateway.types import (
    AgentTaskSpec,
    BudgetLimit,
    ModelProfile,
    ModelTier,
    RoutingDecision,
    TaskKind,
    default_tier_for_task,
)

# Risk threshold above which tasks are auto-upgraded to high_reasoning.
_RISK_UPGRADE_THRESHOLD = 2


class BudgetExhaustedError(Exception):
    """Raised when budget is exhausted and no override is given."""

    def __init__(self, budget: BudgetLimit, estimated_cents: int) -> None:
        super().__init__(
            f"Budget exhausted for scope '{budget.scope}': "
            f"spent {budget.spent_cents}c / limit {budget.limit_cents}c, "
            f"estimated {estimated_cents}c"
        )
        self.budget = budget
        self.estimated_cents = estimated_cents


class NoEligibleModelError(Exception):
    """Raised when no model satisfies the task requirements."""

    def __init__(self, task_kind: TaskKind, reason: str) -> None:
        super().__init__(f"No eligible model for task '{task_kind.value}': {reason}")
        self.task_kind = task_kind
        self.reason = reason


class RouterAgent:
    """Deterministic routing policy service.

    Call ``route(task_spec, budget=...)`` to get a ``RoutingDecision``.
    The decision is reproducible: same catalog + same spec → same output.
    """

    def __init__(self, catalog: PricingCatalog | None = None) -> None:
        self._catalog = catalog or default_catalog()

    def route(
        self,
        task: AgentTaskSpec,
        *,
        budget: BudgetLimit | None = None,
    ) -> RoutingDecision:
        """Produce a routing decision for the given task spec.

        Raises ``BudgetExhaustedError`` if budget is exhausted and no
        eligible model fits within the remaining ceiling.
        Raises ``NoEligibleModelError`` if no model in the catalog
        satisfies the capability/context requirements.
        """

        tier = self._resolve_tier(task)
        candidates = self._filter_candidates(tier, task)

        if not candidates:
            # Try upgrading one tier before giving up
            tier = self._upgrade_tier(tier)
            candidates = self._filter_candidates(tier, task)

        if not candidates:
            raise NoEligibleModelError(
                task.task_kind,
                f"no model in tier '{tier.value}' satisfies "
                f"capabilities={set(task.required_capabilities)} "
                f"context>={task.estimated_input_tokens}",
            )

        # Pick primary model (first in fallback order that passes filters)
        primary = candidates[0]
        fallback_chain = tuple(c.model_id for c in candidates[1:])

        estimated_cost = self._estimate_cost(task, primary)

        budget_ok = True
        if budget is not None:
            if budget.is_exhausted:
                raise BudgetExhaustedError(budget, estimated_cost)
            if budget.remaining_cents < estimated_cost:
                budget_ok = False

        rationale = self._build_rationale(task, tier, primary, budget_ok)

        return RoutingDecision(
            model_id=primary.model_id,
            provider=primary.provider,
            tier=tier,
            rationale=rationale,
            estimated_cost_cents=estimated_cost,
            budget_ok=budget_ok,
            fallback_chain=fallback_chain,
        )

    def _resolve_tier(self, task: AgentTaskSpec) -> ModelTier:
        """Determine the effective tier, applying risk upgrade."""

        base_tier = default_tier_for_task(task.task_kind)
        if task.risk_level >= _RISK_UPGRADE_THRESHOLD:
            return ModelTier.HIGH_REASONING
        return base_tier

    def _filter_candidates(
        self, tier: ModelTier, task: AgentTaskSpec
    ) -> list[ModelProfile]:
        """Return models that satisfy capability + context needs.

        Models are drawn from the fallback chain for ``tier`` and any
        higher tier, so capability-driven upgrades work seamlessly.
        """

        # Gather chains for the resolved tier and all higher tiers
        all_model_ids: list[str] = []
        seen: set[str] = set()
        for t in self._tier_and_above(tier):
            for mid in task.fallback_order or self._catalog.get_fallback_chain(t):
                if mid not in seen:
                    all_model_ids.append(mid)
                    seen.add(mid)

        result: list[ModelProfile] = []
        for model_id in all_model_ids:
            try:
                profile = self._catalog.get_profile(model_id)
            except Exception:
                continue
            if not task.required_capabilities.issubset(profile.capabilities):
                continue
            if profile.context_window < task.estimated_input_tokens:
                continue
            if profile.max_output_tokens < task.estimated_output_tokens:
                continue
            result.append(profile)
        return result

    @staticmethod
    def _tier_and_above(tier: ModelTier) -> list[ModelTier]:
        """Return ``tier`` and all higher tiers in upgrade order."""

        order = [
            ModelTier.CHEAP_BATCH,
            ModelTier.BALANCED_WRITE,
            ModelTier.HIGH_REASONING,
        ]
        idx = order.index(tier)
        return order[idx:]

    def _upgrade_tier(self, current: ModelTier) -> ModelTier:
        """Upgrade one tier level (cheap → balanced → high)."""

        if current == ModelTier.CHEAP_BATCH:
            return ModelTier.BALANCED_WRITE
        return ModelTier.HIGH_REASONING

    def _estimate_cost(self, task: AgentTaskSpec, profile: ModelProfile) -> int:
        """Estimate cost in cents for the primary model."""

        return self._catalog.estimate_cost_cents(
            profile.model_id,
            input_tokens=task.estimated_input_tokens,
            output_tokens=task.estimated_output_tokens,
        )

    def _build_rationale(
        self,
        task: AgentTaskSpec,
        tier: ModelTier,
        profile: ModelProfile,
        budget_ok: bool,
    ) -> str:
        """Build a deterministic, human-readable explanation.

        This is the only "explanation" capability — it is a pure string
        builder, not an LLM call.
        """

        parts: list[str] = []
        parts.append(f"Task '{task.task_kind.value}' → tier '{tier.value}'")
        if task.risk_level >= _RISK_UPGRADE_THRESHOLD:
            parts.append(
                f"(risk_level={task.risk_level} triggers upgrade to high_reasoning)"
            )
        parts.append(f"→ model '{profile.model_id}' ({profile.provider})")
        if not budget_ok:
            parts.append("[BUDGET WARNING: estimated cost exceeds remaining budget]")
        return " ".join(parts)


def route_task(
    task: AgentTaskSpec,
    *,
    budget: BudgetLimit | None = None,
    catalog: PricingCatalog | None = None,
) -> RoutingDecision:
    """Convenience function: route without instantiating RouterAgent."""

    return RouterAgent(catalog=catalog).route(task, budget=budget)
