"""Pydantic schemas for governance policies."""
from __future__ import annotations
from datetime import datetime
from typing import Any, List, Optional
from pydantic import BaseModel


class CreatePolicyIn(BaseModel):
    workspace_id: str = "default"
    policy_scope: str   # request | asset | publish | retention
    version: int
    policy_json: dict[str, Any]
    is_active: bool = True
    effective_from: Optional[datetime] = None
    effective_to: Optional[datetime] = None


class UpdatePolicyIn(BaseModel):
    is_active: Optional[bool] = None
    policy_json: Optional[dict[str, Any]] = None
    effective_to: Optional[datetime] = None


class GovernancePolicyDetail(BaseModel):
    id: str
    workspace_id: str
    policy_scope: str
    version: int
    policy_json: dict[str, Any]
    is_active: bool
    effective_from: datetime
    effective_to: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class GovernancePoliciesResponse(BaseModel):
    policies: List[GovernancePolicyDetail]
    total: int
