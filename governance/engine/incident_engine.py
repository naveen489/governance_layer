"""
Incident Engine v2 – auto-detects governance incidents and creates case records.

Triggers:
  - Repeated policy blocks (≥3) for same workspace in 24h
  - Publish attempted without governance_passed state
  - Provider policy drift (profile not reviewed in > 30 days)
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy.orm import Session

from governance.models.incident import GovernanceIncident
from governance.models.event import GovernanceEvent
from governance.models.provider_profile import ProviderPolicyProfile


def check_repeated_blocks(
    db: Session,
    workspace_id: str,
    actor_id: Optional[str] = None,
    threshold: int = 3,
    window_hours: int = 24,
) -> Optional[GovernanceIncident]:
    """
    Auto-create an incident if there are ≥ threshold 'policy_block' events
    in the last window_hours for this workspace.
    """
    since = datetime.now(timezone.utc) - timedelta(hours=window_hours)
    query = (
        db.query(GovernanceEvent)
        .filter(
            GovernanceEvent.workspace_id == workspace_id,
            GovernanceEvent.action == "policy_block",
            GovernanceEvent.occurred_at >= since,
        )
    )
    if actor_id:
        query = query.filter(GovernanceEvent.actor_id == actor_id)

    count = query.count()
    if count >= threshold:
        # Check if an open incident already exists for this trigger
        existing = (
            db.query(GovernanceIncident)
            .filter(
                GovernanceIncident.workspace_id == workspace_id,
                GovernanceIncident.status.in_(["open", "triaged", "investigating"]),
                GovernanceIncident.summary.like("%repeated policy block%"),
            )
            .first()
        )
        if existing:
            return existing

        incident = GovernanceIncident(
            workspace_id=workspace_id,
            severity="high",
            status="open",
            summary=f"Repeated policy block detected: {count} blocks in {window_hours}h.",
            linked_targets={"actor_id": actor_id or "multiple"},
        )
        db.add(incident)
        db.flush()
        return incident
    return None


def check_unauthorized_publish_attempt(
    db: Session,
    workspace_id: str,
    asset_id: str,
    asset_state: str,
) -> Optional[GovernanceIncident]:
    """
    Create incident if publish was attempted on an asset not in a publishable state.
    """
    PUBLISHABLE = {"governance_passed", "publish_ready"}
    if asset_state not in PUBLISHABLE:
        incident = GovernanceIncident(
            workspace_id=workspace_id,
            severity="high",
            status="open",
            summary=f"Publish attempted on asset '{asset_id}' in non-publishable state '{asset_state}'.",
            linked_targets={"asset_id": asset_id, "state": asset_state},
        )
        db.add(incident)
        db.flush()
        return incident
    return None


def check_provider_policy_drift(
    db: Session,
    workspace_id: str,
    drift_days: int = 30,
) -> list[GovernanceIncident]:
    """
    Create incidents for providers whose profiles haven't been reviewed in > drift_days.
    """
    threshold = datetime.now(timezone.utc) - timedelta(days=drift_days)
    stale = (
        db.query(ProviderPolicyProfile)
        .filter(
            ProviderPolicyProfile.is_active.is_(True),
            (ProviderPolicyProfile.last_reviewed_at.is_(None))
            | (ProviderPolicyProfile.last_reviewed_at < threshold),
        )
        .all()
    )

    incidents = []
    for profile in stale:
        existing = (
            db.query(GovernanceIncident)
            .filter(
                GovernanceIncident.workspace_id == workspace_id,
                GovernanceIncident.status.in_(["open", "triaged"]),
                GovernanceIncident.summary.like(f"%provider policy drift%{profile.provider_key}%"),
            )
            .first()
        )
        if not existing:
            incident = GovernanceIncident(
                workspace_id=workspace_id,
                severity="medium",
                status="open",
                summary=f"Provider policy drift: '{profile.provider_key}' profile not reviewed in > {drift_days} days.",
                linked_targets={"provider_key": profile.provider_key},
            )
            db.add(incident)
            db.flush()
            incidents.append(incident)
    return incidents
