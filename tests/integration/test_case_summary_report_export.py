from fastapi.testclient import TestClient


def _register_and_login(client: TestClient, email: str, role: str = "CLIENT", full_name: str = "Test User"):
    reg_res = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Password123!",
            "full_name": full_name,
            "role": role,
        },
    )
    assert reg_res.status_code == 201, reg_res.text
    user_id = reg_res.json()["id"]

    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    assert login_res.status_code == 200, login_res.text
    token = login_res.json()["access_token"]
    return user_id, {"Authorization": f"Bearer {token}"}


def test_client_case_summary_report_authorized_and_note_privacy(client: TestClient):
    # 1. Setup Client (Owner) and Lawyer
    _client_id, client_headers = _register_and_login(client, "report_owner@test.com", "CLIENT", "Client Owner")
    lawyer_id, lawyer_headers = _register_and_login(client, "report_lawyer@test.com", "LAWYER", "Adv. Malhotra")

    # 2. Client creates case
    case_res = client.post(
        "/api/v1/cases",
        headers=client_headers,
        json={"title": "Commercial Contract Dispute", "description": "Breach of supply agreement section 14."},
    )
    assert case_res.status_code == 201
    case_id = case_res.json()["id"]

    # 3. Add Lawyer as participant
    part_res = client.post(
        f"/api/v1/cases/{case_id}/participants",
        headers=client_headers,
        json={"user_id": lawyer_id, "participant_role": "LAWYER"},
    )
    assert part_res.status_code in (200, 201)

    # 4. Create Tasks, Hearings, Deadlines
    client.post(
        f"/api/v1/cases/{case_id}/tasks",
        headers=client_headers,
        json={"title": "Draft statement of claim", "priority": "HIGH"},
    )
    client.post(
        f"/api/v1/cases/{case_id}/hearings",
        headers=client_headers,
        json={"court_name": "Delhi High Court", "hearing_at": "2026-10-15T10:30:00Z", "purpose": "Admission"},
    )
    client.post(
        f"/api/v1/cases/{case_id}/deadlines",
        headers=client_headers,
        json={
            "title": "Limitation Filing Deadline",
            "deadline_at": "2026-11-01T17:00:00Z",
            "deadline_type": "STATUTORY_LIMITATION",
        },
    )

    # 5. Add Notes with varying visibility
    # SHARED note (visible to all)
    client.post(
        f"/api/v1/cases/{case_id}/notes",
        headers=client_headers,
        json={"title": "Agreed Case Strategy", "content": "File interim injunction application.", "visibility": "SHARED"},
    )
    # CLIENT_PRIVATE note (visible to client only)
    client.post(
        f"/api/v1/cases/{case_id}/notes",
        headers=client_headers,
        json={"title": "Client Private Thoughts", "content": "Settlement threshold is 50 Lakhs.", "visibility": "CLIENT_PRIVATE"},
    )
    # LAWYER_PRIVATE note (visible to lawyer only)
    client.post(
        f"/api/v1/cases/{case_id}/notes",
        headers=lawyer_headers,
        json={"title": "Counsel Work Product", "content": "Opposing counsel precedent weakness in citation.", "visibility": "LAWYER_PRIVATE"},
    )

    # 6. Client fetches report
    rep_res = client.get(f"/api/v1/cases/{case_id}/report", headers=client_headers)
    assert rep_res.status_code == 200, rep_res.text
    rep_data = rep_res.json()

    # Verify overview
    assert rep_data["case_overview"]["title"] == "Commercial Contract Dispute"
    assert len(rep_data["participants"]) >= 2
    assert len(rep_data["tasks"]) == 1
    assert rep_data["tasks"][0]["title"] == "Draft statement of claim"
    assert len(rep_data["hearings"]) == 1
    assert rep_data["hearings"][0]["court_name"] == "Delhi High Court"
    assert len(rep_data["deadlines"]) == 1

    # Verify Note Privacy for Client:
    note_titles = [n["title"] for n in rep_data["notes"]]
    assert "Agreed Case Strategy" in note_titles
    assert "Client Private Thoughts" in note_titles
    assert "Counsel Work Product" not in note_titles  # MUST NOT leak lawyer private work product!


