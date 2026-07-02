"""Example: Basic TBO usage with Anthropic.

Shows the simplest integration — wrap your existing client in 2 lines.
Run with: python examples/01_basic_usage.py

Requires: ANTHROPIC_API_KEY environment variable (or replace below).
Works without a real key in dry-run / mock mode.
"""

import os

from tbo import TBOClient, BudgetConfig

# --- Setup ---
# The TBO client wraps your existing Anthropic client transparently.
# Your API key stays local — TBO never sees or stores it.

client = TBOClient(
    provider="anthropic",
    api_key=os.getenv("ANTHROPIC_API_KEY", "sk-ant-test-key"),
    workspace="my-startup",
    agent_id="support-bot",
    budget=BudgetConfig(
        max_tokens=50_000,      # 50K tokens per day
        max_cost_usd=5.0,       # $5/day hard cap
        period="daily",
        warning_threshold=0.8,  # Alert at 80% usage
    ),
)

# --- Use exactly like the native Anthropic client ---
try:
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=256,
        messages=[{"role": "user", "content": "What is token budget orchestration?"}],
    )
    print(f"Response: {response.content[0].text[:100]}...")
    print(f"\nUsage tracked by TBO:")

    budget = client._budget_manager.get_budget("my-startup", "support-bot")
    print(f"  Tokens used: {budget.used_tokens}")
    print(f"  Cost: ${budget.used_cost_usd:.4f}")
    print(f"  Status: {budget.status}")

except Exception as e:
    print(f"Error (expected without real API key): {e}")
    print("\nTo run with real API: export ANTHROPIC_API_KEY=sk-ant-...")
