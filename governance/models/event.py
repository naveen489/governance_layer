"""ORM model: governance_events (immutable audit trail with v2 hash chaining)"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, JSON, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from governance.database import Base


class GovernanceEvent(Base):
    __tablename__ = "governance_events"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_governance_events_idempotency_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    schema_version: Mapped[str] = mapped_column(String(16), nullable=False, default="gov.event.v2")
    source_service: Mapped[str | None] = mapped_column(String(64), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)   # request | asset | exception | policy | incident | retention
    target_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    actor_id: Mapped[str] = mapped_column(String(36), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(16), nullable=False, default="user")  # user | system | provider
    action: Mapped[str] = mapped_column(String(64), nullable=False)        # approve, reject, block, delete, etc.
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason_code: Mapped[str | None] = mapped_column(String(64), nullable=True)  # e.g. PROVIDER_NOT_APPROVED
    event_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    event_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)           # SHA-256 of event content
    previous_event_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)  # chain link
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
