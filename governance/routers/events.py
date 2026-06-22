"""
Router: /api/governance/events (v2)
GET  – audit log with extended filters including correlation_id, reason_code
GET /integrity-check – tamper-evidence chain validation
"""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from governance.database import get_db
from governance.models.event import GovernanceEvent
from governance.schemas.event import GovernanceEventsResponse, GovernanceEventOut

router = APIRouter(prefix="/api/governance/events", tags=["Audit Events"])

from governance.auth import get_current_user, CurrentUser


@router.get("", response_model=GovernanceEventsResponse)
def query_events(
    workspace_id: Optional[str] = Query(default=None),
    target_type: Optional[str] = Query(default=None),
    target_id: Optional[str] = Query(default=None),
    actor_id: Optional[str] = Query(default=None),
    action: Optional[str] = Query(default=None),
    correlation_id: Optional[str] = Query(default=None),
    reason_code: Optional[str] = Query(default=None),
    date_from: Optional[datetime] = Query(default=None),
    date_to: Optional[datetime] = Query(default=None),
    q: Optional[str] = Query(default=None),
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if workspace_id and workspace_id != current_user.workspace_id:
        raise HTTPException(status_code=403, detail="Cannot query another workspace")

    query = db.query(GovernanceEvent).filter(GovernanceEvent.workspace_id == current_user.workspace_id)
    if target_type:
        query = query.filter(GovernanceEvent.target_type == target_type)
    if target_id:
        query = query.filter(GovernanceEvent.target_id == target_id)
    if actor_id:
        query = query.filter(GovernanceEvent.actor_id == actor_id)
    if action:
        query = query.filter(GovernanceEvent.action == action)
    if correlation_id:
        query = query.filter(GovernanceEvent.correlation_id == correlation_id)
    if reason_code:
        query = query.filter(GovernanceEvent.reason_code == reason_code)
    if date_from:
        query = query.filter(GovernanceEvent.occurred_at >= date_from)
    if date_to:
        query = query.filter(GovernanceEvent.occurred_at <= date_to)
    if q:
        search_pattern = f"%{q}%"
        from sqlalchemy import or_, cast, String
        query = query.filter(
            or_(
                GovernanceEvent.reason.ilike(search_pattern),
                cast(GovernanceEvent.event_payload, String).ilike(search_pattern)
            )
        )

    total = query.count()
    events = query.order_by(GovernanceEvent.occurred_at.desc()).offset(offset).limit(limit).all()
    return GovernanceEventsResponse(events=events, total=total)


@router.get("/integrity-check")
def integrity_check(
    target_id: Optional[str] = Query(default=None),
    limit: int = Query(default=100, le=500),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Validate the SHA-256 hash chain for audit events.
    Checks that each event's previous_event_hash matches the prior event's event_hash.
    Returns: total events checked, broken links, and integrity verdict.
    """
    import hashlib, json

    q = db.query(GovernanceEvent).filter(GovernanceEvent.workspace_id == current_user.workspace_id)
    if target_id:
        q = q.filter(GovernanceEvent.target_id == target_id)
    events = q.order_by(GovernanceEvent.occurred_at.asc()).limit(limit).all()

    broken_links = []
    prev_hash = None

    for event in events:
        if event.event_hash is None:
            # Legacy v1 event – skip
            continue
        if prev_hash is not None and event.previous_event_hash != prev_hash:
            broken_links.append({
                "event_id": event.id,
                "expected_previous_hash": prev_hash,
                "stored_previous_hash": event.previous_event_hash,
            })
        prev_hash = event.event_hash

    total_checked = len([e for e in events if e.event_hash is not None])
    return {
        "total_events_checked": total_checked,
        "broken_links": len(broken_links),
        "integrity": "valid" if not broken_links else "tampered",
        "details": broken_links,
    }
