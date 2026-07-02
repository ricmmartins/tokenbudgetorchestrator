"""Example: Budget fallback — auto-downgrade when budget runs out.

Demonstrates the killer feature: when an agent exhausts its budget,
TBO automatically routes to a cheaper model instead of blocking.

Run with: python examples/03_budget_fallback.py
"""

from unittest.mock import MagicMock, patch

from tbo import TBOClient, BudgetConfig

# --- Mock provider ---
mock_response = MagicMock()
mock_response.usage.input_tokens = 100
mock_response.usage.output_tokens = 400
mock_response.content = [MagicMock(text="Response")]

with patch("tbo.client.TBOClient._create_provider_client") as mock_create:
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response
    mock_create.return_value = mock_client

    # --- Setup: Agent with tight budget and fallback ---
    client = TBOClient(
        provider="anthropic",
        api_key="sk-ant-demo",
        workspace="production",
        agent_id="report-generator",
        budget=BudgetConfig(
            max_tokens=2_000,       # Tight budget: 2K tokens
            period="daily",
            on_exceed="fallback",   # Don't block — fall back!
            fallback_model="claude-haiku-3-5-20241022",
        ),
    )

    print("Budget Fallback Demo")
    print("=" * 60)
    print(f"Budget: 2,000 tokens/day | Fallback: claude-haiku-3-5")
    print("-" * 60)

    # --- Make calls until budget triggers fallback ---
    for i in range(5):
        client.messages.create(
            model="claude-sonnet-4-20250514",
            messages=[{"role": "user", "content": f"Generate report section {i+1}"}],
            max_tokens=512,
        )

        actual_model = mock_client.messages.create.call_args.kwargs["model"]
        budget = client._budget_manager.get_budget("production", "report-generator")

        print(
            f"  Call {i+1}: model={actual_model:<30} "
            f"used={budget.used_tokens:>5} / 2,000 tokens  "
            f"status={budget.status}"
        )

    print("-" * 60)
    print("\n[OK] No calls were blocked!")
    print("    When budget exceeded, TBO auto-downgraded to Haiku.")
    print("    Your agent keeps running — just cheaper.")
    print("\n[TIP] Alternative modes:")
    print('   on_exceed="block"  -> raises BudgetExceededError (strict)')
    print('   on_exceed="alert"  -> allows call but logs warning (permissive)')
