"""
Router: /api/governance/legal-holds
Legal Hold and Incident Hold management endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import Optional

from governance.database import get_db
from governance.auth import get_current_user, CurrentUser
from governance.models.legal_hold import LegalHold
from governance.models.event import GovernanceEvent
from governance.models.asset import GovernanceAsset

router = APIRouter(prefix="/api/governance/legal-holds", tags=["Legal Holds"])


class CreateHoldRequest(BaseModel):
    target_type: str          # request | asset | exception
    target_id: str
    hold_type: str            # legal | incident
    reason: str
    workspace_id: Optional[str] = "default"


class ReleaseHoldRequest(BaseModel):
    release_reason: str


@router.post("", status_code=201)
def create_hold(
    body: CreateHoldRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Create a legal or incident hold on a target record."""
    if body.target_type == "asset":
        asset = db.query(GovernanceAsset).filter(
            GovernanceAsset.id == body.target_id,
            GovernanceAsset.workspace_id == user.workspace_id
        ).first()
        if not asset:
            raise HTTPException(status_code=404, detail="Target asset not found in workspace.")
        if body.hold_type == "legal":
            asset.legal_hold = True
        elif body.hold_type == "incident":
            asset.incident_hold = True

    hold = LegalHold(
        workspace_id=user.workspace_id,
        target_type=body.target_type,
        target_id=body.target_id,
        hold_type=body.hold_type,
        reason=body.reason,
        owner_id=user.user_id,
        status="active",
    )
    db.add(hold)

    # Audit event
    db.add(GovernanceEvent(
        workspace_id=user.workspace_id,
        source_service="legal-hold-service",
        target_type=body.target_type,
        target_id=body.target_id,
        actor_id=user.user_id,
        actor_type="user",
        action="legal_hold_created",
        reason=body.reason,
        reason_code="HOLD_CREATED",
        event_payload={"hold_type": body.hold_type},
        occurred_at=datetime.now(timezone.utc),
    ))
    db.commit()
    db.refresh(hold)

    return {
        "hold_id": hold.id,
        "status": hold.status,
        "hold_type": hold.hold_type,
        "target_type": hold.target_type,
        "target_id": hold.target_id,
        "created_at": hold.created_at,
    }


@router.get("")
def list_holds(
    target_id: Optional[str] = None,
    hold_type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """List legal/incident holds with optional filters."""
    q = db.query(LegalHold).filter(LegalHold.workspace_id == user.workspace_id)
    if target_id:
        q = q.filter(LegalHold.target_id == target_id)
    if hold_type:
        q = q.filter(LegalHold.hold_type == hold_type)
    if status:
        q = q.filter(LegalHold.status == status)
    holds = q.order_by(LegalHold.created_at.desc()).limit(limit).all()
    return [
        {
            "id": h.id,
            "target_type": h.target_type,
            "target_id": h.target_id,
            "hold_type": h.hold_type,
            "status": h.status,
            "reason": h.reason,
            "owner_id": h.owner_id,
            "created_at": h.created_at,
            "released_at": h.released_at,
        }
        for h in holds
    ]


@router.patch("/{hold_id}/release")
def release_hold(
    hold_id: str,
    body: ReleaseHoldRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Release an active legal or incident hold."""
    hold = db.query(LegalHold).filter(
        LegalHold.id == hold_id,
        LegalHold.workspace_id == user.workspace_id,
    ).first()
    if not hold:
        raise HTTPException(status_code=404, detail="Hold not found.")
    if hold.status != "active":
        raise HTTPException(status_code=422, detail=f"Hold is already in state '{hold.status}'.")

    hold.status = "released"
    hold.released_at = datetime.now(timezone.utc)
    hold.released_by = user.user_id
    hold.release_reason = body.release_reason

    # Also update asset's flag if target_type is "asset"
    if hold.target_type == "asset":
        remaining_holds_count = db.query(LegalHold).filter(
            LegalHold.target_id == hold.target_id,
            LegalHold.target_type == "asset",
            LegalHold.hold_type == hold.hold_type,
            LegalHold.status == "active"
        ).count()
        if remaining_holds_count == 0:
            asset = db.query(GovernanceAsset).filter(
                GovernanceAsset.id == hold.target_id,
                GovernanceAsset.workspace_id == user.workspace_id
            ).first()
            if asset:
                if hold.hold_type == "legal":
                    asset.legal_hold = False
                elif hold.hold_type == "incident":
                    asset.incident_hold = False

    db.add(GovernanceEvent(
        workspace_id=user.workspace_id,
        source_service="legal-hold-service",
        target_type=hold.target_type,
        target_id=hold.target_id,
        actor_id=user.user_id,
        actor_type="user",
        action="legal_hold_released",
        reason=body.release_reason,
        reason_code="HOLD_RELEASED",
        occurred_at=datetime.now(timezone.utc),
    ))
    db.commit()
    return {"hold_id": hold.id, "status": hold.status, "released_at": hold.released_at}
