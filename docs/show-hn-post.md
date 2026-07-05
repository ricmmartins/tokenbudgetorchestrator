Title: Show HN: Token Budget Orchestrator - budget enforcement for multi-agent LLM systems

URL: https://github.com/ricmmartins/tokenbudgetorchestrator

Text:

I built this because I kept watching teams burn through LLM budgets without realizing it, especially once they started running multi-agent systems where the agents talk to each other and generate 3-5x more tokens than a single-agent setup doing the same work.

The existing tools (Helicone, Langfuse, Datadog LLM) are good at showing you what happened. But by the time you see the dashboard, the money is already gone. I wanted something that makes decisions before each call, not after.

What it does:

- Budget per agent/project/user with automatic period resets
- Policy routing: "if task_type=draft, use Haiku; if task_type=review, use Sonnet"
- Automatic fallback: budget exceeded? Route to a cheaper model instead of failing
- Two-line integration: wraps your existing Anthropic/OpenAI client

The main design decision: the SDK runs in your process. Prompts never leave your infrastructure. Only metadata (token counts, costs) goes anywhere, and even that part is optional.

Python + Node SDK, MIT licensed. No SaaS required.

    pip install token-budget-orchestrator

Quick example:

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
    # Use like the normal Anthropic client

Some technical details if you are curious:

- Thread-safe budget enforcement with a reservation pattern (prevents race conditions where concurrent calls all pass the check before any of them record usage)
- Local token counting via tiktoken, no network calls for the budget check
- Optional Redis-backed engine for multi-process coordination using Lua scripts for atomicity
- Around 5ms overhead per call

The risk I think about most is token prices dropping fast enough that budget tools become less urgent. But governance and auditability (who used what, why, with what result) seem to hold value even if the raw cost per token shrinks.

Feedback welcome, especially from people running multi-agent systems in production.

GitHub: https://github.com/ricmmartins/tokenbudgetorchestrator
