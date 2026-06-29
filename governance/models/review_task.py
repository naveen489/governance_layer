"""ORM model: governance_review_tasks – structured review queue with SLA tracking"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column
from governance.database import Base


class GovernanceReviewTask(Base):
    __tablename__ = "governance_review_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)    # request | asset | policy | exception
    target_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    task_type: Mapped[str] = mapped_column(String(32), nullable=False, default="review_required")
    # review_required | exception | escalation | policy_activation
    risk_severity: Mapped[str] = mapped_column(String(16), nullable=False, default="medium")  # critical | high | medium | low
    policy_reasons: Mapped[dict | None] = mapped_column(JSON, nullable=True)   # list of reason strings/codes
    assigned_to: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open")
    # open | assigned | in_review | decision_submitted | escalated | closed
    sla_due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    decision: Mapped[str | None] = mapped_column(String(32), nullable=True)   # approve | reject | request_changes | escalate
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    secondary_approved_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
