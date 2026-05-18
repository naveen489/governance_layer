"""
Router: /api/governance/requests
POST  – create + evaluate governance request
GET   – list requests with optional filters
GET /{id} – get single request detail
"""
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
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


def _actor(x_user_id: Optional[str] = Header(default=None)) -> str:
    return x_user_id or "anonymous"


@router.post("", response_model=GovernanceRequestOut, status_code=201)
def create_governance_request(
    body: CreateGovernanceRequestIn,
    db: Session = Depends(get_db),
    actor: str = Depends(_actor),
):
    req_id = str(uuid.uuid4())
    workspace_id = body.workspace_id or "default"

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
        created_by=body.created_by or actor,
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
        actor_id=actor,
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
    db: Session = Depends(get_db),
):
    q = db.query(GovernanceRequest)
    if workspace_id:
        q = q.filter(GovernanceRequest.workspace_id == workspace_id)
    if governance_state:
        q = q.filter(GovernanceRequest.governance_state == governance_state)
    return q.order_by(GovernanceRequest.created_at.desc()).offset(offset).limit(limit).all()


@router.get("/{request_id}", response_model=GovernanceRequestDetail)
def get_request(request_id: str, db: Session = Depends(get_db)):
    req = db.query(GovernanceRequest).filter(GovernanceRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Governance request not found")
    return req
