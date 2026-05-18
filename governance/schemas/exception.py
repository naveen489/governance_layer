"""Pydantic schemas for governance exceptions."""
from __future__ import annotations
from datetime import datetime
from typing import Any, List, Optional
from pydantic import BaseModel


class SubmitExceptionIn(BaseModel):
    target_type: str   # request | asset
    target_id: str
    business_reason: str
    workspace_id: Optional[str] = "default"
    scope_json: Optional[dict[str, Any]] = None
    expiry_at: Optional[datetime] = None


class SubmitExceptionOut(BaseModel):
    exception_id: str
    status: str


class ExceptionDecisionIn(BaseModel):
    decision: str     # approve | reject
    reason: Optional[str] = None
    expiry_at: Optional[datetime] = None
    scope_json: Optional[dict[str, Any]] = None


class GovernanceExceptionDetail(BaseModel):
    id: str
    workspace_id: str
    target_type: str
    target_id: str
    requested_by: str
    approved_by: Optional[str]
    status: str
    scope_json: Optional[dict[str, Any]]
    expiry_at: Optional[datetime]
    business_reason: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class GovernanceExceptionsResponse(BaseModel):
    exceptions: List[GovernanceExceptionDetail]
    total: int
