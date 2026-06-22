"""
Router: /api/governance/simulate
Policy simulation and scenario preview endpoints.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, timezone

from governance.database import get_db
from governance.auth import get_current_user, CurrentUser
from governance.engine.policy_evaluator import evaluate_policy

router = APIRouter(prefix="/api/governance/simulate", tags=["Simulation"])


# Golden scenarios used if none provided
GOLDEN_SCENARIOS = [
    {
        "scenario_id": "safe_request",
        "description": "Low-risk request with approved provider",
        "scope": "request",
        "payload": {"risk_class": "low", "provider_status": "approved", "provider_key": "openai"},
        "expected_action": "pass",
    },
    {
        "scenario_id": "high_risk_block",
        "description": "High-risk request should be blocked",
        "scope": "request",
        "payload": {"risk_class": "high", "provider_status": "approved", "provider_key": "openai"},
        "expected_action": "block",
    },
    {
        "scenario_id": "unknown_provider_review",
        "description": "Unknown provider should require review",
        "scope": "request",
        "payload": {"risk_class": "low", "provider_status": "unknown", "provider_key": "unknown_provider"},
        "expected_action": "review_required",
    },
    {
        "scenario_id": "medium_risk_warn",
        "description": "Medium risk should produce a warning",
        "scope": "request",
        "payload": {"risk_class": "medium", "provider_status": "approved", "provider_key": "openai"},
        "expected_action": "warn",
    },
    {
        "scenario_id": "missing_rights_block",
        "description": "Asset with missing source rights should block publish",
        "scope": "publish",
        "payload": {"source_rights_status": "missing", "provider_key": "runway"},
        "expected_action": "block",
    },
    {
        "scenario_id": "standard_asset_pass",
        "description": "Standard asset policy pass",
        "scope": "asset",
        "payload": {"provider_key": "openai", "retention_class": "standard"},
        "expected_action": "pass",
    },
]


class ScenarioPayload(BaseModel):
    scenario_id: str
    description: Optional[str] = ""
    scope: str
    payload: dict
    expected_action: Optional[str] = None


class RunScenariosRequest(BaseModel):
    policy_version: Optional[int] = None
    scenarios: Optional[list[ScenarioPayload]] = None   # if None, use golden scenarios
    workspace_id: Optional[str] = "default"


@router.post("/scenarios/run")
def run_scenarios(
    body: RunScenariosRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """
    Run governance policy scenarios against the active policy.
    Returns pass/fail coverage report.
    """
    scenarios = body.scenarios or [ScenarioPayload(**s) for s in GOLDEN_SCENARIOS]
    workspace_id = user.workspace_id

    results = []
    passed = 0
    failed = 0
    total = len(scenarios)

    for scenario in scenarios:
        decision = evaluate_policy(db, scope=scenario.scope, payload=scenario.payload, workspace_id=workspace_id)
        expected = scenario.expected_action
        actual = decision.action
        match = (expected is None) or (actual == expected)

        if match:
            passed += 1
        else:
            failed += 1

        results.append({
            "scenario_id": scenario.scenario_id,
            "description": scenario.description,
            "scope": scenario.scope,
            "payload": scenario.payload,
            "expected_action": expected,
            "actual_action": actual,
            "severity": decision.severity,
            "reason_codes": decision.reason_codes,
            "reasons": decision.reasons,
            "rule_ids": decision.rule_ids,
            "next_action": decision.next_action,
            "policy_version": decision.policy_version,
            "result": "pass" if match else "fail",
        })

    coverage_pct = round((passed / total) * 100, 1) if total > 0 else 0.0

    return {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "workspace_id": workspace_id,
        "total": total,
        "passed": passed,
        "failed": failed,
        "coverage_pct": coverage_pct,
        "results": results,
    }


class PreviewPolicyRequest(BaseModel):
    policy_json: dict
    scope: str
    test_payloads: list[dict]
    workspace_id: Optional[str] = "default"


@router.post("/policy/preview")
def preview_policy(
    body: PreviewPolicyRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """
    Preview how a proposed policy JSON would behave against test payloads.
    Does NOT activate the policy – purely a dry-run evaluation.
    """
    from governance.models.policy import GovernancePolicy

    # Create a transient (non-persisted) policy object for evaluation
    mock_policy = GovernancePolicy(
        id="preview",
        workspace_id=user.workspace_id,
        policy_scope=body.scope,
        version=0,
        policy_json=body.policy_json,
        is_active=True,
    )
    # Override DB query by temporarily evaluating directly
    from governance.engine.policy_evaluator import _matches, _ACTION_PRIORITY, _SEVERITY_MAP, PolicyDecision
    from governance.engine.provider_registry import get_provider_traits

    results = []
    rules = body.policy_json.get("rules", [])
    for i, payload in enumerate(body.test_payloads):
        decision = PolicyDecision(action="pass", severity="low", policy_version=0)
        eval_payload = payload.copy()
        if "provider_key" in eval_payload:
            traits = get_provider_traits(eval_payload["provider_key"])
            for k, v in traits.items():
                eval_payload[f"provider_trait_{k}"] = v

        for rule in rules:
            when = rule.get("when", {})
            then = rule.get("then", {})
            rule_id = rule.get("rule_id", "unnamed")
            if _matches(when, eval_payload):
                triggered = then.get("action", "pass")
                if _ACTION_PRIORITY.get(triggered, 0) > _ACTION_PRIORITY.get(decision.action, 0):
                    decision.action = triggered
                    decision.severity = then.get("severity", _SEVERITY_MAP.get(triggered, "medium"))
                decision.reasons.append(then.get("reason", ""))
                decision.reason_codes.append(then.get("reason_code", ""))
                decision.rule_ids.append(rule_id)

        results.append({
            "payload_index": i,
            "payload": payload,
            "action": decision.action,
            "severity": decision.severity,
            "reasons": decision.reasons,
            "reason_codes": decision.reason_codes,
            "matched_rules": decision.rule_ids,
        })

    return {
        "scope": body.scope,
        "policy_rules_count": len(rules),
        "test_payloads_count": len(body.test_payloads),
        "results": results,
    }
