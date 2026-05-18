"""
Pytest configuration – shared test database, TestClient, and scheduler mock.
Everything is session-scoped so fixtures are set up exactly once.
"""
import os
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

TEST_ENGINE = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=TEST_ENGINE)


def get_test_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="session")
def client():
    """
    Session-scoped TestClient that:
    1. Creates all ORM tables in the test engine.
    2. Overrides the get_db dependency.
    3. Mocks the scheduler.
    4. Seeds a basic policy so API evaluation works.
    """
    from governance.models import request, asset, event, exception, policy  # noqa
    from governance.database import Base, get_db
    from governance.main import app

    Base.metadata.create_all(bind=TEST_ENGINE)
    app.dependency_overrides[get_db] = get_test_db

    # Seed a request-scope policy
    from governance.models.policy import GovernancePolicy
    from datetime import datetime, timezone
    db = TestSessionLocal()
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
    db.commit()
    db.close()

    with patch("governance.scheduler.start_scheduler"), \
         patch("governance.scheduler.stop_scheduler"):
        with TestClient(app) as c:
            yield c

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=TEST_ENGINE)
