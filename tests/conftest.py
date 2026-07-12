"""
Pytest configuration.
Uses sqlite:///:memory: which is now pooled with StaticPool in database.py.
"""
import os
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

# Must set before importing anything from governance
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from governance.database import Base, engine, get_db
from governance.main import app
from governance.models.request import GovernanceRequest
from governance.models.asset import GovernanceAsset
from governance.models.event import GovernanceEvent
from governance.models.exception import GovernanceException
from governance.models.policy import GovernancePolicy

from governance.auth import get_current_user, CurrentUser
from fastapi import Request

def override_get_current_user(request: Request):
    user_id = request.headers.get("X-User-Id", "test-user")
    role = request.headers.get("X-User-Role", "admin")
    workspace_id = request.headers.get("X-Workspace-Id", "default")
    return CurrentUser(user_id=user_id, role=role, workspace_id=workspace_id)

app.dependency_overrides[get_current_user] = override_get_current_user

# We don't override get_db because the normal get_db uses SessionLocal, 
# which is bound to the StaticPool engine!

@pytest.fixture(scope="session")
def client():
    """
    Session-scoped TestClient that initializes the db.
    """
    Base.metadata.create_all(bind=engine)

    from governance.database import SessionLocal
    from datetime import datetime, timezone
    db = SessionLocal()
    
    if not db.query(GovernancePolicy).filter(GovernancePolicy.id == "shared-req-pol").first():
        pol = GovernancePolicy(
            id="shared-req-pol",
            workspace_id="default",
            policy_scope="request",
            version=1,
            policy_json={
                "rules": [
                    {"rule_id": "block_high", "when": {"risk_class": "high"}, "then": {"action": "block", "reason": "High risk"}},
                    {"rule_id": "review_unknown", "when": {"provider_status": "unknown"}, "then": {"action": "review_required", "reason": "Unknown provider"}},
                ]
            },
            is_active=True,
            effective_from=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
        )
        db.add(pol)
    if not db.query(GovernancePolicy).filter(GovernancePolicy.id == "shared-asset-pol").first():
        pol2 = GovernancePolicy(
            id="shared-asset-pol",
            workspace_id="default",
            policy_scope="asset",
            version=1,
            policy_json={"rules": []},
            is_active=True,
            effective_from=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
        )
        db.add(pol2)
    if not db.query(GovernancePolicy).filter(GovernancePolicy.id == "shared-publish-pol").first():
        pol3 = GovernancePolicy(
            id="shared-publish-pol",
            workspace_id="default",
            policy_scope="publish",
            version=1,
            policy_json={"rules": []},
            is_active=True,
            effective_from=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
        )
        db.add(pol3)
    db.commit()
    db.close()

    with patch("governance.scheduler.start_scheduler"), \
         patch("governance.scheduler.stop_scheduler"):
        with TestClient(app) as c:
            yield c

    Base.metadata.drop_all(bind=engine)
