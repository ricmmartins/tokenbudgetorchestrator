"""Example: Drift detection — get alerted when an agent's token usage trends up.

This catches the "quiet regression" scenario: a prompt template changed,
an agent started retrying, or context is growing call over call. TBO alerts
you before the budget actually trips.
"""

from tbo import TBOClient, BudgetConfig, DriftConfig
from tbo.drift import DriftAlert


def handle_drift(alert: DriftAlert):
    """Called when an agent's token consumption drifts above baseline."""
    print(
        f"⚠️  DRIFT DETECTED: agent '{alert.agent_id}' "
        f"usage up {alert.increase_pct:.0f}% "
        f"(baseline ~{alert.baseline_avg:.0f} → recent ~{alert.recent_avg:.0f} tokens/call)"
    )


# Configure drift detection alongside the budget
client = TBOClient(
    provider="anthropic",
    api_key="your-key",
    workspace="my-project",
    agent_id="support-bot",
    budget=BudgetConfig(
        max_tokens=500_000,
        period="daily",
        on_exceed="fallback",
        fallback_model="claude-haiku-3-5-20241022",
    ),
    drift=DriftConfig(
        window_size=50,       # track last 50 calls
        recent_window=10,     # compare last 10 vs older 40
        sensitivity=0.3,      # alert on 30%+ increase
        min_samples=15,       # need 15 calls before detection starts
        cooldown_seconds=300, # max one alert per 5 minutes per agent
    ),
    on_drift=handle_drift,
)

# Usage is the same as always. Drift detection runs automatically
# in the post-call hook with <1ms overhead.
#
# If the agent's prompt template changes and starts burning 40% more
# tokens per call, you'll see the alert after ~15 calls — well before
# the daily budget actually runs out.
#
# response = client.messages.create(
#     model="claude-sonnet-4-20250514",
#     max_tokens=1024,
#     messages=[{"role": "user", "content": "Help me with..."}],
# )

# You can also check stats programmatically:
# stats = client._drift_detector.get_stats("my-project", "support-bot")
# print(f"Current avg: {stats['overall_avg']:.0f} tokens/call")

# And reset after a known intentional change (new prompt template deploy):
# client._drift_detector.reset("my-project", "support-bot")
