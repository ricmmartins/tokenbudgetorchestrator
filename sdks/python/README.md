# TBO Python SDK

Active budget governance for multi-agent LLM systems.

## Install

```bash
pip install tbo[anthropic]  # or tbo[openai] or tbo[all]
```

## Quick Start

```python
from tbo import TBOClient, BudgetConfig

client = TBOClient(
    provider="anthropic",
    api_key="your-key",
    workspace="my-project",
    agent_id="support-bot",
    budget=BudgetConfig(max_tokens=100_000, period="daily"),
)

response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Hello"}]
)
```
