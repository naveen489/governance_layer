"""Integration tests for the assets API."""
import pytest

REQUEST_ID = "shared-request-id-for-assets"


def _ensure_parent_request(client):
    """Create a parent request if needed."""
    from tests.conftest import TestSessionLocal
    from governance.models.request import GovernanceRequest
    from datetime import datetime, timezone

    db = TestSessionLocal()
    if not db.query(GovernanceRequest).filter(GovernanceRequest.id == REQUEST_ID).first():
        req = GovernanceRequest(
            id=REQUEST_ID,
            workspace_id="default",
            request_payload={"prompt": "Test asset parent"},
            governance_state="approved_for_execution",
            policy_version=1,
            decision_summary={"action": "pass", "reasons": [], "rule_ids": []},
            created_by="user-01",
            simulation_mode=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(req)
        db.commit()
    db.close()


def test_evaluate_asset_pass(client):
    _ensure_parent_request(client)
    resp = client.post("/api/governance/assets/evaluate", json={
        "request_id": REQUEST_ID,
        "asset_payload": {"prompt": "Safe output", "output_url": "https://mock/asset.mp4"},
        "provider_key": "openai",
        "model_key": "gpt-4o-video",
        "retention_class": "standard",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert "asset_id" in data
    assert data["state"] == "governance_passed"


def test_list_assets(client):
    resp = client.get("/api/governance/assets")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    assert len(resp.json()) >= 1


def test_get_asset_detail(client):
    _ensure_parent_request(client)
    resp = client.post("/api/governance/assets/evaluate", json={
        "request_id": REQUEST_ID,
        "asset_payload": {"prompt": "Detail test"},
        "provider_key": "runway",
        "model_key": "gen-3-alpha",
        "retention_class": "short",
    })
    asset_id = resp.json()["asset_id"]
    detail_resp = client.get(f"/api/governance/assets/{asset_id}")
    assert detail_resp.status_code == 200
    data = detail_resp.json()
    assert data["id"] == asset_id
    assert data["provider_key"] == "runway"
    assert data["provenance_json"] is not None
    assert data["rights_manifest_json"] is not None


def test_download_manifest(client):
    _ensure_parent_request(client)
    resp = client.post("/api/governance/assets/evaluate", json={
        "request_id": REQUEST_ID,
        "asset_payload": {"prompt": "Manifest test"},
        "provider_key": "fal",
        "model_key": "fal-ai/video-gen",
        "retention_class": "extended",
    })
    asset_id = resp.json()["asset_id"]
    manifest_resp = client.get(f"/api/governance/assets/{asset_id}/manifest")
    assert manifest_resp.status_code == 200
    assert "license_class" in manifest_resp.json()


def test_asset_not_found(client):
    resp = client.get("/api/governance/assets/nonexistent")
    assert resp.status_code == 404
