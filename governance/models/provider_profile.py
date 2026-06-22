"""ORM model: provider_policy_profiles – versioned provider policy intelligence"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from governance.database import Base


class ProviderPolicyProfile(Base):
    __tablename__ = "provider_policy_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    provider_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    version: Mapped[int] = mapped_column(nullable=False, default=1)
    # Moderation: { type: pre_and_post|pre_only|post_only|none, categories: [], auto_reject: bool }
    moderation_behavior: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Retention: { default_hours, max_hours, deletion_support, export_support }
    retention_behavior: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Webhook: { supported, signature_header, retry_policy }
    webhook_behavior: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Data controls: { scoped_key_support, pii_handling, data_residency }
    data_controls: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    risk_class: Mapped[str] = mapped_column(String(16), nullable=False, default="medium")  # low | medium | high
    evidence_capture_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    source_notes: Mapped[str | None] = mapped_column(String(512), nullable=True)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
