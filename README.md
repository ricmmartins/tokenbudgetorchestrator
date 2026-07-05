# Token Budget Orchestrator (TBO)

[![PyPI](https://img.shields.io/pypi/v/token-budget-orchestrator)](https://pypi.org/project/token-budget-orchestrator/)
[![npm](https://img.shields.io/npm/v/token-budget-orchestrator)](https://www.npmjs.com/package/token-budget-orchestrator)
[![CI](https://github.com/ricmmartins/tokenbudgetorchestrator/actions/workflows/ci.yml/badge.svg)](https://github.com/ricmmartins/tokenbudgetorchestrator/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**Active budget orchestration engine for multi-agent LLM systems.**

> Helicone and Langfuse show you what happened to your budget. TBO decides what **will** happen — enforcing policies before each call, not after.

## The Problem

Teams running multi-agent LLM systems burn 3-5x more tokens than single-agent workflows. Without active enforcement, budgets are consumed silently — and you only find out at the end of the month.

## What TBO Does

- **Budget per agent** — Set token/cost limits per agent, project, or user with automatic period resets
- **Policy-based routing** — `"If task_type=draft → Haiku; if task_type=review → Sonnet"`
- **Automatic fallback** — Budget exceeded? Auto-route to a cheaper model instead of failing
- **Zero data leakage** — Prompts NEVER leave your infrastructure. Only metadata (token counts, costs, latency)

## Quick Start

### Python

```bash
pip install token-budget-orchestrator
```

```python
from tbo import TBOClient, BudgetConfig

client = TBOClient(
    provider="anthropic",
    api_key="your-key",
    workspace="my-project",
    agent_id="support-bot",
    budget=BudgetConfig(
        max_tokens=100_000,
        period="daily",
        on_exceed="fallback",
        fallback_model="claude-haiku-3-5-20241022",
    ),
)

# Use exactly like the original Anthropic client
response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Hello"}],
)
# TBO automatically: counts tokens → checks budget → routes to optimal model → records usage
```

### Node.js

```bash
npm install token-budget-orchestrator
```

```typescript
import { TBOClient } from "token-budget-orchestrator";

const client = new TBOClient({
  provider: "anthropic",
  apiKey: "your-key",
  workspace: "my-project",
  agentId: "support-bot",
  budget: { maxTokens: 100_000, period: "daily", onExceed: "fallback", fallbackModel: "claude-haiku-3-5-20241022" },
});

const response = await client.messages.create({
  model: "claude-sonnet-4-20250514",
  maxTokens: 1024,
  messages: [{ role: "user", content: "Hello" }],
});
```

## How It Works

```
┌─────────────────────────────────────────────────────────┐
│                    Your Infrastructure                    │
│                                                          │
│  ┌──────────┐    ┌──────────────┐    ┌───────────────┐  │
│  │ Your App │───▶│  TBO SDK     │───▶│ LLM Provider  │  │
│  └──────────┘    │ (runs local) │    │ (Anthropic/   │  │
│                  │              │    │  OpenAI)      │  │
│                  │ 1. Count     │    └───────────────┘  │
│                  │ 2. Policy    │                        │
│                  │ 3. Budget    │                        │
│                  │ 4. Route     │                        │
│                  └──────┬───────┘                        │
│                         │ metadata only                  │
└─────────────────────────┼───────────────────────────────┘
                          ▼
              ┌───────────────────────┐
              │   TBO Engine          │
              │   (optional)          │
              │                       │
              │ • Dashboard           │
              │ • Cross-agent budgets │
              │ • Alerts & reports    │
              └───────────────────────┘
```

**Key principle:** The SDK runs entirely in your process. Prompts never leave your infrastructure. The optional engine only receives aggregated metadata (token counts, costs, latency).

## Policy Routing

Define rules to automatically route calls to the right model:

```python
from tbo import Policy, RoutingRule

policies = [
    Policy(
        name="cost-optimization",
        rules=[
            RoutingRule(conditions={"task_type": "draft"}, route_to="claude-haiku-3-5-20241022"),
            RoutingRule(conditions={"task_type": "review"}, route_to="claude-sonnet-4-20250514"),
            RoutingRule(conditions={"task_type": "final"}, route_to="claude-opus-4-20250514"),
        ],
    )
]

client = TBOClient(provider="anthropic", api_key="...", policies=policies)
```

## Project Structure

```
tokenbudgetorchestrator/
├── sdks/python/     # Python SDK — pip install token-budget-orchestrator
├── sdks/node/       # Node.js SDK — npm install token-budget-orchestrator
├── engine/          # Policy Engine (FastAPI + Redis) — optional, for multi-process
├── dashboard/       # Web Dashboard (Next.js)
└── examples/        # Runnable examples
```

## Security

| What we collect | What we NEVER collect |
|-----------------|----------------------|
| Token count (in/out) | Prompt content |
| Model used | Response content |
| Cost estimate | API keys |
| Latency (ms) | User data |
| Agent ID | Business logic |

The SDK is designed for enterprise use. See [SECURITY.md](SECURITY.md) for details on our trust architecture.

## Contributing

We welcome contributions! The SDK is MIT-licensed and open source.

```bash
# Python SDK
cd sdks/python && pip install -e ".[dev]" && pytest

# Node SDK
cd sdks/node && npm install && npm test
```

## License

MIT
