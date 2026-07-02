import { describe, it, expect } from "vitest";
import { PolicyEvaluator, type Policy } from "../src/policy.js";

describe("PolicyEvaluator", () => {
  it("allows all when no policies configured", () => {
    const evaluator = new PolicyEvaluator();
    const decision = evaluator.evaluate("claude-sonnet-4-20250514", { task_type: "draft" });

    expect(decision.action).toBe("allow");
    expect(decision.routedModel).toBe("claude-sonnet-4-20250514");
  });

  it("reroutes by task_type condition", () => {
    const evaluator = new PolicyEvaluator();
    evaluator.addPolicy({
      name: "cost-opt",
      rules: [{ name: "drafts-haiku", condition: { task_type: "draft" }, targetModel: "claude-haiku-3-5-20241022" }],
    });

    const decision = evaluator.evaluate("claude-sonnet-4-20250514", { task_type: "draft" });
    expect(decision.routedModel).toBe("claude-haiku-3-5-20241022");
    expect(decision.ruleApplied).toBe("drafts-haiku");
  });

  it("allows original model when no condition matches", () => {
    const evaluator = new PolicyEvaluator();
    evaluator.addPolicy({
      name: "cost-opt",
      rules: [{ name: "drafts-haiku", condition: { task_type: "draft" }, targetModel: "claude-haiku-3-5-20241022" }],
    });

    const decision = evaluator.evaluate("claude-sonnet-4-20250514", { task_type: "review" });
    expect(decision.action).toBe("allow");
    expect(decision.routedModel).toBe("claude-sonnet-4-20250514");
  });

  it("applies highest priority rule", () => {
    const evaluator = new PolicyEvaluator();
    evaluator.addPolicy({
      name: "multi",
      rules: [
        { name: "low", condition: { task_type: "draft" }, targetModel: "claude-haiku-3-5-20241022", priority: 1 },
        { name: "high", condition: { task_type: "draft" }, targetModel: "gpt-4o-mini", priority: 10 },
      ],
    });

    const decision = evaluator.evaluate("claude-sonnet-4-20250514", { task_type: "draft" });
    expect(decision.routedModel).toBe("gpt-4o-mini");
    expect(decision.ruleApplied).toBe("high");
  });

  it("ignores disabled policies", () => {
    const evaluator = new PolicyEvaluator();
    evaluator.addPolicy({
      name: "disabled",
      enabled: false,
      rules: [{ name: "rule", condition: { task_type: "draft" }, targetModel: "gpt-4o-mini" }],
    });

    const decision = evaluator.evaluate("claude-sonnet-4-20250514", { task_type: "draft" });
    expect(decision.action).toBe("allow");
  });

  it("matches list conditions", () => {
    const evaluator = new PolicyEvaluator();
    evaluator.addPolicy({
      name: "multi-match",
      rules: [{ name: "cheap-tasks", condition: { task_type: ["draft", "summary", "classify"] }, targetModel: "gpt-4o-mini" }],
    });

    expect(evaluator.evaluate("gpt-4o", { task_type: "summary" }).routedModel).toBe("gpt-4o-mini");
    expect(evaluator.evaluate("gpt-4o", { task_type: "code-review" }).action).toBe("allow");
  });

  it("requires all condition keys to match", () => {
    const evaluator = new PolicyEvaluator();
    evaluator.addPolicy({
      name: "strict",
      rules: [{ name: "rule", condition: { task_type: "draft", priority: "low" }, targetModel: "gpt-4o-mini" }],
    });

    expect(evaluator.evaluate("gpt-4o", { task_type: "draft", priority: "low" }).routedModel).toBe("gpt-4o-mini");
    expect(evaluator.evaluate("gpt-4o", { task_type: "draft", priority: "high" }).action).toBe("allow");
  });
});
