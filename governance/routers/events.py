"""
Router: /api/governance/events
GET – audit log with filters: workspace_id, target_type, target_id, actor_id,
      action, date_from, date_to
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
