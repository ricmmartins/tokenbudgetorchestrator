import { z } from "zod";

export const Provider = z.enum(["anthropic", "openai"]);
export type Provider = z.infer<typeof Provider>;

export const BudgetPeriod = z.enum(["hourly", "daily", "weekly", "monthly"]);
export type BudgetPeriod = z.infer<typeof BudgetPeriod>;

export const BudgetStatus = z.enum(["ok", "warning", "exceeded", "blocked"]);
export type BudgetStatus = z.infer<typeof BudgetStatus>;

export const OnExceed = z.enum(["block", "fallback", "alert"]);
export type OnExceed = z.infer<typeof OnExceed>;

export const PolicyAction = z.enum(["allow", "block", "reroute", "fallback", "alert"]);
export type PolicyAction = z.infer<typeof PolicyAction>;

export interface AgentBudget {
  agentId: string;
  workspace: string;
  maxTokens?: number;
  maxCostUsd?: number;
  period: BudgetPeriod;
  usedTokens: number;
  usedCostUsd: number;
  status: BudgetStatus;
  warningThreshold: number;
}

export interface UsageRecord {
  timestamp: Date;
  workspace: string;
  agentId: string;
  provider: Provider;
  model: string;
  inputTokens: number;
  outputTokens: number;
  totalTokens: number;
  estimatedCostUsd: number;
  latencyMs: number;
  policyApplied?: string;
  modelRoutedTo?: string;
  budgetRemainingTokens?: number;
  budgetRemainingUsd?: number;
}

export interface ModelPricing {
  model: string;
  provider: Provider;
  inputPerMillion: number;
  outputPerMillion: number;
}

export const DEFAULT_PRICING: ModelPricing[] = [
  { model: "claude-sonnet-4-20250514", provider: "anthropic", inputPerMillion: 3.0, outputPerMillion: 15.0 },
  { model: "claude-haiku-3-5-20241022", provider: "anthropic", inputPerMillion: 0.8, outputPerMillion: 4.0 },
  { model: "claude-opus-4-20250514", provider: "anthropic", inputPerMillion: 15.0, outputPerMillion: 75.0 },
  { model: "gpt-4o", provider: "openai", inputPerMillion: 2.5, outputPerMillion: 10.0 },
  { model: "gpt-4o-mini", provider: "openai", inputPerMillion: 0.15, outputPerMillion: 0.6 },
];
