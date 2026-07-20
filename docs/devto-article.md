---
title: Budget enforcement for multi-agent LLM systems (without a proxy)
published: true
tags: opensource, python, ai, llm
cover_image: https://raw.githubusercontent.com/ricmmartins/tokenbudgetorchestrator/master/docs/architecture.svg
---

## The problem I kept running into

I work with teams that run multi-agent LLM systems. The common pattern: an orchestrator agent decomposes a task, dispatches sub-agents, those sub-agents sometimes call other agents, and by the time the task completes you have 10-20 LLM calls where you expected 3.

The cost isn't the only issue. The unpredictability is. A task that costs $0.30 on Monday costs $4 on Tuesday because one agent hit a retry loop or generated a longer chain of reasoning. You only find out when you check the dashboard.

Monitoring tools (Langfuse, Helicone, Datadog LLM Observability) are good at the "find out" part. They show you what happened. But by then, the money is gone.

I wanted something that makes a decision before each LLM call, not after.

## What I built

Token Budget Orchestrator is a Python and Node SDK that wraps your existing LLM client. Before each call, it:

1. Estimates how many tokens the call will use
2. Checks whether the agent/user/project has budget remaining
3. Evaluates routing policies (should this call go to a cheaper model?)
4. Either allows the call, blocks it, or reroutes it

After the call, it records actual usage and reconciles the estimate.

```
pip install token-budget-orchestrator
```

```python
from tbo import TBOClient, BudgetConfig

client = TBOClient(
    provider="anthropic",
    api_key="sk-ant-...",
    budget=BudgetConfig(
        max_tokens=100_000,
        period="daily",
        on_exceed="fallback",
        fallback_model="claude-haiku-3-5-20241022",
    ),
)

response = client.chat("Summarize this document", metadata={"agent_id": "summarizer"})
```

When the summarizer agent burns through its daily 100K tokens, instead of failing it routes to Haiku. The calling code doesn't need to know this happened.

## The design decision that shaped everything

I could have built this as a gateway (like LiteLLM or Bifrost do). Route all traffic through a proxy, enforce budgets there. That approach is proven and works.

I chose a different path: the SDK runs in your process. Prompts never leave your infrastructure. No proxy sits between you and the LLM provider.

Why? Because the teams I work with handle sensitive data. They don't want another service seeing their prompts, even if that service is self-hosted. The trust boundary matters.

The tradeoff: if you control the code, you can bypass the SDK. This is a governance tool for cooperative systems, not a security boundary against adversarial code.

## Policy routing

Budget enforcement is useful, but the feature I actually use most is policy-based model routing:

```python
from tbo import PolicyConfig, RoutingRule

policy = PolicyConfig(rules=[
    RoutingRule(
        name="drafts-use-haiku",
        condition={"task_type": "draft"},
        target_model="claude-haiku-3-5-20241022",
        priority=10,
    ),
    RoutingRule(
        name="code-review-uses-sonnet",
        condition={"task_type": "code_review"},
        target_model="claude-sonnet-4-20250514",
        priority=10,
    ),
])

client = TBOClient(
    provider="anthropic",
    api_key="sk-...",
    budget=budget_config,
    policy=policy,
)
```

The agent code just calls `client.chat(...)` with metadata about what it's doing. The SDK picks the model. This means you can change your model allocation strategy without touching agent code.

## The concurrency problem

Here's the bug that took me the longest to figure out.

Imagine 5 agents check the budget simultaneously. Each one sees "80K tokens used, 100K limit, 20K remaining." Each one proceeds. They all use 10K tokens. You end up at 130K, 30% over budget.

The fix is a reservation pattern. When an agent checks the budget, the SDK atomically reserves the estimated tokens. If the call uses less than estimated, the difference is released. If it uses more, the overage is recorded.

```
Agent checks budget -> reserves 10K -> makes LLM call -> actual usage: 7K -> releases 3K
```

For single-process setups, this uses a thread-safe dict. For multi-process (multiple services sharing a budget), there's an optional Redis-backed engine that uses Lua scripts for atomicity.

## What I'd do differently

If I started over, I'd skip the Node SDK until the Python one had real production usage. Supporting two languages doubles the maintenance surface and the Node SDK is essentially a port that nobody has tested in production yet.

I'd also integrate with LiteLLM's provider abstraction from day one instead of building my own. Their model catalog and retry logic is better than what I have.

## Alternatives

Being honest about the landscape:

- **LiteLLM** has budget enforcement at the gateway level. If you're already using their proxy, you might not need a separate SDK.
- **TokenBudget** (PyPI) does code-level budget enforcement with decorators. Lighter weight than TBO but no policy routing.
- **Bifrost** (Maxim AI) is a full gateway with hierarchical budgets.

Where TBO fits: you want budget enforcement plus model routing, you don't want a proxy in the path, and you want it as a library you import rather than infrastructure you deploy.

## Links

- GitHub: [github.com/ricmmartins/tokenbudgetorchestrator](https://github.com/ricmmartins/tokenbudgetorchestrator)
- PyPI: `pip install token-budget-orchestrator`
- npm: `npm install token-budget-orchestrator`

MIT licensed. Issues and feedback welcome.
