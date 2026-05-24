import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from governance.main import app
from governance.database import Base, engine, get_db, SessionLocal
from governance.models.request import GovernanceRequest
from governance.models.asset import GovernanceAsset
from governance.models.exception import GovernanceException
from governance.models.event import GovernanceEvent
from governance.engine.retention import expire_exceptions

client = TestClient(app)

@pytest.fixture
def db_session(client):
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def test_reviewer_escalate_workflow(db_session: Session):
    # Create request in review_required
    req = GovernanceRequest(
        id="req-escalate-123",
        workspace_id="default",
        governance_state="review_required",
        created_by="user1",
        request_payload={"prompt": "test"}
    )
    db_session.add(req)
    db_session.commit()

    # 1. request_changes -> changes_requested
    resp = client.post("/api/governance/reviews/req-escalate-123/decision", json={"decision": "request_changes", "reason": "need updates"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "changes_requested"
    assert resp.json()["updated_state"] == "changes_requested"
    
    # 2. Resubmit (manually transitioning via state machine for test sake, since resubmit endpoint isn't defined explicitly in reviews router yet)
    # wait, there's no endpoint for 'resubmit'. But let's escalate from review_required.
    req.governance_state = "review_required"
    db_session.commit()
    
    resp = client.post("/api/governance/reviews/req-escalate-123/decision", json={"decision": "escalate", "reason": "need legal"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "escalated"
    assert resp.json()["updated_state"] == "escalated"
    
    # 3. approve from escalated -> approved_for_execution
    resp = client.post("/api/governance/reviews/req-escalate-123/decision", json={"decision": "approve"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"
    assert resp.json()["updated_state"] == "approved_for_execution"


def test_exception_auto_expiry_reverts_request(db_session: Session):
    # Create request in approved_for_execution
    req = GovernanceRequest(
        id="req-exp-123",
        workspace_id="default",
        governance_state="approved_for_execution",
        created_by="user1",
        request_payload={"prompt": "test"}
    )
    # Create an expired exception targeting this request
    exc = GovernanceException(
        id="exc-123",
        workspace_id="default",
        target_type="request",
        target_id="req-exp-123",
        requested_by="user1",
        business_reason="test",
        status="approved",
        expiry_at=datetime.now(timezone.utc) - timedelta(minutes=5)
    )
    db_session.add(req)
    db_session.add(exc)
    db_session.commit()

    # Trigger auto-expiry
    count = expire_exceptions(db_session)
    assert count == 1
    
    db_session.refresh(req)
    db_session.refresh(exc)
    
    # Exception should be expired, request should be reverted to blocked
    assert exc.status == "expired"
    assert req.governance_state == "blocked"


def test_audit_log_keyword_search(db_session: Session):
    # Insert events with specific reasons
    evt1 = GovernanceEvent(
        id="evt-1",
        workspace_id="default",
        target_type="request",
        target_id="req-1",
        actor_id="user1",
        action="approve",
        reason="SuperUniqueKeyword search string",
        occurred_at=datetime.now(timezone.utc)
    )
    evt2 = GovernanceEvent(
        id="evt-2",
        workspace_id="default",
        target_type="request",
        target_id="req-1",
        actor_id="user1",
        action="reject",
        reason="Completely different",
        occurred_at=datetime.now(timezone.utc)
    )
    db_session.add_all([evt1, evt2])
    db_session.commit()

    resp = client.get("/api/governance/events?q=SuperUniqueKeyword")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["events"][0]["reason"] == "SuperUniqueKeyword search string"


def test_publish_policy_endpoint(db_session: Session):
    # Create asset in governance_passed
    asset = GovernanceAsset(
        id="asset-pub-123",
        workspace_id="default",
        request_id="req-1",
        provider_key="openai",
        model_key="gpt-4o",
        governance_state="governance_passed",
        retention_class="standard",
        asset_payload={"text": "Hello world"},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    db_session.add(asset)
    db_session.commit()

    # Without a publish policy, it should default to pass and go to published
    resp = client.post("/api/governance/assets/asset-pub-123/publish")
    assert resp.status_code == 200
    assert resp.json()["state"] == "published"
    
    db_session.refresh(asset)
    assert asset.governance_state == "published"
