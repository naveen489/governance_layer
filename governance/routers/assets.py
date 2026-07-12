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
from pydantic import BaseModel
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
        from governance.auth import audit_access_denied
        audit_access_denied(db, current_user.user_id, body.workspace_id, "create_asset", "Cannot create asset in another workspace")
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
        db=db,
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
    
    if new_state in ("review_required", "escalated"):
        from governance.models.review_task import GovernanceReviewTask
        severity = decision.severity if hasattr(decision, "severity") else "medium"
        task = GovernanceReviewTask(
            id=str(uuid.uuid4()),
            workspace_id=workspace_id,
            target_type="asset",
            target_id=asset_id,
            task_type="review_required",
            risk_severity=severity,
            policy_reasons=decision.reasons,
            status="open",
            sla_due_at=datetime.now(timezone.utc) + timedelta(hours=24),
            created_at=datetime.now(timezone.utc),
        )
        db.add(task)
        
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
        from governance.auth import audit_access_denied
        audit_access_denied(db, current_user.user_id, workspace_id, "list_assets", "Cannot query another workspace")
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

@router.post("/{asset_id}/publish")
def check_publish_policy(
    asset_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    asset = db.query(GovernanceAsset).filter(
        GovernanceAsset.id == asset_id,
        GovernanceAsset.workspace_id == current_user.workspace_id
    ).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    from governance.engine.publish_gate import evaluate_publish_gate
    from governance.engine.incident_engine import check_unauthorized_publish_attempt

    # Evaluate the full multi-factor publish gate
    result = evaluate_publish_gate(db, asset_id=asset_id, workspace_id=current_user.workspace_id)
    if not result.publish_ready:
        # Create an incident for unauthorized attempt
        check_unauthorized_publish_attempt(
            db, 
            workspace_id=current_user.workspace_id, 
            asset_id=asset_id, 
            asset_state=asset.governance_state
        )
        db.commit()
        raise HTTPException(
            status_code=403,
            detail={
                "message": "Publish blocked by publish gate checks",
                "blockers": result.blockers,
                "warnings": result.warnings
            }
        )

    decision = evaluate_policy(db, scope="publish", payload=asset.asset_payload, workspace_id=asset.workspace_id)
    
    if decision.action == "pass":
        trigger = "publish_pass"
    else:
        trigger = "publish_block"
        
    try:
        new_state = transition(
            db,
            current_state=asset.governance_state,
            trigger=trigger,
            target_type="asset",
            target_id=asset.id,
            workspace_id=asset.workspace_id,
            actor_id=current_user.id,
            reason="; ".join(decision.reasons) if decision.reasons else "Asset published",
            event_payload={"decision": decision.action, "rule_ids": decision.rule_ids},
        )
        asset.governance_state = new_state
        asset.publish_ready = True
        asset.updated_at = datetime.now(timezone.utc)
        db.commit()
        return {"asset_id": asset_id, "state": new_state, "reasons": decision.reasons}
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))

