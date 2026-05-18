"""Integration tests for the exceptions API."""
import pytest

TARGET_ASSET_ID = "mock-asset-id-exception-test"


def test_submit_exception(client):
    resp = client.post("/api/governance/exceptions", json={
        "target_type": "asset",
        "target_id": TARGET_ASSET_ID,
        "business_reason": "Executive preview required for board meeting",
        "workspace_id": "default",
    }, headers={"X-User-Id": "user-requester-01"})
    assert resp.status_code == 201
    data = resp.json()
    assert "exception_id" in data
    assert data["status"] == "pending"


def test_list_exceptions(client):
    resp = client.get("/api/governance/exceptions")
    assert resp.status_code == 200
    data = resp.json()
    assert "exceptions" in data
    assert data["total"] >= 1


def test_approve_exception(client):
    sub = client.post("/api/governance/exceptions", json={
        "target_type": "asset",
        "target_id": TARGET_ASSET_ID,
        "business_reason": "BD demo access required",
        "workspace_id": "default",
    }, headers={"X-User-Id": "user-requester-02"})
    exc_id = sub.json()["exception_id"]

    resp = client.patch(f"/api/governance/exceptions/{exc_id}", json={
        "decision": "approve",
        "reason": "Approved after review",
        "scope_json": {"use": "internal_demo", "max_viewers": 3},
    }, headers={"X-User-Id": "exc-reviewer-01"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "approved"
    assert data["approved_by"] == "exc-reviewer-01"


def test_reject_exception(client):
    sub = client.post("/api/governance/exceptions", json={
        "target_type": "asset",
        "target_id": TARGET_ASSET_ID,
        "business_reason": "Test rejection",
        "workspace_id": "default",
    }, headers={"X-User-Id": "user-requester-03"})
    exc_id = sub.json()["exception_id"]

    resp = client.patch(f"/api/governance/exceptions/{exc_id}", json={
        "decision": "reject",
        "reason": "Insufficient justification",
    }, headers={"X-User-Id": "exc-reviewer-01"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"


def test_cannot_decide_non_pending_exception(client):
    sub = client.post("/api/governance/exceptions", json={
        "target_type": "asset",
        "target_id": TARGET_ASSET_ID,
        "business_reason": "Double approve test",
        "workspace_id": "default",
    }, headers={"X-User-Id": "user-requester-04"})
    exc_id = sub.json()["exception_id"]

    client.patch(f"/api/governance/exceptions/{exc_id}", json={"decision": "approve"})
    resp = client.patch(f"/api/governance/exceptions/{exc_id}", json={"decision": "approve"})
    assert resp.status_code == 422


def test_exception_not_found(client):
    resp = client.patch("/api/governance/exceptions/nonexistent", json={"decision": "approve"})
    assert resp.status_code == 404