def test_lawyer_case_summary_report_and_note_privacy(client: TestClient):
    _client_id, client_headers = _register_and_login(client, "rep_cl2@test.com", "CLIENT", "Client Two")
    lawyer_id, lawyer_headers = _register_and_login(client, "rep_lw2@test.com", "LAWYER", "Adv. Verma")

    case_res = client.post(
        "/api/v1/cases",
        headers=client_headers,
        json={"title": "Arbitration Matter", "description": "Arbitration proceedings under Section 11."},
    )
    case_id = case_res.json()["id"]

    client.post(
        f"/api/v1/cases/{case_id}/participants",
        headers=client_headers,
        json={"user_id": lawyer_id, "participant_role": "LAWYER"},
    )

    client.post(
        f"/api/v1/cases/{case_id}/notes",
        headers=client_headers,
        json={"title": "Client Secret Budget", "content": "Budget is confidential.", "visibility": "CLIENT_PRIVATE"},
    )
    client.post(
        f"/api/v1/cases/{case_id}/notes",
        headers=lawyer_headers,
        json={"title": "Advocate Strategy Memo", "content": "Section 9 interim relief strategy.", "visibility": "LAWYER_PRIVATE"},
    )
    client.post(
        f"/api/v1/cases/{case_id}/notes",
        headers=client_headers,
        json={"title": "Shared Minutes", "content": "Hearing scheduled for next month.", "visibility": "SHARED"},
    )

    # Lawyer requests report
    rep_res = client.get(f"/api/v1/cases/{case_id}/report", headers=lawyer_headers)
    assert rep_res.status_code == 200, rep_res.text
    rep_data = rep_res.json()

    note_titles = [n["title"] for n in rep_data["notes"]]
    assert "Shared Minutes" in note_titles
    assert "Advocate Strategy Memo" in note_titles  # Lawyer's own private note is visible
    assert "Client Secret Budget" not in note_titles  # Client's private note is STRICTLY EXCLUDED


def test_viewer_case_summary_report_privacy(client: TestClient):
    _client_id, client_headers = _register_and_login(client, "rep_cl3@test.com", "CLIENT", "Client Three")
    viewer_id, viewer_headers = _register_and_login(client, "rep_vw3@test.com", "CLIENT", "Auditor Viewer")

    case_res = client.post(
        "/api/v1/cases",
        headers=client_headers,
        json={"title": "Corporate Due Diligence", "description": "Audit of contracts."},
    )
    case_id = case_res.json()["id"]

    client.post(
        f"/api/v1/cases/{case_id}/participants",
        headers=client_headers,
        json={"user_id": viewer_id, "participant_role": "VIEWER"},
    )

    client.post(
        f"/api/v1/cases/{case_id}/notes",
        headers=client_headers,
        json={"title": "Private Owner Note", "content": "Confidential internal owner note.", "visibility": "CLIENT_PRIVATE"},
    )
    client.post(
        f"/api/v1/cases/{case_id}/notes",
        headers=client_headers,
        json={"title": "Shared Audit Agenda", "content": "Public audit schedule.", "visibility": "SHARED"},
    )

    # Viewer requests report
    rep_res = client.get(f"/api/v1/cases/{case_id}/report", headers=viewer_headers)
    assert rep_res.status_code == 200
    rep_data = rep_res.json()

    note_titles = [n["title"] for n in rep_data["notes"]]
    assert "Shared Audit Agenda" in note_titles
    assert "Private Owner Note" not in note_titles


def test_unauthorized_and_unauthenticated_report_access(client: TestClient):
    _client_id, client_headers = _register_and_login(client, "rep_cl4@test.com", "CLIENT", "Client Four")
    _other_id, other_headers = _register_and_login(client, "rep_stranger@test.com", "CLIENT", "Stranger")

    case_res = client.post(
        "/api/v1/cases",
        headers=client_headers,
        json={"title": "Secret Patent Dispute", "description": "Confidential matter."},
    )
    case_id = case_res.json()["id"]

    # 1. Unauthenticated request -> 401
    unauth_res = client.get(f"/api/v1/cases/{case_id}/report")
    assert unauth_res.status_code == 401

    # 2. Unaffiliated user (BOLA) -> 404 (Obscures case existence)
    stranger_res = client.get(f"/api/v1/cases/{case_id}/report", headers=other_headers)
    assert stranger_res.status_code == 404


