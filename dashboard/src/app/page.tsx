import Link from "next/link";

export default function Home() {
  return (
    <div className="flex flex-col flex-1 items-center justify-center font-sans">
      <main className="flex flex-1 w-full max-w-4xl flex-col items-center justify-center py-16 px-8">
        <div className="flex flex-col items-center gap-8 text-center">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-lg bg-blue-600 flex items-center justify-center">
              <span className="text-white font-bold text-lg">T</span>
            </div>
            <h1 className="text-3xl font-bold text-zinc-900 dark:text-zinc-50">
              Token Budget Orchestrator
            </h1>
          </div>

          <p className="max-w-lg text-lg text-zinc-600 dark:text-zinc-400">
            Real-time budget governance for multi-agent LLM systems.
            Control costs, route models by policy, and never get surprised by a bill again.
          </p>

          <div className="flex gap-4">
            <Link
              href="/dashboard"
              className="flex h-12 items-center justify-center gap-2 rounded-lg bg-blue-600 px-6 text-white font-medium transition-colors hover:bg-blue-700"
            >
              Open Dashboard
            </Link>
            <a
              href="https://github.com/ricardomac/tokenbudgetorchestrator"
              className="flex h-12 items-center justify-center rounded-lg border border-zinc-200 dark:border-zinc-700 px-6 font-medium text-zinc-700 dark:text-zinc-300 transition-colors hover:bg-zinc-100 dark:hover:bg-zinc-800"
              target="_blank"
              rel="noopener noreferrer"
            >
              GitHub
            </a>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 mt-8 w-full max-w-2xl">
            <FeatureCard
              title="Budget per Agent"
              description="Set token/cost limits per agent, project, or user with automatic period resets."
            />
            <FeatureCard
              title="Smart Routing"
              description="Automatically route to the cheapest model that's good enough for each task."
            />
            <FeatureCard
              title="Zero Data Leakage"
              description="Prompts never leave your infrastructure. We only see metadata."
            />
          </div>
        </div>
      </main>
    </div>
  );
}

function FeatureCard({ title, description }: { title: string; description: string }) {
  return (
    <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 p-5 text-left">
      <h3 className="font-semibold text-zinc-900 dark:text-zinc-100 mb-1">{title}</h3>
      <p className="text-sm text-zinc-500 dark:text-zinc-400">{description}</p>
    </div>
  );
}
