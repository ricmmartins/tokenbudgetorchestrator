"""Data models for TBO SDK."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Provider(str, Enum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"


class BudgetPeriod(str, Enum):
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class BudgetStatus(str, Enum):
    OK = "ok"
    WARNING = "warning"  # Above threshold (e.g., 80%)
    EXCEEDED = "exceeded"
    BLOCKED = "blocked"


class AgentBudget(BaseModel):
    """Budget allocation for a specific agent."""

    agent_id: str
    workspace: str
    max_tokens: Optional[int] = None
    max_cost_usd: Optional[float] = None
    period: BudgetPeriod = BudgetPeriod.DAILY
    used_tokens: int = 0
    used_cost_usd: float = 0.0
    status: BudgetStatus = BudgetStatus.OK
    warning_threshold: float = Field(default=0.8, ge=0.0, le=1.0)


class UsageRecord(BaseModel):
    """Single LLM call usage record — metadata only, never content."""

    timestamp: datetime = Field(default_factory=datetime.utcnow)
    workspace: str
    agent_id: str
    provider: Provider
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    latency_ms: float
    policy_applied: Optional[str] = None
    model_routed_to: Optional[str] = None  # If rerouted by policy
    budget_remaining_tokens: Optional[int] = None
    budget_remaining_usd: Optional[float] = None


class ModelPricing(BaseModel):
    """Pricing per million tokens for a model."""

    model: str
    provider: Provider
    input_per_million: float
    output_per_million: float
    # Cache-related pricing
    cache_write_per_million: Optional[float] = None
    cache_read_per_million: Optional[float] = None


# Pricing table — updated as of 2026. SDK ships with defaults, user can override.
DEFAULT_PRICING: list[ModelPricing] = [
    # Anthropic
    ModelPricing(
        model="claude-sonnet-4-20250514",
        provider=Provider.ANTHROPIC,
        input_per_million=3.0,
        output_per_million=15.0,
    ),
    ModelPricing(
        model="claude-haiku-3-5-20241022",
        provider=Provider.ANTHROPIC,
        input_per_million=0.80,
        output_per_million=4.0,
    ),
    ModelPricing(
        model="claude-opus-4-20250514",
        provider=Provider.ANTHROPIC,
        input_per_million=15.0,
        output_per_million=75.0,
    ),
    # OpenAI
    ModelPricing(
        model="gpt-4o",
        provider=Provider.OPENAI,
        input_per_million=2.50,
        output_per_million=10.0,
    ),
    ModelPricing(
        model="gpt-4o-mini",
        provider=Provider.OPENAI,
        input_per_million=0.15,
        output_per_million=0.60,
    ),
    ModelPricing(
        model="o1",
        provider=Provider.OPENAI,
        input_per_million=15.0,
        output_per_million=60.0,
    ),
]