@router.post("/{asset_id}/retention")
def check_retention_policy(
    asset_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    asset = db.query(GovernanceAsset).filter(
        GovernanceAsset.id == asset_id,
        GovernanceAsset.workspace_id == current_user.workspace_id
    ).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    decision = evaluate_policy(db, scope="retention", payload=asset.asset_payload, workspace_id=asset.workspace_id)
    
    new_class = asset.retention_class
    if decision.action in ["block", "review_required"]:
        new_class = "extended"
    elif decision.action == "warn":
        new_class = "standard"
        
    if new_class != asset.retention_class:
        asset.retention_class = new_class
        days = RETENTION_CLASSES.get(new_class, 30)
        # Recompute from created_at
        if asset.created_at.tzinfo is None:
            created_at = asset.created_at.replace(tzinfo=timezone.utc)
        else:
            created_at = asset.created_at
        asset.retention_expires_at = created_at + timedelta(days=days)
        
        from governance.models.event import GovernanceEvent
        event = GovernanceEvent(
            workspace_id=asset.workspace_id,
            target_type="asset",
            target_id=asset.id,
            actor_id=current_user.id,
            action="update_retention",
            reason=f"Retention policy evaluated to {decision.action}, updated class to {new_class}",
            event_payload={"new_class": new_class, "rule_ids": decision.rule_ids},
            occurred_at=datetime.now(timezone.utc),
        )
        db.add(event)
        
    asset.updated_at = datetime.now(timezone.utc)
    db.commit()

    return {"asset_id": asset_id, "retention_class": asset.retention_class, "reasons": decision.reasons}


@router.post("/{asset_id}/publish-gate")
def publish_gate(
    asset_id: str,
    quality_verdict: Optional[str] = None,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Full multi-factor publish-readiness gate (v2).
    Checks: governance state, legal holds, rights manifest, retention, quality verdict.
    """
    from governance.engine.publish_gate import evaluate_publish_gate
    from governance.engine.incident_engine import check_unauthorized_publish_attempt

    asset = db.query(GovernanceAsset).filter(
        GovernanceAsset.id == asset_id,
        GovernanceAsset.workspace_id == current_user.workspace_id
    ).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    result = evaluate_publish_gate(db, asset_id=asset_id, workspace_id=current_user.workspace_id, quality_verdict=quality_verdict)

    # Auto-create incident if publish attempted on wrong state
    if not result.publish_ready:
        check_unauthorized_publish_attempt(db, workspace_id=current_user.workspace_id, asset_id=asset_id, asset_state=asset.governance_state)

    # If ready, advance to publish_ready state
    if result.publish_ready and asset.governance_state not in ("publish_ready", "published"):
        try:
            new_state = transition(
                db,
                current_state=asset.governance_state,
                trigger="publish_pass",
                target_type="asset",
                target_id=asset.id,
                workspace_id=asset.workspace_id,
                actor_id=current_user.id,
                reason="Publish gate passed all checks",
                reason_code="PUBLISH_GATE_PASSED",
            )
            asset.governance_state = new_state
            asset.publish_ready = True
            asset.updated_at = datetime.now(timezone.utc)
        except Exception:
            pass  # Already in right state

    db.commit()

    return {
        "asset_id": asset_id,
        "publish_ready": result.publish_ready,
        "blockers": result.blockers,
        "warnings": result.warnings,
        "checks": result.checks,
        "governance_state": asset.governance_state,
    }


@router.post("/{asset_id}/rights-manifest", status_code=201)
def create_rights_manifest(
    asset_id: str,
    body: dict,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create or update a structured rights manifest for an asset (v2)."""
    from governance.models.rights_manifest import RightsManifest

    asset = db.query(GovernanceAsset).filter(
        GovernanceAsset.id == asset_id,
        GovernanceAsset.workspace_id == current_user.workspace_id
    ).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    # Upsert rights manifest
    existing = db.query(RightsManifest).filter(RightsManifest.asset_id == asset_id).first()
    if existing:
        for key, val in body.items():
            if hasattr(existing, key):
                setattr(existing, key, val)
        existing.updated_at = datetime.now(timezone.utc)
        manifest = existing
    else:
        manifest = RightsManifest(
            workspace_id=current_user.workspace_id,
            asset_id=asset_id,
            source_rights_status=body.get("source_rights_status", "missing"),
            generated_output_rights_status=body.get("generated_output_rights_status", "unknown"),
            allowed_usage=body.get("allowed_usage"),
            restrictions=body.get("restrictions"),
            attribution=body.get("attribution"),
            source_assets=body.get("source_assets"),
            confidence_score=body.get("confidence_score"),
            missing_evidence=body.get("missing_evidence"),
        )
        db.add(manifest)

    db.commit()
    db.refresh(manifest)
    return {
        "manifest_id": manifest.id,
        "asset_id": manifest.asset_id,
        "source_rights_status": manifest.source_rights_status,
        "generated_output_rights_status": manifest.generated_output_rights_status,
        "confidence_score": manifest.confidence_score,
    }


@router.get("/{asset_id}/provenance")
def get_asset_provenance(
    asset_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the full provenance record for an asset (v2)."""
    from governance.models.provenance_record import ProvenanceRecord

    asset = db.query(GovernanceAsset).filter(
        GovernanceAsset.id == asset_id,
        GovernanceAsset.workspace_id == current_user.workspace_id
    ).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    prov_record = db.query(ProvenanceRecord).filter(ProvenanceRecord.asset_id == asset_id).first()
    if prov_record:
        return {
            "id": prov_record.id,
            "asset_id": prov_record.asset_id,
            "request_id": prov_record.request_id,
            "provider_key": prov_record.provider_key,
            "model_key": prov_record.model_key,
            "source_assets": prov_record.source_assets,
            "transformations": prov_record.transformations,
            "prompt_refs": prov_record.prompt_refs,
            "output_hash": prov_record.output_hash,
            "created_at": prov_record.created_at,
        }

    # Fallback to inline JSON
    return {"asset_id": asset_id, "provenance_json": asset.provenance_json or {}, "source": "inline"}


class QualityVerdictUpdate(BaseModel):
    quality_verdict_ref: str


@router.patch("/{asset_id}/quality-verdict")
def update_quality_verdict(
    asset_id: str,
    body: QualityVerdictUpdate,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update the quality_verdict_ref for an asset. Triggered by QualityOps integration."""
    asset = db.query(GovernanceAsset).filter(
        GovernanceAsset.id == asset_id,
        GovernanceAsset.workspace_id == current_user.workspace_id
    ).first()
    
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    asset.quality_verdict_ref = body.quality_verdict_ref
    asset.updated_at = datetime.now(timezone.utc)
    
    from governance.models.event import GovernanceEvent
    event = GovernanceEvent(
        id=str(uuid.uuid4()),
        workspace_id=asset.workspace_id,
        target_type="asset",
        target_id=asset.id,
        actor_id=current_user.id,
        action="update_quality_verdict",
        reason=f"QualityOps verdict updated to {body.quality_verdict_ref}",
        event_payload={"quality_verdict_ref": body.quality_verdict_ref},
        occurred_at=datetime.now(timezone.utc),
    )
    db.add(event)
    db.commit()

    return {"asset_id": asset_id, "quality_verdict_ref": asset.quality_verdict_ref}

