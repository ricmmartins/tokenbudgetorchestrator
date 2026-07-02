"""Integration test — full end-to-end flow with mocked provider."""

from unittest.mock import MagicMock, patch

from tbo.budget import BudgetConfig, OnExceed
from tbo.client import TBOClient
from tbo.models import BudgetPeriod
from tbo.policy import Policy, RoutingRule


class TestEndToEndFlow:
    """Simulates a complete TBO flow with mocked LLM providers."""

    @patch("tbo.client.TBOClient._create_provider_client")
    def test_full_flow_anthropic_with_budget_and_policy(self, mock_create):
        """Agent makes calls, budget decreases, policy routes correctly."""
        # Mock Anthropic response
        mock_response = MagicMock()
        mock_response.usage.input_tokens = 50
        mock_response.usage.output_tokens = 150

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_create.return_value = mock_client

        # Setup: agent with budget + routing policy
        policy = Policy(
            name="cost-opt",
            rules=[
                RoutingRule(
                    name="drafts-use-haiku",
                    condition={"task_type": "draft"},
                    target_model="claude-haiku-3-5-20241022",
                ),
                RoutingRule(
                    name="reviews-use-sonnet",
                    condition={"task_type": "review"},
                    target_model="claude-sonnet-4-20250514",
                ),
            ],
        )

        client = TBOClient(
            provider="anthropic",
            api_key="sk-test",
            workspace="my-project",
            agent_id="support-bot",
            budget=BudgetConfig(
                max_tokens=10_000,
                period=BudgetPeriod.DAILY,
                on_exceed=OnExceed.FALLBACK,
                fallback_model="claude-haiku-3-5-20241022",
            ),
            policies=[policy],
        )

        # Call 1: draft task → should route to Haiku
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            messages=[{"role": "user", "content": "Write a draft email"}],
            max_tokens=512,
            metadata={"task_type": "draft"},
        )

        # Verify routing happened
        call_args = mock_client.messages.create.call_args
        assert call_args.kwargs["model"] == "claude-haiku-3-5-20241022"
        assert response == mock_response

        # Call 2: review task → should route to Sonnet
        client.messages.create(
            model="claude-haiku-3-5-20241022",
            messages=[{"role": "user", "content": "Review this code"}],
            max_tokens=1024,
            metadata={"task_type": "review"},
        )

        call_args = mock_client.messages.create.call_args
        assert call_args.kwargs["model"] == "claude-sonnet-4-20250514"

        # Verify budget tracking
        budget = client._budget_manager.get_budget("my-project", "support-bot")
        assert budget.used_tokens == 400  # 2 calls × (50 + 150) tokens

    @patch("tbo.client.TBOClient._create_provider_client")
    def test_budget_fallback_triggers_on_exhaustion(self, mock_create):
        """When budget runs out, automatically falls back to cheaper model."""
        mock_response = MagicMock()
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 400

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_create.return_value = mock_client

        client = TBOClient(
            provider="anthropic",
            api_key="sk-test",
            workspace="ws",
            agent_id="agent",
            budget=BudgetConfig(
                max_tokens=1_000,
                on_exceed=OnExceed.FALLBACK,
                fallback_model="claude-haiku-3-5-20241022",
            ),
        )

        # First call: uses 500 tokens, budget OK → uses requested model
        client.messages.create(
            model="claude-sonnet-4-20250514",
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=1024,
        )
        first_call_model = mock_client.messages.create.call_args.kwargs["model"]
        assert first_call_model == "claude-sonnet-4-20250514"

        # Second call: budget nearly exhausted → falls back to Haiku
        # Budget has 500 remaining, but estimated total (input + max_tokens*0.5)
        # will exceed it
        client.messages.create(
            model="claude-sonnet-4-20250514",
            messages=[{"role": "user", "content": "Generate a long response"}],
            max_tokens=2048,
        )
        second_call_model = mock_client.messages.create.call_args.kwargs["model"]
        assert second_call_model == "claude-haiku-3-5-20241022"

    @patch("tbo.client.TBOClient._create_provider_client")
    def test_openai_provider_flow(self, mock_create):
        """Verify OpenAI provider works with same interface."""
        mock_response = MagicMock()
        mock_response.usage.prompt_tokens = 30
        mock_response.usage.completion_tokens = 100

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_create.return_value = mock_client

        client = TBOClient(
            provider="openai",
            api_key="sk-test",
            workspace="ws",
            agent_id="gpt-agent",
            budget=BudgetConfig(max_tokens=50_000),
        )

        response = client.messages.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=512,
        )

        assert response == mock_response
        mock_client.chat.completions.create.assert_called_once()
        budget = client._budget_manager.get_budget("ws", "gpt-agent")
        assert budget.used_tokens == 130

    @patch("tbo.client.TBOClient._create_provider_client")
    def test_telemetry_records_emitted(self, mock_create):
        """Verify telemetry collector receives records after calls."""
        mock_response = MagicMock()
        mock_response.usage.input_tokens = 25
        mock_response.usage.output_tokens = 75

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_create.return_value = mock_client

        client = TBOClient(
            provider="anthropic",
            api_key="sk-test",
            workspace="ws",
            agent_id="agent",
        )

        client.messages.create(
            model="claude-sonnet-4-20250514",
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=256,
        )

        # Telemetry queue should have one record
        assert client._telemetry._queue.qsize() == 1
        record = client._telemetry._queue.get_nowait()
        assert record.input_tokens == 25
        assert record.output_tokens == 75
        assert record.agent_id == "agent"
        assert record.workspace == "ws"
        assert record.model == "claude-sonnet-4-20250514"

    @patch("tbo.client.TBOClient._create_provider_client")
    def test_multiple_agents_isolated_budgets(self, mock_create):
        """Two agents in same workspace have independent budgets."""
        mock_response = MagicMock()
        mock_response.usage.input_tokens = 200
        mock_response.usage.output_tokens = 300

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_create.return_value = mock_client

        agent_a = TBOClient(
            provider="anthropic",
            api_key="sk-test",
            workspace="shared-ws",
            agent_id="agent-a",
            budget=BudgetConfig(max_tokens=5_000),
        )

        agent_b = TBOClient(
            provider="anthropic",
            api_key="sk-test",
            workspace="shared-ws",
            agent_id="agent-b",
            budget=BudgetConfig(max_tokens=50_000),
        )

        # Agent A makes a call
        agent_a.messages.create(
            model="claude-sonnet-4-20250514",
            messages=[{"role": "user", "content": "Task A"}],
            max_tokens=512,
        )

        # Agent B makes a call
        agent_b.messages.create(
            model="claude-sonnet-4-20250514",
            messages=[{"role": "user", "content": "Task B"}],
            max_tokens=512,
        )

        budget_a = agent_a._budget_manager.get_budget("shared-ws", "agent-a")
        budget_b = agent_b._budget_manager.get_budget("shared-ws", "agent-b")

        assert budget_a.used_tokens == 500
        assert budget_b.used_tokens == 500
        # Independent managers, independent budgets
