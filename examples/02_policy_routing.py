"""Example: Policy-based routing — route models by task type.

This is the core value proposition of TBO: automatically use the cheapest
model that's good enough for each task.

Run with: python examples/02_policy_routing.py
"""

import os
from unittest.mock import MagicMock, patch

from tbo import TBOClient, BudgetConfig
from tbo.policy import Policy, RoutingRule

# --- Define routing policies ---
# "If the task is a draft or summary, use Haiku (cheap).
#  If it's a code review or final edit, use Sonnet (quality)."

cost_optimization_policy = Policy(
    name="cost-optimization",
    description="Route to cheapest adequate model per task type",
    rules=[
        RoutingRule(
            name="drafts-use-haiku",
            condition={"task_type": ["draft", "summary", "classification"]},
            target_model="claude-haiku-3-5-20241022",
            priority=10,
        ),
        RoutingRule(
            name="quality-tasks-use-sonnet",
            condition={"task_type": ["review", "final-edit", "code-review"]},
            target_model="claude-sonnet-4-20250514",
            priority=10,
        ),
        RoutingRule(
            name="low-priority-use-mini",
            condition={"priority": "low"},
            target_model="claude-haiku-3-5-20241022",
            priority=5,  # Lower priority — overridden by task_type rules
        ),
    ],
)

# --- Create client with policy ---
# Using mock to demonstrate without real API key
mock_response = MagicMock()
mock_response.usage.input_tokens = 50
mock_response.usage.output_tokens = 150
mock_response.content = [MagicMock(text="Mock response")]

with patch("tbo.client.TBOClient._create_provider_client") as mock_create:
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response
    mock_create.return_value = mock_client

    client = TBOClient(
        provider="anthropic",
        api_key="sk-ant-demo",
        workspace="my-project",
        agent_id="content-writer",
        budget=BudgetConfig(max_tokens=100_000, period="daily"),
        policies=[cost_optimization_policy],
    )

    # --- Simulate different task types ---
    tasks = [
        ("Write a rough draft of an email", {"task_type": "draft"}),
        ("Review this pull request carefully", {"task_type": "code-review"}),
        ("Classify this support ticket", {"task_type": "classification"}),
        ("Polish this final customer response", {"task_type": "final-edit"}),
    ]

    print("Policy Routing Demo")
    print("=" * 60)
    print(f"{'Task':<45} {'Model Used'}")
    print("-" * 60)

    for prompt, metadata in tasks:
        client.messages.create(
            model="claude-sonnet-4-20250514",  # Always request Sonnet...
            messages=[{"role": "user", "content": prompt}],
            max_tokens=256,
            metadata=metadata,
        )

        # Check which model was actually called
        actual_model = mock_client.messages.create.call_args.kwargs["model"]
        print(f"{prompt:<45} {actual_model}")

    print("-" * 60)
    budget = client._budget_manager.get_budget("my-project", "content-writer")
    print(f"\nTotal tokens used: {budget.used_tokens}")
    print(f"Total cost: ${budget.used_cost_usd:.4f}")
    print("\n[TIP] Without TBO, all 4 calls would use Sonnet ($15/M output).")
    print("      With TBO, 2 calls used Haiku ($4/M output) — ~50% savings on those calls.")
