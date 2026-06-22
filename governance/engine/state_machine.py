"""
Approval State Machine v2 – extended governance model with hash-chaining audit events.

States added in v2:
  warned, policy_evaluating, evidence_pending, rights_pending, publish_ready, cancelled

Every transition computes SHA-256(event content) and stores previous_event_hash
to form a tamper-evident audit chain.
"""
from __future__ import annotations
import hashlib
import json
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session

from governance.models.event import GovernanceEvent


class InvalidTransitionError(Exception):
    pass


# Allowed (current_state, trigger) → new_state
TRANSITIONS: dict[tuple[str, str], str] = {
    # ── Request pre-execution lifecycle ──────────────────────────────────────
    ("draft",                   "policy_pass"):             "policy_passed",
    ("draft",                   "policy_warn"):             "warned",
    ("draft",                   "policy_review_required"):  "review_required",
    ("draft",                   "policy_block"):            "blocked",
    ("draft",                   "cancel"):                  "cancelled",
    ("policy_passed",           "auto_approve"):            "approved_for_execution",
    ("warned",                  "auto_approve"):            "approved_for_execution",
    ("warned",                  "reviewer_approve"):        "approved_for_execution",
    ("review_required",         "reviewer_approve"):        "approved_for_execution",
    ("review_required",         "asset_reviewer_approve"):  "governance_passed",
    ("review_required",         "reviewer_reject"):         "rejected",
    ("review_required",         "request_exception"):       "exception_pending",
    ("review_required",         "request_changes"):         "changes_requested",
    ("review_required",         "escalate"):                "escalated",
    ("changes_requested",       "resubmit"):                "review_required",
    ("escalated",               "reviewer_approve"):        "approved_for_execution",
    ("escalated",               "reviewer_reject"):         "rejected",
    ("escalated",               "request_changes"):         "changes_requested",
    ("escalated",               "asset_reviewer_approve"):  "governance_passed",
    ("blocked",                 "request_exception"):       "exception_pending",
    ("exception_pending",       "exception_approve"):       "exception_approved",
    ("exception_pending",       "exception_reject"):        "rejected",
    ("exception_approved",      "grant_execution"):         "approved_for_execution",
    ("approved_for_execution",  "execute"):                 "executed",
    ("approved_for_execution",  "exception_expired"):       "blocked",
    # ── Asset lifecycle ───────────────────────────────────────────────────────
    ("executed",                "register_asset"):          "asset_registered",
    ("asset_registered",        "begin_evidence"):          "evidence_pending",
    ("evidence_pending",        "evidence_complete"):       "rights_pending",
    ("rights_pending",          "rights_complete"):         "governance_passed",
    ("asset_registered",        "asset_policy_pass"):       "governance_passed",
    ("asset_registered",        "asset_policy_review"):     "review_required",
    ("asset_registered",        "asset_policy_block"):      "blocked",
    ("governance_passed",       "publish_pass"):            "publish_ready",
    ("governance_passed",       "publish_block"):           "blocked",
    ("publish_ready",           "publish"):                 "published",
    ("governance_passed",       "publish"):                 "published",   # direct publish
    # ── Retention lifecycle ───────────────────────────────────────────────────
    ("governance_passed",       "expire"):                  "expired",
    ("published",               "expire"):                  "expired",
    ("publish_ready",           "expire"):                  "expired",
    ("expired",                 "delete"):                  "deleted",
}


def _compute_event_hash(event_data: dict, previous_hash: Optional[str]) -> str:
    """Compute SHA-256 of the event content + previous_hash for tamper-evidence."""
    occurred = event_data.get("occurred_at", "")
    if hasattr(occurred, "isoformat"):
        occurred = occurred.isoformat()
    payload = {
        "target_type":  event_data.get("target_type"),
        "target_id":    event_data.get("target_id"),
        "actor_id":     event_data.get("actor_id"),
        "action":       event_data.get("action"),
        "occurred_at":  str(occurred),
        "previous_hash": previous_hash or "",
    }
    raw = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def _get_previous_hash(db: Session, workspace_id: str, target_id: str) -> Optional[str]:
    """Fetch the most recent event_hash for this target to form the chain."""
    last_event = (
        db.query(GovernanceEvent)
        .filter(
            GovernanceEvent.workspace_id == workspace_id,
            GovernanceEvent.target_id == target_id,
            GovernanceEvent.event_hash.isnot(None),
        )
        .order_by(GovernanceEvent.occurred_at.desc())
        .first()
    )
    return last_event.event_hash if last_event else None


def transition(
    db: Session,
    *,
    current_state: str,
    trigger: str,
    target_type: str,
    target_id: str,
    workspace_id: str,
    actor_id: str,
    actor_type: str = "system",
    reason: Optional[str] = None,
    reason_code: Optional[str] = None,
    event_payload: Optional[dict] = None,
    correlation_id: Optional[str] = None,
    idempotency_key: Optional[str] = None,
    source_service: str = "state-machine",
) -> str:
    """
    Perform a state transition, write a hash-chained audit event, and return the new state.
    Raises InvalidTransitionError if the (current_state, trigger) pair is illegal.
    """
    key = (current_state, trigger)
    if key not in TRANSITIONS:
        raise InvalidTransitionError(
            f"No transition defined for state='{current_state}' trigger='{trigger}'"
        )

    new_state = TRANSITIONS[key]
    occurred_at = datetime.now(timezone.utc)

    # Idempotency guard – skip if this key was already processed
    if idempotency_key:
        existing = (
            db.query(GovernanceEvent)
            .filter(GovernanceEvent.idempotency_key == idempotency_key)
            .first()
        )
        if existing:
            return new_state

    previous_hash = _get_previous_hash(db, workspace_id, target_id)

    event_data = {
        "target_type": target_type,
        "target_id":   target_id,
        "actor_id":    actor_id,
        "action":      trigger,
        "occurred_at": occurred_at.isoformat(),
    }
    event_hash = _compute_event_hash(event_data, previous_hash)

    event = GovernanceEvent(
        workspace_id=workspace_id,
        schema_version="gov.event.v2",
        source_service=source_service,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
        target_type=target_type,
        target_id=target_id,
        actor_id=actor_id,
        actor_type=actor_type,
        action=trigger,
        reason=reason,
        reason_code=reason_code,
        event_payload=event_payload or {"from_state": current_state, "to_state": new_state},
        event_hash=event_hash,
        previous_event_hash=previous_hash,
        occurred_at=occurred_at,
    )
    db.add(event)
    db.flush()

    return new_state
