"""Token pricing catalog and budget estimation.

All prices are in **USD cents per million tokens** to avoid float drift.
The catalog is a plain dict so it can be serialised, diffed, and versioned.
"""

from __future__ import annotations

from dataclasses import dataclass

from vet_manuscript_lab.infrastructure.model_gateway.types import (
    ModelProfile,
    ModelTier,
)


@dataclass(frozen=True, slots=True)
class ModelPricing:
    """Per-model token prices in cents per million tokens.

    A value of ``0`` means the component is free (e.g. cached input on
    providers that don't charge for cache hits).
    """

    input_per_million_cents: int
    output_per_million_cents: int
    cached_input_per_million_cents: int = 0
    reasoning_surcharge_per_million_cents: int = 0

    def estimate_cost_cents(
        self,
        *,
        input_tokens: int,
        output_tokens: int,
        cached_input_tokens: int = 0,
        reasoning_tokens: int = 0,
    ) -> int:
        """Return estimated cost in integer cents.

        Rounding is always floor (truncation) so estimates never over-promise.
        """

        input_cost = (input_tokens * self.input_per_million_cents) // 1_000_000
        output_cost = (output_tokens * self.output_per_million_cents) // 1_000_000
        cached_cost = (
            cached_input_tokens * self.cached_input_per_million_cents
        ) // 1_000_000
        reasoning_cost = (
            reasoning_tokens * self.reasoning_surcharge_per_million_cents
        ) // 1_000_000
        return input_cost + output_cost + cached_cost + reasoning_cost


# ---------------------------------------------------------------------------
# Fixture pricing table (mock values for MVP — replace with real catalog later)
# ---------------------------------------------------------------------------

_DEFAULT_PRICING: dict[str, ModelPricing] = {
    # DeepSeek V4 Flash — cheap tier
    "deepseek-v4-flash": ModelPricing(
        input_per_million_cents=14,  # $0.14 / M
        output_per_million_cents=28,  # $0.28 / M
        cached_input_per_million_cents=4,
    ),
    # DeepSeek V4 Pro — balanced tier
    "deepseek-v4-pro": ModelPricing(
        input_per_million_cents=110,  # $1.10 / M
        output_per_million_cents=280,  # $2.80 / M
        cached_input_per_million_cents=28,
    ),
    # GLM 5.2 — high reasoning tier
    "glm-5.2": ModelPricing(
        input_per_million_cents=200,  # $2.00 / M
        output_per_million_cents=600,  # $6.00 / M
        cached_input_per_million_cents=50,
        reasoning_surcharge_per_million_cents=300,
    ),
}

_DEFAULT_PROFILES: dict[str, ModelProfile] = {
    "deepseek-v4-flash": ModelProfile(
        model_id="deepseek-v4-flash",
        provider="deepseek",
        tier=ModelTier.CHEAP_BATCH,
        context_window=128_000,
        max_output_tokens=8_192,
        capabilities=frozenset({"json_mode", "tool_use"}),
    ),
    "deepseek-v4-pro": ModelProfile(
        model_id="deepseek-v4-pro",
        provider="deepseek",
        tier=ModelTier.BALANCED_WRITE,
        context_window=128_000,
        max_output_tokens=8_192,
        capabilities=frozenset({"json_mode", "tool_use"}),
    ),
    "glm-5.2": ModelProfile(
        model_id="glm-5.2",
        provider="zhipu",
        tier=ModelTier.HIGH_REASONING,
        context_window=200_000,
        max_output_tokens=16_384,
        capabilities=frozenset({"json_mode", "tool_use", "vision"}),
    ),
}

# Default fallback order within each tier (first = primary, rest = fallbacks)
_DEFAULT_FALLBACK: dict[ModelTier, tuple[str, ...]] = {
    ModelTier.CHEAP_BATCH: ("deepseek-v4-flash",),
    ModelTier.BALANCED_WRITE: ("deepseek-v4-pro", "glm-5.2"),
    ModelTier.HIGH_REASONING: ("glm-5.2", "deepseek-v4-pro"),
}


class PricingCatalog:
    """Read-only lookup for model profiles and pricing.

    The catalog is intentionally a plain object (not a database table)
    so it can be frozen at deployment time and version-controlled.
    """

    def __init__(
        self,
        *,
        pricing: dict[str, ModelPricing] | None = None,
        profiles: dict[str, ModelProfile] | None = None,
        fallback: dict[ModelTier, tuple[str, ...]] | None = None,
    ) -> None:
        self._pricing = dict(pricing or _DEFAULT_PRICING)
        self._profiles = dict(profiles or _DEFAULT_PROFILES)
        self._fallback = dict(fallback or _DEFAULT_FALLBACK)

    def get_pricing(self, model_id: str) -> ModelPricing:
        try:
            return self._pricing[model_id]
        except KeyError:
            raise UnknownModelError(model_id) from None

    def get_profile(self, model_id: str) -> ModelProfile:
        try:
            return self._profiles[model_id]
        except KeyError:
            raise UnknownModelError(model_id) from None

    def get_fallback_chain(self, tier: ModelTier) -> tuple[str, ...]:
        return self._fallback.get(tier, ())

    def models_by_tier(self, tier: ModelTier) -> list[ModelProfile]:
        return [p for p in self._profiles.values() if p.tier == tier]

    def estimate_cost_cents(
        self,
        model_id: str,
        *,
        input_tokens: int,
        output_tokens: int,
        cached_input_tokens: int = 0,
        reasoning_tokens: int = 0,
    ) -> int:
        pricing = self.get_pricing(model_id)
        return pricing.estimate_cost_cents(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_input_tokens=cached_input_tokens,
            reasoning_tokens=reasoning_tokens,
        )


class UnknownModelError(Exception):
    """Raised when a model_id is not in the pricing catalog."""

    def __init__(self, model_id: str) -> None:
        super().__init__(f"Unknown model: {model_id}")
        self.model_id = model_id


def default_catalog() -> PricingCatalog:
    """Return the built-in catalog with fixture pricing."""

    return PricingCatalog()
