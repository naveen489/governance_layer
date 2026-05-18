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


@router.get("", response_model=GovernancePoliciesResponse)
def list_policies(
    workspace_id: Optional[str] = Query(default=None),
    policy_scope: Optional[str] = Query(default=None),
    is_active: Optional[bool] = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0),
    db: Session = Depends(get_db),
):
    q = db.query(GovernancePolicy)
    if workspace_id:
        q = q.filter(GovernancePolicy.workspace_id == workspace_id)
    if policy_scope:
        q = q.filter(GovernancePolicy.policy_scope == policy_scope)
    if is_active is not None:
        q = q.filter(GovernancePolicy.is_active == is_active)
    total = q.count()
    items = q.order_by(GovernancePolicy.version.desc()).offset(offset).limit(limit).all()
    return GovernancePoliciesResponse(policies=items, total=total)


@router.post("", response_model=GovernancePolicyDetail, status_code=201)
def create_policy(body: CreatePolicyIn, db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    policy = GovernancePolicy(
        id=str(uuid.uuid4()),
        workspace_id=body.workspace_id,
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
def update_policy(policy_id: str, body: UpdatePolicyIn, db: Session = Depends(get_db)):
    policy = db.query(GovernancePolicy).filter(GovernancePolicy.id == policy_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    if body.is_active is not None:
        policy.is_active = body.is_active
    if body.policy_json is not None:
        policy.policy_json = body.policy_json
    if body.effective_to is not None:
        policy.effective_to = body.effective_to
    db.commit()
    db.refresh(policy)
    return policy
