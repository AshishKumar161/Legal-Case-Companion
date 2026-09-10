from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


def test_full_client_e2e_journey(client: TestClient, db: Session):
    """E2E Test: Validates the complete real-world client journey from registration to AI analysis and workflow operations."""
    # ----------------------------------------------------
    # 1. Register Client Account
    # ----------------------------------------------------
    client_email = "e2e_client_journey@example.com"
    client_pwd = "StrongClientPass123!"
    reg_res = client.post(
        "/api/v1/auth/register",
        json={
            "email": client_email,
            "password": client_pwd,
            "role": "CLIENT",
            "full_name": "E2E Test Client",
        },
    )
    assert reg_res.status_code == 201
    _client_id = reg_res.json()["id"]

    # ----------------------------------------------------
    # 2. Login Client
    # ----------------------------------------------------
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": client_email, "password": client_pwd},
    )
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    csrf_token = login_res.cookies.get("csrf_token")
    refresh_token = login_res.cookies.get("refresh_token")
    assert csrf_token is not None
    assert refresh_token is not None

    # ----------------------------------------------------
    # 3. Authenticated Profile Me
    # ----------------------------------------------------
    me_res = client.get("/api/v1/profiles/me", headers=headers)
    assert me_res.status_code == 200
    assert me_res.json()["full_name"] == "E2E Test Client"

    # ----------------------------------------------------
    # 4. Create Legal Case Matter
    # ----------------------------------------------------
    case_payload = {
        "title": "E2E Commercial Contract Dispute Matter",
        "description": "Breach of software service agreement and unpaid invoices under Section 73 Indian Contract Act.",
    }
    case_res = client.post("/api/v1/cases", headers=headers, json=case_payload)
    assert case_res.status_code == 201
    case_id = case_res.json()["id"]

    # ----------------------------------------------------
    # 5. Add Lawyer Participant
    # ----------------------------------------------------
    lawyer_email = "e2e_assigned_lawyer@example.com"
    lawyer_reg = client.post(
        "/api/v1/auth/register",
        json={
            "email": lawyer_email,
            "password": "StrongLawyerPass123!",
            "role": "LAWYER",
            "full_name": "Adv. Vikram Sethi",
        },
    )
    lawyer_id = lawyer_reg.json()["id"]

    part_res = client.post(
        f"/api/v1/cases/{case_id}/participants",
        headers=headers,
        json={"user_id": lawyer_id, "participant_role": "LAWYER"},
    )
    assert part_res.status_code in [200, 201]

    # ----------------------------------------------------
    # 6. Upload Document Metadata & Complete
    # ----------------------------------------------------
    upload_res = client.post(
        f"/api/v1/cases/{case_id}/documents/upload-init",
        headers=headers,
        json={
            "filename": "master_agreement.pdf",
            "mime_type": "application/pdf",
            "file_size": 2048,
            "category": "CONTRACT",
        },
    )
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["document"]["id"]

    comp_res = client.post(
        f"/api/v1/cases/{case_id}/documents/{doc_id}/complete",
        headers=headers,
    )
    assert comp_res.status_code == 200

    # ----------------------------------------------------
    # 7. Indian Legal Authority Search
    # ----------------------------------------------------
    legal_search_res = client.post(
        "/api/v1/legal-authorities/search",
        headers=headers,
        json={"query": "Indian Contract Act breach", "source_type": "PRIMARY_LEGISLATION"},
    )
    assert legal_search_res.status_code == 200

    # ----------------------------------------------------
    # 8. AI Copilot Conversation & Grounded Citations
    # ----------------------------------------------------
    conv_res = client.post(
        f"/api/v1/cases/{case_id}/ai/conversations",
        headers=headers,
        json={"title": "Contract Breach Assessment"},
    )
    assert conv_res.status_code == 201
    conv_id = conv_res.json()["id"]

    msg_res = client.post(
        f"/api/v1/cases/{case_id}/ai/conversations/{conv_id}/messages",
        headers=headers,
        json={"query": "What are the payment terms in Clause 12 of our agreement?"},
    )
    assert msg_res.status_code == 200
    msg_data = msg_res.json()
    assert "content" in msg_data

    # ----------------------------------------------------
    # 9. Case Intelligence Aggregation
    # ----------------------------------------------------
    intel_refresh = client.post(
        f"/api/v1/cases/{case_id}/intelligence/refresh",
        headers=headers,
    )
    assert intel_refresh.status_code == 200

    intel_res = client.get(
        f"/api/v1/cases/{case_id}/intelligence",
        headers=headers,
    )
    assert intel_res.status_code == 200
    intel_data = intel_res.json()
    assert "facts" in intel_data
    assert "issues" in intel_data
    assert "timeline" in intel_data
    assert "evidence_gaps" in intel_data
    assert "risks" in intel_data

    # ----------------------------------------------------
    # 10. Workflow Operations: Tasks & Deadlines
    # ----------------------------------------------------
    task_res = client.post(
        f"/api/v1/cases/{case_id}/tasks",
        headers=headers,
        json={
            "title": "Review payment ledger from Alpha Ltd",
            "description": "Reconcile invoices against Clause 12 terms",
            "priority": "HIGH",
        },
    )
    assert task_res.status_code == 201
    task_id = task_res.json()["id"]

    task_patch = client.patch(
        f"/api/v1/cases/{case_id}/tasks/{task_id}",
        headers=headers,
        json={"status": "IN_PROGRESS"},
    )
    assert task_patch.status_code == 200
    assert task_patch.json()["status"] == "IN_PROGRESS"

    # ----------------------------------------------------
    # 11. Notifications & Unread Management
    # ----------------------------------------------------
    notif_res = client.get("/api/v1/notifications", headers=headers)
    assert notif_res.status_code == 200
    notifs = notif_res.json().get("items", [])
    assert isinstance(notifs, list)

    # ----------------------------------------------------
    # 12. Session Refresh & Logout
    # ----------------------------------------------------
    ref_res = client.post(
        "/api/v1/auth/refresh",
        headers={"X-CSRF-Token": csrf_token},
        cookies={"refresh_token": refresh_token, "csrf_token": csrf_token},
    )
    assert ref_res.status_code == 200
    new_token = ref_res.json()["access_token"]

    logout_res = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {new_token}"},
    )
    assert logout_res.status_code == 200
