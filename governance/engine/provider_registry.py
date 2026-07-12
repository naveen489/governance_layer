from sqlalchemy.orm import Session
from governance.models.provider_profile import ProviderPolicyProfile

PROVIDER_REGISTRY = {
    "openai": {
        "name": "OpenAI",
        "default_retention_hours": 720,  # 30 days configurable
        "moderation_type": "pre_and_post",
        "supports_scoped_keys": False,
        "requires_webhook_persistence": False,
        "risk_class": "low",
        "status": "approved",
    },
    "runway": {
        "name": "Runway",
        "default_retention_hours": 720,  # 30 days
        "moderation_type": "pre_and_post",  # moderates inputs and outputs
        "supports_scoped_keys": False,
        "requires_webhook_persistence": False,
        "risk_class": "medium",
        "status": "approved",
    },
    "fal": {
        "name": "fal.ai",
        "default_retention_hours": 24,
        "moderation_type": "none",
        "supports_scoped_keys": True, # Exposes scoped keys
        "requires_webhook_persistence": True,
        "risk_class": "low",
        "status": "approved",
    },
    "replicate": {
        "name": "Replicate",
        "default_retention_hours": 1,  # 1 hour default retention
        "moderation_type": "none",
        "supports_scoped_keys": False,
        "requires_webhook_persistence": True,
        "risk_class": "medium",
        "status": "approved",
    },
    "unknown_provider": {
        "name": "Unknown",
        "default_retention_hours": 0,
        "moderation_type": "unknown",
        "supports_scoped_keys": False,
        "requires_webhook_persistence": False,
        "risk_class": "unknown",
        "status": "unknown",
    }
}

def get_provider_traits(provider_key: str, db: Session = None) -> dict:
    """Retrieve traits for a given provider, querying DB if session is available."""
    if db:
        profile = (
            db.query(ProviderPolicyProfile)
            .filter(
                ProviderPolicyProfile.provider_key == provider_key,
                ProviderPolicyProfile.is_active == True
            )
            .first()
        )
        if profile:
            retention = profile.retention_behavior or {}
            moderation = profile.moderation_behavior or {}
            controls = profile.data_controls or {}
            webhook = profile.webhook_behavior or {}
            
            return {
                "name": provider_key.capitalize(),
                "default_retention_hours": retention.get("default_hours", 720),
                "moderation_type": moderation.get("type", "none"),
                "supports_scoped_keys": controls.get("scoped_key_support", False),
                "requires_webhook_persistence": webhook.get("supported", False),
                "risk_class": profile.risk_class,
                "evidence_capture_required": profile.evidence_capture_required,
                "status": "approved" if profile.is_active else "under_review",
            }
            
    # Fallback to static dictionary lookup
    return PROVIDER_REGISTRY.get(provider_key, PROVIDER_REGISTRY["unknown_provider"])
