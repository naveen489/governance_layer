"""Tests for the policy evaluator engine."""
import pytest
from unittest.mock import MagicMock
from governance.engine.policy_evaluator import evaluate_policy, PolicyDecision
from governance.models.policy import GovernancePolicy
from datetime import datetime, timezone


def _make_db_with_policy(policy_json, scope="request"):
    """Return a mock DB session that returns a policy row."""
    mock_policy = GovernancePolicy(
        id="test-policy-id",
        workspace_id="default",
        policy_scope=scope,
        version=1,
        policy_json=policy_json,
        is_active=True,
        effective_from=datetime.now(timezone.utc),
        effective_to=None,
        created_at=datetime.now(timezone.utc),
    )
    # The evaluator calls: db.query(GovernancePolicy)
    #   .filter(ws).filter(scope).filter(is_active).order_by(version).first()
    # Build a chain where filter() returns chain, order_by returns terminal, first returns policy
    terminal = MagicMock()
    terminal.first.return_value = mock_policy
    chain = MagicMock()
    chain.filter.return_value = chain
    chain.order_by.return_value = terminal
    db = MagicMock()
    db.query.return_value = chain
    return db


def _make_db_no_policy():
    """Return a mock DB session where no policy is found (first() returns None)."""
    terminal = MagicMock()
    terminal.first.return_value = None
    chain = MagicMock()
    chain.filter.return_value = chain
    chain.order_by.return_value = terminal
    db = MagicMock()
    db.query.return_value = chain
    return db


SAMPLE_POLICY = {
    "rules": [
        {
            "rule_id": "high_risk_block",
            "when": {"risk_class": "high"},
            "then": {"action": "block", "reason": "High risk content"},
        },
        {
            "rule_id": "unknown_provider_review",
            "when": {"provider_status": "unknown"},
            "then": {"action": "review_required", "reason": "Unknown provider"},
        },
        {
            "rule_id": "medium_risk_warn",
            "when": {"risk_class": "medium"},
            "then": {"action": "warn", "reason": "Medium risk warning"},
        },
    ]
}


def test_evaluate_policy_pass_when_no_active_policy():
    """When no active policy is found, default to pass."""
    db = _make_db_no_policy()
    decision = evaluate_policy(db, scope="request", payload={"risk_class": "low"})
    assert decision.action == "pass"


def test_evaluate_policy_block_on_high_risk():
    """High risk payload must return block."""
    db = _make_db_with_policy(SAMPLE_POLICY)
    decision = evaluate_policy(db, scope="request", payload={"risk_class": "high"})
    assert decision.action == "block"
    assert "high_risk_block" in decision.rule_ids


def test_evaluate_policy_review_on_unknown_provider():
    """Unknown provider should trigger review_required."""
    db = _make_db_with_policy(SAMPLE_POLICY)
    decision = evaluate_policy(db, scope="request", payload={"provider_status": "unknown"})
    assert decision.action == "review_required"


def test_evaluate_policy_block_wins_over_warn():
    """Block should win over warn when both rules match."""
    db = _make_db_with_policy(SAMPLE_POLICY)
    decision = evaluate_policy(
        db, scope="request",
        payload={"risk_class": "high", "provider_status": "unknown"},
    )
    # block > review_required (both triggered), block should win
    assert decision.action == "block"


def test_evaluate_policy_warn_on_medium_risk():
    """Medium risk payload should trigger warn."""
    db = _make_db_with_policy(SAMPLE_POLICY)
    decision = evaluate_policy(db, scope="request", payload={"risk_class": "medium"})
    assert decision.action == "warn"
    assert "medium_risk_warn" in decision.rule_ids
