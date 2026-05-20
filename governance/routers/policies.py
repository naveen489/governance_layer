"""
Router: /api/governance/policies
GET          – list policies (filterable by scope, workspace, active)
POST         – create new policy version
PATCH /{id}  – update policy (toggle active, update rules, set effective_to)
"""
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from governance.database import get_db
from governance.models.policy import GovernancePolicy
from governance.schemas.policy import (
    CreatePolicyIn,
    UpdatePolicyIn,
    GovernancePolicyDetail,
    GovernancePoliciesResponse,
)

router = APIRouter(prefix="/api/governance/policies", tags=["Policies"])

from governance.auth import get_current_user, CurrentUser


@router.get("", response_model=GovernancePoliciesResponse)
def list_policies(
    workspace_id: Optional[str] = Query(default=None),
    policy_scope: Optional[str] = Query(default=None),
    is_active: Optional[bool] = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if workspace_id and workspace_id != current_user.workspace_id:
        raise HTTPException(status_code=403, detail="Cannot query another workspace")
    
    q = db.query(GovernancePolicy).filter(GovernancePolicy.workspace_id == current_user.workspace_id)
    if policy_scope:
        q = q.filter(GovernancePolicy.policy_scope == policy_scope)
    if is_active is not None:
        q = q.filter(GovernancePolicy.is_active == is_active)
    total = q.count()
    items = q.order_by(GovernancePolicy.version.desc()).offset(offset).limit(limit).all()
    return GovernancePoliciesResponse(policies=items, total=total)


@router.post("", response_model=GovernancePolicyDetail, status_code=201)
def create_policy(body: CreatePolicyIn, current_user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    workspace_id = current_user.workspace_id
    if body.workspace_id and body.workspace_id != workspace_id:
        raise HTTPException(status_code=403, detail="Cannot create policy in another workspace")

    now = datetime.now(timezone.utc)
    policy = GovernancePolicy(
        id=str(uuid.uuid4()),
        workspace_id=workspace_id,
        policy_scope=body.policy_scope,
        version=body.version,
        policy_json=body.policy_json,
        is_active=body.is_active,
        effective_from=body.effective_from or now,
        effective_to=body.effective_to,
        created_at=now,
    )
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return policy


@router.patch("/{policy_id}", response_model=GovernancePolicyDetail)
def update_policy(policy_id: str, body: UpdatePolicyIn, current_user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    policy = db.query(GovernancePolicy).filter(
        GovernancePolicy.id == policy_id,
        GovernancePolicy.workspace_id == current_user.workspace_id
    ).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found in workspace")
    if body.is_active is not None:
        policy.is_active = body.is_active
    if body.policy_json is not None:
        policy.policy_json = body.policy_json
    if body.effective_to is not None:
        policy.effective_to = body.effective_to
    db.commit()
    db.refresh(policy)
    return policy
