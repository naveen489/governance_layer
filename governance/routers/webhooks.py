"""
Router: /api/governance/webhooks
Provider webhook ingestion and normalization.
"""
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel

from governance.database import get_db
from governance.models.event import GovernanceEvent

router = APIRouter(prefix="/api/governance/webhooks", tags=["Webhooks"])


class NormalizationResult(BaseModel):
    normalized_event_id: str
    processing_status: str


def verify_signature(provider: str, payload: bytes, signature: str | None) -> bool:
    """Mock signature verification."""
    if not signature:
        return False
    # In a real implementation, verify HMAC or equivalent
    return signature.startswith("valid_")


@router.post("/{provider}", response_model=NormalizationResult, status_code=200)
async def ingest_webhook(
    provider: str,
    request: Request,
    db: Session = Depends(get_db),
    x_signature: str | None = Header(None, alias="X-Provider-Signature"),
    x_idempotency_key: str | None = Header(None, alias="X-Idempotency-Key"),
):
    """
    Ingest provider webhook/poll evidence, verify signature, and normalize into an audit event.
    """
    body = await request.body()
    
    if not verify_signature(provider, body, x_signature):
        # Log security event for invalid signature
        invalid_event = GovernanceEvent(
            id=str(uuid.uuid4()),
            workspace_id="system",  # System-level event
            target_type="webhook",
            target_id=provider,
            actor_id="system:webhook_ingestion",
            action="webhook_rejected",
            reason="Invalid webhook signature",
            reason_code="WEBHOOK_SIGNATURE_INVALID",
            event_payload={"headers": dict(request.headers)},
            occurred_at=datetime.now(timezone.utc),
        )
        db.add(invalid_event)
        db.commit()
        raise HTTPException(status_code=401, detail="Invalid signature")

    payload_json = await request.json()
    idemp_key = x_idempotency_key or payload_json.get("event_id") or str(uuid.uuid4())

    # Deduplication check
    existing = db.query(GovernanceEvent).filter(
        GovernanceEvent.idempotency_key == idemp_key
    ).first()
    
    if existing:
        return NormalizationResult(
            normalized_event_id=existing.id,
            processing_status="deduplicated"
        )

    # Normalization (Mock behavior)
    event_id = str(uuid.uuid4())
    normalized_event = GovernanceEvent(
        id=event_id,
        workspace_id=payload_json.get("workspace_id", "default"),
        target_type="provider",
        target_id=provider,
        actor_id=f"provider:{provider}",
        actor_type="provider",
        action="provider_event_normalized",
        reason=payload_json.get("type", "unknown_event"),
        reason_code="PROVIDER_EVENT_RECEIVED",
        event_payload=payload_json,
        idempotency_key=idemp_key,
        occurred_at=datetime.now(timezone.utc),
    )
    
    db.add(normalized_event)
    db.commit()

    return NormalizationResult(
        normalized_event_id=event_id,
        processing_status="processed"
    )
