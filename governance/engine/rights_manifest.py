"""
Rights Manifest and Provenance Generator.

Generates structured JSON for:
  - rights_manifest_json: usage rights, license class, restrictions
  - provenance_json: source request, provider, model, timestamps, transformations
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Optional


def build_provenance(
    *,
    request_id: str,
    provider_key: str,
    model_key: str,
    asset_payload: dict[str, Any],
    workspace_id: str,
    generated_at: Optional[datetime] = None,
) -> dict[str, Any]:
    """Build the provenance record for a generated asset."""
    return {
        "schema_version": "1.0",
        "source_request_id": request_id,
        "workspace_id": workspace_id,
        "provider_key": provider_key,
        "model_key": model_key,
        "generation_method": "ai_generated",
        "transformations": asset_payload.get("transformations", []),
        "input_prompt": asset_payload.get("prompt", ""),
        "input_reference_assets": asset_payload.get("reference_assets", []),
        "generated_at": (generated_at or datetime.now(timezone.utc)).isoformat(),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }


def build_rights_manifest(
    *,
    request_id: str,
    provider_key: str,
    model_key: str,
    asset_payload: dict[str, Any],
    retention_class: str = "standard",
) -> dict[str, Any]:
    """
    Build the rights manifest for a generated asset.
    Providers map to known license/usage classes; unknown providers get restricted defaults.
    """
    _PROVIDER_RIGHTS: dict[str, dict[str, Any]] = {
        "openai": {
            "license_class": "commercial_use_permitted",
            "attribution_required": False,
            "restrictions": ["no_deceptive_use", "comply_with_openai_usage_policy"],
            "provider_terms_url": "https://openai.com/policies/usage-policies",
        },
        "runway": {
            "license_class": "commercial_use_permitted",
            "attribution_required": False,
            "restrictions": ["no_harmful_content", "comply_with_runway_terms"],
            "provider_terms_url": "https://runwayml.com/terms",
        },
        "fal": {
            "license_class": "commercial_use_permitted",
            "attribution_required": False,
            "restrictions": ["comply_with_fal_terms"],
            "provider_terms_url": "https://fal.ai/terms",
        },
        "replicate": {
            "license_class": "model_specific",
            "attribution_required": True,
            "restrictions": ["check_model_license", "comply_with_replicate_terms"],
            "provider_terms_url": "https://replicate.com/terms",
        },
    }

    rights = _PROVIDER_RIGHTS.get(
        provider_key.lower(),
        {
            "license_class": "unverified",
            "attribution_required": True,
            "restrictions": ["requires_manual_rights_review"],
            "provider_terms_url": None,
        },
    )

    return {
        "schema_version": "1.0",
        "source_request_id": request_id,
        "provider_key": provider_key,
        "model_key": model_key,
        "license_class": rights["license_class"],
        "attribution_required": rights["attribution_required"],
        "restrictions": rights["restrictions"],
        "provider_terms_url": rights["provider_terms_url"],
        "retention_class": retention_class,
        "internal_use_only": asset_payload.get("internal_use_only", True),
        "publish_cleared": False,   # always False at registration; requires further governance
        "issued_at": datetime.now(timezone.utc).isoformat(),
    }
