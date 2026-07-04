# Token Budget Orchestrator (TBO)

**Active budget orchestration and governance engine for multi-agent LLM systems.**

> While tools like Helicone and Langfuse show you what happened to your budget, TBO decides what will happen — enforcing policies before each call, not after.

## Core Capabilities

- **Budget per agent** — Set token/cost limits per agent, project, or user
- **Policy-based routing** — "If task_type=draft, use Haiku; if task_type=review, use Sonnet"
- **Dynamic reallocation** — Agent A exhausted its budget? Redistribute from Agent C
- **Zero data leakage** — Prompts NEVER leave your infrastructure. Only metadata.

## Quick Start (Python SDK)

```bash
pip install tbo
```

```python
from tbo import TBOClient

# Wrap your existing Anthropic client — 2 lines of code
client = TBOClient(
    provider="anthropic",
    api_key="your-anthropic-key",
    workspace="my-project",
    agent_id="support-bot",
)

# Use exactly like the original client
response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Hello"}]
)
# TBO automatically: counts tokens, enforces budget, routes to optimal model
```

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Client Infrastructure                  │
│                                                          │
│  ┌──────────┐    ┌──────────────┐    ┌───────────────┐  │
│  │ Your App │───▶│  TBO SDK     │───▶│ LLM Provider  │  │
│  └──────────┘    │ (local)      │    │ (Anthropic/   │  │
│                  │              │    │  OpenAI)      │  │
│                  │ • Policy eval│    └───────────────┘  │
│                  │ • Token count│                        │
│                  │ • Budget gate│                        │
│                  └──────┬───────┘                        │
│                         │ metadata only                  │
└─────────────────────────┼───────────────────────────────┘
                          ▼
              ┌───────────────────────┐
              │   TBO Cloud/Self-host │
              │                       │
              │ • Dashboard           │
              │ • Budget aggregation  │
              │ • Alerts              │
              │ • Policy management   │
              └───────────────────────┘
```

## Project Structure

```
tokenbudgetorchestrator/
├── sdks/
│   ├── python/          # Python SDK (P0 — MVP)
│   └── node/            # Node.js SDK (P0 — MVP)
├── engine/              # Policy Engine (FastAPI + Redis)
├── dashboard/           # Web Dashboard (Next.js — Phase 2)
├── infra/               # Docker, K8s, Terraform
└── docs/                # Documentation
```

## Security Principle

**Content of prompts NEVER leaves client infrastructure.**

The TBO SDK operates at the metadata level only. What we collect:
- Token count (input/output)
- Model used
- Cost estimate
- Latency
- Agent ID
- Timestamp

What we NEVER collect:
- Prompt content
- Response content
- API keys
- User data

## License

MIT (SDK) | Commercial (Engine + Dashboard)
