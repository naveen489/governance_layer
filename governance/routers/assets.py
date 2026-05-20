"""
Router: /api/governance/assets
POST /evaluate   – register + evaluate asset governance
GET              – list assets
GET /{id}        – asset detail with provenance + manifest
GET /{id}/manifest – download rights manifest JSON
"""
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from governance.database import get_db
from governance.engine.policy_evaluator import evaluate_policy, ACTION_TO_ASSET_TRIGGER
from governance.engine.state_machine import transition
from governance.engine.rights_manifest import build_provenance, build_rights_manifest
from governance.engine.retention import RETENTION_CLASSES
from governance.models.asset import GovernanceAsset
from governance.models.request import GovernanceRequest
from governance.schemas.asset import EvaluateAssetIn, EvaluateAssetOut, GovernanceAssetDetail

router = APIRouter(prefix="/api/governance/assets", tags=["Assets"])


from governance.auth import get_current_user, CurrentUser


@router.post("/evaluate", response_model=EvaluateAssetOut, status_code=201)
def evaluate_asset(
    body: EvaluateAssetIn,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    workspace_id = current_user.workspace_id
    if body.workspace_id and body.workspace_id != workspace_id:
        raise HTTPException(status_code=403, detail="Cannot create asset in another workspace")
    
    if body.request_id:
        parent = db.query(GovernanceRequest).filter(
            GovernanceRequest.id == body.request_id,
            GovernanceRequest.workspace_id == workspace_id
        ).first()
        if not parent:
            raise HTTPException(status_code=404, detail="Parent request not found in workspace")

    # Evaluate asset policy
    eval_payload = {**body.asset_payload, "provider_key": body.provider_key, "model_key": body.model_key}
    decision = evaluate_policy(db, scope="asset", payload=eval_payload, workspace_id=workspace_id)

    # Compute retention expiry
    days = RETENTION_CLASSES.get(body.retention_class, 30)
    now = datetime.now(timezone.utc)
    retention_expires_at = now + timedelta(days=days)

    # Build provenance and manifest
    provenance = build_provenance(
        request_id=body.request_id,
        provider_key=body.provider_key,
        model_key=body.model_key,
        asset_payload=body.asset_payload,
        workspace_id=workspace_id,
        generated_at=now,
    )
    manifest = build_rights_manifest(
        request_id=body.request_id,
        provider_key=body.provider_key,
        model_key=body.model_key,
        asset_payload=body.asset_payload,
        retention_class=body.retention_class,
    )

    asset_id = str(uuid.uuid4())
    trigger = ACTION_TO_ASSET_TRIGGER.get(decision.action, "asset_policy_pass")

    asset = GovernanceAsset(
        id=asset_id,
        workspace_id=workspace_id,
        request_id=body.request_id,
        provider_key=body.provider_key,
        model_key=body.model_key,
        governance_state="asset_registered",
        retention_class=body.retention_class,
        retention_expires_at=retention_expires_at,
        provenance_json=provenance,
        rights_manifest_json=manifest,
        asset_payload=body.asset_payload,
        created_at=now,
        updated_at=now,
    )
    db.add(asset)
    db.flush()

    # Transition asset_registered → next state
    new_state = transition(
        db,
        current_state="asset_registered",
        trigger=trigger,
        target_type="asset",
        target_id=asset_id,
        workspace_id=workspace_id,
        actor_id=current_user.id,
        reason="; ".join(decision.reasons) if decision.reasons else None,
        event_payload={"decision": decision.action, "rule_ids": decision.rule_ids},
    )

    asset.governance_state = new_state
    asset.updated_at = datetime.now(timezone.utc)
    db.commit()

    return EvaluateAssetOut(asset_id=asset_id, state=new_state, reasons=decision.reasons)


@router.get("", response_model=List[GovernanceAssetDetail])
def list_assets(
    workspace_id: Optional[str] = Query(default=None),
    governance_state: Optional[str] = Query(default=None),
    request_id: Optional[str] = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if workspace_id and workspace_id != current_user.workspace_id:
        raise HTTPException(status_code=403, detail="Cannot query another workspace")

    q = db.query(GovernanceAsset).filter(GovernanceAsset.workspace_id == current_user.workspace_id)
    if governance_state:
        q = q.filter(GovernanceAsset.governance_state == governance_state)
    if request_id:
        q = q.filter(GovernanceAsset.request_id == request_id)
    return q.order_by(GovernanceAsset.created_at.desc()).offset(offset).limit(limit).all()


@router.get("/{asset_id}", response_model=GovernanceAssetDetail)
def get_asset(asset_id: str, current_user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    asset = db.query(GovernanceAsset).filter(
        GovernanceAsset.id == asset_id,
        GovernanceAsset.workspace_id == current_user.workspace_id
    ).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset


@router.get("/{asset_id}/manifest")
def download_manifest(asset_id: str, current_user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    asset = db.query(GovernanceAsset).filter(
        GovernanceAsset.id == asset_id,
        GovernanceAsset.workspace_id == current_user.workspace_id
    ).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return JSONResponse(
        content=asset.rights_manifest_json or {},
        headers={"Content-Disposition": f'attachment; filename="manifest_{asset_id}.json"'},
    )
