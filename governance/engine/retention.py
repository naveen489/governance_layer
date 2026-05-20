"""
Retention and Deletion Engine.

Retention classes and their windows:
  short    → 7 days
  standard → 30 days
  extended → 90 days

evaluate_retention():
  - Finds assets past their retention window
  - Checks legal_hold, incident_hold, and active exceptions
  - Marks eligible assets as 'expired' and writes a deletion event
"""
from __future__ import annotations
from datetime import datetime, timezone
import uuid
from sqlalchemy.orm import Session

from governance.models.asset import GovernanceAsset
from governance.models.event import GovernanceEvent
from governance.models.exception import GovernanceException

RETENTION_CLASSES = {
    "short": 7,
    "standard": 30,
    "extended": 90,
}


def _has_active_exception(db: Session, asset_id: str) -> bool:
    """Return True if the asset has an approved and not-yet-expired exception."""
    now = datetime.now(timezone.utc)
    exc: GovernanceException | None = (
        db.query(GovernanceException)
        .filter(
            GovernanceException.target_id == asset_id,
            GovernanceException.target_type == "asset",
            GovernanceException.status == "approved",
        )
        .first()
    )
    if exc is None:
        return False
    if exc.expiry_at is None:
        return True  # Indefinite exception
    # Compare timezone-aware datetimes
    expiry = exc.expiry_at
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    return expiry > now


def evaluate_retention(db: Session) -> dict[str, int]:
    """
    Scan all assets, expire those past their retention window with no blockers.
    Returns a summary dict with counts.
    """
    now = datetime.now(timezone.utc)
    expired_count = 0
    skipped_count = 0

    assets = (
        db.query(GovernanceAsset)
        .filter(GovernanceAsset.governance_state.notin_(["expired", "deleted"]))
        .all()
    )

    for asset in assets:
        if asset.retention_expires_at is None:
            continue

        expires_at = asset.retention_expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if expires_at > now:
            continue  # Not expired yet

        # Check blockers
        if asset.legal_hold:
            skipped_count += 1
            continue
        if asset.incident_hold:
            skipped_count += 1
            continue
        if _has_active_exception(db, asset.id):
            skipped_count += 1
            continue

        # Mark expired and write event
        asset.governance_state = "expired"
        event = GovernanceEvent(
            workspace_id=asset.workspace_id,
            target_type="asset",
            target_id=asset.id,
            actor_id="system:retention_scheduler",
            action="expire",
            reason=f"Retention window ({asset.retention_class}) ended on {expires_at.isoformat()}",
            event_payload={"retention_class": asset.retention_class, "expired_at": now.isoformat()},
            occurred_at=now,
        )
        db.add(event)
        expired_count += 1

    db.commit()
    return {"expired": expired_count, "skipped_due_to_hold": skipped_count}

def delete_expired_assets(db: Session) -> int:
    """
    Find assets in the 'expired' state and move them to 'deleted' state
    if no legal holds or incident holds apply.
    """
    now = datetime.now(timezone.utc)
    deleted_count = 0

    expired_assets = (
        db.query(GovernanceAsset)
        .filter(GovernanceAsset.governance_state == "expired")
        .all()
    )

    for asset in expired_assets:
        # Final safety check before deletion
        if asset.legal_hold or asset.incident_hold or _has_active_exception(db, asset.id):
            continue
        
        # Soft delete the asset
        asset.governance_state = "deleted"
        asset.updated_at = now
        
        event = GovernanceEvent(
            id=str(uuid.uuid4()),
            workspace_id=asset.workspace_id,
            target_type="asset",
            target_id=asset.id,
            actor_id="system:retention_scheduler",
            action="delete",
            reason="Asset expired and safely passed hold checks",
            event_payload={"deleted_at": now.isoformat()},
            occurred_at=now,
        )
        db.add(event)
        deleted_count += 1
        
    db.commit()
    return deleted_count


def expire_exceptions(db: Session) -> int:
    """Auto-expire exceptions past their expiry_at date."""
    now = datetime.now(timezone.utc)
    count = 0

    exceptions = (
        db.query(GovernanceException)
        .filter(GovernanceException.status == "approved")
        .all()
    )

    for exc in exceptions:
        if exc.expiry_at is None:
            continue
        expiry = exc.expiry_at
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        if expiry <= now:
            exc.status = "expired"
            count += 1

    db.commit()
    return count
