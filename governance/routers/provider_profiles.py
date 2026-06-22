"""
Router: /api/governance/provider-profiles
Provider Policy Intelligence endpoints – DB-backed versioned provider profiles.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import Optional

from governance.database import get_db
from governance.auth import get_current_user, CurrentUser
from governance.models.provider_profile import ProviderPolicyProfile
from governance.engine.provider_registry import PROVIDER_REGISTRY

router = APIRouter(prefix="/api/governance/provider-profiles", tags=["Provider Profiles"])

# Drift threshold in days
DRIFT_THRESHOLD_DAYS = 30


class UpsertProviderProfileRequest(BaseModel):
    provider_key: str
    moderation_behavior: Optional[dict] = None
    retention_behavior: Optional[dict] = None
    webhook_behavior: Optional[dict] = None
    data_controls: Optional[dict] = None
    risk_class: str = "medium"
    evidence_capture_required: bool = False
    source_notes: Optional[str] = None


@router.get("")
def list_provider_profiles(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """List all active provider profiles (DB + in-memory fallbacks)."""
    db_profiles = (
        db.query(ProviderPolicyProfile)
        .filter(ProviderPolicyProfile.is_active.is_(True))
        .order_by(ProviderPolicyProfile.provider_key)
        .all()
    )

    db_keys = {p.provider_key for p in db_profiles}
    result = []

    # Emit DB profiles
    for p in db_profiles:
        days_since_review = None
        drift_alert = False
        if p.last_reviewed_at:
            delta = datetime.now(timezone.utc) - p.last_reviewed_at.replace(tzinfo=timezone.utc) if p.last_reviewed_at.tzinfo is None else datetime.now(timezone.utc) - p.last_reviewed_at
            days_since_review = delta.days
            drift_alert = days_since_review > DRIFT_THRESHOLD_DAYS
        else:
            drift_alert = True

        result.append({
            "provider_key": p.provider_key,
            "version": p.version,
            "risk_class": p.risk_class,
            "evidence_capture_required": p.evidence_capture_required,
            "moderation_behavior": p.moderation_behavior,
            "retention_behavior": p.retention_behavior,
            "webhook_behavior": p.webhook_behavior,
            "data_controls": p.data_controls,
            "source": "database",
            "last_reviewed_at": p.last_reviewed_at,
            "days_since_review": days_since_review,
            "drift_alert": drift_alert,
            "source_notes": p.source_notes,
        })

    # Fill in in-memory fallbacks for providers not in DB
    for key, traits in PROVIDER_REGISTRY.items():
        if key not in db_keys and key != "unknown_provider":
            result.append({
                "provider_key": key,
                "version": None,
                "risk_class": "medium",
                "evidence_capture_required": traits.get("requires_webhook_persistence", False),
                "moderation_behavior": {"type": traits.get("moderation_type", "unknown")},
                "retention_behavior": {"default_hours": traits.get("default_retention_hours", 0)},
                "webhook_behavior": {"supported": traits.get("requires_webhook_persistence", False)},
                "data_controls": {"scoped_key_support": traits.get("supports_scoped_keys", False)},
                "source": "in_memory_registry",
                "last_reviewed_at": None,
                "days_since_review": None,
                "drift_alert": True,
                "source_notes": "Auto-populated from in-memory registry – update with DB record.",
            })

    return result


@router.get("/{provider_key}")
def get_provider_profile(
    provider_key: str,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Fetch provider policy profile snapshot (DB-first, fallback to registry)."""
    profile = (
        db.query(ProviderPolicyProfile)
        .filter(
            ProviderPolicyProfile.provider_key == provider_key,
            ProviderPolicyProfile.is_active.is_(True),
        )
        .order_by(ProviderPolicyProfile.version.desc())
        .first()
    )

    if profile:
        drift_alert = (
            profile.last_reviewed_at is None
            or (datetime.now(timezone.utc) - (profile.last_reviewed_at.replace(tzinfo=timezone.utc) if profile.last_reviewed_at.tzinfo is None else profile.last_reviewed_at)).days > DRIFT_THRESHOLD_DAYS
        )
        return {
            "provider_key": profile.provider_key,
            "version": profile.version,
            "risk_class": profile.risk_class,
            "evidence_capture_required": profile.evidence_capture_required,
            "moderation_behavior": profile.moderation_behavior,
            "retention_behavior": profile.retention_behavior,
            "webhook_behavior": profile.webhook_behavior,
            "data_controls": profile.data_controls,
            "source": "database",
            "drift_alert": drift_alert,
            "last_reviewed_at": profile.last_reviewed_at,
            "source_notes": profile.source_notes,
        }

    traits = PROVIDER_REGISTRY.get(provider_key)
    if traits:
        return {
            "provider_key": provider_key,
            "version": None,
            "risk_class": "medium",
            "evidence_capture_required": traits.get("requires_webhook_persistence", False),
            "moderation_behavior": {"type": traits.get("moderation_type", "unknown")},
            "retention_behavior": {"default_hours": traits.get("default_retention_hours", 0)},
            "webhook_behavior": {"supported": traits.get("requires_webhook_persistence", False)},
            "data_controls": {"scoped_key_support": traits.get("supports_scoped_keys", False)},
            "source": "in_memory_registry",
            "drift_alert": True,
            "last_reviewed_at": None,
        }

    raise HTTPException(status_code=404, detail=f"Provider '{provider_key}' not found.")


@router.post("", status_code=201)
def upsert_provider_profile(
    body: UpsertProviderProfileRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Create or update a provider policy profile (creates new version)."""
    # Get current max version for this provider
    latest = (
        db.query(ProviderPolicyProfile)
        .filter(ProviderPolicyProfile.provider_key == body.provider_key)
        .order_by(ProviderPolicyProfile.version.desc())
        .first()
    )
    new_version = (latest.version + 1) if latest else 1
    if latest:
        latest.is_active = False  # deactivate old version

    profile = ProviderPolicyProfile(
        provider_key=body.provider_key,
        version=new_version,
        moderation_behavior=body.moderation_behavior,
        retention_behavior=body.retention_behavior,
        webhook_behavior=body.webhook_behavior,
        data_controls=body.data_controls,
        risk_class=body.risk_class,
        evidence_capture_required=body.evidence_capture_required,
        source_notes=body.source_notes,
        is_active=True,
        last_reviewed_at=datetime.now(timezone.utc),
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return {
        "id": profile.id,
        "provider_key": profile.provider_key,
        "version": profile.version,
        "risk_class": profile.risk_class,
        "created_at": profile.created_at,
    }
