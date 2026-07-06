# ADR-0007: Model Gateway and Router Agent

- Status: accepted
- Date: 2026-07-06

## Context

Phases 3-5 introduce LLM-driven nodes: Methodology Critic, Statistics Critic,
section writing, reviewer, revision, and final compliance audit. Each has
different risk, cost, and capability requirements. If every node calls model
providers directly, the system loses auditability, budget control, and the
ability to enforce routing policies.

The DEVELOPMENT.md Phase 2.5 section specifies that all model calls must go
through a single Gateway with a deterministic Router Agent that selects models
based on task type, risk, context length, budget, and capabilities.

## Decision

Implement a three-layer model invocation architecture:

1. **Router Agent** (`infrastructure/model_gateway/router.py`): a pure,
   deterministic policy function. Given an `AgentTaskSpec` (task kind, risk
   level, context length, budget, required capabilities), it produces a
   `RoutingDecision` with model tier, model ID, provider, fallback chain, and
   a human-readable rationale. The router is **not** an LLM; it is a testable,
   reproducible, auditable pure function.

2. **Model Gateway** (`infrastructure/model_gateway/gateway.py`): the single
   entry point for all LLM calls. It takes an `AgentTaskSpec` + prompt,
   routes via the Router, invokes the provider, records `ModelInvocation`
   provenance (prompt template version, model ID, tokens, cost, fallback
   chain, status), and returns a `GatewayResult`. Budget is a hard
   constraint: exceeding it raises rather than silently downgrading.

3. **Provider Protocol** (`ModelProvider`): pluggable backends. The default
   `MockProvider` returns deterministic output for testing. Real providers
   (DeepSeek, GLM) are added later without changing Gateway or Router code.

### Task-to-tier mapping

| Tier | Models | Task kinds |
|---|---|---|
| cheap_batch | DeepSeek Flash | literature_search, screening, first_pass_extraction, format_conversion, schema_repair |
| balanced_write | DeepSeek Pro | evidence_audit, citation_audit, section_writing |
| high_reasoning | GLM 5.2 | methodology_critic, statistics_critic, reviewer, final_compliance_audit |

Risk level >= 2 automatically upgrades to high_reasoning regardless of task
kind default.

### Cost tracking

Every invocation is recorded in a `UsageLog` (AI_USAGE_LOG artifact). The log
includes:
- Per-invocation: model ID, provider, tier, status, cost (cents), tokens,
  fallback provenance.
- Aggregated: total cost, total tokens, fallback count, failure count.
- By-stage breakdown: `cost_report_by_stage()` groups invocations by task kind.

The UI displays usage summaries (invocations, cost, tokens, per-task breakdown)
in the Streamlit sidebar.

## Consequences

- No business node can bypass the Gateway to call a model provider directly.
- All model calls have full provenance for audit and reproducibility.
- Router decisions are deterministic and testable; the same inputs always
  produce the same routing.
- Budget overruns are hard failures, not silent downgrades.
- Adding a new provider requires only implementing the `ModelProvider` Protocol;
  no changes to Router, Gateway, or business logic.
- The mock provider enables full offline testing of LLM-dependent workflows.
