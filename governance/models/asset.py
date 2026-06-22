"""ORM model: governance_assets (v2)"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, JSON, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from governance.database import Base


class GovernanceAsset(Base):
    __tablename__ = "governance_assets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    request_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    parent_asset_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)  # for derivative assets
    asset_type: Mapped[str] = mapped_column(String(32), nullable=False, default="generated")  # generated | derivative | transformed
    provider_key: Mapped[str] = mapped_column(String(64), nullable=False)
    model_key: Mapped[str] = mapped_column(String(128), nullable=False)
    governance_state: Mapped[str] = mapped_column(String(64), nullable=False, default="asset_registered")
    quality_verdict_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)  # reference to quality verdict
    publish_ready: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    retention_class: Mapped[str] = mapped_column(String(32), nullable=False, default="standard")
    retention_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    legal_hold: Mapped[bool] = mapped_column(default=False)
    incident_hold: Mapped[bool] = mapped_column(default=False)
    provenance_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    rights_manifest_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    asset_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
