"""TBO Client — transparent wrapper for Anthropic/OpenAI with budget governance.

Usage:
    from tbo import TBOClient

    client = TBOClient(
        provider="anthropic",
        api_key="sk-ant-...",
        workspace="my-project",
        agent_id="support-bot",
        budget=BudgetConfig(max_tokens=100_000, period="daily"),
    )

    # Use exactly like the original Anthropic client
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[{"role": "user", "content": "Hello"}]
    )
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from tbo.budget import BudgetConfig, BudgetExceededError, BudgetManager
from tbo.drift import DriftConfig, DriftDetector
from tbo.models import DEFAULT_PRICING, ModelPricing, Provider, UsageRecord
from tbo.policy import Policy, PolicyAction, PolicyEvaluator
from tbo.telemetry import TelemetryCollector
from tbo.tokenizer import TokenCounter


class TBOClient:
    """Transparent wrapper that adds budget governance to LLM clients.

    Intercepts calls to count tokens, evaluate policies, enforce budgets,
    and emit telemetry — all without sending prompt content externally.
    """

    def __init__(
        self,
        provider: str,
        api_key: str | None = None,
        workspace: str = "default",
        agent_id: str = "default",
        budget: BudgetConfig | None = None,
        policies: list[Policy] | None = None,
        engine_url: str | None = None,
        metadata: dict | None = None,
        pricing: list[ModelPricing] | None = None,
        drift: DriftConfig | None = None,
        on_drift: callable | None = None,
        **provider_kwargs: Any,
    ):
        """Initialize TBO wrapper.

        Args:
            provider: "anthropic" or "openai"
            api_key: Provider API key (stays local, never sent to TBO)
            workspace: Workspace/project identifier for budget grouping
            agent_id: Unique identifier for this agent
            budget: Budget configuration (limits, period, actions)
            policies: List of routing policies to apply
            engine_url: Optional TBO engine URL for telemetry aggregation
            metadata: Default metadata attached to every call (task_type, etc.)
            pricing: Custom pricing table (defaults to built-in)
            drift: Drift detection config (window size, sensitivity, cooldown)
            on_drift: Callback fired when token consumption drift is detected
            **provider_kwargs: Additional args passed to the underlying client
        """
        self._provider = Provider(provider)
        self._workspace = workspace
        self._agent_id = agent_id
        self._default_metadata = metadata or {}

        # Initialize components
        self._token_counter = TokenCounter(self._provider)
        self._budget_manager = BudgetManager()
        self._policy_evaluator = PolicyEvaluator()
        self._telemetry = TelemetryCollector(engine_url=engine_url)
        self._drift_detector: DriftDetector | None = None

        if drift:
            self._drift_detector = DriftDetector(config=drift, on_drift=on_drift)

        # Build pricing lookup
        pricing_list = pricing or DEFAULT_PRICING
        self._pricing = {p.model: p for p in pricing_list}

        # Register budget if configured
        if budget:
            self._budget_manager.register_agent(workspace, agent_id, budget)

        # Register policies
        if policies:
            for policy in policies:
                self._policy_evaluator.add_policy(policy)

        # Create the underlying provider client
        self._client = self._create_provider_client(api_key, **provider_kwargs)

        # Expose provider-compatible interface
        self.messages = _MessagesAPI(self)

    def _create_provider_client(self, api_key: str | None, **kwargs: Any) -> Any:
        """Create the underlying LLM provider client."""
        if self._provider == Provider.ANTHROPIC:
            try:
                import anthropic

                return anthropic.Anthropic(api_key=api_key, **kwargs)
            except ImportError:
                raise ImportError(
                    "anthropic package required. Install with: pip install tbo[anthropic]"
                )
        elif self._provider == Provider.OPENAI:
            try:
                import openai

                return openai.OpenAI(api_key=api_key, **kwargs)
            except ImportError:
                raise ImportError(
                    "openai package required. Install with: pip install tbo[openai]"
                )
        raise ValueError(f"Unsupported provider: {self._provider}")

    def _pre_call(
        self, model: str, messages: list, metadata: dict, max_tokens: int
    ) -> tuple[str, int]:
        """Pre-call hook: count tokens, check budget, evaluate policies.

        Returns:
            Tuple of (final_model, estimated_input_tokens)
        """
        # 1. Count input tokens locally
        estimated_input = self._token_counter.count(messages)

        # 2. Evaluate policies (may reroute model)
        merged_metadata = {**self._default_metadata, **metadata}
        merged_metadata["agent_id"] = self._agent_id
        merged_metadata["original_model"] = model

        decision = self._policy_evaluator.evaluate(model, merged_metadata)

        if decision.action == PolicyAction.BLOCK:
            raise BudgetExceededError(
                self._agent_id,
                self._budget_manager.get_budget(self._workspace, self._agent_id),
                estimated_input,
            )

        final_model = decision.routed_model

        # 3. Check budget (with safety margin for output token estimation uncertainty)
        safety_margin = 0.5
        budget_config = self._budget_manager._configs.get(
            self._budget_manager._make_key(self._workspace, self._agent_id)
        )
        if budget_config and budget_config.safety_margin:
            safety_margin = budget_config.safety_margin
        estimated_total = estimated_input + int(max_tokens * safety_margin)
        budget_result = self._budget_manager.check_budget(
            self._workspace, self._agent_id, estimated_total
        )

        # If budget says fallback, override model selection
        if budget_result.fallback_model:
            final_model = budget_result.fallback_model

        return final_model, estimated_input

    def _post_call(
        self,
        model: str,
        routed_model: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: float,
        policy_applied: str | None = None,
    ) -> None:
        """Post-call hook: record usage and emit telemetry."""
        total_tokens = input_tokens + output_tokens

        # Calculate cost
        pricing = self._pricing.get(routed_model)
        cost = 0.0
        if pricing:
            cost = (
                (input_tokens / 1_000_000) * pricing.input_per_million
                + (output_tokens / 1_000_000) * pricing.output_per_million
            )

        # Record against budget
        self._budget_manager.record_usage(self._workspace, self._agent_id, total_tokens, cost)

        # Check for drift (token consumption trending up)
        if self._drift_detector:
            self._drift_detector.record(self._workspace, self._agent_id, total_tokens)

        # Emit telemetry (async, never blocks)
        budget = self._budget_manager.get_budget(self._workspace, self._agent_id)
        record = UsageRecord(
            timestamp=datetime.now(timezone.utc),
            workspace=self._workspace,
            agent_id=self._agent_id,
            provider=self._provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            estimated_cost_usd=cost,
            latency_ms=latency_ms,
            policy_applied=policy_applied,
            model_routed_to=routed_model if routed_model != model else None,
            budget_remaining_tokens=(
                (budget.max_tokens - budget.used_tokens) if budget and budget.max_tokens else None
            ),
            budget_remaining_usd=(
                (budget.max_cost_usd - budget.used_cost_usd)
                if budget and budget.max_cost_usd
                else None
            ),
        )
        self._telemetry.record(record)


class _MessagesAPI:
    """Mimics the provider's messages API interface."""

    def __init__(self, tbo_client: TBOClient):
        self._tbo = tbo_client

    def create(
        self,
        model: str,
        messages: list,
        max_tokens: int = 1024,
        metadata: dict | None = None,
        **kwargs: Any,
    ) -> Any:
        """Create a message — with TBO budget governance applied transparently.

        Args:
            model: Model to use (may be rerouted by policy)
            messages: Message list (same format as provider)
            max_tokens: Max output tokens
            metadata: Optional call metadata for policy evaluation
            **kwargs: All other args passed to provider unchanged

        Returns:
            Provider response object (unchanged)
        """
        call_metadata = metadata or {}

        # Pre-call: policy + budget check
        final_model, estimated_input = self._tbo._pre_call(
            model, messages, call_metadata, max_tokens
        )

        # Execute the actual LLM call
        start = time.perf_counter()

        if self._tbo._provider == Provider.ANTHROPIC:
            response = self._tbo._client.messages.create(
                model=final_model,
                messages=messages,
                max_tokens=max_tokens,
                **kwargs,
            )
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
        elif self._tbo._provider == Provider.OPENAI:
            response = self._tbo._client.chat.completions.create(
                model=final_model,
                messages=messages,
                max_tokens=max_tokens,
                **kwargs,
            )
            input_tokens = response.usage.prompt_tokens
            output_tokens = response.usage.completion_tokens
        else:
            raise ValueError(f"Unsupported provider: {self._tbo._provider}")

        latency_ms = (time.perf_counter() - start) * 1000

        # Post-call: record usage + telemetry
        merged_metadata = {**self._tbo._default_metadata, **call_metadata}
        merged_metadata["agent_id"] = self._tbo._agent_id
        merged_metadata["original_model"] = model
        decision = self._tbo._policy_evaluator.evaluate(model, merged_metadata)
        self._tbo._post_call(
            model=model,
            routed_model=final_model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            policy_applied=decision.rule_applied,
        )

        return response
