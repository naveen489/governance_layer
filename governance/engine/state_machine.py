"""
Approval State Machine – implements the 13-state governance model.

States:
  draft → policy_passed → approved_for_execution → executed → asset_registered
       → review_required → (approved_for_execution | rejected | exception_pending)
       → blocked → exception_pending
       → exception_pending → (exception_approved | rejected)
       → exception_approved → approved_for_execution
       → governance_passed → expired → deleted

Every transition writes an immutable governance event.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session

from governance.models.event import GovernanceEvent


class InvalidTransitionError(Exception):
    pass


# Allowed (current_state, trigger) → new_state
TRANSITIONS: dict[tuple[str, str], str] = {
    # Request lifecycle
    ("draft", "policy_pass"):                   "policy_passed",
    ("draft", "policy_warn"):                   "policy_passed",
    ("draft", "policy_review_required"):        "review_required",
    ("draft", "policy_block"):                  "blocked",
    ("policy_passed", "auto_approve"):          "approved_for_execution",
    ("review_required", "reviewer_approve"):    "approved_for_execution",
    ("review_required", "reviewer_reject"):     "rejected",
    ("review_required", "request_exception"):   "exception_pending",
    ("blocked", "request_exception"):           "exception_pending",
    ("exception_pending", "exception_approve"): "exception_approved",
    ("exception_pending", "exception_reject"):  "rejected",
    ("exception_approved", "grant_execution"):  "approved_for_execution",
    ("approved_for_execution", "execute"):      "executed",
    # Asset lifecycle
    ("executed", "register_asset"):             "asset_registered",
    ("asset_registered", "asset_policy_pass"):  "governance_passed",
    ("asset_registered", "asset_policy_review"): "review_required",
    ("asset_registered", "asset_policy_block"): "blocked",
    # Retention lifecycle
    ("governance_passed", "expire"):            "expired",
    ("expired", "delete"):                      "deleted",
    # Re-review after changes
    ("review_required", "escalate"):            "review_required",
}





def transition(
    db: Session,
    *,
    current_state: str,
    trigger: str,
    target_type: str,   # request | asset | exception | policy
    target_id: str,
    workspace_id: str,
    actor_id: str,
    reason: Optional[str] = None,
    event_payload: Optional[dict] = None,
) -> str:
    """
    Perform a state transition, write an audit event, and return the new state.
    Raises InvalidTransitionError if the (current_state, trigger) pair is illegal.
    """
    key = (current_state, trigger)
    if key not in TRANSITIONS:
        raise InvalidTransitionError(
            f"No transition defined for state='{current_state}' trigger='{trigger}'"
        )

    new_state = TRANSITIONS[key]

    event = GovernanceEvent(
        workspace_id=workspace_id,
        target_type=target_type,
        target_id=target_id,
        actor_id=actor_id,
        action=trigger,
        reason=reason,
        event_payload=event_payload or {"from_state": current_state, "to_state": new_state},
        occurred_at=datetime.now(timezone.utc),
    )
    db.add(event)
    db.flush()

    return new_state
