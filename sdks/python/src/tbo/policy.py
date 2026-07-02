"""Policy engine — evaluates routing and budget policies before each LLM call."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel


class PolicyAction(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"
    REROUTE = "reroute"
    FALLBACK = "fallback"
    ALERT = "alert"


class RoutingRule(BaseModel):
    """A single routing rule that maps conditions to model selection.

    Example:
        RoutingRule(
            name="drafts-use-haiku",
            condition={"task_type": "draft"},
            target_model="claude-haiku-3-5-20241022",
            priority=10
        )
    """

    name: str
    condition: dict  # Key-value pairs to match against call metadata
    target_model: Optional[str] = None
    action: PolicyAction = PolicyAction.REROUTE
    priority: int = 0  # Higher = evaluated first


class Policy(BaseModel):
    """A named policy containing routing rules and budget actions."""

    name: str
    description: str = ""
    rules: list[RoutingRule] = []
    enabled: bool = True


class PolicyDecision(BaseModel):
    """Result of evaluating policies for a call."""

    action: PolicyAction
    original_model: str
    routed_model: str  # May differ from original if rerouted
    rule_applied: Optional[str] = None
    reason: Optional[str] = None


class PolicyEvaluator:
    """Evaluates policies against call metadata to decide routing.

    Evaluation is LOCAL and synchronous — designed for <5ms latency.
    """

    def __init__(self):
        self._policies: list[Policy] = []

    def add_policy(self, policy: Policy) -> None:
        """Register a policy."""
        self._policies.append(policy)

    def remove_policy(self, name: str) -> None:
        """Remove a policy by name."""
        self._policies = [p for p in self._policies if p.name != name]

    def evaluate(self, model: str, metadata: dict) -> PolicyDecision:
        """Evaluate all active policies against call metadata.

        Args:
            model: The model originally requested by the caller
            metadata: Call metadata (task_type, agent_id, priority, etc.)

        Returns:
            PolicyDecision with the action to take and final model to use.
        """
        # Collect all matching rules across all active policies
        matching_rules: list[RoutingRule] = []

        for policy in self._policies:
            if not policy.enabled:
                continue
            for rule in policy.rules:
                if self._matches(rule.condition, metadata):
                    matching_rules.append(rule)

        if not matching_rules:
            return PolicyDecision(
                action=PolicyAction.ALLOW,
                original_model=model,
                routed_model=model,
            )

        # Apply highest priority matching rule
        matching_rules.sort(key=lambda r: r.priority, reverse=True)
        winner = matching_rules[0]

        routed_model = winner.target_model or model

        return PolicyDecision(
            action=winner.action,
            original_model=model,
            routed_model=routed_model,
            rule_applied=winner.name,
            reason=f"Matched condition: {winner.condition}",
        )

    def _matches(self, condition: dict, metadata: dict) -> bool:
        """Check if all condition key-values match the metadata."""
        for key, value in condition.items():
            if key not in metadata:
                return False
            if isinstance(value, list):
                if metadata[key] not in value:
                    return False
            elif metadata[key] != value:
                return False
        return True
