from __future__ import annotations
"""
Policy Evaluator – evaluates an input payload against the active governance policy
for a given scope (request | asset | publish | retention) and workspace.

Returns a PolicyDecision with: action, reasons, rule_ids.
Action can be: pass | warn | block | review_required
"""

# Map policy evaluator action → state machine trigger (for requests)
ACTION_TO_REQUEST_TRIGGER: dict[str, str] = {
    "pass":             "policy_pass",
    "warn":             "policy_warn",
    "review_required":  "policy_review_required",
    "block":            "policy_block",
}

# Map policy evaluator action → state machine trigger (for assets)
ACTION_TO_ASSET_TRIGGER: dict[str, str] = {
    "pass":             "asset_policy_pass",
    "warn":             "asset_policy_pass",
    "review_required":  "asset_policy_review",
    "block":            "asset_policy_block",
}

from dataclasses import dataclass, field
from typing import Any, Optional
from sqlalchemy.orm import Session

from governance.models.policy import GovernancePolicy



@dataclass
class PolicyDecision:
    action: str                          # pass | warn | block | review_required
    reasons: list[str] = field(default_factory=list)
    rule_ids: list[str] = field(default_factory=list)
    policy_version: Optional[int] = None


_ACTION_PRIORITY = {
    "pass": 0,
    "warn": 1,
    "review_required": 2,
    "block": 3,
}


def _matches(when_clause: dict[str, Any], payload: dict[str, Any]) -> bool:
    """
    Simple attribute matcher: every key-value pair in `when_clause` must match
    the corresponding value in `payload` (top-level keys only).
    Supports exact match and list containment via 'in' operator in value.
    """
    for key, expected in when_clause.items():
        actual = payload.get(key)
        if isinstance(expected, dict) and "in" in expected:
            if actual not in expected["in"]:
                return False
        else:
            if actual != expected:
                return False
    return True


from governance.engine.provider_registry import get_provider_traits

def evaluate_policy(
    db: Session,
    scope: str,
    payload: dict[str, Any],
    workspace_id: str = "default",
) -> PolicyDecision:
    """
    Load the active policy for the given scope and workspace, then evaluate
    all rules against `payload`. Return the highest-priority action found.
    Falls back to 'default' workspace policy if workspace-specific one absent.
    """
    # Try workspace-specific first, then default
    policy_row: Optional[GovernancePolicy] = None
    for ws in [workspace_id, "default"]:
        policy_row = (
            db.query(GovernancePolicy)
            .filter(
                GovernancePolicy.workspace_id == ws,
                GovernancePolicy.policy_scope == scope,
                GovernancePolicy.is_active.is_(True),
            )
            .order_by(GovernancePolicy.version.desc())
            .first()
        )
        if policy_row:
            break

    if policy_row is None:
        # No policy found – default to pass
        return PolicyDecision(action="pass", reasons=["No active policy found – defaulting to pass"])

    rules = policy_row.policy_json.get("rules", [])
    decision = PolicyDecision(action="pass", policy_version=policy_row.version)

    # Inject provider traits into payload for evaluation if provider_key exists
    eval_payload = payload.copy()
    if "provider_key" in eval_payload:
        traits = get_provider_traits(eval_payload["provider_key"])
        # Prefix traits to avoid collisions
        for k, v in traits.items():
            eval_payload[f"provider_trait_{k}"] = v

    for rule in rules:
        when = rule.get("when", {})
        then = rule.get("then", {})
        rule_id = rule.get("rule_id", "unnamed_rule")

        if _matches(when, eval_payload):
            triggered_action = then.get("action", "pass")
            triggered_reason = then.get("reason", "")

            # Escalate only if new action has higher priority
            if _ACTION_PRIORITY.get(triggered_action, 0) > _ACTION_PRIORITY.get(decision.action, 0):
                decision.action = triggered_action

            decision.reasons.append(triggered_reason)
            decision.rule_ids.append(rule_id)

    return decision
