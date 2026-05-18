import httpx
import json

base_url = "http://127.0.0.1:8001"

print("--- 1. Request with Unknown Provider (Expect: review_required) ---")
payload_1 = {
    "workspace_id": "default",
    "request_payload": {
        "prompt": "Test video with unknown provider",
        "risk_class": "low",
        "provider_status": "unknown"
    },
    "simulation_mode": True,
    "created_by": "demo-user-123"
}
res1 = httpx.post(f"{base_url}/api/governance/requests", json=payload_1)
print(f"Status: {res1.status_code}")
print(f"Response: {json.dumps(res1.json(), indent=2)}\n")


print("--- 2. Request with High Risk (Expect: blocked) ---")
payload_2 = {
    "workspace_id": "default",
    "request_payload": {
        "prompt": "Test video with high risk",
        "risk_class": "high",
        "provider_status": "approved"
    },
    "simulation_mode": True,
    "created_by": "demo-user-123"
}
res2 = httpx.post(f"{base_url}/api/governance/requests", json=payload_2)
print(f"Status: {res2.status_code}")
print(f"Response: {json.dumps(res2.json(), indent=2)}\n")


print("--- 3. Review Approval Flow (Expect: approved) ---")
reviews_res = httpx.get(f"{base_url}/api/governance/reviews")
reviews = reviews_res.json()
if not reviews:
    print("No pending reviews found in the system.")
else:
    # Find the one we just created, or any pending one
    target_review = reviews[-1]  # Pick the latest one
    req_id = target_review["item_id"]
    print(f"Selected pending review for request ID: {req_id}")
    
    approve_payload = {
        "decision": "approve",
        "reason": "Reviewed and cleared for alpha testing by operations."
    }
    headers = {
        "X-User-Id": "ops-reviewer-01",
        "X-User-Role": "reviewer"
    }
    res3 = httpx.post(
        f"{base_url}/api/governance/reviews/{req_id}/decision", 
        json=approve_payload,
        headers=headers
    )
    print(f"Status: {res3.status_code}")
    print(f"Response: {json.dumps(res3.json(), indent=2)}\n")
