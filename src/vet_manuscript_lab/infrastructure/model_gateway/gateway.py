"""Model Gateway: unified entry point for all LLM invocations.

The Gateway enforces three invariants:

1. **No bypass**: every LLM call goes through ``invoke()``, which routes
   via the deterministic Router, calls the provider, and records the full
   ``ModelInvocation``.
2. **Budget enforcement**: if the Router returns ``budget_ok=False`` the
   Gateway raises ``BudgetExhaustedError`` instead of calling the provider.
3. **Fallback with provenance**: if the primary provider fails, the
   Gateway tries fallback models from the decision's ``fallback_chain``
   and records which model was the fallback source.

For MVP all providers are ``MockProvider`` instances that return
deterministic output.  Real provider adapters will be added in Phase 3.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from vet_manuscript_lab.domain.conventions import new_id, sha256_bytes, utc_now
from vet_manuscript_lab.infrastructure.model_gateway.pricing import (
    PricingCatalog,
    default_catalog,
)
from vet_manuscript_lab.infrastructure.model_gateway.router import (
    BudgetExhaustedError,
    RouterAgent,
)
from vet_manuscript_lab.infrastructure.model_gateway.types import (
    AgentTaskSpec,
    BudgetLimit,
    ModelInvocation,
    PromptInputManifest,
    PromptTemplate,
    TokenUsageRecord,
    UsageLog,
)


class ModelProvider(Protocol):
    """Protocol every provider adapter must satisfy."""

    def invoke(
        self,
        model_id: str,
        prompt: str,
        *,
        max_tokens: int,
    ) -> dict[str, Any]:
        """Return ``{"text": str, "input_tokens": int, "output_tokens": int}``.

        Raise ``ProviderError`` on failure.
        """
        ...


class ProviderError(Exception):
    """Raised when a provider call fails (network, auth, parse, etc.)."""


@dataclass(slots=True)
class MockProvider:
    """Deterministic mock provider for offline development.

    Returns a fixed echo of the input with predictable token counts.
    Optionally raises on the first ``fail_first`` calls to test fallback.
    """

    fail_first: int = 0
    _call_count: int = field(default=0, init=False, repr=False)

    def invoke(
        self,
        model_id: str,
        prompt: str,
        *,
        max_tokens: int,
    ) -> dict[str, Any]:
        self._call_count += 1
        if self._call_count <= self.fail_first:
            raise ProviderError(f"MockProvider simulated failure {self._call_count}")
        # Deterministic token counts: ~4 chars per token
        input_tokens = max(1, len(prompt) // 4)
        output_text = f"[{model_id}] Processed: {prompt[:80]}"
        output_tokens = max(1, len(output_text) // 4)
        return {
            "text": output_text,
            "input_tokens": input_tokens,
            "output_tokens": min(output_tokens, max_tokens),
        }


class ModelGateway:
    """Unified LLM invocation entry point with routing + provenance.

    Usage::

        gateway = ModelGateway()
        result = gateway.invoke(task_spec, prompt="...", budget=budget)
        print(result.invocation)   # ModelInvocation with full provenance
        print(gateway.usage_log)   # UsageLog (AI_USAGE_LOG artifact)
    """

    def __init__(
        self,
        *,
        catalog: PricingCatalog | None = None,
        router: RouterAgent | None = None,
        provider: ModelProvider | None = None,
        prompt_template_version: str = "v1",
    ) -> None:
        self._catalog = catalog or default_catalog()
        self._router = router or RouterAgent(self._catalog)
        self._provider: ModelProvider = provider or MockProvider()
        self._prompt_template_version = prompt_template_version
        self._invocations: list[ModelInvocation] = []

    @property
    def usage_log(self) -> UsageLog:
        """Return the accumulated ``AI_USAGE_LOG`` artifact data."""

        return UsageLog(invocations=list(self._invocations))

    @property
    def total_cost_cents(self) -> int:
        return sum(inv.usage.cost_cents for inv in self._invocations)

    def invoke(
        self,
        task: AgentTaskSpec,
        *,
        prompt: str,
        budget: BudgetLimit | None = None,
        prompt_template: PromptTemplate | None = None,
        output_schema_version: str = "",
        input_artifact_refs: PromptInputManifest | None = None,
        validator_version: str = "",
    ) -> GatewayResult:
        """Route → call provider → record invocation.

        Returns a ``GatewayResult`` containing the output text and the
        full ``ModelInvocation`` provenance record.

        Governance parameters (Phase B):

        - ``prompt_template``: versioned prompt identity (template_id,
          version, template_hash).  When omitted, falls back to the
          gateway's default ``prompt_template_version``.
        - ``output_schema_version``: version of the output schema
          validator used to check the provider response.
        - ``input_artifact_refs``: manifest of input artifacts consumed
          by the prompt rendering, enabling reproducibility audits.
        - ``validator_version``: version of the structured-output
          validator that checked the response.

        Raises ``BudgetExhaustedError`` if budget is insufficient.
        """

        decision = self._router.route(task, budget=budget)

        if not decision.budget_ok:
            raise BudgetExhaustedError(
                budget or BudgetLimit(scope="unknown", limit_cents=0),
                decision.estimated_cost_cents,
            )

        input_hash = sha256_bytes(prompt.encode())
        rendered_prompt_hash = sha256_bytes(prompt.encode())

        # Resolve governance fields
        template_id: str | None = None
        template_version = self._prompt_template_version
        if prompt_template is not None:
            template_id = prompt_template.template_id
            template_version = prompt_template.version

        artifact_ids: tuple[str, ...] = ()
        artifact_hashes: tuple[str, ...] = ()
        if input_artifact_refs is not None:
            artifact_ids = input_artifact_refs.artifact_ids
            artifact_hashes = input_artifact_refs.artifact_hashes

        # Try primary model, then fallback chain
        models_to_try: list[tuple[str, str | None]] = [(decision.model_id, None)]
        for fb_model in decision.fallback_chain:
            models_to_try.append((fb_model, decision.model_id))

        last_error: str | None = None
        for model_id, fallback_from in models_to_try:
            try:
                profile = self._catalog.get_profile(model_id)
                response = self._provider.invoke(
                    model_id,
                    prompt,
                    max_tokens=profile.max_output_tokens,
                )
            except ProviderError as exc:
                last_error = str(exc)
                continue

            usage = self._build_usage(model_id, response, task)
            status = "fallback" if fallback_from is not None else "success"
            invocation = ModelInvocation(
                invocation_id=new_id(),
                task_kind=task.task_kind,
                model_id=model_id,
                provider=profile.provider,
                tier=profile.tier,
                prompt_template_version=template_version,
                input_hash=input_hash,
                routing_decision=decision,
                usage=usage,
                status=status,
                fallback_from=fallback_from,
                error_message=None,
                timestamp=utc_now(),
                prompt_template_id=template_id,
                rendered_prompt_hash=rendered_prompt_hash,
                output_schema_version=output_schema_version,
                input_artifact_ids=artifact_ids,
                input_artifact_hashes=artifact_hashes,
                validator_version=validator_version,
            )
            self._invocations.append(invocation)

            return GatewayResult(
                text=response["text"],
                invocation=invocation,
            )

        # All models failed — record the failure
        fail_invocation = ModelInvocation(
            invocation_id=new_id(),
            task_kind=task.task_kind,
            model_id=decision.model_id,
            provider=decision.provider,
            tier=decision.tier,
            prompt_template_version=template_version,
            input_hash=input_hash,
            routing_decision=decision,
            usage=TokenUsageRecord(
                model_id=decision.model_id,
                provider=decision.provider,
                input_tokens=0,
                output_tokens=0,
                cost_cents=0,
            ),
            status="failed",
            fallback_from=None,
            error_message=last_error,
            timestamp=utc_now(),
            prompt_template_id=template_id,
            rendered_prompt_hash=rendered_prompt_hash,
            output_schema_version=output_schema_version,
            input_artifact_ids=artifact_ids,
            input_artifact_hashes=artifact_hashes,
            validator_version=validator_version,
        )
        self._invocations.append(fail_invocation)
        raise ProviderError(
            f"All models failed for task '{task.task_kind.value}': {last_error}"
        )

    def _build_usage(
        self,
        model_id: str,
        response: dict[str, Any],
        task: AgentTaskSpec,
    ) -> TokenUsageRecord:
        """Compute actual cost from token counts in the response."""

        input_tokens = int(response.get("input_tokens", 0))
        output_tokens = int(response.get("output_tokens", 0))
        cost_cents = self._catalog.estimate_cost_cents(
            model_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        return TokenUsageRecord(
            model_id=model_id,
            provider=self._catalog.get_profile(model_id).provider,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_cents=cost_cents,
        )


@dataclass(frozen=True, slots=True)
class GatewayResult:
    """Output of a successful Gateway invocation."""

    text: str
    invocation: ModelInvocation
