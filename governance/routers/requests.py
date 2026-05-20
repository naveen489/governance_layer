"""
Router: /api/governance/requests
POST  – create + evaluate governance request
GET   – list requests with optional filters
GET /{id} – get single request detail
"""
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from governance.database import get_db
from governance.engine.policy_evaluator import evaluate_policy, ACTION_TO_REQUEST_TRIGGER
from governance.engine.state_machine import transition, InvalidTransitionError
from governance.models.request import GovernanceRequest
from governance.schemas.request import (
    CreateGovernanceRequestIn,
    GovernanceRequestOut,
    GovernanceRequestDetail,
)

router = APIRouter(prefix="/api/governance/requests", tags=["Requests"])


from governance.auth import get_current_user, CurrentUser


@router.post("", response_model=GovernanceRequestOut, status_code=201)
def create_governance_request(
    body: CreateGovernanceRequestIn,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    req_id = str(uuid.uuid4())
    
    # Strictly enforce workspace isolation
    workspace_id = current_user.workspace_id
    if body.workspace_id and body.workspace_id != workspace_id:
        raise HTTPException(status_code=403, detail="Cannot create request in another workspace")

    # Evaluate policy
    decision = evaluate_policy(db, scope="request", payload=body.request_payload, workspace_id=workspace_id)

    # Determine initial trigger
    trigger = ACTION_TO_REQUEST_TRIGGER.get(decision.action, "policy_pass")

    req = GovernanceRequest(
        id=req_id,
        workspace_id=workspace_id,
        request_payload=body.request_payload,
        governance_state="draft",
        policy_version=decision.policy_version,
        decision_summary={
            "action": decision.action,
            "reasons": decision.reasons,
            "rule_ids": decision.rule_ids,
        },
        created_by=body.created_by or current_user.id,
        simulation_mode=body.simulation_mode,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(req)
    db.flush()

    # Transition from draft → new state
    new_state = transition(
        db,
        current_state="draft",
        trigger=trigger,
        target_type="request",
        target_id=req_id,
        workspace_id=workspace_id,
        actor_id=current_user.id,
        reason="; ".join(decision.reasons) if decision.reasons else None,
        event_payload={"decision": decision.action, "rule_ids": decision.rule_ids},
    )

    # If auto-approvable, proceed to approved_for_execution
    if new_state == "policy_passed":
        new_state = transition(
            db,
            current_state="policy_passed",
            trigger="auto_approve",
            target_type="request",
            target_id=req_id,
            workspace_id=workspace_id,
            actor_id="system",
        )

    req.governance_state = new_state
    req.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(req)

    return GovernanceRequestOut(
        governance_request_id=req.id,
        state=req.governance_state,
        policy_version=req.policy_version,
        decision_summary=req.decision_summary,
        created_at=req.created_at,
        updated_at=req.updated_at,
    )


@router.get("", response_model=List[GovernanceRequestDetail])
def list_requests(
    workspace_id: Optional[str] = Query(default=None),
    governance_state: Optional[str] = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Strict workspace isolation
    if workspace_id and workspace_id != current_user.workspace_id:
        raise HTTPException(status_code=403, detail="Cannot query another workspace")
    
    q = db.query(GovernanceRequest).filter(GovernanceRequest.workspace_id == current_user.workspace_id)
    if governance_state:
        q = q.filter(GovernanceRequest.governance_state == governance_state)
    return q.order_by(GovernanceRequest.created_at.desc()).offset(offset).limit(limit).all()


@router.get("/{request_id}", response_model=GovernanceRequestDetail)
def get_request(
    request_id: str, 
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    req = db.query(GovernanceRequest).filter(
        GovernanceRequest.id == request_id,
        GovernanceRequest.workspace_id == current_user.workspace_id
    ).first()
    if not req:
        raise HTTPException(status_code=404, detail="Governance request not found")
    return req
