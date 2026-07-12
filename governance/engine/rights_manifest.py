"""
Rights Manifest and Provenance Generator.

Generates structured JSON for:
  - rights_manifest_json: usage rights, license class, restrictions
  - provenance_json: source request, provider, model, timestamps, transformations
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Optional


from sqlalchemy.orm import Session
from governance.models.provider_profile import ProviderPolicyProfile
from governance.models.event import GovernanceEvent


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
    db: Optional[Session] = None,
) -> dict[str, Any]:
    """
    Build the rights manifest for a generated asset.
    Computes missing_evidence, confidence_score, and publish_cleared flag
    based on the provider profile and webhook ingestion events.
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

    # 1. Evidence logic & missing_evidence computation
    missing_evidence = []
    evidence_capture_required = False
    
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
            evidence_capture_required = profile.evidence_capture_required

    # If evidence capture is required, check if we have a webhook normalization event
    if evidence_capture_required:
        webhook_event = None
        if db:
            # Query provider events and check payload in Python for database agnosticism
            candidates = db.query(GovernanceEvent).filter(
                GovernanceEvent.target_type == "provider",
                GovernanceEvent.target_id == provider_key,
                GovernanceEvent.action == "provider_event_normalized"
            ).all()
            for cand in candidates:
                payload = cand.event_payload or {}
                if payload.get("request_id") == request_id or payload.get("event_id") == request_id:
                    webhook_event = cand
                    break
            
        if not webhook_event:
            missing_evidence.append("provider_webhook_metadata")

    # 2. Confidence score computation (range: 0.0 - 1.0)
    confidence_score = 1.0
    if rights["license_class"] == "unverified":
        confidence_score = 0.3
    else:
        # Deduct 0.4 per missing evidence item
        confidence_score -= len(missing_evidence) * 0.4
        # Deduct 0.2 if manual review is flagged
        if "requires_manual_rights_review" in rights["restrictions"]:
            confidence_score -= 0.2
            
    confidence_score = max(0.0, min(1.0, confidence_score))

    # 3. Publish cleared computation
    # Publish is cleared only if license class permits commercial use, no manual review is flagged,
    # and there is no missing evidence.
    publish_cleared = (
        rights["license_class"] == "commercial_use_permitted"
        and "requires_manual_rights_review" not in rights["restrictions"]
        and len(missing_evidence) == 0
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
        "publish_cleared": publish_cleared,
        "confidence_score": confidence_score,
        "missing_evidence": missing_evidence,
        "issued_at": datetime.now(timezone.utc).isoformat(),
    }
