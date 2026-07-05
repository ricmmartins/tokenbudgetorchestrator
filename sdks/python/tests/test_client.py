"""Tests for the TBO client wrapper."""

from unittest.mock import MagicMock, patch

import pytest

from tbo.budget import BudgetConfig, BudgetExceededError
from tbo.client import TBOClient
from tbo.policy import Policy, RoutingRule


class TestTBOClientInit:
    def test_requires_provider_package(self):
        with patch.dict("sys.modules", {"anthropic": None}):
            with pytest.raises(ImportError, match="anthropic package required"):
                TBOClient(provider="anthropic", api_key="test")

    def test_invalid_provider_raises(self):
        with pytest.raises(ValueError):
            TBOClient(provider="invalid", api_key="test")


class TestTBOClientPreCall:
    @patch("tbo.client.TBOClient._create_provider_client")
    def test_pre_call_counts_tokens(self, mock_create):
        mock_create.return_value = MagicMock()
        client = TBOClient(
            provider="anthropic",
            api_key="test-key",
            workspace="ws",
            agent_id="agent-1",
        )

        messages = [{"role": "user", "content": "Hello, how are you?"}]
        final_model, estimated = client._pre_call("claude-sonnet-4-20250514", messages, {}, 1024)

        assert final_model == "claude-sonnet-4-20250514"
        assert estimated > 0

    @patch("tbo.client.TBOClient._create_provider_client")
    def test_pre_call_applies_routing_policy(self, mock_create):
        mock_create.return_value = MagicMock()
        policy = Policy(
            name="cost-opt",
            rules=[
                RoutingRule(
                    name="drafts-haiku",
                    condition={"task_type": "draft"},
                    target_model="claude-haiku-3-5-20241022",
                )
            ],
        )
        client = TBOClient(
            provider="anthropic",
            api_key="test-key",
            workspace="ws",
            agent_id="agent-1",
            policies=[policy],
        )

        messages = [{"role": "user", "content": "Write a draft"}]
        final_model, _ = client._pre_call(
            "claude-sonnet-4-20250514", messages, {"task_type": "draft"}, 1024
        )

        assert final_model == "claude-haiku-3-5-20241022"

    @patch("tbo.client.TBOClient._create_provider_client")
    def test_pre_call_blocks_when_budget_exceeded(self, mock_create):
        mock_create.return_value = MagicMock()
        client = TBOClient(
            provider="anthropic",
            api_key="test-key",
            workspace="ws",
            agent_id="agent-1",
            budget=BudgetConfig(max_tokens=100),
        )

        messages = [{"role": "user", "content": "A" * 2000}]  # Way over 100 tokens

        with pytest.raises(BudgetExceededError):
            client._pre_call("claude-sonnet-4-20250514", messages, {}, 1024)

    @patch("tbo.client.TBOClient._create_provider_client")
    def test_pre_call_fallback_when_budget_exceeded(self, mock_create):
        mock_create.return_value = MagicMock()
        client = TBOClient(
            provider="anthropic",
            api_key="test-key",
            workspace="ws",
            agent_id="agent-1",
            budget=BudgetConfig(
                max_tokens=100,
                on_exceed="fallback",
                fallback_model="claude-haiku-3-5-20241022",
            ),
        )

        messages = [{"role": "user", "content": "A" * 2000}]

        final_model, _ = client._pre_call("claude-sonnet-4-20250514", messages, {}, 1024)
        assert final_model == "claude-haiku-3-5-20241022"


class TestTBOClientPostCall:
    @patch("tbo.client.TBOClient._create_provider_client")
    def test_post_call_records_usage(self, mock_create):
        mock_create.return_value = MagicMock()
        client = TBOClient(
            provider="anthropic",
            api_key="test-key",
            workspace="ws",
            agent_id="agent-1",
            budget=BudgetConfig(max_tokens=100_000),
        )

        client._post_call(
            model="claude-sonnet-4-20250514",
            routed_model="claude-sonnet-4-20250514",
            input_tokens=500,
            output_tokens=200,
            latency_ms=150.0,
        )

        budget = client._budget_manager.get_budget("ws", "agent-1")
        assert budget.used_tokens == 700
        assert budget.used_cost_usd > 0
