Title: Show HN: Token Budget Orchestrator – Active budget enforcement for multi-agent LLM systems

URL: https://github.com/ricmmartins/tokenbudgetorchestrator

Text:

Hey HN,

I built Token Budget Orchestrator (TBO) because I kept seeing teams burn through LLM budgets silently — especially when running multi-agent systems where communication between agents generates 3-5x more tokens than single-agent workflows.

The existing tools (Helicone, Langfuse, Datadog LLM) are great at showing you what happened. But by the time you see the dashboard, the money is already gone. I wanted something that decides what will happen — enforcing policies before each call.

What it does:
- Budget per agent/project/user with automatic period resets (daily, weekly, monthly)
- Policy-based routing: "If task_type=draft → use Haiku ($0.25/M); if task_type=review → use Sonnet"
- Automatic fallback: budget exceeded → auto-routes to cheaper model instead of failing
- 2-line integration: wraps your existing Anthropic/OpenAI client transparently

The key design decision: the SDK runs entirely in your process. Prompts never leave your infrastructure. Only metadata (token counts, costs) goes anywhere — and even that's optional.

It's a Python + Node SDK, MIT licensed. No SaaS required.

    pip install token-budget-orchestrator

Example:

    from tbo import TBOClient, BudgetConfig

    client = TBOClient(
        provider="anthropic",
        api_key="sk-...",
        budget=BudgetConfig(
            max_tokens=100_000,
            period="daily",
            on_exceed="fallback",
            fallback_model="claude-haiku-3-5-20241022",
        ),
    )
    # Use exactly like the original client — TBO handles the rest

Technical details:
- Thread-safe budget enforcement with reservation pattern (prevents TOCTOU races)
- Local token counting via tiktoken (no network calls)
- Optional Redis-backed engine for multi-process coordination (Lua scripts for atomicity)
- <5ms overhead per call

Would love feedback on the approach. The main risk I see is token price deflation making budget tools less urgent over time — but governance/control seems to have value beyond pure cost savings.

GitHub: https://github.com/ricmmartins/tokenbudgetorchestrator
