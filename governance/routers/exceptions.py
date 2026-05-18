"""
Router: /api/governance/exceptions
POST          – submit exception request
GET           – list exceptions (filterable by status)
PATCH /{id}   – approve | reject exception
"""
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from governance.database import get_db
from governance.models.exception import GovernanceException
from governance.models.event import GovernanceEvent
from governance.schemas.exception import (
    SubmitExceptionIn,
    SubmitExceptionOut,
    ExceptionDecisionIn,
    GovernanceExceptionDetail,
    GovernanceExceptionsResponse,
)

router = APIRouter(prefix="/api/governance/exceptions", tags=["Exceptions"])


def _actor(x_user_id: Optional[str] = Header(default=None)) -> str:
    return x_user_id or "anonymous"


@router.post("", response_model=SubmitExceptionOut, status_code=201)
def submit_exception(
    body: SubmitExceptionIn,
    db: Session = Depends(get_db),
    actor: str = Depends(_actor),
):
    exc_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    exc = GovernanceException(
        id=exc_id,
        workspace_id=body.workspace_id or "default",
        target_type=body.target_type,
        target_id=body.target_id,
        requested_by=actor,
        status="pending",
        scope_json=body.scope_json,
        expiry_at=body.expiry_at,
        business_reason=body.business_reason,
        created_at=now,
        updated_at=now,
    )
    db.add(exc)

    # Audit event
    event = GovernanceEvent(
        workspace_id=body.workspace_id or "default",
        target_type="exception",
        target_id=exc_id,
        actor_id=actor,
        action="exception_submitted",
        reason=body.business_reason,
        event_payload={"target_type": body.target_type, "target_id": body.target_id},
        occurred_at=now,
    )
    db.add(event)
    db.commit()

    return SubmitExceptionOut(exception_id=exc_id, status="pending")


@router.get("", response_model=GovernanceExceptionsResponse)
def list_exceptions(
    workspace_id: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    target_type: Optional[str] = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0),
    db: Session = Depends(get_db),
):
    q = db.query(GovernanceException)
    if workspace_id:
        q = q.filter(GovernanceException.workspace_id == workspace_id)
    if status:
        q = q.filter(GovernanceException.status == status)
    if target_type:
        q = q.filter(GovernanceException.target_type == target_type)

    total = q.count()
    items = q.order_by(GovernanceException.created_at.desc()).offset(offset).limit(limit).all()
    return GovernanceExceptionsResponse(exceptions=items, total=total)


@router.patch("/{exception_id}", response_model=GovernanceExceptionDetail)
def decide_exception(
    exception_id: str,
    body: ExceptionDecisionIn,
    db: Session = Depends(get_db),
    actor: str = Depends(_actor),
):
    exc = db.query(GovernanceException).filter(GovernanceException.id == exception_id).first()
    if not exc:
        raise HTTPException(status_code=404, detail="Exception not found")
    if exc.status != "pending":
        raise HTTPException(status_code=422, detail=f"Exception is already '{exc.status}'")

    if body.decision not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="Decision must be 'approve' or 'reject'")

    now = datetime.now(timezone.utc)
    exc.status = "approved" if body.decision == "approve" else "rejected"
    exc.approved_by = actor
    exc.updated_at = now
    if body.expiry_at and body.decision == "approve":
        exc.expiry_at = body.expiry_at
    if body.scope_json and body.decision == "approve":
        exc.scope_json = body.scope_json

    event = GovernanceEvent(
        workspace_id=exc.workspace_id,
        target_type="exception",
        target_id=exception_id,
        actor_id=actor,
        action=f"exception_{exc.status}",
        reason=body.reason,
        event_payload={"decision": body.decision, "scope_json": body.scope_json},
        occurred_at=now,
    )
    db.add(event)
    db.commit()
    db.refresh(exc)
    return exc
