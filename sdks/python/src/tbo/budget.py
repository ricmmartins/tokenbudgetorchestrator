"""Budget management — tracks and enforces token/cost budgets per agent."""

from __future__ import annotations

import logging
import threading
import time
from enum import Enum

from pydantic import BaseModel, Field

from tbo.models import AgentBudget, BudgetPeriod, BudgetStatus

logger = logging.getLogger("tbo.budget")


class OnExceed(str, Enum):
    BLOCK = "block"
    FALLBACK = "fallback"
    ALERT = "alert"


class BudgetConfig(BaseModel):
    """Configuration for budget enforcement."""

    max_tokens: int | None = None
    max_cost_usd: float | None = None
    period: BudgetPeriod = BudgetPeriod.DAILY
    warning_threshold: float = Field(default=0.8, ge=0.0, le=1.0)
    # Safety margin for output token estimation uncertainty
    safety_margin: float = Field(default=0.15, ge=0.0, le=0.5)
    # What to do when budget is exceeded
    on_exceed: OnExceed = OnExceed.BLOCK
    fallback_model: str | None = None


class BudgetCheckResult(BaseModel):
    """Result of a budget check — tells caller what to do."""

    allowed: bool = True
    budget: AgentBudget
    fallback_model: str | None = None
    reason: str | None = None


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
        self._configs: dict[str, BudgetConfig] = {}
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
            self._configs[key] = config
            self._period_start[key] = time.time()
        return budget

    def check_budget(
        self, workspace: str, agent_id: str, estimated_input_tokens: int
    ) -> BudgetCheckResult:
        """Check if agent has budget for a call. Resets if period expired.

        Returns:
            BudgetCheckResult with allowed=True/False and optional fallback_model.

        Raises:
            BudgetExceededError: Only if on_exceed="block" and budget is exceeded.
        """
        key = f"{workspace}:{agent_id}"
        with self._lock:
            budget = self._budgets.get(key)
            if budget is None:
                return BudgetCheckResult(
                    allowed=True,
                    budget=AgentBudget(agent_id=agent_id, workspace=workspace),
                )

            config = self._configs.get(key)

            # Check if period has rolled over
            self._maybe_reset_period(key, budget)

            exceeded = False
            reason = None

            # Check token budget
            if budget.max_tokens is not None:
                remaining = budget.max_tokens - budget.used_tokens
                if estimated_input_tokens > remaining:
                    exceeded = True
                    reason = (
                        f"Requested ~{estimated_input_tokens} tokens, "
                        f"remaining {remaining} in {budget.period.value} period"
                    )
                else:
                    usage_ratio = budget.used_tokens / budget.max_tokens
                    if usage_ratio >= budget.warning_threshold:
                        budget.status = BudgetStatus.WARNING

            # Check cost budget
            if not exceeded and budget.max_cost_usd is not None:
                usage_ratio = budget.used_cost_usd / budget.max_cost_usd
                if usage_ratio >= 1.0:
                    exceeded = True
                    reason = (
                        f"Cost budget exhausted: ${budget.used_cost_usd:.2f} / "
                        f"${budget.max_cost_usd:.2f}"
                    )
                elif usage_ratio >= budget.warning_threshold:
                    budget.status = BudgetStatus.WARNING

            if not exceeded:
                return BudgetCheckResult(allowed=True, budget=budget)

            # Budget exceeded — decide action based on config
            budget.status = BudgetStatus.EXCEEDED

            if config and config.on_exceed == OnExceed.FALLBACK and config.fallback_model:
                logger.info(
                    f"Budget exceeded for '{agent_id}', falling back to {config.fallback_model}"
                )
                return BudgetCheckResult(
                    allowed=True,
                    budget=budget,
                    fallback_model=config.fallback_model,
                    reason=reason,
                )

            if config and config.on_exceed == OnExceed.ALERT:
                logger.warning(f"Budget exceeded for '{agent_id}': {reason}")
                return BudgetCheckResult(
                    allowed=True,
                    budget=budget,
                    reason=reason,
                )

            # Default: block
            raise BudgetExceededError(agent_id, budget, estimated_input_tokens)

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

    def get_budget(self, workspace: str, agent_id: str) -> AgentBudget | None:
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
