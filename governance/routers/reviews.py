"""
Router: /api/governance/reviews
GET  – reviewer queue (items in review_required state)
POST /{id}/decision – approve | reject | escalate | request_changes
"""
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from governance.database import get_db
from governance.engine.state_machine import transition, InvalidTransitionError
from governance.models.request import GovernanceRequest
from governance.models.asset import GovernanceAsset
from governance.schemas.request import GovernanceRequestDetail
from governance.schemas.asset import GovernanceAssetDetail

router = APIRouter(prefix="/api/governance/reviews", tags=["Reviews"])


from governance.auth import get_current_user, CurrentUser


class ReviewDecisionIn(BaseModel):
    decision: str              # approve | reject | escalate | request_changes
    reason: Optional[str] = None


class ReviewDecisionOut(BaseModel):
    status: str
    updated_state: str


class ReviewItem(BaseModel):
    item_type: str
    item_id: str
    workspace_id: str
    governance_state: str
    created_at: datetime
    updated_at: datetime
    policy_reasons: Optional[List[str]] = None
    created_by: Optional[str] = None


@router.get("", response_model=List[ReviewItem])
def get_reviewer_queue(current_user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """Return all requests and assets currently in review_required state for the current workspace."""
    items: List[ReviewItem] = []

    reqs = (
        db.query(GovernanceRequest)
        .filter(
            GovernanceRequest.governance_state.in_(["review_required", "escalated"]),
            GovernanceRequest.workspace_id == current_user.workspace_id
        )
        .order_by(GovernanceRequest.updated_at.asc())
        .all()
    )
    for r in reqs:
        reasons = (r.decision_summary or {}).get("reasons", []) if r.decision_summary else []
        items.append(ReviewItem(
            item_type="request",
            item_id=r.id,
            workspace_id=r.workspace_id,
            governance_state=r.governance_state,
            created_at=r.created_at,
            updated_at=r.updated_at,
            policy_reasons=reasons,
            created_by=r.created_by,
        ))

    assets = (
        db.query(GovernanceAsset)
        .filter(
            GovernanceAsset.governance_state.in_(["review_required", "escalated"]),
            GovernanceAsset.workspace_id == current_user.workspace_id
        )
        .order_by(GovernanceAsset.updated_at.asc())
        .all()
    )
    for a in assets:
        items.append(ReviewItem(
            item_type="asset",
            item_id=a.id,
            workspace_id=a.workspace_id,
            governance_state=a.governance_state,
            created_at=a.created_at,
            updated_at=a.updated_at,
        ))

    return items


@router.post("/{item_id}/decision", response_model=ReviewDecisionOut)
def submit_decision(
    item_id: str,
    body: ReviewDecisionIn,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    decision_map = {
        "approve":          "reviewer_approve",
        "reject":           "reviewer_reject",
        "escalate":         "escalate",
        "request_changes":  "request_changes",
    }
    base_trigger = decision_map.get(body.decision)
    if not base_trigger:
        raise HTTPException(status_code=400, detail=f"Unknown decision '{body.decision}'")

    # Try request first, then asset
    record = db.query(GovernanceRequest).filter(
        GovernanceRequest.id == item_id,
        GovernanceRequest.workspace_id == current_user.workspace_id
    ).first()
    record_type = "request"
    if record is None:
        record = db.query(GovernanceAsset).filter(
            GovernanceAsset.id == item_id,
            GovernanceAsset.workspace_id == current_user.workspace_id
        ).first()
        record_type = "asset"
    if record is None:
        raise HTTPException(status_code=404, detail="Review item not found in workspace")

    from governance.models.review_task import GovernanceReviewTask
    task = db.query(GovernanceReviewTask).filter(
        GovernanceReviewTask.target_id == item_id,
        GovernanceReviewTask.status.in_(["open", "assigned", "in_review"])
    ).first()

    if task and task.risk_severity in ("high", "critical") and base_trigger == "reviewer_approve":
        if not task.decision_by:
            task.decision_by = current_user.id
            task.status = "in_review"
            db.commit()
            return ReviewDecisionOut(status="first_approval_granted", updated_state=record.governance_state)
        elif task.decision_by == current_user.id:
            raise HTTPException(status_code=403, detail="Separation of Duties violation: Need a different reviewer for second approval")
        else:
            task.secondary_approved_by = current_user.id

    if record_type == "asset" and base_trigger == "reviewer_approve":
        trigger = "asset_reviewer_approve"
    else:
        trigger = base_trigger

    try:
        new_state = transition(
            db,
            current_state=record.governance_state,
            trigger=trigger,
            target_type=record_type,
            target_id=item_id,
            workspace_id=record.workspace_id,
            actor_id=current_user.id,
            reason=body.reason,
        )
    except InvalidTransitionError as e:
        raise HTTPException(status_code=422, detail=str(e))

    record.governance_state = new_state
    record.updated_at = datetime.now(timezone.utc)
    
    if task:
        task.status = "closed"
        task.decision = body.decision
        if not task.decision_by:
            task.decision_by = current_user.id
        task.closed_at = datetime.now(timezone.utc)

    db.commit()

    status_map = {
        "approve": "approved",
        "reject": "rejected",
        "escalate": "escalated",
        "request_changes": "changes_requested"
    }
    return ReviewDecisionOut(status=status_map.get(body.decision, body.decision), updated_state=new_state)
