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


def validate_policy_json(policy_json: dict) -> None:
    """Validate the structure of a policy_json. Raises HTTPException(422) if invalid."""
    if not isinstance(policy_json, dict):
        raise HTTPException(status_code=422, detail="Policy payload must be a JSON object.")
        
    rules = policy_json.get("rules")
    if rules is None:
        raise HTTPException(status_code=422, detail="Policy JSON must contain a 'rules' list.")
    if not isinstance(rules, list):
        raise HTTPException(status_code=422, detail="'rules' key must be a list of rules.")
        
    for idx, rule in enumerate(rules):
        if not isinstance(rule, dict):
            raise HTTPException(status_code=422, detail=f"Rule at index {idx} must be a JSON object.")
            
        rule_id = rule.get("rule_id")
        if not rule_id or not isinstance(rule_id, str):
            raise HTTPException(status_code=422, detail=f"Rule at index {idx} must have a non-empty string 'rule_id'.")
            
        when = rule.get("when")
        if when is None or not isinstance(when, dict):
            raise HTTPException(status_code=422, detail=f"Rule '{rule_id}' must have a 'when' dictionary.")
            
        then = rule.get("then")
        if then is None or not isinstance(then, dict):
            raise HTTPException(status_code=422, detail=f"Rule '{rule_id}' must have a 'then' dictionary.")
            
        action = then.get("action")
        ALLOWED_ACTIONS = {"pass", "warn", "review_required", "block"}
        if not action or action not in ALLOWED_ACTIONS:
            raise HTTPException(
                status_code=422,
                detail=f"Rule '{rule_id}' has invalid action '{action}'; must be one of {ALLOWED_ACTIONS}."
            )


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
        from governance.auth import audit_access_denied
        audit_access_denied(db, current_user.user_id, workspace_id, "list_policies", "Cannot query another workspace")
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
        from governance.auth import audit_access_denied
        audit_access_denied(db, current_user.user_id, body.workspace_id, "create_policy", "Cannot create policy in another workspace")
        raise HTTPException(status_code=403, detail="Cannot create policy in another workspace")

    if body.policy_json:
        validate_policy_json(body.policy_json)

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
    
    if body.is_active:
        # Enforce single active policy per scope and workspace
        db.query(GovernancePolicy).filter(
            GovernancePolicy.workspace_id == workspace_id,
            GovernancePolicy.policy_scope == body.policy_scope
        ).update({"is_active": False})

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
        
    if policy.is_active and (body.policy_json is not None):
        raise HTTPException(
            status_code=409,
            detail="Cannot modify rules of an active policy. Create a new version instead."
        )

    if body.policy_json is not None:
        validate_policy_json(body.policy_json)
        policy.policy_json = body.policy_json
        
    if body.is_active is not None:
        if body.is_active:
            # Enforce single active policy per scope/workspace
            db.query(GovernancePolicy).filter(
                GovernancePolicy.workspace_id == policy.workspace_id,
                GovernancePolicy.policy_scope == policy.policy_scope,
                GovernancePolicy.id != policy.id
            ).update({"is_active": False})
            policy.is_active = True
            policy.effective_from = datetime.now(timezone.utc)
        else:
            policy.is_active = False
            
    if body.effective_to is not None:
        policy.effective_to = body.effective_to
        
    db.commit()
    db.refresh(policy)
    return policy


@router.post("/{policy_id}/new-version", response_model=GovernancePolicyDetail, status_code=201)
def create_new_version(
    policy_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Clone an existing policy to create a new inactive version with incremented version number."""
    existing = db.query(GovernancePolicy).filter(
        GovernancePolicy.id == policy_id,
        GovernancePolicy.workspace_id == current_user.workspace_id
    ).first()
    if not existing:
        raise HTTPException(status_code=404, detail="Source policy not found in workspace")
        
    # Find the maximum version for this scope
    max_ver = db.query(GovernancePolicy.version).filter(
        GovernancePolicy.workspace_id == current_user.workspace_id,
        GovernancePolicy.policy_scope == existing.policy_scope
    ).order_by(GovernancePolicy.version.desc()).first()
    
    new_version = (max_ver[0] if max_ver else existing.version) + 1
    
    now = datetime.now(timezone.utc)
    new_pol = GovernancePolicy(
        id=str(uuid.uuid4()),
        workspace_id=current_user.workspace_id,
        policy_scope=existing.policy_scope,
        version=new_version,
        policy_json=existing.policy_json,
        is_active=False,
        effective_from=now,
        created_at=now,
    )
    db.add(new_pol)
    db.commit()
    db.refresh(new_pol)
    return new_pol
