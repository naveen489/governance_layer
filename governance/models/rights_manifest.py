"""ORM model: rights_manifests – structured rights and usage manifest per asset"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, JSON, Float
from sqlalchemy.orm import Mapped, mapped_column
from governance.database import Base


class RightsManifest(Base):
    __tablename__ = "rights_manifests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    asset_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, unique=True)
    # complete | partial | missing | expired | not_required
    source_rights_status: Mapped[str] = mapped_column(String(32), nullable=False, default="missing")
    # allowed | restricted | unknown
    generated_output_rights_status: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    allowed_usage: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # { internal_preview, external_publish, commercial_use, paid_ads, platforms }
    restrictions: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    attribution: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    source_assets: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # [{ source_asset_id, source_type, license_ref, evidence_ref }]
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    missing_evidence: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # list of missing items
    expiry_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
