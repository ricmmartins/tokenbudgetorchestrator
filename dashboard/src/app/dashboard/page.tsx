"use client";

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

// Mock data — will connect to engine API
const usageData = [
  { time: "00:00", tokens: 2400, cost: 0.12 },
  { time: "04:00", tokens: 1398, cost: 0.07 },
  { time: "08:00", tokens: 9800, cost: 0.49 },
  { time: "12:00", tokens: 15800, cost: 0.79 },
  { time: "16:00", tokens: 12000, cost: 0.60 },
  { time: "20:00", tokens: 8500, cost: 0.43 },
  { time: "Now", tokens: 4300, cost: 0.22 },
];

const agents = [
  { id: "support-bot", tokens: 45_200, budget: 200_000, cost: 2.15, status: "ok" },
  { id: "code-reviewer", tokens: 32_100, budget: 50_000, cost: 4.82, status: "warning" },
  { id: "report-gen", tokens: 12_800, budget: 500_000, cost: 1.92, status: "ok" },
  { id: "data-analyst", tokens: 8_400, budget: 100_000, cost: 0.63, status: "ok" },
];

export default function DashboardPage() {
  const totalTokens = agents.reduce((sum, a) => sum + a.tokens, 0);
  const totalCost = agents.reduce((sum, a) => sum + a.cost, 0);
  const totalBudget = agents.reduce((sum, a) => sum + a.budget, 0);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-50">Overview</h1>
        <p className="text-zinc-500 dark:text-zinc-400 mt-1">
          Real-time token consumption across all agents
        </p>
      </div>

      {/* Stats cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Tokens Used Today" value={totalTokens.toLocaleString()} sub={`/ ${totalBudget.toLocaleString()} budget`} />
        <StatCard label="Cost Today" value={`$${totalCost.toFixed(2)}`} sub="projected $18.40/month" />
        <StatCard label="Active Agents" value={agents.length.toString()} sub="4 within budget" />
        <StatCard label="Calls Routed" value="847" sub="62% to cheaper models" />
      </div>

      {/* Chart */}
      <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-6">
        <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100 mb-4">
          Token Usage (Today)
        </h2>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={usageData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e4e4e7" />
              <XAxis dataKey="time" stroke="#71717a" fontSize={12} />
              <YAxis stroke="#71717a" fontSize={12} />
              <Tooltip />
              <Area
                type="monotone"
                dataKey="tokens"
                stroke="#2563eb"
                fill="#2563eb"
                fillOpacity={0.1}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Agent table */}
      <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-6">
        <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100 mb-4">
          Agent Budgets
        </h2>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-zinc-500 dark:text-zinc-400 border-b border-zinc-100 dark:border-zinc-800">
              <th className="pb-3 font-medium">Agent</th>
              <th className="pb-3 font-medium">Tokens Used</th>
              <th className="pb-3 font-medium">Budget</th>
              <th className="pb-3 font-medium">Usage</th>
              <th className="pb-3 font-medium">Cost</th>
              <th className="pb-3 font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {agents.map((agent) => {
              const pct = Math.round((agent.tokens / agent.budget) * 100);
              return (
                <tr key={agent.id} className="border-b border-zinc-50 dark:border-zinc-800/50">
                  <td className="py-3 font-medium text-zinc-900 dark:text-zinc-100">
                    {agent.id}
                  </td>
                  <td className="py-3 text-zinc-600 dark:text-zinc-300">
                    {agent.tokens.toLocaleString()}
                  </td>
                  <td className="py-3 text-zinc-600 dark:text-zinc-300">
                    {agent.budget.toLocaleString()}
                  </td>
                  <td className="py-3">
                    <div className="flex items-center gap-2">
                      <div className="w-24 h-2 bg-zinc-100 dark:bg-zinc-800 rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full ${
                            pct > 80 ? "bg-amber-500" : pct > 95 ? "bg-red-500" : "bg-blue-500"
                          }`}
                          style={{ width: `${Math.min(pct, 100)}%` }}
                        />
                      </div>
                      <span className="text-zinc-500 text-xs">{pct}%</span>
                    </div>
                  </td>
                  <td className="py-3 text-zinc-600 dark:text-zinc-300">
                    ${agent.cost.toFixed(2)}
                  </td>
                  <td className="py-3">
                    <StatusBadge status={agent.status} />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function StatCard({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-5">
      <p className="text-sm text-zinc-500 dark:text-zinc-400">{label}</p>
      <p className="text-2xl font-bold text-zinc-900 dark:text-zinc-50 mt-1">{value}</p>
      <p className="text-xs text-zinc-400 mt-1">{sub}</p>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    ok: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
    warning: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
    exceeded: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
  };
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${colors[status] || colors.ok}`}>
      {status}
    </span>
  );
}
