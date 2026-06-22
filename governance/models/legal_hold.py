"""ORM model: legal_holds – legal and incident hold records"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from governance.database import Base


class LegalHold(Base):
    __tablename__ = "legal_holds"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)   # request | asset | exception
    target_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    hold_type: Mapped[str] = mapped_column(String(16), nullable=False)     # legal | incident
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    owner_id: Mapped[str] = mapped_column(String(36), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")  # active | released
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    released_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    released_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    release_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
