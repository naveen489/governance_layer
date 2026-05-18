"""ORM model: governance_policies"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, JSON, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from governance.database import Base


class GovernancePolicy(Base):
    __tablename__ = "governance_policies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    policy_scope: Mapped[str] = mapped_column(String(32), nullable=False)   # request | asset | publish | retention
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    policy_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    effective_from: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    effective_to: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