def test_document_privacy_and_s3_safety_in_report(client: TestClient):
    _client_id, client_headers = _register_and_login(client, "rep_cl5@test.com", "CLIENT", "Client Five")

    case_res = client.post(
        "/api/v1/cases",
        headers=client_headers,
        json={"title": "Document Test Matter", "description": "Testing safe document metadata."},
    )
    case_id = case_res.json()["id"]

    # Upload document intent
    upload_res = client.post(
        f"/api/v1/cases/{case_id}/documents/upload-init",
        headers=client_headers,
        json={
            "filename": "ConfidentialContract.pdf",
            "document_type": "CONTRACT",
            "file_size": 1048576,
            "mime_type": "application/pdf",
        },
    )
    assert upload_res.status_code == 201
    assert upload_res.status_code == 201

    # Fetch report
    rep_res = client.get(f"/api/v1/cases/{case_id}/report", headers=client_headers)
    assert rep_res.status_code == 200
    rep_data = rep_res.json()

    assert len(rep_data["documents"]) == 1
    doc_meta = rep_data["documents"][0]
    assert doc_meta["name"] == "ConfidentialContract.pdf"
    assert "upload_url" not in doc_meta
    assert "s3_key" not in doc_meta
    assert "aws_secret" not in doc_meta


def test_markdown_and_json_download_formats(client: TestClient):
    _client_id, client_headers = _register_and_login(client, "rep_cl6@test.com", "CLIENT", "Client Six")

    case_res = client.post(
        "/api/v1/cases",
        headers=client_headers,
        json={"title": "Trademark Registration", "description": "Brand trademark filings."},
    )
    case_id = case_res.json()["id"]

    # 1. Download Markdown format
    md_res = client.get(f"/api/v1/cases/{case_id}/report?format=markdown", headers=client_headers)
    assert md_res.status_code == 200
    assert "text/markdown" in md_res.headers["content-type"]
    assert "attachment; filename=" in md_res.headers["content-disposition"]
    assert "LEGAL CASE COMPANION — CASE SUMMARY REPORT" in md_res.text
    assert "Trademark Registration" in md_res.text

    # 2. Download JSON format with attachment header
    json_dl_res = client.get(f"/api/v1/cases/{case_id}/report?format=json&download=true", headers=client_headers)
    assert json_dl_res.status_code == 200
    assert "application/json" in json_dl_res.headers["content-type"]
    assert "attachment; filename=" in json_dl_res.headers["content-disposition"]
    assert "Trademark Registration" in json_dl_res.text


def test_malicious_content_and_injection_handling(client: TestClient):
    _client_id, client_headers = _register_and_login(client, "rep_cl7@test.com", "CLIENT", "Client Seven")

    malicious_title = "<script>alert('xss')</script> / Dispute: Test \n\r \"injection\" & ⚖️ Special"
    case_res = client.post(
        "/api/v1/cases",
        headers=client_headers,
        json={"title": malicious_title, "description": "Testing character sanitization."},
    )
    case_id = case_res.json()["id"]

    # Fetch markdown report
    md_res = client.get(f"/api/v1/cases/{case_id}/report?format=markdown", headers=client_headers)
    assert md_res.status_code == 200
    disp = md_res.headers["content-disposition"]
    # Filename should not contain control chars or unescaped quotes
    assert "\n" not in disp
    assert "\r" not in disp
    assert "<script>" not in disp


def test_admin_case_summary_report_and_audit_event(client: TestClient, db):
    from sqlalchemy import select

    from app.models.audit import AuditEvent
    from app.models.user import User, UserRole

    # Create client case
    _client_id, client_headers = _register_and_login(client, "rep_cl8@test.com", "CLIENT", "Client Eight")
    case_res = client.post(
        "/api/v1/cases",
        headers=client_headers,
        json={"title": "Admin Audit Test Case", "description": "Testing admin export and audit logs."},
    )
    case_id = case_res.json()["id"]

    # Register admin user and upgrade role in DB
    admin_id, _ = _register_and_login(client, "rep_admin@test.com", "CLIENT", "System Admin")
    admin_user = db.execute(select(User).where(User.id == admin_id)).scalar_one()
    admin_user.role = UserRole.ADMIN
    db.commit()

    # Log in as admin to obtain JWT with ADMIN role
    admin_login = client.post(
        "/api/v1/auth/login",
        json={"email": "rep_admin@test.com", "password": "Password123!"},
    )
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

    # Admin exports report
    admin_rep_res = client.get(f"/api/v1/cases/{case_id}/report", headers=admin_headers)
    assert admin_rep_res.status_code == 200
    rep_data = admin_rep_res.json()
    assert rep_data["case_overview"]["title"] == "Admin Audit Test Case"
    assert rep_data["metadata"]["generated_by_role"] == "ADMIN"

    # Verify audit event in DB
    audit_event = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "CASE_REPORT_GENERATED",
            AuditEvent.actor_user_id == admin_id,
        )
    ).scalars().first()
    assert audit_event is not None
    assert str(case_id) in str(audit_event.metadata_)

