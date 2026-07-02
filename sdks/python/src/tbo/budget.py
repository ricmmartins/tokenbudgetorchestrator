"""Budget management — tracks and enforces token/cost budgets per agent."""

from __future__ import annotations

import threading
import time
from typing import Optional

from pydantic import BaseModel, Field

from tbo.models import AgentBudget, BudgetPeriod, BudgetStatus


class BudgetConfig(BaseModel):
    """Configuration for budget enforcement."""

    max_tokens: Optional[int] = None
    max_cost_usd: Optional[float] = None
    period: BudgetPeriod = BudgetPeriod.DAILY
    warning_threshold: float = Field(default=0.8, ge=0.0, le=1.0)
    # Safety margin for output token estimation uncertainty
    safety_margin: float = Field(default=0.15, ge=0.0, le=0.5)
    # What to do when budget is exceeded
    on_exceed: str = "block"  # "block" | "fallback" | "alert"
    fallback_model: Optional[str] = None


class BudgetExceededError(Exception):
    """Raised when a call would exceed the configured budget."""

    def __init__(self, agent_id: str, budget: AgentBudget, requested_tokens: int):
        self.agent_id = agent_id
        self.budget = budget
        self.requested_tokens = requested_tokens
        remaining = (budget.max_tokens or 0) - budget.used_tokens
        super().__init__(
            f"Budget exceeded for agent '{agent_id}': "
            f"requested ~{requested_tokens} tokens, "
            f"remaining {remaining} tokens in {budget.period.value} period"
        )


class BudgetManager:
    """Manages token budgets for agents. Thread-safe, local-first.

    In standalone mode (no TBO engine), budgets are tracked in-memory.
    With TBO engine, syncs with Redis-backed central budget store.
    """

    def __init__(self):
        self._budgets: dict[str, AgentBudget] = {}
        self._lock = threading.Lock()
        self._period_start: dict[str, float] = {}

    def register_agent(self, workspace: str, agent_id: str, config: BudgetConfig) -> AgentBudget:
        """Register an agent with a budget configuration."""
        key = f"{workspace}:{agent_id}"
        budget = AgentBudget(
            agent_id=agent_id,
            workspace=workspace,
            max_tokens=config.max_tokens,
            max_cost_usd=config.max_cost_usd,
            period=config.period,
            warning_threshold=config.warning_threshold,
        )
        with self._lock:
            self._budgets[key] = budget
            self._period_start[key] = time.time()
        return budget

    def check_budget(
        self, workspace: str, agent_id: str, estimated_input_tokens: int
    ) -> AgentBudget:
        """Check if agent has budget for a call. Resets if period expired.

        Args:
            workspace: Workspace identifier
            agent_id: Agent identifier
            estimated_input_tokens: Estimated tokens for the call

        Returns:
            Current budget state

        Raises:
            BudgetExceededError: If call would exceed budget and on_exceed="block"
        """
        key = f"{workspace}:{agent_id}"
        with self._lock:
            budget = self._budgets.get(key)
            if budget is None:
                # No budget configured = unlimited
                return AgentBudget(agent_id=agent_id, workspace=workspace)

            # Check if period has rolled over
            self._maybe_reset_period(key, budget)

            # Check token budget
            if budget.max_tokens is not None:
                remaining = budget.max_tokens - budget.used_tokens
                if estimated_input_tokens > remaining:
                    budget.status = BudgetStatus.EXCEEDED
                    raise BudgetExceededError(agent_id, budget, estimated_input_tokens)

                usage_ratio = budget.used_tokens / budget.max_tokens
                if usage_ratio >= budget.warning_threshold:
                    budget.status = BudgetStatus.WARNING

            # Check cost budget
            if budget.max_cost_usd is not None:
                usage_ratio = budget.used_cost_usd / budget.max_cost_usd
                if usage_ratio >= 1.0:
                    budget.status = BudgetStatus.EXCEEDED
                    raise BudgetExceededError(agent_id, budget, estimated_input_tokens)
                elif usage_ratio >= budget.warning_threshold:
                    budget.status = BudgetStatus.WARNING

            return budget

    def record_usage(
        self, workspace: str, agent_id: str, tokens_used: int, cost_usd: float
    ) -> AgentBudget:
        """Record actual usage after a call completes."""
        key = f"{workspace}:{agent_id}"
        with self._lock:
            budget = self._budgets.get(key)
            if budget is None:
                return AgentBudget(agent_id=agent_id, workspace=workspace)

            budget.used_tokens += tokens_used
            budget.used_cost_usd += cost_usd

            # Update status
            if budget.max_tokens and budget.used_tokens >= budget.max_tokens:
                budget.status = BudgetStatus.EXCEEDED
            elif budget.max_cost_usd and budget.used_cost_usd >= budget.max_cost_usd:
                budget.status = BudgetStatus.EXCEEDED

            return budget

    def get_budget(self, workspace: str, agent_id: str) -> Optional[AgentBudget]:
        """Get current budget state for an agent."""
        key = f"{workspace}:{agent_id}"
        with self._lock:
            return self._budgets.get(key)

    def _maybe_reset_period(self, key: str, budget: AgentBudget) -> None:
        """Reset counters if the budget period has rolled over."""
        start = self._period_start.get(key, time.time())
        elapsed = time.time() - start

        period_seconds = {
            BudgetPeriod.HOURLY: 3600,
            BudgetPeriod.DAILY: 86400,
            BudgetPeriod.WEEKLY: 604800,
            BudgetPeriod.MONTHLY: 2592000,
        }

        if elapsed >= period_seconds[budget.period]:
            budget.used_tokens = 0
            budget.used_cost_usd = 0.0
            budget.status = BudgetStatus.OK
            self._period_start[key] = time.time()
