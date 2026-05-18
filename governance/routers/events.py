"""
Router: /api/governance/events
GET – audit log with filters: workspace_id, target_type, target_id, actor_id,
      action, date_from, date_to
"""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from governance.database import get_db
from governance.models.event import GovernanceEvent
from governance.schemas.event import GovernanceEventsResponse, GovernanceEventOut

router = APIRouter(prefix="/api/governance/events", tags=["Audit Events"])


@router.get("", response_model=GovernanceEventsResponse)
def query_events(
    workspace_id: Optional[str] = Query(default=None),
    target_type: Optional[str] = Query(default=None),
    target_id: Optional[str] = Query(default=None),
    actor_id: Optional[str] = Query(default=None),
    action: Optional[str] = Query(default=None),
    date_from: Optional[datetime] = Query(default=None),
    date_to: Optional[datetime] = Query(default=None),
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0),
    db: Session = Depends(get_db),
):
    q = db.query(GovernanceEvent)
    if workspace_id:
        q = q.filter(GovernanceEvent.workspace_id == workspace_id)
    if target_type:
        q = q.filter(GovernanceEvent.target_type == target_type)
    if target_id:
        q = q.filter(GovernanceEvent.target_id == target_id)
    if actor_id:
        q = q.filter(GovernanceEvent.actor_id == actor_id)
    if action:
        q = q.filter(GovernanceEvent.action == action)
    if date_from:
        q = q.filter(GovernanceEvent.occurred_at >= date_from)
    if date_to:
        q = q.filter(GovernanceEvent.occurred_at <= date_to)

    total = q.count()
    events = q.order_by(GovernanceEvent.occurred_at.desc()).offset(offset).limit(limit).all()
    return GovernanceEventsResponse(events=events, total=total)
