"""Pydantic schemas for governance assets."""
from __future__ import annotations
from datetime import datetime
from typing import Any, List, Optional
from pydantic import BaseModel


class EvaluateAssetIn(BaseModel):
    request_id: str
    asset_payload: dict[str, Any]
    provider_key: str
    model_key: str = "unknown"
    workspace_id: Optional[str] = None
    retention_class: str = "standard"


class EvaluateAssetOut(BaseModel):
    asset_id: str
    state: str
    reasons: List[str]


class GovernanceAssetDetail(BaseModel):
    id: str
    workspace_id: str
    request_id: str
    provider_key: str
    model_key: str
    governance_state: str
    retention_class: str
    retention_expires_at: Optional[datetime]
    legal_hold: bool
    incident_hold: bool
    provenance_json: Optional[dict[str, Any]]
    rights_manifest_json: Optional[dict[str, Any]]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
