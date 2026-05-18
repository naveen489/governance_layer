"""Pydantic schemas for governance events (audit trail)."""
from __future__ import annotations
from datetime import datetime
from typing import Any, List, Optional
from pydantic import BaseModel


class GovernanceEventOut(BaseModel):
    id: str
    workspace_id: str
    target_type: str
    target_id: str
    actor_id: str
    action: str
    reason: Optional[str]
    event_payload: Optional[dict[str, Any]]
    occurred_at: datetime

    model_config = {"from_attributes": True}


class GovernanceEventsResponse(BaseModel):
    events: List[GovernanceEventOut]
    total: int
