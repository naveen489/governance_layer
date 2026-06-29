import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from governance.main import app
from governance.models.asset import GovernanceAsset
from governance.models.exception import GovernanceException
from governance.models.review_task import GovernanceReviewTask
from governance.models.incident import GovernanceIncident
from governance.models.event import GovernanceEvent

from governance.database import SessionLocal

client = TestClient(app)

@pytest.fixture
def db_session(client):
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def test_webhook_ingestion(db_session: Session):
    headers = {"X-Provider-Signature": "valid_signature_123", "X-Idempotency-Key": "test_idemp_1"}
    payload = {"type": "content_moderation_block", "workspace_id": "test_ws"}
    
    resp = client.post("/api/governance/webhooks/qualityops", json=payload, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["processing_status"] == "processed"
    assert "normalized_event_id" in data
    
    # Test deduplication
    resp2 = client.post("/api/governance/webhooks/qualityops", json=payload, headers=headers)
    assert resp2.status_code == 200
    assert resp2.json()["processing_status"] == "deduplicated"


def test_separation_of_duties(db_session: Session):
    # Setup current user
    user_id = "test_user_id"
    
    # Submit exception
    resp = client.post("/api/governance/exceptions", json={
        "workspace_id": "default",
        "target_type": "asset",
        "target_id": "a1",
        "business_reason": "Need it"
    }, headers={"X-User-Id": user_id, "X-User-Role": "admin", "X-Workspace-Id": "default"})
    
    assert resp.status_code == 201
    exc_id = resp.json()["exception_id"]
    
    # Try to approve it as the same user
    resp = client.patch(f"/api/governance/exceptions/{exc_id}", json={
        "decision": "approve",
        "reason": "I approve my own request"
    }, headers={"X-User-Id": user_id, "X-User-Role": "admin", "X-Workspace-Id": "default"})
    
    assert resp.status_code == 403
    assert "Separation of Duties violation" in resp.json()["detail"]


def test_two_level_approval(db_session: Session):
    user_1 = "reviewer_1"
    user_2 = "reviewer_2"
    
    task = GovernanceReviewTask(
        workspace_id="default",
        target_type="asset",
        target_id="asset_123",
        risk_severity="high",
        status="open"
    )
    db_session.add(task)
    db_session.commit()
    
    # Mock an asset in review_required
    asset = GovernanceAsset(
        id="asset_123",
        workspace_id="default",
        request_id="req1",
        provider_key="test",
        model_key="test",
        governance_state="review_required"
    )
    db_session.add(asset)
    db_session.commit()

    # First approval
    resp = client.post("/api/governance/reviews/asset_123/decision", json={
        "decision": "approve", "reason": "Looks ok"
    }, headers={"X-User-Id": user_1, "X-User-Role": "admin", "X-Workspace-Id": "default"})
    
    assert resp.status_code == 200
    assert resp.json()["status"] == "first_approval_granted"
    
    # Same user tries second approval
    resp = client.post("/api/governance/reviews/asset_123/decision", json={
        "decision": "approve", "reason": "Looks ok again"
    }, headers={"X-User-Id": user_1, "X-User-Role": "admin", "X-Workspace-Id": "default"})
    
    assert resp.status_code == 403
    
    # Different user approves
    resp = client.post("/api/governance/reviews/asset_123/decision", json={
        "decision": "approve", "reason": "Second reviewer agrees"
    }, headers={"X-User-Id": user_2, "X-User-Role": "admin", "X-Workspace-Id": "default"})
    
    assert resp.status_code == 200
    assert resp.json()["updated_state"] == "governance_passed"


def test_quality_verdict_update(db_session: Session):
    asset = GovernanceAsset(
        id="asset_q1",
        workspace_id="default",
        request_id="req1",
        provider_key="p1",
        model_key="m1",
        governance_state="asset_registered"
    )
    db_session.add(asset)
    db_session.commit()
    
    resp = client.patch("/api/governance/assets/asset_q1/quality-verdict", json={
        "quality_verdict_ref": "PASS_123"
    }, headers={"X-User-Id": "test", "X-User-Role": "admin", "X-Workspace-Id": "default"})
    
    assert resp.status_code == 200
    db_session.refresh(asset)
    assert asset.quality_verdict_ref == "PASS_123"


def test_incident_auto_creation(db_session: Session):
    from governance.engine.incident_engine import check_repeated_blocks
    
    # Seed 3 blocks
    for i in range(3):
        e = GovernanceEvent(
            workspace_id="ws_incident",
            target_type="asset",
            target_id=f"a_{i}",
            actor_id="bad_user",
            action="policy_block",
            reason="Violation",
            occurred_at=datetime.now(timezone.utc)
        )
        db_session.add(e)
    db_session.commit()
    
    incident = check_repeated_blocks(db_session, workspace_id="ws_incident")
    assert incident is not None
    assert incident.severity == "high"


def test_compliance_export(db_session: Session):
    # Add a dummy event
    e = GovernanceEvent(
        workspace_id="default",
        target_type="asset",
        target_id="a1",
        actor_id="user1",
        action="test",
        reason="test",
        occurred_at=datetime.now(timezone.utc)
    )
    db_session.add(e)
    db_session.commit()
    
    resp = client.get("/api/governance/events/export", headers={"X-User-Id": "test", "X-User-Role": "admin", "X-Workspace-Id": "default"})
    assert resp.status_code == 200
    data = resp.json()
    assert "bundle_signature" in data
    assert len(data["events"]) >= 1
