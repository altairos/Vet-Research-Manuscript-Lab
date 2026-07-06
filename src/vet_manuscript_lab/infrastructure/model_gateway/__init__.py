"""Model Gateway: unified LLM invocation, routing, cost tracking, and audit.

This package provides the deterministic Router Agent, pricing calculator,
and Model Gateway protocol that all LLM calls must pass through.

Key design principle: the Router is a **deterministic policy service**, not an
LLM agent. Model selection is a pure function of task spec, risk, budget, and
model capabilities — never delegated to another model.
"""

from vet_manuscript_lab.infrastructure.model_gateway.gateway import ModelGateway
from vet_manuscript_lab.infrastructure.model_gateway.pricing import PricingCatalog
from vet_manuscript_lab.infrastructure.model_gateway.router import RouterAgent
from vet_manuscript_lab.infrastructure.model_gateway.types import (
    AgentTaskSpec,
    BudgetLimit,
    ModelInvocation,
    ModelProfile,
    ModelTier,
    RoutingDecision,
    TaskKind,
    TokenUsageRecord,
    UsageLog,
)

__all__ = [
    "AgentTaskSpec",
    "BudgetLimit",
    "ModelGateway",
    "ModelInvocation",
    "ModelProfile",
    "ModelTier",
    "PricingCatalog",
    "RouterAgent",
    "RoutingDecision",
    "TaskKind",
    "TokenUsageRecord",
    "UsageLog",
]
