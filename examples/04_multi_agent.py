"""Example: Multi-agent orchestration with independent budgets.

Real-world scenario: 3 agents with different roles, budgets, and policies.
TBO manages each independently — no cross-contamination.

Run with: python examples/04_multi_agent.py
"""

from unittest.mock import MagicMock, patch

from tbo import TBOClient, BudgetConfig
from tbo.policy import Policy, RoutingRule

# --- Mock ---
mock_response = MagicMock()
mock_response.usage.input_tokens = 80
mock_response.usage.output_tokens = 200
mock_response.content = [MagicMock(text="Response")]


def create_agent(agent_id: str, budget: BudgetConfig, policies=None):
    """Helper to create an agent with mock provider."""
    with patch("tbo.client.TBOClient._create_provider_client") as mock_create:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_create.return_value = mock_client

        return TBOClient(
            provider="anthropic",
            api_key="sk-ant-demo",
            workspace="acme-corp",
            agent_id=agent_id,
            budget=budget,
            policies=policies or [],
        )


# --- Define 3 agents with different budgets ---

# Agent 1: Support bot — high volume, tight per-call budget
support_bot = create_agent(
    "support-bot",
    BudgetConfig(
        max_tokens=200_000,  # 200K/day — handles many short interactions
        max_cost_usd=10.0,
        period="daily",
        on_exceed="fallback",
        fallback_model="claude-haiku-3-5-20241022",
    ),
    policies=[
        Policy(
            name="support-routing",
            rules=[
                RoutingRule(
                    name="simple-queries-haiku",
                    condition={"complexity": "simple"},
                    target_model="claude-haiku-3-5-20241022",
                ),
            ],
        )
    ],
)

# Agent 2: Code reviewer — low volume, quality-first
code_reviewer = create_agent(
    "code-reviewer",
    BudgetConfig(
        max_tokens=50_000,   # 50K/day — fewer but larger calls
        max_cost_usd=5.0,
        period="daily",
        on_exceed="block",   # Never compromise on code review quality
    ),
)

# Agent 3: Report generator — runs once daily, big budget burst
report_gen = create_agent(
    "report-generator",
    BudgetConfig(
        max_tokens=500_000,  # 500K/day — generates long documents
        max_cost_usd=25.0,
        period="daily",
        on_exceed="alert",   # Alert but don't block reports
    ),
)

# --- Simulate usage ---
print("Multi-Agent Budget Orchestration")
print("=" * 70)
print(f"{'Agent':<20} {'Budget':<15} {'On Exceed':<12} {'Model Policy'}")
print("-" * 70)
print(f"{'support-bot':<20} {'200K tok/day':<15} {'fallback':<12} simple->Haiku")
print(f"{'code-reviewer':<20} {'50K tok/day':<15} {'block':<12} always Sonnet")
print(f"{'report-generator':<20} {'500K tok/day':<15} {'alert':<12} unrestricted")
print("-" * 70)

# Simulate calls
agents = [
    (support_bot, "support-bot", 20),
    (code_reviewer, "code-reviewer", 5),
    (report_gen, "report-generator", 10),
]

for agent, name, num_calls in agents:
    for _ in range(num_calls):
        try:
            agent.messages.create(
                model="claude-sonnet-4-20250514",
                messages=[{"role": "user", "content": "Task"}],
                max_tokens=256,
                metadata={"complexity": "simple"} if name == "support-bot" else {},
            )
        except Exception:
            pass  # Block mode may raise

    budget = agent._budget_manager.get_budget("acme-corp", name)
    print(
        f"  {name:<20} | "
        f"Calls: {num_calls:<3} | "
        f"Tokens: {budget.used_tokens:>7} / {budget.max_tokens:>7} | "
        f"Cost: ${budget.used_cost_usd:.2f} | "
        f"Status: {budget.status}"
    )

print("\n[OK] Each agent has independent budget — no cross-contamination.")
print("     Support bot's high usage doesn't affect code reviewer's budget.")
