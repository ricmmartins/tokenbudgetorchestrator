export default function PoliciesPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-50">Policies</h1>
        <p className="text-zinc-500 dark:text-zinc-400 mt-1">
          Configure routing and budget policies
        </p>
      </div>

      <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-6">
        <h2 className="font-semibold text-zinc-900 dark:text-zinc-100 mb-4">Active Policies</h2>

        <div className="space-y-3">
          <PolicyCard
            name="cost-optimization"
            description="Route drafts and summaries to Haiku, reviews to Sonnet"
            rules={3}
            enabled={true}
          />
          <PolicyCard
            name="after-hours-savings"
            description="Use cheapest model between 22:00-06:00"
            rules={1}
            enabled={false}
          />
        </div>
      </div>

      <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-6">
        <p className="text-zinc-500 dark:text-zinc-400 text-sm">
          Visual policy editor coming in v1.0. Configure via SDK:
        </p>
        <pre className="mt-4 p-4 bg-zinc-50 dark:bg-zinc-800 rounded-lg text-sm font-mono text-zinc-700 dark:text-zinc-300 overflow-x-auto">
{`from tbo.policy import Policy, RoutingRule

policy = Policy(
    name="cost-optimization",
    rules=[
        RoutingRule(
            name="drafts-use-haiku",
            condition={"task_type": ["draft", "summary"]},
            target_model="claude-haiku-3-5-20241022",
        ),
        RoutingRule(
            name="reviews-use-sonnet",
            condition={"task_type": "code-review"},
            target_model="claude-sonnet-4-20250514",
        ),
    ],
)`}
        </pre>
      </div>
    </div>
  );
}

function PolicyCard({
  name,
  description,
  rules,
  enabled,
}: {
  name: string;
  description: string;
  rules: number;
  enabled: boolean;
}) {
  return (
    <div className="flex items-center justify-between p-4 rounded-lg border border-zinc-100 dark:border-zinc-800">
      <div>
        <div className="flex items-center gap-2">
          <span className="font-medium text-zinc-900 dark:text-zinc-100">{name}</span>
          <span className="text-xs text-zinc-400">{rules} rules</span>
        </div>
        <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-0.5">{description}</p>
      </div>
      <span
        className={`px-2 py-0.5 rounded-full text-xs font-medium ${
          enabled
            ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400"
            : "bg-zinc-100 text-zinc-500 dark:bg-zinc-800 dark:text-zinc-500"
        }`}
      >
        {enabled ? "active" : "disabled"}
      </span>
    </div>
  );
}
