"""Tests for budget management."""

import pytest

from tbo.budget import BudgetConfig, BudgetExceededError, BudgetManager, OnExceed
from tbo.models import BudgetPeriod, BudgetStatus


class TestBudgetManager:
    def setup_method(self):
        self.manager = BudgetManager()

    def test_register_agent(self):
        config = BudgetConfig(max_tokens=100_000, period=BudgetPeriod.DAILY)
        budget = self.manager.register_agent("workspace-1", "agent-a", config)

        assert budget.agent_id == "agent-a"
        assert budget.workspace == "workspace-1"
        assert budget.max_tokens == 100_000
        assert budget.used_tokens == 0
        assert budget.status == BudgetStatus.OK

    def test_check_budget_within_limit(self):
        config = BudgetConfig(max_tokens=100_000)
        self.manager.register_agent("ws", "agent", config)

        result = self.manager.check_budget("ws", "agent", 5_000)
        assert result.allowed is True
        assert result.budget.status == BudgetStatus.OK

    def test_check_budget_exceeds_limit_blocks(self):
        config = BudgetConfig(max_tokens=10_000, on_exceed=OnExceed.BLOCK)
        self.manager.register_agent("ws", "agent", config)

        with pytest.raises(BudgetExceededError) as exc_info:
            self.manager.check_budget("ws", "agent", 15_000)

        assert "agent" in str(exc_info.value)
        assert exc_info.value.requested_tokens == 15_000

    def test_check_budget_exceeds_limit_fallback(self):
        config = BudgetConfig(
            max_tokens=10_000,
            on_exceed=OnExceed.FALLBACK,
            fallback_model="claude-haiku-3-5-20241022",
        )
        self.manager.register_agent("ws", "agent", config)

        result = self.manager.check_budget("ws", "agent", 15_000)
        assert result.allowed is True
        assert result.fallback_model == "claude-haiku-3-5-20241022"
        assert result.budget.status == BudgetStatus.EXCEEDED

    def test_check_budget_exceeds_limit_alert(self):
        config = BudgetConfig(max_tokens=10_000, on_exceed=OnExceed.ALERT)
        self.manager.register_agent("ws", "agent", config)

        result = self.manager.check_budget("ws", "agent", 15_000)
        assert result.allowed is True
        assert result.fallback_model is None
        assert result.reason is not None

    def test_budget_warning_threshold(self):
        config = BudgetConfig(max_tokens=10_000, warning_threshold=0.8)
        self.manager.register_agent("ws", "agent", config)

        # Use 8500 tokens (85% > 80% threshold)
        self.manager.record_usage("ws", "agent", 8_500, 0.05)

        result = self.manager.check_budget("ws", "agent", 500)
        assert result.budget.status == BudgetStatus.WARNING

    def test_record_usage(self):
        config = BudgetConfig(max_tokens=100_000, max_cost_usd=10.0)
        self.manager.register_agent("ws", "agent", config)

        budget = self.manager.record_usage("ws", "agent", 5_000, 0.05)
        assert budget.used_tokens == 5_000
        assert budget.used_cost_usd == 0.05

        budget = self.manager.record_usage("ws", "agent", 3_000, 0.03)
        assert budget.used_tokens == 8_000
        assert budget.used_cost_usd == 0.08

    def test_no_budget_configured_allows_all(self):
        # Agent without budget = unlimited
        result = self.manager.check_budget("ws", "unknown-agent", 999_999)
        assert result.allowed is True

    def test_cost_budget_exceeded_blocks(self):
        config = BudgetConfig(max_cost_usd=1.0, on_exceed=OnExceed.BLOCK)
        self.manager.register_agent("ws", "agent", config)

        self.manager.record_usage("ws", "agent", 50_000, 1.05)

        with pytest.raises(BudgetExceededError):
            self.manager.check_budget("ws", "agent", 1_000)

    def test_cost_budget_exceeded_fallback(self):
        config = BudgetConfig(
            max_cost_usd=1.0,
            on_exceed=OnExceed.FALLBACK,
            fallback_model="gpt-4o-mini",
        )
        self.manager.register_agent("ws", "agent", config)
        self.manager.record_usage("ws", "agent", 50_000, 1.05)

        result = self.manager.check_budget("ws", "agent", 1_000)
        assert result.allowed is True
        assert result.fallback_model == "gpt-4o-mini"

    def test_multiple_agents_independent(self):
        config_a = BudgetConfig(max_tokens=10_000)
        config_b = BudgetConfig(max_tokens=50_000)

        self.manager.register_agent("ws", "agent-a", config_a)
        self.manager.register_agent("ws", "agent-b", config_b)

        self.manager.record_usage("ws", "agent-a", 9_500, 0.1)

        # Agent A should be near limit
        budget_a = self.manager.get_budget("ws", "agent-a")
        assert budget_a.used_tokens == 9_500

        # Agent B should be unaffected
        result_b = self.manager.check_budget("ws", "agent-b", 40_000)
        assert result_b.allowed is True
        assert result_b.budget.status == BudgetStatus.OK
