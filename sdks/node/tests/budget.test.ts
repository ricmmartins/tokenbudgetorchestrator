import { describe, it, expect } from "vitest";
import { BudgetManager, BudgetExceededError } from "../src/budget.js";

describe("BudgetManager", () => {
  it("registers agent and returns initial budget", () => {
    const mgr = new BudgetManager();
    const budget = mgr.registerAgent("ws", "agent-1", { maxTokens: 100_000, period: "daily" });

    expect(budget.agentId).toBe("agent-1");
    expect(budget.maxTokens).toBe(100_000);
    expect(budget.usedTokens).toBe(0);
    expect(budget.status).toBe("ok");
  });

  it("allows calls within budget", () => {
    const mgr = new BudgetManager();
    mgr.registerAgent("ws", "agent", { maxTokens: 100_000 });

    const result = mgr.checkBudget("ws", "agent", 5_000);
    expect(result.allowed).toBe(true);
  });

  it("blocks when budget exceeded (default)", () => {
    const mgr = new BudgetManager();
    mgr.registerAgent("ws", "agent", { maxTokens: 10_000, onExceed: "block" });

    expect(() => mgr.checkBudget("ws", "agent", 15_000)).toThrow(BudgetExceededError);
  });

  it("falls back to cheaper model when exceeded + fallback configured", () => {
    const mgr = new BudgetManager();
    mgr.registerAgent("ws", "agent", {
      maxTokens: 10_000,
      onExceed: "fallback",
      fallbackModel: "claude-haiku-3-5-20241022",
    });

    const result = mgr.checkBudget("ws", "agent", 15_000);
    expect(result.allowed).toBe(true);
    expect(result.fallbackModel).toBe("claude-haiku-3-5-20241022");
    expect(result.budget.status).toBe("exceeded");
  });

  it("alerts without blocking when on_exceed=alert", () => {
    const mgr = new BudgetManager();
    mgr.registerAgent("ws", "agent", { maxTokens: 10_000, onExceed: "alert" });

    const result = mgr.checkBudget("ws", "agent", 15_000);
    expect(result.allowed).toBe(true);
    expect(result.reason).toBeDefined();
  });

  it("records usage and updates budget", () => {
    const mgr = new BudgetManager();
    mgr.registerAgent("ws", "agent", { maxTokens: 100_000 });

    mgr.recordUsage("ws", "agent", 5_000, 0.05);
    const budget = mgr.getBudget("ws", "agent");

    expect(budget?.usedTokens).toBe(5_000);
    expect(budget?.usedCostUsd).toBe(0.05);
  });

  it("allows unlimited when no budget configured", () => {
    const mgr = new BudgetManager();
    const result = mgr.checkBudget("ws", "no-budget-agent", 999_999);
    expect(result.allowed).toBe(true);
  });

  it("tracks agents independently", () => {
    const mgr = new BudgetManager();
    mgr.registerAgent("ws", "a", { maxTokens: 10_000 });
    mgr.registerAgent("ws", "b", { maxTokens: 50_000 });

    mgr.recordUsage("ws", "a", 9_500, 0.1);

    expect(mgr.getBudget("ws", "a")?.usedTokens).toBe(9_500);
    expect(mgr.getBudget("ws", "b")?.usedTokens).toBe(0);
  });
});
