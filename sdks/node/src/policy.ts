import type { PolicyAction } from "./models.js";

export interface RoutingRule {
  name: string;
  condition: Record<string, unknown>;
  targetModel?: string;
  action?: PolicyAction;
  priority?: number;
}

export interface Policy {
  name: string;
  description?: string;
  rules: RoutingRule[];
  enabled?: boolean;
}

export interface PolicyDecision {
  action: PolicyAction;
  originalModel: string;
  routedModel: string;
  ruleApplied?: string;
  reason?: string;
}

export class PolicyEvaluator {
  private policies: Policy[] = [];

  addPolicy(policy: Policy): void {
    this.policies.push(policy);
  }

  removePolicy(name: string): void {
    this.policies = this.policies.filter((p) => p.name !== name);
  }

  evaluate(model: string, metadata: Record<string, unknown>): PolicyDecision {
    const matchingRules: RoutingRule[] = [];

    for (const policy of this.policies) {
      if (policy.enabled === false) continue;
      for (const rule of policy.rules) {
        if (this.matches(rule.condition, metadata)) {
          matchingRules.push(rule);
        }
      }
    }

    if (matchingRules.length === 0) {
      return { action: "allow", originalModel: model, routedModel: model };
    }

    matchingRules.sort((a, b) => (b.priority ?? 0) - (a.priority ?? 0));
    const winner = matchingRules[0];

    return {
      action: winner.action ?? "reroute",
      originalModel: model,
      routedModel: winner.targetModel ?? model,
      ruleApplied: winner.name,
      reason: `Matched condition: ${JSON.stringify(winner.condition)}`,
    };
  }

  private matches(condition: Record<string, unknown>, metadata: Record<string, unknown>): boolean {
    for (const [key, value] of Object.entries(condition)) {
      if (!(key in metadata)) return false;
      if (Array.isArray(value)) {
        if (!value.includes(metadata[key])) return false;
      } else if (metadata[key] !== value) {
        return false;
      }
    }
    return true;
  }
}
