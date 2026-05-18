"""
Seed script for the IncuBrix Governance Layer.

Seeds:
  - 3 policy versions (request, asset, retention scopes)
  - 9 mock users across all roles
  - 20 governance requests (5 safe, 5 warned, 5 review_required, 5 blocked)
  - 20 governance assets
  - 10 exception requests
  - 100+ governance events

Run with:
    python -m governance.seed.seed_data
"""
import sys
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Ensure the governance package is importable when run as a script
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from governance.database import SessionLocal, create_all_tables
from governance.models.policy import GovernancePolicy
from governance.models.request import GovernanceRequest
from governance.models.asset import GovernanceAsset
from governance.models.event import GovernanceEvent
from governance.models.exception import GovernanceException
from governance.engine.rights_manifest import build_provenance, build_rights_manifest
from governance.engine.retention import RETENTION_CLASSES

now = datetime.now(timezone.utc)

# ── Mock Users ─────────────────────────────────────────────────────────────────

USERS = {
    "admin_01":          {"role": "admin",              "name": "Alex Admin"},
    "reviewer_01":       {"role": "reviewer",           "name": "Riley Reviewer"},
    "reviewer_02":       {"role": "reviewer",           "name": "Jordan Reviewer"},
    "reviewer_03":       {"role": "reviewer",           "name": "Sam Reviewer"},
    "reviewer_04":       {"role": "reviewer",           "name": "Casey Reviewer"},
    "reviewer_05":       {"role": "reviewer",           "name": "Dana Reviewer"},
    "exc_reviewer_01":   {"role": "exception_reviewer", "name": "Morgan Exception"},
    "exc_reviewer_02":   {"role": "exception_reviewer", "name": "Taylor Exception"},
    "auditor_01":        {"role": "auditor",            "name": "Quinn Auditor"},
}

WORKSPACE_ID = "default"
PROVIDERS = ["openai", "runway", "fal", "replicate", "unknown_provider"]
MODELS = {
    "openai":           "gpt-4o-video",
    "runway":           "gen-3-alpha",
    "fal":              "fal-ai/video-gen",
    "replicate":        "stability-ai/stable-video",
    "unknown_provider": "unverified-model-v1",
}
RETENTION_CLASSES_LIST = ["short", "standard", "extended"]


def _uid() -> str:
    return str(uuid.uuid4())


# ── Policies ───────────────────────────────────────────────────────────────────

POLICY_REQUEST_V1 = {
    "policy_id": "gov_request_policy_v1",
    "policy_scope": "request",
    "workspace_id": WORKSPACE_ID,
    "version": 1,
    "rules": [
        {
            "rule_id": "unknown_provider_requires_review",
            "when": {"provider_status": "unknown"},
            "then": {"action": "review_required", "reason": "Provider not in approved registry"},
        },
        {
            "rule_id": "high_risk_content_block",
            "when": {"risk_class": "high"},
            "then": {"action": "block", "reason": "High-risk content class"},
        },
        {
            "rule_id": "medium_risk_warn",
            "when": {"risk_class": "medium"},
            "then": {"action": "warn", "reason": "Medium-risk content – proceed with caution"},
        },
        {
            "rule_id": "explicit_content_block",
            "when": {"content_flags": {"in": ["explicit", "violence_extreme"]}},
            "then": {"action": "block", "reason": "Explicit or extreme violence content flag"},
        },
    ],
}

POLICY_ASSET_V1 = {
    "policy_id": "gov_asset_policy_v1",
    "policy_scope": "asset",
    "workspace_id": WORKSPACE_ID,
    "version": 1,
    "rules": [
        {
            "rule_id": "unverified_provider_asset_review",
            "when": {"provider_key": "unknown_provider"},
            "then": {"action": "review_required", "reason": "Asset from unverified provider requires manual review"},
        },
        {
            "rule_id": "replicate_attribution_warn",
            "when": {"provider_key": "replicate"},
            "then": {"action": "warn", "reason": "Replicate assets may require model-specific attribution"},
        },
    ],
}

