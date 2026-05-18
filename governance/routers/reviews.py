"""
Router: /api/governance/reviews
GET  – reviewer queue (items in review_required state)
POST /{id}/decision – approve | reject | escalate | request_changes
"""
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from governance.database import get_db
from governance.engine.state_machine import transition, InvalidTransitionError
from governance.models.request import GovernanceRequest
from governance.models.asset import GovernanceAsset
from governance.schemas.request import GovernanceRequestDetail
from governance.schemas.asset import GovernanceAssetDetail

router = APIRouter(prefix="/api/governance/reviews", tags=["Reviews"])


def _actor(x_user_id: Optional[str] = Header(default=None)) -> str:
    return x_user_id or "anonymous"


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
def get_reviewer_queue(db: Session = Depends(get_db)):
    """Return all requests and assets currently in review_required state."""
    items: List[ReviewItem] = []

    reqs = (
        db.query(GovernanceRequest)
        .filter(GovernanceRequest.governance_state == "review_required")
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
        .filter(GovernanceAsset.governance_state == "review_required")
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
    db: Session = Depends(get_db),
    actor: str = Depends(_actor),
):
    decision_map = {
        "approve":          "reviewer_approve",
        "reject":           "reviewer_reject",
        "escalate":         "escalate",
        "request_changes":  "escalate",
    }
    trigger = decision_map.get(body.decision)
    if not trigger:
        raise HTTPException(status_code=400, detail=f"Unknown decision '{body.decision}'")

    # Try request first, then asset
    record = db.query(GovernanceRequest).filter(GovernanceRequest.id == item_id).first()
    record_type = "request"
    if record is None:
        record = db.query(GovernanceAsset).filter(GovernanceAsset.id == item_id).first()
        record_type = "asset"
    if record is None:
        raise HTTPException(status_code=404, detail="Review item not found")

    try:
        new_state = transition(
            db,
            current_state=record.governance_state,
            trigger=trigger,
            target_type=record_type,
            target_id=item_id,
            workspace_id=record.workspace_id,
            actor_id=actor,
            reason=body.reason,
        )
    except InvalidTransitionError as e:
        raise HTTPException(status_code=422, detail=str(e))

    record.governance_state = new_state
    record.updated_at = datetime.now(timezone.utc)
    db.commit()

    return ReviewDecisionOut(status=body.decision, updated_state=new_state)
