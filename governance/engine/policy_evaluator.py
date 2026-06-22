"""
Policy Evaluator v2 – evaluates payloads against active governance policies.

v2 enhancements:
  - PolicyDecision now includes severity, next_action, evidence_refs
  - Supports nested attribute access via dot notation (e.g., provider.status)
  - Supports eq, in, neq, gt, lt operators in when clauses
  - Returns reason_codes alongside human-readable reasons
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Optional
from sqlalchemy.orm import Session

from governance.models.policy import GovernancePolicy
from governance.engine.provider_registry import get_provider_traits

# Map policy action → state machine trigger (requests)
ACTION_TO_REQUEST_TRIGGER: dict[str, str] = {
    "pass":             "policy_pass",
    "warn":             "policy_warn",
    "review_required":  "policy_review_required",
    "block":            "policy_block",
}

# Map policy action → state machine trigger (assets)
ACTION_TO_ASSET_TRIGGER: dict[str, str] = {
    "pass":             "asset_policy_pass",
    "warn":             "asset_policy_pass",
    "review_required":  "asset_policy_review",
    "block":            "asset_policy_block",
}

_ACTION_PRIORITY = {
    "pass": 0,
    "warn": 1,
    "review_required": 2,
    "block": 3,
}


@dataclass
class PolicyDecision:
    action: str                           # pass | warn | block | review_required
    severity: str = "low"                 # low | medium | high | critical
    reasons: list[str] = field(default_factory=list)
    reason_codes: list[str] = field(default_factory=list)
    rule_ids: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    next_action: Optional[str] = None     # e.g. route_to_reviewer_queue, request_rights_evidence
    policy_version: Optional[int] = None


def _resolve(payload: dict, key: str) -> Any:
    """
    Resolve a possibly dot-notated key from the payload.
    e.g., 'provider.status' → payload['provider']['status']
    Falls back to top-level key if no dot.
    """
    parts = key.split(".")
    val: Any = payload
    for part in parts:
        if isinstance(val, dict):
            val = val.get(part)
        else:
            return None
    return val


def _matches(when_clause: dict[str, Any], payload: dict[str, Any]) -> bool:
    """
    Extended attribute matcher supporting:
      { "key": value }           → exact match
      { "key": {"eq": v} }       → equality
      { "key": {"neq": v} }      → not equal
      { "key": {"in": [v1,v2]} } → membership
      { "key": {"gt": n} }       → greater than
      { "key": {"lt": n} }       → less than
    """
    for key, expected in when_clause.items():
        actual = _resolve(payload, key)
        if isinstance(expected, dict):
            if "eq" in expected:
                if actual != expected["eq"]:
                    return False
            if "neq" in expected:
                if actual == expected["neq"]:
                    return False
            if "in" in expected:
                if actual not in expected["in"]:
                    return False
            if "gt" in expected:
                if actual is None or actual <= expected["gt"]:
                    return False
            if "lt" in expected:
                if actual is None or actual >= expected["lt"]:
                    return False
        else:
            if actual != expected:
                return False
    return True


_SEVERITY_MAP = {
    "pass":             "low",
    "warn":             "medium",
    "review_required":  "medium",
    "block":            "high",
}


def evaluate_policy(
    db: Session,
    scope: str,
    payload: dict[str, Any],
    workspace_id: str = "default",
) -> PolicyDecision:
    """
    Load the active policy for the given scope and workspace, evaluate all
    rules against `payload`, and return the highest-priority decision.
    Falls back to 'default' workspace policy if workspace-specific one is absent.
    """
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
        return PolicyDecision(
            action="pass",
            severity="low",
            reasons=["No active policy found – defaulting to pass"],
            next_action="continue",
        )

    rules = policy_row.policy_json.get("rules", [])
    decision = PolicyDecision(action="pass", severity="low", policy_version=policy_row.version)

    # Inject provider traits into payload for evaluation
    eval_payload = payload.copy()
    if "provider_key" in eval_payload:
        traits = get_provider_traits(eval_payload["provider_key"])
        for k, v in traits.items():
            eval_payload[f"provider_trait_{k}"] = v

    for rule in rules:
        when = rule.get("when", {})
        then = rule.get("then", {})
        rule_id = rule.get("rule_id", "unnamed_rule")

        if _matches(when, eval_payload):
            triggered_action = then.get("action", "pass")
            triggered_reason = then.get("reason", "")
            triggered_reason_code = then.get("reason_code", "")
            triggered_next_action = then.get("next_action", None)
            triggered_severity = then.get("severity", _SEVERITY_MAP.get(triggered_action, "medium"))

            if _ACTION_PRIORITY.get(triggered_action, 0) > _ACTION_PRIORITY.get(decision.action, 0):
                decision.action = triggered_action
                decision.severity = triggered_severity
                decision.next_action = triggered_next_action

            if triggered_reason:
                decision.reasons.append(triggered_reason)
            if triggered_reason_code:
                decision.reason_codes.append(triggered_reason_code)
            decision.rule_ids.append(rule_id)

    # Set default next_action if not already set
    if decision.next_action is None:
        default_next = {
            "pass":             "continue",
            "warn":             "continue_with_warning",
            "review_required":  "route_to_reviewer_queue",
            "block":            "halt_and_notify",
        }
        decision.next_action = default_next.get(decision.action, "continue")

    return decision
