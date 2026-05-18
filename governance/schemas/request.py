"""Pydantic schemas for governance requests."""
from __future__ import annotations
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field


class CreateGovernanceRequestIn(BaseModel):
    workspace_id: str
    request_payload: dict[str, Any]
    simulation_mode: bool = True
    created_by: Optional[str] = "system"


class GovernanceRequestOut(BaseModel):
    governance_request_id: str
    state: str
    policy_version: Optional[int]
    decision_summary: Optional[dict[str, Any]]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class GovernanceRequestDetail(BaseModel):
    id: str
    workspace_id: str
    request_payload: dict[str, Any]
    governance_state: str
    policy_version: Optional[int]
    decision_summary: Optional[dict[str, Any]]
    created_by: str
    simulation_mode: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
