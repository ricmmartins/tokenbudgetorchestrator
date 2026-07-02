export default function AgentsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-50">Agents</h1>
        <p className="text-zinc-500 dark:text-zinc-400 mt-1">
          Manage budget and policies per agent
        </p>
      </div>

      <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-6">
        <p className="text-zinc-500 dark:text-zinc-400 text-sm">
          Agent management UI coming in v1.0. For now, configure agents via the SDK:
        </p>
        <pre className="mt-4 p-4 bg-zinc-50 dark:bg-zinc-800 rounded-lg text-sm font-mono text-zinc-700 dark:text-zinc-300 overflow-x-auto">
{`from tbo import TBOClient, BudgetConfig

client = TBOClient(
    provider="anthropic",
    api_key="sk-ant-...",
    workspace="my-project",
    agent_id="support-bot",
    budget=BudgetConfig(
        max_tokens=200_000,
        period="daily",
        on_exceed="fallback",
        fallback_model="claude-haiku-3-5-20241022",
    ),
)`}
        </pre>
      </div>
    </div>
  );
}
