"""
Router: /api/governance/exceptions
POST          – submit exception request
GET           – list exceptions (filterable by status)
PATCH /{id}   – approve | reject exception
"""
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
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


from governance.auth import get_current_user, CurrentUser


@router.post("", response_model=SubmitExceptionOut, status_code=201)
def submit_exception(
    body: SubmitExceptionIn,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    exc_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    
    workspace_id = current_user.workspace_id
    if body.workspace_id and body.workspace_id != workspace_id:
        from governance.auth import audit_access_denied
        audit_access_denied(db, current_user.user_id, body.workspace_id, "create_exception", "Cannot create exception in another workspace")
        raise HTTPException(status_code=403, detail="Cannot create exception in another workspace")

    exc = GovernanceException(
        id=exc_id,
        workspace_id=workspace_id,
        target_type=body.target_type,
        target_id=body.target_id,
        requested_by=current_user.id,
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
        workspace_id=workspace_id,
        target_type="exception",
        target_id=exc_id,
        actor_id=current_user.id,
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
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if workspace_id and workspace_id != current_user.workspace_id:
        from governance.auth import audit_access_denied
        audit_access_denied(db, current_user.user_id, workspace_id, "list_exceptions", "Cannot query another workspace")
        raise HTTPException(status_code=403, detail="Cannot query another workspace")
    
    q = db.query(GovernanceException).filter(GovernanceException.workspace_id == current_user.workspace_id)
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
    current_user: CurrentUser = Depends(get_current_user),
):
    exc = db.query(GovernanceException).filter(
        GovernanceException.id == exception_id,
        GovernanceException.workspace_id == current_user.workspace_id
    ).first()
    if not exc:
        raise HTTPException(status_code=404, detail="Exception not found in workspace")
    if exc.status != "pending":
        raise HTTPException(status_code=422, detail=f"Exception is already '{exc.status}'")
    if exc.requested_by == current_user.id:
        raise HTTPException(status_code=403, detail="Separation of Duties violation: Cannot approve own exception")

    if body.decision not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="Decision must be 'approve' or 'reject'")

    now = datetime.now(timezone.utc)
    exc.status = "approved" if body.decision == "approve" else "rejected"
    exc.approved_by = current_user.id
    exc.updated_at = now
    if body.expiry_at and body.decision == "approve":
        exc.expiry_at = body.expiry_at
    if body.scope_json and body.decision == "approve":
        exc.scope_json = body.scope_json

    event = GovernanceEvent(
        workspace_id=exc.workspace_id,
        target_type="exception",
        target_id=exception_id,
        actor_id=current_user.id,
        action=f"exception_{exc.status}",
        reason=body.reason,
        event_payload={"decision": body.decision, "scope_json": body.scope_json},
        occurred_at=now,
    )
    db.add(event)
    db.commit()
    db.refresh(exc)
    return exc
