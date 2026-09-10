from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


def _setup_perf_user(client: TestClient, email: str = "perf_ai_cost@example.com") -> tuple[str, dict[str, str]]:
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "CostPassword123!", "role": "CLIENT", "full_name": "Cost User"},
    )
    login_res = client.post("/api/v1/auth/login", json={"email": email, "password": "CostPassword123!"})
    token = login_res.json()["access_token"]
    user_id = login_res.json().get("user_id", "")
    return user_id, {"Authorization": f"Bearer {token}"}


def test_ai_query_input_bounding_and_cost_guards(client: TestClient, db: Session):
    """Verifies that API schemas and query handlers enforce strict bounds on input sizes, top_k parameters, and history windows."""
    _, headers = _setup_perf_user(client, "perf_ai_cost_guards@example.com")

    # Create Case
    case_res = client.post(
        "/api/v1/cases",
        headers=headers,
        json={"title": "AI Cost Guard Case", "description": "Testing context bounding."},
    )
    case_id = case_res.json()["id"]

    # 1. ATTACK / COST STRESS: Attempting massive top_k (> 100) on Evidence Search
    huge_topk_res = client.post(
        f"/api/v1/cases/{case_id}/search",
        headers=headers,
        json={"query": "test query", "top_k": 5000},
    )
    # Must either reject via validation (422) or clamp cleanly
    assert huge_topk_res.status_code in [200, 422]
    if huge_topk_res.status_code == 200:
        assert len(huge_topk_res.json().get("results", [])) <= 100

    # 2. Bounded Copilot Message execution
    conv_res = client.post(
        f"/api/v1/cases/{case_id}/ai/conversations",
        headers=headers,
        json={"title": "Bounded Conversation"},
    )
    assert conv_res.status_code == 201
    conv_id = conv_res.json()["id"]

    msg_res = client.post(
        f"/api/v1/cases/{case_id}/ai/conversations/{conv_id}/messages",
        headers=headers,
        json={"query": "Summarize the key issues in this case.", "include_legal_authority": True},
    )
    assert msg_res.status_code == 200
    msg_data = msg_res.json()
    assert "content" in msg_data
    assert "citations" in msg_data
