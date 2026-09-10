from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


def test_cross_case_isolation_and_security_matrix(client: TestClient, db: Session):
    """E2E Security Test: Proves cross-case isolation across Case Workspace, Documents, Search, Copilot, Intelligence, Workflow, Notes, and IDOR vectors."""
    # ----------------------------------------------------
    # 1. Setup User A and Case A
    # ----------------------------------------------------
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "user_a_isolation@example.com",
            "password": "UserPass123!A",
            "role": "CLIENT",
            "full_name": "User Alpha",
        },
    )
    login_a = client.post(
        "/api/v1/auth/login",
        json={"email": "user_a_isolation@example.com", "password": "UserPass123!A"},
    )
    token_a = login_a.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    case_a_res = client.post(
        "/api/v1/cases",
        headers=headers_a,
        json={"title": "Case Alpha Private", "description": "Highly confidential matter for Alpha."},
    )
    case_a_id = case_a_res.json()["id"]

    # Upload document in Case A
    upload_init_a = client.post(
        f"/api/v1/cases/{case_a_id}/documents/upload-init",
        headers=headers_a,
        json={
            "filename": "alpha_secret.pdf",
            "mime_type": "application/pdf",
            "file_size": 1024,
            "category": "EVIDENCE",
        },
    )
    assert upload_init_a.status_code == 201
    doc_a_id = upload_init_a.json()["document"]["id"]

    # ----------------------------------------------------
    # 2. Setup User B and Case B
    # ----------------------------------------------------
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "user_b_isolation@example.com",
            "password": "UserPass123!B",
            "role": "CLIENT",
            "full_name": "User Beta",
        },
    )
    login_b = client.post(
        "/api/v1/auth/login",
        json={"email": "user_b_isolation@example.com", "password": "UserPass123!B"},
    )
    token_b = login_b.json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    case_b_res = client.post(
        "/api/v1/cases",
        headers=headers_b,
        json={"title": "Case Beta Private", "description": "Highly confidential matter for Beta."},
    )
    _case_b_id = case_b_res.json()["id"]

    # ----------------------------------------------------
    # 3. User B attempts unauthorized access to Case A resources (BOLA / IDOR)
    # ----------------------------------------------------
    # Case metadata
    res_case = client.get(f"/api/v1/cases/{case_a_id}", headers=headers_b)
    assert res_case.status_code in [403, 404]

    # Documents list
    res_docs = client.get(f"/api/v1/cases/{case_a_id}/documents", headers=headers_b)
    assert res_docs.status_code in [403, 404]

    # Document download / chunks
    res_chunks = client.get(f"/api/v1/cases/{case_a_id}/documents/{doc_a_id}/chunks", headers=headers_b)
    assert res_chunks.status_code in [403, 404]

    # Evidence Search
    res_search = client.post(
        f"/api/v1/cases/{case_a_id}/search",
        headers=headers_b,
        json={"query": "financial records", "mode": "HYBRID"},
    )
    assert res_search.status_code in [403, 404]

    # AI Conversations
    res_conv = client.post(
        f"/api/v1/cases/{case_a_id}/conversations",
        headers=headers_b,
        json={"title": "Attacker Conversation"},
    )
    assert res_conv.status_code in [403, 404]

    # Case Intelligence
    res_intel = client.get(f"/api/v1/cases/{case_a_id}/intelligence", headers=headers_b)
    assert res_intel.status_code in [403, 404]

    # Workflow Tasks
    res_tasks = client.get(f"/api/v1/cases/{case_a_id}/tasks", headers=headers_b)
    assert res_tasks.status_code in [403, 404]

    # Case Notes
    res_notes = client.get(f"/api/v1/cases/{case_a_id}/notes", headers=headers_b)
    assert res_notes.status_code in [403, 404]
