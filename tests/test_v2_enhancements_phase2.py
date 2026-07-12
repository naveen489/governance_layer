import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from governance.main import app
from governance.database import SessionLocal
from governance.models.policy import GovernancePolicy
from governance.models.event import GovernanceEvent
from governance.models.asset import GovernanceAsset
from governance.models.provider_profile import ProviderPolicyProfile
from governance.auth import get_current_user, CurrentUser

client = TestClient(app)

@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_policy_validation_and_immutability(db_session: Session):
    # Setup test workspace user headers
    headers = {
        "X-User-Id": "admin_test",
        "X-User-Role": "admin",
        "X-Workspace-Id": "default"
    }

    # 1. Test policy JSON validation (invalid action)
    bad_policy_payload = {
        "policy_scope": "request",
        "version": 1,
        "is_active": False,
        "policy_json": {
            "rules": [
                {
                    "rule_id": "rule_1",
                    "when": {"provider_key": "openai"},
                    "then": {"action": "super_pass"}  # Invalid action!
                }
            ]
        }
    }
    resp = client.post("/api/governance/policies", json=bad_policy_payload, headers=headers)
    assert resp.status_code == 422
    assert "invalid action" in resp.json()["detail"]

    # 2. Create a valid inactive policy
    good_policy_payload = {
        "policy_scope": "request",
        "version": 1,
        "is_active": False,
        "policy_json": {
            "rules": [
                {
                    "rule_id": "rule_1",
                    "when": {"provider_key": "openai"},
                    "then": {"action": "pass"}
                }
            ]
        }
    }
    resp = client.post("/api/governance/policies", json=good_policy_payload, headers=headers)
    assert resp.status_code == 201
    policy_id = resp.json()["id"]

    # 3. Modify rules of an inactive policy -> should succeed
    update_payload = {
        "policy_json": {
            "rules": [
                {
                    "rule_id": "rule_1_updated",
                    "when": {"provider_key": "openai"},
                    "then": {"action": "warn", "reason": "warn openai"}
                }
            ]
        }
    }
    resp = client.patch(f"/api/governance/policies/{policy_id}", json=update_payload, headers=headers)
    assert resp.status_code == 200

    # 4. Activate the policy
    resp = client.patch(f"/api/governance/policies/{policy_id}", json={"is_active": True}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["is_active"] is True

    # 5. Modify rules of an active policy -> should raise 409 Conflict
    resp = client.patch(f"/api/governance/policies/{policy_id}", json=update_payload, headers=headers)
    assert resp.status_code == 409
    assert "Cannot modify rules of an active policy" in resp.json()["detail"]

    # 6. Test cloning / new-version endpoint
    resp = client.post(f"/api/governance/policies/{policy_id}/new-version", headers=headers)
    assert resp.status_code == 201
    new_pol = resp.json()
    assert new_pol["version"] == 2
    assert new_pol["is_active"] is False


def test_rights_manifest_evidence_and_confidence_scoring(db_session: Session):
    headers = {
        "X-User-Id": "admin_test",
        "X-User-Role": "admin",
        "X-Workspace-Id": "default"
    }

    # Setup Provider Policy Profile requiring evidence capture
    profile = ProviderPolicyProfile(
        provider_key="provider_x",
        version=1,
        evidence_capture_required=True,
        is_active=True,
        moderation_behavior={"type": "none"},
        retention_behavior={"default_hours": 24},
        data_controls={"scoped_key_support": True},
        webhook_behavior={"supported": True}
    )
    from governance.models.request import GovernanceRequest
    req = GovernanceRequest(
        id="req-missing-evidence",
        workspace_id="default",
        governance_state="approved_for_execution",
        created_by="admin_test",
        request_payload={"prompt": "testing evidence"}
    )
    db_session.add(req)
    db_session.add(profile)
    db_session.commit()

    # 1. Register asset without webhook evidence
    asset_payload = {
        "request_id": "req-missing-evidence",
        "workspace_id": "default",
        "provider_key": "provider_x",
        "model_key": "model_y",
        "retention_class": "standard",
        "asset_payload": {"prompt": "testing evidence"}
    }
    resp = client.post("/api/governance/assets/evaluate", json=asset_payload, headers=headers)
    assert resp.status_code == 201
    asset_id = resp.json()["asset_id"]
    
    asset = db_session.query(GovernanceAsset).filter(GovernanceAsset.id == asset_id).first()
    assert asset is not None
    manifest = asset.rights_manifest_json
    
    # Missing evidence should contain webhook metadata and confidence score should be lower than 1.0
    assert "provider_webhook_metadata" in manifest["missing_evidence"]
    assert manifest["confidence_score"] < 1.0
    assert manifest["publish_cleared"] is False


def test_workspace_isolation_audit_logs(db_session: Session):
    # Setup user headers for 'default' workspace
    headers = {
        "X-User-Id": "admin_test",
        "X-User-Role": "admin",
        "X-Workspace-Id": "default"
    }

    # Attempt to list assets in workspace_2 -> should fail with 403 Forbidden
    resp = client.get("/api/governance/assets?workspace_id=workspace_2", headers=headers)
    assert resp.status_code == 403

    # Check that an access_denied event was written to the audit log
    event = db_session.query(GovernanceEvent).filter(
        GovernanceEvent.action == "access_denied",
        GovernanceEvent.workspace_id == "workspace_2"
    ).first()
    assert event is not None
    assert event.actor_id == "admin_test"
    assert "Cannot query another workspace" in event.reason
