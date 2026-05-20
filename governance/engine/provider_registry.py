"""
Provider Policy Registry

Centralizes provider-specific behaviors and capabilities so the Governance Layer 
can normalize policies across different AI video generation models.
"""

PROVIDER_REGISTRY = {
    "openai": {
        "name": "OpenAI",
        "default_retention_hours": 720,  # 30 days configurable
        "moderation_type": "pre_and_post",
        "supports_scoped_keys": False,
        "requires_webhook_persistence": False,
    },
    "runway": {
        "name": "Runway",
        "default_retention_hours": 720,  # 30 days
        "moderation_type": "pre_and_post",  # moderates inputs and outputs
        "supports_scoped_keys": False,
        "requires_webhook_persistence": False,
    },
    "fal": {
        "name": "fal.ai",
        "default_retention_hours": 24,
        "moderation_type": "none",
        "supports_scoped_keys": True, # Exposes scoped keys
        "requires_webhook_persistence": True,
    },
    "replicate": {
        "name": "Replicate",
        "default_retention_hours": 1,  # 1 hour default retention
        "moderation_type": "none",
        "supports_scoped_keys": False,
        "requires_webhook_persistence": True,
    },
    "unknown_provider": {
        "name": "Unknown",
        "default_retention_hours": 0,
        "moderation_type": "unknown",
        "supports_scoped_keys": False,
        "requires_webhook_persistence": False,
    }
}

def get_provider_traits(provider_key: str) -> dict:
    """Retrieve traits for a given provider, defaulting to unknown if not found."""
    return PROVIDER_REGISTRY.get(provider_key, PROVIDER_REGISTRY["unknown_provider"])
