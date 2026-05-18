"""ORM model: governance_requests"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, JSON, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column
from governance.database import Base


class GovernanceRequest(Base):
    __tablename__ = "governance_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    request_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    governance_state: Mapped[str] = mapped_column(String(64), nullable=False, default="draft")
    policy_version: Mapped[int] = mapped_column(Integer, nullable=True)
    decision_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    simulation_mode: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
