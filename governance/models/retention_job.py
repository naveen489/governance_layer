"""ORM model: retention_jobs – tracks retention scheduler runs per target"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column
from governance.database import Base


class RetentionJob(Base):
    __tablename__ = "retention_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)     # request | asset | exception
    target_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    retention_class: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="scheduled")
    # scheduled | evaluating | delete_blocked | deletion_pending | soft_deleted | purged | failed
    evaluation_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    deletion_evidence: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