POLICY_RETENTION_V1 = {
    "policy_id": "gov_retention_policy_v1",
    "policy_scope": "retention",
    "workspace_id": WORKSPACE_ID,
    "version": 1,
    "rules": [
        {
            "rule_id": "short_retention_class",
            "when": {"retention_class": "short"},
            "then": {"action": "pass", "reason": "Short retention: 7 days"},
        },
        {
            "rule_id": "standard_retention_class",
            "when": {"retention_class": "standard"},
            "then": {"action": "pass", "reason": "Standard retention: 30 days"},
        },
        {
            "rule_id": "extended_retention_class",
            "when": {"retention_class": "extended"},
            "then": {"action": "pass", "reason": "Extended retention: 90 days"},
        },
    ],
}


# ── Request scenarios ──────────────────────────────────────────────────────────

def _request_scenarios():
    """Return list of (payload, expected_state, provider) tuples for 20 requests."""
    scenarios = []

    # 5 safe requests – policy_passed → approved_for_execution
    for i in range(5):
        prov = PROVIDERS[i % 4]
        scenarios.append({
            "payload": {
                "prompt": f"Create a safe corporate explainer video #{i+1}",
                "risk_class": "low",
                "provider": prov,
                "provider_status": "approved",
            },
            "expected_state": "approved_for_execution",
            "provider": prov,
            "retention_class": "standard",
        })

    # 5 warned requests – approved_for_execution with warn
    for i in range(5):
        prov = PROVIDERS[i % 4]
        scenarios.append({
            "payload": {
                "prompt": f"Create a brand video #{i+1} with mild action",
                "risk_class": "medium",
                "provider": prov,
                "provider_status": "approved",
            },
            "expected_state": "approved_for_execution",
            "provider": prov,
            "retention_class": "standard",
        })

    # 5 review_required requests
    for i in range(5):
        scenarios.append({
            "payload": {
                "prompt": f"Generate a video for partner event #{i+1}",
                "risk_class": "low",
                "provider": "unknown_provider",
                "provider_status": "unknown",
            },
            "expected_state": "review_required",
            "provider": "unknown_provider",
            "retention_class": "short",
        })

    # 5 blocked requests
    for i in range(5):
        scenarios.append({
            "payload": {
                "prompt": f"Generate video content #{i+1}",
                "risk_class": "high",
                "provider": PROVIDERS[i % 4],
                "provider_status": "approved",
            },
            "expected_state": "blocked",
            "provider": PROVIDERS[i % 4],
            "retention_class": "short",
        })

    return scenarios


def _map_decision_to_state(payload: dict) -> tuple[str, str]:
    """Simplified in-seed policy evaluator (mirrors rule set above)."""
    risk = payload.get("risk_class", "low")
    provider_status = payload.get("provider_status", "approved")

    if risk == "high":
        return "blocked", "block"
    if provider_status == "unknown":
        return "review_required", "review_required"
    # pass or warn both → approved_for_execution
    return "approved_for_execution", "pass"


