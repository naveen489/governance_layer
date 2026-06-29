"""
Router: /api/governance/retention
Endpoints for manually triggering retention and deletion tasks.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from governance.database import get_db
from governance.engine.retention import evaluate_retention, delete_expired_assets, hard_delete_asset
from governance.auth import get_current_user, CurrentUser

router = APIRouter(prefix="/api/governance/retention", tags=["Retention"])


class RetentionResult(BaseModel):
    expired_assets: int
    skipped_due_to_hold: int
    soft_deleted: int


class HardDeleteResult(BaseModel):
    success: bool
    message: str


@router.post("/evaluate", response_model=RetentionResult)
def run_retention_evaluation(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    Manually trigger the retention evaluation and soft-delete cycle.
    """
    # Requires admin/system role
    if current_user.role not in ("admin", "system_actor"):
        raise HTTPException(status_code=403, detail="Admin role required")

    summary = evaluate_retention(db)
    deleted = delete_expired_assets(db)
    
    return RetentionResult(
        expired_assets=summary.get("expired", 0),
        skipped_due_to_hold=summary.get("skipped_due_to_hold", 0),
        soft_deleted=deleted,
    )


@router.delete("/purge/{asset_id}", response_model=HardDeleteResult)
def purge_asset_evidence(
    asset_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    Permanently purge asset evidence (hard delete).
    """
    if current_user.role not in ("admin", "system_actor"):
        raise HTTPException(status_code=403, detail="Admin role required")

    success = hard_delete_asset(db, asset_id)
    if success:
        return HardDeleteResult(success=True, message="Asset evidence successfully purged")
    else:
        raise HTTPException(status_code=422, detail="Asset not found or blocked by active hold/exception")
