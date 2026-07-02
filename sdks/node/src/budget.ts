import type { AgentBudget, BudgetPeriod, BudgetStatus, OnExceed } from "./models.js";

export interface BudgetConfig {
  maxTokens?: number;
  maxCostUsd?: number;
  period?: BudgetPeriod;
  warningThreshold?: number;
  safetyMargin?: number;
  onExceed?: OnExceed;
  fallbackModel?: string;
}

export interface BudgetCheckResult {
  allowed: boolean;
  budget: AgentBudget;
  fallbackModel?: string;
  reason?: string;
}

export class BudgetExceededError extends Error {
  constructor(
    public readonly agentId: string,
    public readonly budget: AgentBudget,
    public readonly requestedTokens: number
  ) {
    const remaining = (budget.maxTokens ?? 0) - budget.usedTokens;
    super(
      `Budget exceeded for agent '${agentId}': ` +
        `requested ~${requestedTokens} tokens, ` +
        `remaining ${remaining} tokens in ${budget.period} period`
    );
    this.name = "BudgetExceededError";
  }
}

const PERIOD_MS: Record<BudgetPeriod, number> = {
  hourly: 3_600_000,
  daily: 86_400_000,
  weekly: 604_800_000,
  monthly: 2_592_000_000,
};

export class BudgetManager {
  private budgets = new Map<string, AgentBudget>();
  private configs = new Map<string, BudgetConfig>();
  private periodStart = new Map<string, number>();

  registerAgent(workspace: string, agentId: string, config: BudgetConfig): AgentBudget {
    const key = `${workspace}:${agentId}`;
    const budget: AgentBudget = {
      agentId,
      workspace,
      maxTokens: config.maxTokens,
      maxCostUsd: config.maxCostUsd,
      period: config.period ?? "daily",
      usedTokens: 0,
      usedCostUsd: 0,
      status: "ok",
      warningThreshold: config.warningThreshold ?? 0.8,
    };
    this.budgets.set(key, budget);
    this.configs.set(key, config);
    this.periodStart.set(key, Date.now());
    return budget;
  }

  checkBudget(workspace: string, agentId: string, estimatedTokens: number): BudgetCheckResult {
    const key = `${workspace}:${agentId}`;
    const budget = this.budgets.get(key);

    if (!budget) {
      return {
        allowed: true,
        budget: { agentId, workspace, period: "daily", usedTokens: 0, usedCostUsd: 0, status: "ok", warningThreshold: 0.8 },
      };
    }

    const config = this.configs.get(key);
    this.maybeResetPeriod(key, budget);

    let exceeded = false;
    let reason: string | undefined;

    if (budget.maxTokens != null) {
      const remaining = budget.maxTokens - budget.usedTokens;
      if (estimatedTokens > remaining) {
        exceeded = true;
        reason = `Requested ~${estimatedTokens} tokens, remaining ${remaining} in ${budget.period} period`;
      } else {
        const ratio = budget.usedTokens / budget.maxTokens;
        if (ratio >= budget.warningThreshold) budget.status = "warning";
      }
    }

    if (!exceeded && budget.maxCostUsd != null) {
      const ratio = budget.usedCostUsd / budget.maxCostUsd;
      if (ratio >= 1.0) {
        exceeded = true;
        reason = `Cost budget exhausted: $${budget.usedCostUsd.toFixed(2)} / $${budget.maxCostUsd.toFixed(2)}`;
      } else if (ratio >= budget.warningThreshold) {
        budget.status = "warning";
      }
    }

    if (!exceeded) {
      return { allowed: true, budget };
    }

    budget.status = "exceeded";

    if (config?.onExceed === "fallback" && config.fallbackModel) {
      return { allowed: true, budget, fallbackModel: config.fallbackModel, reason };
    }

    if (config?.onExceed === "alert") {
      return { allowed: true, budget, reason };
    }

    throw new BudgetExceededError(agentId, budget, estimatedTokens);
  }

  recordUsage(workspace: string, agentId: string, tokensUsed: number, costUsd: number): AgentBudget {
    const key = `${workspace}:${agentId}`;
    const budget = this.budgets.get(key);
    if (!budget) {
      return { agentId, workspace, period: "daily", usedTokens: 0, usedCostUsd: 0, status: "ok", warningThreshold: 0.8 };
    }
    budget.usedTokens += tokensUsed;
    budget.usedCostUsd += costUsd;
    if (budget.maxTokens && budget.usedTokens >= budget.maxTokens) budget.status = "exceeded";
    if (budget.maxCostUsd && budget.usedCostUsd >= budget.maxCostUsd) budget.status = "exceeded";
    return budget;
  }

  getBudget(workspace: string, agentId: string): AgentBudget | undefined {
    return this.budgets.get(`${workspace}:${agentId}`);
  }

  private maybeResetPeriod(key: string, budget: AgentBudget): void {
    const start = this.periodStart.get(key) ?? Date.now();
    const elapsed = Date.now() - start;
    if (elapsed >= PERIOD_MS[budget.period]) {
      budget.usedTokens = 0;
      budget.usedCostUsd = 0;
      budget.status = "ok";
      this.periodStart.set(key, Date.now());
    }
  }
}
