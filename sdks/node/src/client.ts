import type { ModelPricing, Provider, UsageRecord } from "./models.js";
import { DEFAULT_PRICING } from "./models.js";
import { BudgetConfig, BudgetExceededError, BudgetManager } from "./budget.js";
import { Policy, PolicyEvaluator } from "./policy.js";
import { TokenCounter } from "./tokenizer.js";
import { TelemetryCollector } from "./telemetry.js";

export interface TBOClientOptions {
  provider: Provider;
  apiKey?: string;
  workspace?: string;
  agentId?: string;
  budget?: BudgetConfig;
  policies?: Policy[];
  engineUrl?: string;
  metadata?: Record<string, unknown>;
  pricing?: ModelPricing[];
}

/**
 * TBO Client — transparent wrapper for Anthropic/OpenAI with budget governance.
 *
 * Usage:
 * ```ts
 * const client = new TBOClient({
 *   provider: "anthropic",
 *   apiKey: "sk-ant-...",
 *   workspace: "my-project",
 *   agentId: "support-bot",
 *   budget: { maxTokens: 100_000, period: "daily" },
 * });
 *
 * const response = await client.messages.create({
 *   model: "claude-sonnet-4-20250514",
 *   maxTokens: 1024,
 *   messages: [{ role: "user", content: "Hello" }],
 * });
 * ```
 */
export class TBOClient {
  private provider: Provider;
  private workspace: string;
  private agentId: string;
  private defaultMetadata: Record<string, unknown>;
  private tokenCounter: TokenCounter;
  private budgetManager: BudgetManager;
  private policyEvaluator: PolicyEvaluator;
  private telemetry: TelemetryCollector;
  private pricing: Map<string, ModelPricing>;
  private innerClient: unknown;

  public messages: MessagesAPI;

  constructor(options: TBOClientOptions) {
    this.provider = options.provider;
    this.workspace = options.workspace ?? "default";
    this.agentId = options.agentId ?? "default";
    this.defaultMetadata = options.metadata ?? {};

    this.tokenCounter = new TokenCounter(options.provider);
    this.budgetManager = new BudgetManager();
    this.policyEvaluator = new PolicyEvaluator();
    this.telemetry = new TelemetryCollector({ engineUrl: options.engineUrl });

    this.pricing = new Map((options.pricing ?? DEFAULT_PRICING).map((p) => [p.model, p]));

    if (options.budget) {
      this.budgetManager.registerAgent(this.workspace, this.agentId, options.budget);
    }

    if (options.policies) {
      for (const policy of options.policies) {
        this.policyEvaluator.addPolicy(policy);
      }
    }

    this.innerClient = this.createProviderClient(options.apiKey);
    this.messages = new MessagesAPI(this);
  }

  private createProviderClient(apiKey?: string): unknown {
    if (this.provider === "anthropic") {
      try {
        // eslint-disable-next-line @typescript-eslint/no-require-imports
        const { default: Anthropic } = require("@anthropic-ai/sdk");
        return new Anthropic({ apiKey });
      } catch {
        throw new Error("@anthropic-ai/sdk required. Install with: npm install @anthropic-ai/sdk");
      }
    } else if (this.provider === "openai") {
      try {
        // eslint-disable-next-line @typescript-eslint/no-require-imports
        const { default: OpenAI } = require("openai");
        return new OpenAI({ apiKey });
      } catch {
        throw new Error("openai package required. Install with: npm install openai");
      }
    }
    throw new Error(`Unsupported provider: ${this.provider}`);
  }

