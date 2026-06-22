"""
Publish Gate Engine v2 – multi-factor publish-readiness check.

Checks (in order):
  1. Asset governance_state == governance_passed or publish_ready
  2. No active legal or incident holds
  3. Rights manifest is complete and not expired
  4. Retention class is not expired
  5. Quality verdict (if provided) is acceptable
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session

from governance.models.asset import GovernanceAsset
from governance.models.legal_hold import LegalHold
from governance.models.rights_manifest import RightsManifest


@dataclass
class PublishGateResult:
    publish_ready: bool
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    checks: dict = field(default_factory=dict)


def evaluate_publish_gate(
    db: Session,
    asset_id: str,
    workspace_id: str,
    quality_verdict: Optional[str] = None,
) -> PublishGateResult:
    """
    Run all publish-readiness checks for the given asset.
    Returns a PublishGateResult with publish_ready bool, blockers, warnings, and check details.
    """
    result = PublishGateResult(publish_ready=False)

    # ── 1. Fetch asset ────────────────────────────────────────────────────────
    asset: Optional[GovernanceAsset] = (
        db.query(GovernanceAsset)
        .filter(GovernanceAsset.id == asset_id, GovernanceAsset.workspace_id == workspace_id)
        .first()
    )
    if not asset:
        result.blockers.append(f"Asset '{asset_id}' not found in workspace.")
        result.checks["asset_found"] = False
        return result

    result.checks["asset_found"] = True
    result.checks["governance_state"] = asset.governance_state

    # ── 2. Governance state check ─────────────────────────────────────────────
    PUBLISHABLE_STATES = {"governance_passed", "publish_ready"}
    if asset.governance_state not in PUBLISHABLE_STATES:
        result.blockers.append(
            f"Asset is in state '{asset.governance_state}'; must be governance_passed or publish_ready."
        )
        result.checks["governance_state_ok"] = False
    else:
        result.checks["governance_state_ok"] = True

    # ── 3. Legal & incident hold check ────────────────────────────────────────
    active_holds = (
        db.query(LegalHold)
        .filter(
            LegalHold.target_id == asset_id,
            LegalHold.workspace_id == workspace_id,
            LegalHold.status == "active",
        )
        .all()
    )
    if asset.legal_hold or any(h.hold_type == "legal" for h in active_holds):
        result.blockers.append("Asset has an active legal hold – publish blocked.")
        result.checks["legal_hold_clear"] = False
    else:
        result.checks["legal_hold_clear"] = True

    if asset.incident_hold or any(h.hold_type == "incident" for h in active_holds):
        result.blockers.append("Asset has an active incident hold – publish blocked.")
        result.checks["incident_hold_clear"] = False
    else:
        result.checks["incident_hold_clear"] = True

    # ── 4. Rights manifest check ──────────────────────────────────────────────
    rights: Optional[RightsManifest] = (
        db.query(RightsManifest)
        .filter(RightsManifest.asset_id == asset_id, RightsManifest.workspace_id == workspace_id)
        .first()
    )

    if not rights:
        # Fall back to inline JSON manifest on asset
        inline = asset.rights_manifest_json or {}
        if not inline:
            result.blockers.append("No rights manifest found for this asset.")
            result.checks["rights_manifest_ok"] = False
        else:
            result.checks["rights_manifest_ok"] = True
            result.checks["rights_source"] = "inline_json"
    else:
        result.checks["rights_source"] = "rights_manifests_table"
        if rights.source_rights_status in ("missing", "expired"):
            result.blockers.append(
                f"Source rights status is '{rights.source_rights_status}' – publish blocked."
            )
            result.checks["rights_manifest_ok"] = False
        elif rights.source_rights_status == "partial":
            result.warnings.append("Source rights are only partially complete.")
            result.checks["rights_manifest_ok"] = "partial"
        else:
            result.checks["rights_manifest_ok"] = True

        # Check expiry
        if rights.expiry_at and rights.expiry_at < datetime.now(timezone.utc):
            result.blockers.append("Rights manifest has expired.")
            result.checks["rights_not_expired"] = False
        else:
            result.checks["rights_not_expired"] = True

        # Check unresolved restrictions
        restrictions = rights.restrictions or []
        blocking_restrictions = [r for r in restrictions if isinstance(r, dict) and r.get("blocks_publish")]
        if blocking_restrictions:
            result.blockers.append(f"{len(blocking_restrictions)} unresolved publish-blocking restriction(s).")
            result.checks["restrictions_clear"] = False
        else:
            result.checks["restrictions_clear"] = True

        # Missing evidence
        missing = rights.missing_evidence or []
        if missing:
            result.warnings.append(f"Missing evidence items: {', '.join(str(m) for m in missing)}")

    # ── 5. Retention check ────────────────────────────────────────────────────
    if asset.retention_expires_at and asset.retention_expires_at < datetime.now(timezone.utc):
        result.blockers.append("Asset retention period has expired – cannot publish.")
        result.checks["retention_valid"] = False
    else:
        result.checks["retention_valid"] = True

    # ── 6. Quality verdict check ──────────────────────────────────────────────
    if quality_verdict is not None:
        PASSING_VERDICTS = {"pass", "acceptable", "approved"}
        if quality_verdict.lower() not in PASSING_VERDICTS:
            result.blockers.append(f"Quality verdict '{quality_verdict}' does not meet publish threshold.")
            result.checks["quality_verdict_ok"] = False
        else:
            result.checks["quality_verdict_ok"] = True
    else:
        result.checks["quality_verdict_ok"] = "not_provided"

    # ── Final determination ────────────────────────────────────────────────────
    result.publish_ready = len(result.blockers) == 0
    return result
