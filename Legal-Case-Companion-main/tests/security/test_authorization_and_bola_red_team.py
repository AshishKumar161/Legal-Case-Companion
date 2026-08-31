from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


def _create_user(client: TestClient, email: str, role: str = "CLIENT") -> tuple[str, dict[str, str]]:
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "SecurePassword123!", "role": role, "full_name": f"User {email}"},
    )
    login_res = client.post("/api/v1/auth/login", json={"email": email, "password": "SecurePassword123!"})
    token = login_res.json()["access_token"]
    user_id = login_res.json().get("user_id", "")
    return user_id, {"Authorization": f"Bearer {token}"}


def test_cross_tenant_bola_idor_matrix(client: TestClient, db: Session):
    """Red Team: Validates that horizontal and vertical IDOR attacks across all resources are blocked."""
    _, headers_a = _create_user(client, "victim_a_bola@test.com", "CLIENT")
    _, headers_b = _create_user(client, "attacker_b_bola@test.com", "CLIENT")

    # Victim A creates a case
    case_res = client.post(
        "/api/v1/cases",
        headers=headers_a,
        json={"title": "Victim A Private Case", "description": "Strictly confidential legal matter."},
    )
    case_a_id = case_res.json()["id"]

    # Victim A uploads document
    upload_res = client.post(
        f"/api/v1/cases/{case_a_id}/documents/upload-init",
        headers=headers_a,
        json={
            "filename": "victim_a_trade_secret.pdf",
            "mime_type": "application/pdf",
            "file_size": 2048,
            "category": "EVIDENCE",
        },
    )
    doc_a_id = upload_res.json()["document"]["id"]

    # Victim A creates task
    task_res = client.post(
        f"/api/v1/cases/{case_a_id}/tasks",
        headers=headers_a,
        json={"title": "Confidential Task A", "description": "Prepare settlement terms"},
    )
    task_a_id = task_res.json()["id"]

    # Victim A creates note
    note_res = client.post(
        f"/api/v1/cases/{case_a_id}/notes",
        headers=headers_a,
        json={"content": "Victim A secret note", "visibility": "SHARED"},
    )
    assert note_res.status_code == 201
    _note_a_id = note_res.json()["id"]

    # ATTACK 1: Attacker B tries to read Victim A Case
    assert client.get(f"/api/v1/cases/{case_a_id}", headers=headers_b).status_code in [403, 404]

    # ATTACK 2: Attacker B tries to list Victim A Documents
    assert client.get(f"/api/v1/cases/{case_a_id}/documents", headers=headers_b).status_code in [403, 404]

    # ATTACK 3: Attacker B tries to download Victim A Document
    assert client.get(f"/api/v1/cases/{case_a_id}/documents/{doc_a_id}/download", headers=headers_b).status_code in [403, 404]

    # ATTACK 4: Attacker B tries to mutate Victim A Task
    assert client.patch(f"/api/v1/cases/{case_a_id}/tasks/{task_a_id}", headers=headers_b, json={"status": "COMPLETED"}).status_code in [403, 404]

    # ATTACK 5: Attacker B tries to access Victim A Notes
    assert client.get(f"/api/v1/cases/{case_a_id}/notes", headers=headers_b).status_code in [403, 404]

    # ATTACK 6: Attacker B tries to query Case Intelligence
    assert client.get(f"/api/v1/cases/{case_a_id}/intelligence", headers=headers_b).status_code in [403, 404]


def test_role_escalation_attacks(client: TestClient, db: Session):
    """Red Team: Validates that clients and lawyers cannot escalate privileges or access admin control planes."""
    _, headers_client = _create_user(client, "client_role_esc@test.com", "CLIENT")
    _, headers_lawyer = _create_user(client, "lawyer_role_esc@test.com", "LAWYER")

    # ATTACK 1: Client attempts to access Admin Metrics
    assert client.get("/api/v1/admin/metrics", headers=headers_client).status_code == 403

    # ATTACK 2: Lawyer attempts to access Admin Metrics
    assert client.get("/api/v1/admin/metrics", headers=headers_lawyer).status_code == 403

    # ATTACK 3: Client attempts to access Admin Lawyer Verifications
    assert client.get("/api/v1/admin/verifications", headers=headers_client).status_code == 403

    # ATTACK 4: Lawyer attempts to access Admin Lawyer Verifications
    assert client.get("/api/v1/admin/verifications", headers=headers_lawyer).status_code == 403

    # ATTACK 5: Client attempts mass assignment to escalate role in profile update
    esc_res = client.patch(
        "/api/v1/profiles/client",
        headers=headers_client,
        json={"role": "ADMIN"},
    )
    assert esc_res.status_code == 422  # Extra fields forbidden
