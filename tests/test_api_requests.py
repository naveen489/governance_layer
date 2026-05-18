"""Integration tests for the governance requests API."""
import pytest


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_create_safe_request(client):
    resp = client.post("/api/governance/requests", json={
        "workspace_id": "default",
        "request_payload": {"prompt": "Safe video", "risk_class": "low", "provider_status": "approved"},
        "simulation_mode": True,
        "created_by": "user-test-01",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["state"] == "approved_for_execution"
    assert "governance_request_id" in data


def test_create_blocked_request(client):
    resp = client.post("/api/governance/requests", json={
        "workspace_id": "default",
        "request_payload": {"prompt": "Risky video", "risk_class": "high", "provider_status": "approved"},
        "simulation_mode": True,
        "created_by": "user-test-02",
    })
    assert resp.status_code == 201
    assert resp.json()["state"] == "blocked"


def test_create_review_required_request(client):
    resp = client.post("/api/governance/requests", json={
        "workspace_id": "default",
        "request_payload": {"prompt": "Partner event video", "risk_class": "low", "provider_status": "unknown"},
        "simulation_mode": True,
        "created_by": "user-test-03",
    })
    assert resp.status_code == 201
    assert resp.json()["state"] == "review_required"


def test_list_requests(client):
    resp = client.get("/api/governance/requests")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    assert len(resp.json()) >= 3


def test_get_request_not_found(client):
    resp = client.get("/api/governance/requests/nonexistent-id")
    assert resp.status_code == 404
