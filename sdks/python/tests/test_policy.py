"""Tests for policy evaluation."""

from tbo.policy import Policy, PolicyAction, PolicyEvaluator, RoutingRule


class TestPolicyEvaluator:
    def setup_method(self):
        self.evaluator = PolicyEvaluator()

    def test_no_policies_allows_all(self):
        decision = self.evaluator.evaluate("claude-sonnet-4-20250514", {"task_type": "draft"})

        assert decision.action == PolicyAction.ALLOW
        assert decision.routed_model == "claude-sonnet-4-20250514"
        assert decision.rule_applied is None

    def test_simple_reroute_by_task_type(self):
        policy = Policy(
            name="cost-optimization",
            rules=[
                RoutingRule(
                    name="drafts-use-haiku",
                    condition={"task_type": "draft"},
                    target_model="claude-haiku-3-5-20241022",
                    action=PolicyAction.REROUTE,
                ),
            ],
        )
        self.evaluator.add_policy(policy)

        decision = self.evaluator.evaluate(
            "claude-sonnet-4-20250514", {"task_type": "draft"}
        )

        assert decision.action == PolicyAction.REROUTE
        assert decision.original_model == "claude-sonnet-4-20250514"
        assert decision.routed_model == "claude-haiku-3-5-20241022"
        assert decision.rule_applied == "drafts-use-haiku"

    def test_no_match_allows_original(self):
        policy = Policy(
            name="cost-optimization",
            rules=[
                RoutingRule(
                    name="drafts-use-haiku",
                    condition={"task_type": "draft"},
                    target_model="claude-haiku-3-5-20241022",
                ),
            ],
        )
        self.evaluator.add_policy(policy)

        decision = self.evaluator.evaluate(
            "claude-sonnet-4-20250514", {"task_type": "review"}
        )

        assert decision.action == PolicyAction.ALLOW
        assert decision.routed_model == "claude-sonnet-4-20250514"

    def test_priority_ordering(self):
        policy = Policy(
            name="multi-rule",
            rules=[
                RoutingRule(
                    name="low-priority",
                    condition={"task_type": "draft"},
                    target_model="claude-haiku-3-5-20241022",
                    priority=1,
                ),
                RoutingRule(
                    name="high-priority",
                    condition={"task_type": "draft"},
                    target_model="gpt-4o-mini",
                    priority=10,
                ),
            ],
        )
        self.evaluator.add_policy(policy)

        decision = self.evaluator.evaluate("claude-sonnet-4-20250514", {"task_type": "draft"})

        assert decision.routed_model == "gpt-4o-mini"
        assert decision.rule_applied == "high-priority"

    def test_disabled_policy_ignored(self):
        policy = Policy(
            name="disabled-policy",
            enabled=False,
            rules=[
                RoutingRule(
                    name="should-not-fire",
                    condition={"task_type": "draft"},
                    target_model="claude-haiku-3-5-20241022",
                ),
            ],
        )
        self.evaluator.add_policy(policy)

        decision = self.evaluator.evaluate("claude-sonnet-4-20250514", {"task_type": "draft"})
        assert decision.action == PolicyAction.ALLOW
        assert decision.routed_model == "claude-sonnet-4-20250514"

    def test_list_condition_matching(self):
        policy = Policy(
            name="multi-match",
            rules=[
                RoutingRule(
                    name="low-priority-tasks",
                    condition={"task_type": ["draft", "summary", "classification"]},
                    target_model="gpt-4o-mini",
                ),
            ],
        )
        self.evaluator.add_policy(policy)

        decision = self.evaluator.evaluate("gpt-4o", {"task_type": "summary"})
        assert decision.routed_model == "gpt-4o-mini"

        decision = self.evaluator.evaluate("gpt-4o", {"task_type": "code-review"})
        assert decision.action == PolicyAction.ALLOW

    def test_multiple_condition_keys(self):
        policy = Policy(
            name="strict-routing",
            rules=[
                RoutingRule(
                    name="internal-drafts-only",
                    condition={"task_type": "draft", "priority": "low"},
                    target_model="claude-haiku-3-5-20241022",
                ),
            ],
        )
        self.evaluator.add_policy(policy)

        # Both conditions match
        decision = self.evaluator.evaluate(
            "claude-sonnet-4-20250514", {"task_type": "draft", "priority": "low"}
        )
        assert decision.routed_model == "claude-haiku-3-5-20241022"

        # Only one matches — should NOT reroute
        decision = self.evaluator.evaluate(
            "claude-sonnet-4-20250514", {"task_type": "draft", "priority": "high"}
        )
        assert decision.action == PolicyAction.ALLOW

    def test_remove_policy(self):
        policy = Policy(
            name="to-remove",
            rules=[
                RoutingRule(
                    name="rule1",
                    condition={"task_type": "draft"},
                    target_model="claude-haiku-3-5-20241022",
                ),
            ],
        )
        self.evaluator.add_policy(policy)
        self.evaluator.remove_policy("to-remove")

        decision = self.evaluator.evaluate("claude-sonnet-4-20250514", {"task_type": "draft"})
        assert decision.action == PolicyAction.ALLOW
