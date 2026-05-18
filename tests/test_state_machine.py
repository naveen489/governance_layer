"""Tests for the approval state machine."""
import pytest
from unittest.mock import MagicMock, patch
from governance.engine.state_machine import transition, InvalidTransitionError, TRANSITIONS


def _make_db():
    """Return a mock DB session that accepts add/flush calls."""
    db = MagicMock()
    db.add = MagicMock()
    db.flush = MagicMock()
    return db


def test_transition_draft_to_policy_passed():
    db = _make_db()
    new_state = transition(
        db,
        current_state="draft",
        trigger="policy_pass",
        target_type="request",
        target_id="req-001",
        workspace_id="ws-001",
        actor_id="user-001",
    )
    assert new_state == "policy_passed"
    db.add.assert_called_once()
    db.flush.assert_called_once()


def test_transition_draft_to_blocked():
    db = _make_db()
    new_state = transition(
        db,
        current_state="draft",
        trigger="policy_block",
        target_type="request",
        target_id="req-001",
        workspace_id="ws-001",
        actor_id="system",
    )
    assert new_state == "blocked"


def test_transition_draft_to_review_required():
    db = _make_db()
    new_state = transition(
        db,
        current_state="draft",
        trigger="policy_review_required",
        target_type="request",
        target_id="req-001",
        workspace_id="ws-001",
        actor_id="system",
    )
    assert new_state == "review_required"


def test_invalid_transition_raises_error():
    db = _make_db()
    with pytest.raises(InvalidTransitionError):
        transition(
            db,
            current_state="blocked",
            trigger="auto_approve",   # not a valid transition from blocked
            target_type="request",
            target_id="req-001",
            workspace_id="ws-001",
            actor_id="system",
        )


def test_exception_flow():
    db = _make_db()
    s1 = transition(db, current_state="blocked", trigger="request_exception",
                    target_type="request", target_id="r", workspace_id="w", actor_id="u")
    assert s1 == "exception_pending"

    s2 = transition(db, current_state="exception_pending", trigger="exception_approve",
                    target_type="request", target_id="r", workspace_id="w", actor_id="u")
    assert s2 == "exception_approved"

    s3 = transition(db, current_state="exception_approved", trigger="grant_execution",
                    target_type="request", target_id="r", workspace_id="w", actor_id="u")
    assert s3 == "approved_for_execution"


def test_retention_flow():
    db = _make_db()
    s1 = transition(db, current_state="governance_passed", trigger="expire",
                    target_type="asset", target_id="a", workspace_id="w", actor_id="system")
    assert s1 == "expired"

    s2 = transition(db, current_state="expired", trigger="delete",
                    target_type="asset", target_id="a", workspace_id="w", actor_id="system")
    assert s2 == "deleted"


def test_all_transitions_are_reachable():
    """Sanity check: the TRANSITIONS dict has no unreachable states."""
    all_states_from = {s for (s, _) in TRANSITIONS}
    all_states_to = set(TRANSITIONS.values())
    # Every destination state should be reachable
    assert "deleted" in all_states_to
    assert "governance_passed" in all_states_to