def seed(db):
    print("Seeding governance layer...")

    # ── Policies ───────────────────────────────────────────────────────────────
    policies_data = [
        (POLICY_REQUEST_V1, "request", 1),
        (POLICY_ASSET_V1, "asset", 1),
        (POLICY_RETENTION_V1, "retention", 1),
    ]
    policy_records = []
    for pol_json, scope, ver in policies_data:
        pol = GovernancePolicy(
            id=_uid(),
            workspace_id=WORKSPACE_ID,
            policy_scope=scope,
            version=ver,
            policy_json=pol_json,
            is_active=True,
            effective_from=now - timedelta(days=30),
            effective_to=None,
            created_at=now - timedelta(days=30),
        )
        db.add(pol)
        policy_records.append(pol)
    db.flush()
    print(f"  OK: {len(policy_records)} policies seeded")

    # ── Requests ───────────────────────────────────────────────────────────────
    scenarios = _request_scenarios()
    request_ids = []
    users = list(USERS.keys())

    for i, scenario in enumerate(scenarios):
        req_id = _uid()
        state, action = _map_decision_to_state(scenario["payload"])
        created_by = users[i % len(users)]
        created_at = now - timedelta(hours=100 - i * 4)

        req = GovernanceRequest(
            id=req_id,
            workspace_id=WORKSPACE_ID,
            request_payload=scenario["payload"],
            governance_state=state,
            policy_version=1,
            decision_summary={
                "action": action,
                "reasons": [f"Matched rule for risk_class={scenario['payload'].get('risk_class')}"],
                "rule_ids": ["seeded_rule"],
            },
            created_by=created_by,
            simulation_mode=True,
            created_at=created_at,
            updated_at=created_at,
        )
        db.add(req)
        request_ids.append((req_id, scenario, state, created_at))

        # Audit event for request creation
        db.add(GovernanceEvent(
            id=_uid(),
            workspace_id=WORKSPACE_ID,
            target_type="request",
            target_id=req_id,
            actor_id=created_by,
            action=f"policy_{action}",
            reason=f"Seeded request #{i+1}",
            event_payload={"state": state},
            occurred_at=created_at,
        ))

    db.flush()
    print(f"  OK: {len(request_ids)} governance requests seeded")

    # ── Assets ─────────────────────────────────────────────────────────────────
    asset_ids = []
    # Use first 20 requests to generate assets
    for i, (req_id, scenario, req_state, created_at) in enumerate(request_ids):
        provider = scenario["provider"]
        model = MODELS.get(provider, "unknown-model")
        rc = scenario["retention_class"]
        days = RETENTION_CLASSES.get(rc, 30)
        asset_created = created_at + timedelta(hours=1)

        # Determine asset state based on request state
        if req_state == "blocked":
            asset_state = "blocked"
        elif req_state == "review_required":
            asset_state = "review_required"
        elif i < 10:
            asset_state = "governance_passed"
        else:
            asset_state = "asset_registered"

        # Make some expired for retention testing
        if i < 3:
            retention_expires_at = now - timedelta(days=2)  # already expired
            asset_state = "expired"
        else:
            retention_expires_at = asset_created + timedelta(days=days)

        asset_payload = {
            "prompt": scenario["payload"].get("prompt", ""),
            "output_url": f"https://mock-storage.incubrix.local/assets/{_uid()}.mp4",
            "duration_seconds": 10 + (i * 3),
            "resolution": "1920x1080",
            "provider_key": provider,
        }
        provenance = build_provenance(
            request_id=req_id,
            provider_key=provider,
            model_key=model,
            asset_payload=asset_payload,
            workspace_id=WORKSPACE_ID,
            generated_at=asset_created,
        )
        manifest = build_rights_manifest(
            request_id=req_id,
            provider_key=provider,
            model_key=model,
            asset_payload=asset_payload,
            retention_class=rc,
        )

        asset_id = _uid()
        asset = GovernanceAsset(
            id=asset_id,
            workspace_id=WORKSPACE_ID,
            request_id=req_id,
            provider_key=provider,
            model_key=model,
            governance_state=asset_state,
            retention_class=rc,
            retention_expires_at=retention_expires_at,
            legal_hold=(i == 0),       # First asset has legal hold
            incident_hold=(i == 1),    # Second has incident hold
            provenance_json=provenance,
            rights_manifest_json=manifest,
            asset_payload=asset_payload,
            created_at=asset_created,
            updated_at=asset_created,
        )
        db.add(asset)
        asset_ids.append(asset_id)

        db.add(GovernanceEvent(
            id=_uid(),
            workspace_id=WORKSPACE_ID,
            target_type="asset",
            target_id=asset_id,
            actor_id="system:seed",
            action="asset_registered",
            reason="Seeded asset",
            event_payload={"governance_state": asset_state, "provider_key": provider},
            occurred_at=asset_created,
        ))

    db.flush()
    print(f"  OK: {len(asset_ids)} governance assets seeded")

    # ── Exceptions ─────────────────────────────────────────────────────────────
    exception_configs = [
        {"status": "pending",  "target_idx": 0, "reason": "Executive preview required before retention expiry"},
        {"status": "pending",  "target_idx": 1, "reason": "BD team needs access for partner demo"},
        {"status": "approved", "target_idx": 2, "reason": "Legal reviewed and approved for limited internal use"},
        {"status": "approved", "target_idx": 3, "reason": "Compliance approved with 14-day scope"},
        {"status": "rejected", "target_idx": 4, "reason": "Exception denied – high risk content policy"},
        {"status": "pending",  "target_idx": 5, "reason": "Request for extended review window"},
        {"status": "approved", "target_idx": 6, "reason": "Product team approved for alpha testing"},
        {"status": "rejected", "target_idx": 7, "reason": "Insufficient business justification"},
        {"status": "pending",  "target_idx": 8, "reason": "Awaiting compliance sign-off"},
        {"status": "expired",  "target_idx": 9, "reason": "Exception scope expired after 7-day window"},
    ]

    exc_reviewer = "exc_reviewer_01"
    for i, ec in enumerate(exception_configs):
        target_asset_idx = ec["target_idx"] % len(asset_ids)
        exc_id = _uid()
        exc_created = now - timedelta(hours=50 - i * 5)
        expiry = exc_created + timedelta(days=7) if ec["status"] in ("approved", "expired") else None

        exc = GovernanceException(
            id=exc_id,
            workspace_id=WORKSPACE_ID,
            target_type="asset",
            target_id=asset_ids[target_asset_idx],
            requested_by=users[i % len(users)],
            approved_by=exc_reviewer if ec["status"] in ("approved", "rejected", "expired") else None,
            status=ec["status"],
            scope_json={"use": "internal_preview", "max_viewers": 5} if ec["status"] == "approved" else None,
            expiry_at=expiry,
            business_reason=ec["reason"],
            created_at=exc_created,
            updated_at=exc_created,
        )
        db.add(exc)

        db.add(GovernanceEvent(
            id=_uid(),
            workspace_id=WORKSPACE_ID,
            target_type="exception",
            target_id=exc_id,
            actor_id=users[i % len(users)],
            action="exception_submitted",
            reason=ec["reason"],
            event_payload={"status": ec["status"]},
            occurred_at=exc_created,
        ))

        if ec["status"] in ("approved", "rejected", "expired"):
            db.add(GovernanceEvent(
                id=_uid(),
                workspace_id=WORKSPACE_ID,
                target_type="exception",
                target_id=exc_id,
                actor_id=exc_reviewer,
                action=f"exception_{ec['status']}",
                reason="Reviewed by exception reviewer",
                event_payload={"decision": ec["status"]},
                occurred_at=exc_created + timedelta(hours=2),
            ))

    db.flush()
    print(f"  OK: {len(exception_configs)} exceptions seeded")

    # ── Extra Governance Events (to reach 100+) ────────────────────────────────
    actions = [
        "policy_pass", "policy_warn", "policy_block", "policy_review_required",
        "reviewer_approve", "reviewer_reject", "auto_approve", "escalate",
        "asset_registered", "asset_policy_pass", "expire", "delete",
    ]
    event_count = 0
    target_cycle = request_ids + [(aid, {}, "governance_passed", now) for aid in asset_ids]

    for i in range(80):
        target_rec = target_cycle[i % len(target_cycle)]
        target_id = target_rec[0]
        target_type = "request" if i < 40 else "asset"
        action = actions[i % len(actions)]
        actor = users[i % len(users)]
        occurred = now - timedelta(hours=200 - i * 2)

        db.add(GovernanceEvent(
            id=_uid(),
            workspace_id=WORKSPACE_ID,
            target_type=target_type,
            target_id=target_id,
            actor_id=actor,
            action=action,
            reason=f"Seeded audit event #{i+1}",
            event_payload={"simulated": True, "index": i},
            occurred_at=occurred,
        ))
        event_count += 1

    db.flush()
    db.commit()
    print(f"  OK: {event_count} extra audit events seeded")
    print("OK: Seed complete.")


if __name__ == "__main__":
    create_all_tables()
    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()
