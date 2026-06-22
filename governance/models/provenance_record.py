"""ORM model: provenance_records – full lineage chain for generated/derived assets"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column
from governance.database import Base


class ProvenanceRecord(Base):
    __tablename__ = "provenance_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    asset_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    request_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    route_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    provider_key: Mapped[str] = mapped_column(String(64), nullable=False)
    model_key: Mapped[str] = mapped_column(String(128), nullable=False)
    # Source inputs: [{ source_asset_id, source_type, description }]
    source_assets: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Transformation steps: [{ step, tool, params }]
    transformations: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Prompt/reference identifiers
    prompt_refs: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    output_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)  # SHA-256 of output content
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