  /** @internal */
  _preCall(
    model: string,
    messages: Array<{ role: string; content: string | unknown[] }>,
    metadata: Record<string, unknown>,
    maxTokens: number
  ): { finalModel: string; estimatedInput: number } {
    const estimatedInput = this.tokenCounter.count(messages);

    const mergedMetadata = { ...this.defaultMetadata, ...metadata, agentId: this.agentId, originalModel: model };
    const decision = this.policyEvaluator.evaluate(model, mergedMetadata);

    if (decision.action === "block") {
      const budget = this.budgetManager.getBudget(this.workspace, this.agentId);
      throw new BudgetExceededError(
        this.agentId,
        budget ?? { agentId: this.agentId, workspace: this.workspace, period: "daily", usedTokens: 0, usedCostUsd: 0, status: "blocked", warningThreshold: 0.8 },
        estimatedInput
      );
    }

    let finalModel = decision.routedModel;

    const estimatedTotal = estimatedInput + Math.floor(maxTokens * 0.5);
    const budgetResult = this.budgetManager.checkBudget(this.workspace, this.agentId, estimatedTotal);

    if (budgetResult.fallbackModel) {
      finalModel = budgetResult.fallbackModel;
    }

    return { finalModel, estimatedInput };
  }

  /** @internal */
  _postCall(
    model: string,
    routedModel: string,
    inputTokens: number,
    outputTokens: number,
    latencyMs: number,
    policyApplied?: string
  ): void {
    const totalTokens = inputTokens + outputTokens;
    const pricing = this.pricing.get(routedModel);
    const cost = pricing ? this.tokenCounter.estimateCost(inputTokens, outputTokens, pricing) : 0;

    this.budgetManager.recordUsage(this.workspace, this.agentId, totalTokens, cost);

    const budget = this.budgetManager.getBudget(this.workspace, this.agentId);
    const record: UsageRecord = {
      timestamp: new Date(),
      workspace: this.workspace,
      agentId: this.agentId,
      provider: this.provider,
      model,
      inputTokens,
      outputTokens,
      totalTokens,
      estimatedCostUsd: cost,
      latencyMs,
      policyApplied,
      modelRoutedTo: routedModel !== model ? routedModel : undefined,
      budgetRemainingTokens: budget?.maxTokens ? budget.maxTokens - budget.usedTokens : undefined,
      budgetRemainingUsd: budget?.maxCostUsd ? budget.maxCostUsd - budget.usedCostUsd : undefined,
    };

    this.telemetry.record(record);
  }

  /** @internal — exposed for testing */
  get _budgetManager(): BudgetManager {
    return this.budgetManager;
  }

  get _telemetry(): TelemetryCollector {
    return this.telemetry;
  }

  get _innerClient(): unknown {
    return this.innerClient;
  }

  get _provider(): Provider {
    return this.provider;
  }
}

class MessagesAPI {
  constructor(private tbo: TBOClient) {}

  async create(options: {
    model: string;
    messages: Array<{ role: string; content: string | unknown[] }>;
    maxTokens?: number;
    metadata?: Record<string, unknown>;
    [key: string]: unknown;
  }): Promise<unknown> {
    const { model, messages, maxTokens = 1024, metadata = {}, ...rest } = options;

    const { finalModel, estimatedInput } = this.tbo._preCall(model, messages, metadata, maxTokens);

    const start = performance.now();
    let response: unknown;
    let inputTokens: number;
    let outputTokens: number;

    const client = this.tbo._innerClient as any;

    if (this.tbo._provider === "anthropic") {
      response = await client.messages.create({ model: finalModel, messages, max_tokens: maxTokens, ...rest });
      inputTokens = (response as any).usage.input_tokens;
      outputTokens = (response as any).usage.output_tokens;
    } else {
      response = await client.chat.completions.create({ model: finalModel, messages, max_tokens: maxTokens, ...rest });
      inputTokens = (response as any).usage.prompt_tokens;
      outputTokens = (response as any).usage.completion_tokens;
    }

    const latencyMs = performance.now() - start;
    const decision = new PolicyEvaluator(); // re-evaluate is redundant but cheap
    this.tbo._postCall(model, finalModel, inputTokens, outputTokens, latencyMs);

    return response;
  }
}
