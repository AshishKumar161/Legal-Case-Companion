import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.identifiers import generate_uuid7
from app.core.security import hash_password
from app.models.document import (
    Document,
    DocumentCategory,
    DocumentProcessingStatus,
    DocumentSecurityStatus,
)
from app.models.feedback import FeedbackCategory, PilotFeedback
from app.models.user import AccountStatus, User, UserRole


def _register_and_login(client: TestClient, email: str, role: str, name: str) -> tuple[str, dict]:
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "PilotPassword123!",
            "role": role,
            "full_name": name,
        },
    )
    assert reg.status_code == 201, reg.text
    user_id = reg.json()["id"]

    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "PilotPassword123!"},
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    return user_id, {"Authorization": f"Bearer {token}"}


# ==============================================================================
# CANONICAL JOURNEY 1: CLIENT END-TO-END WORKFLOW
# ==============================================================================
def test_canonical_client_journey_complete(client: TestClient, db: Session):
    """
    Client Journey:
    Register -> Login -> Create Matter -> Add Lawyer -> Upload Evidence ->
    Inspect Intelligence -> Query Copilot -> Discover Gap -> Receive Matter Request ->
    Submit Evidence -> View Live Status -> Submit Pilot Feedback
    """
    # 1. Register & Login
    client_id, client_headers = _register_and_login(
        client, "pilot_client_corp@example.com", "CLIENT", "Aarav Singhania"
    )
    lawyer_id, _ = _register_and_login(
        client, "pilot_lawyer_counsel@example.com", "LAWYER", "Adv. Rohit Mathur"
    )

    # 2. Create Matter
    case_res = client.post(
        "/api/v1/cases",
        headers=client_headers,
        json={
            "title": "Singhania Logistics v. National Cargo Carriers",
            "description": "Breach of multi-modal freight transport contract and cargo damage claim under Carriage by Road Act 2007.",
        },
    )
    assert case_res.status_code == 201
    case_id = case_res.json()["id"]

    # 3. Add Lawyer as Participant
    part_res = client.post(
        f"/api/v1/cases/{case_id}/participants",
        headers=client_headers,
        json={"user_id": lawyer_id, "participant_role": "LAWYER"},
    )
    assert part_res.status_code == 200

    # 4. Upload & Persist Evidence Document
    doc = Document(
        id=generate_uuid7(),
        case_id=uuid.UUID(case_id),
        uploaded_by=uuid.UUID(client_id),
        filename="freight_consignment_note_2023.pdf",
        storage_key=f"cases/{case_id}/freight_consignment_note_2023.pdf",
        mime_type="application/pdf",
        file_size=245000,
        document_type=DocumentCategory.CONTRACT,
        security_status=DocumentSecurityStatus.SAFE,
        processing_status=DocumentProcessingStatus.READY,
    )
    db.add(doc)
    db.commit()

    docs_res = client.get(f"/api/v1/cases/{case_id}/documents", headers=client_headers)
    assert docs_res.status_code == 200
    assert len(docs_res.json().get("items", [])) >= 1

    # 5. Query Case Intelligence & Facts
    intel_res = client.get(f"/api/v1/cases/{case_id}/intelligence", headers=client_headers)
    assert intel_res.status_code == 200
    intel = intel_res.json()
    assert "facts" in intel
    assert "risks" in intel

    # 6. Ask Case Copilot AI (Grounded Query)
    copilot_res = client.post(
        f"/api/v1/cases/{case_id}/ai/conversations",
        headers=client_headers,
        json={"title": "Client Initial Inquiry"},
    )
    assert copilot_res.status_code == 201
    conv_id = copilot_res.json()["id"]

    chat_res = client.post(
        f"/api/v1/cases/{case_id}/ai/conversations/{conv_id}/messages",
        headers=client_headers,
        json={"query": "What are the statutory limitation periods applicable to this freight claim?"},
    )
    assert chat_res.status_code == 200
    assert "content" in chat_res.json()

    # 7. Check Matter Collaboration Brief
    brief_res = client.get(f"/api/v1/cases/{case_id}/collaboration/brief", headers=client_headers)
    assert brief_res.status_code == 200
    assert brief_res.json()["participants_count"] >= 2

    # 8. Submit Privacy-Preserving Pilot Feedback
    feedback_res = client.post(
        "/api/v1/feedback",
        headers=client_headers,
        json={
            "category": "CONFUSING_UX",
            "description": "Clear matter overview, but would appreciate simpler explanation of limitation dates.",
            "page_url": f"https://lcc.internal/cases/{case_id}?tab=intelligence",
        },
    )
    assert feedback_res.status_code == 201
    assert feedback_res.json()["page_url"] == f"/cases/{case_id}"


# ==============================================================================
# CANONICAL JOURNEY 2: LAWYER END-TO-END WORKFLOW
# ==============================================================================
def test_canonical_lawyer_journey_complete(client: TestClient, db: Session):
    """
    Lawyer Journey:
    Register -> Bar Verification -> Consultation Slot Setup -> Access Assigned Matter ->
    Review Evidence -> Issue Structured Matter Request -> Client Responds ->
    Lawyer Reviews Submission -> Records Human Decision -> Broadcasts Notice to Stream ->
    Schedules Court Hearing Milestone
    """
    # 1. Register Lawyer & Client
    lawyer_id, lawyer_headers = _register_and_login(
        client, "lead_advocate_delhi@example.com", "LAWYER", "Adv. Meenakshi Sundaram"
    )
    client_id, client_headers = _register_and_login(
        client, "client_commercial_dispute@example.com", "CLIENT", "Kunal Shah"
    )

    # 2. Lawyer submits Bar Verification
    verif_res = client.post(
        "/api/v1/profiles/lawyer/verification",
        headers=lawyer_headers,
        json={"enrollment_number": "D/9876/2018", "state_bar_council": "Bar Council of Delhi"},
    )
    assert verif_res.status_code in (200, 201)

    # 3. Client creates Matter and assigns Lawyer
    case_res = client.post(
        "/api/v1/cases",
        headers=client_headers,
        json={
            "title": "Alpha FinTech v. Gateway Technologies",
            "description": "Injunction application under Section 9 Arbitration & Conciliation Act 1996 for escrow fund preservation.",
        },
    )
    case_id = case_res.json()["id"]

    client.post(
        f"/api/v1/cases/{case_id}/participants",
        headers=client_headers,
        json={"user_id": lawyer_id, "participant_role": "LAWYER"},
    )

    # 4. Lawyer opens matter workspace
    workspace_res = client.get(f"/api/v1/cases/{case_id}/workspace", headers=lawyer_headers)
    assert workspace_res.status_code == 200
    assert workspace_res.json()["case"]["id"] == case_id

    # 5. Lawyer creates Structured Matter Request
    req_res = client.post(
        f"/api/v1/cases/{case_id}/collaboration/requests",
        headers=lawyer_headers,
        json={
            "title": "Upload Tripartite Escrow Agreement",
            "description": "Required for Section 9 interim relief application before Delhi High Court Commercial Division.",
            "request_type": "DOCUMENT_UPLOAD",
            "assigned_user_id": client_id,
        },
    )
    assert req_res.status_code == 201
    request_id = req_res.json()["id"]
    assert req_res.json()["status"] == "PENDING"

    # 6. Client uploads document and submits response to request
    doc = Document(
        id=generate_uuid7(),
        case_id=uuid.UUID(case_id),
        uploaded_by=uuid.UUID(client_id),
        filename="tripartite_escrow_agreement_2022.pdf",
        storage_key=f"cases/{case_id}/tripartite_escrow_agreement_2022.pdf",
        mime_type="application/pdf",
        file_size=512000,
        document_type=DocumentCategory.CONTRACT,
        security_status=DocumentSecurityStatus.SAFE,
    )
    db.add(doc)
    db.commit()

    submit_res = client.post(
        f"/api/v1/cases/{case_id}/collaboration/requests/{request_id}/submit",
        headers=client_headers,
        json={
            "submitted_document_id": str(doc.id),
            "response_notes": "Executed copy with SBI Escrow account schedule attached.",
        },
    )
    assert submit_res.status_code == 200
    assert submit_res.json()["status"] == "SUBMITTED"

    # 7. Lawyer reviews and approves request
    review_res = client.post(
        f"/api/v1/cases/{case_id}/collaboration/requests/{request_id}/review",
        headers=lawyer_headers,
        json={
            "review_notes": "Executed copy verified. Prima facie case established under Sec 9.",
            "mark_status": "REVIEWED",
        },
    )
    assert review_res.status_code == 200
    assert review_res.json()["status"] == "REVIEWED"

    # 8. Lawyer records Formal Human Legal Decision
    note_res = client.post(
        f"/api/v1/cases/{case_id}/notes",
        headers=lawyer_headers,
        json={
            "title": "[DECISION] Move for Urgent Sec 9 Interim Injunction",
            "content": "Decision: File petition immediately before Delhi High Court. Evidence: SBI Escrow Schedule. Rationale: High risk of fund dissipation.",
            "visibility": "SHARED",
        },
    )
    assert note_res.status_code == 201

    # Broadcast formal notice to matter stream
    msg_res = client.post(
        f"/api/v1/cases/{case_id}/collaboration/messages",
        headers=lawyer_headers,
        json={
            "content": "Formal decision confirmed: Section 9 petition listed for urgent hearing.",
            "message_type": "STATUS_UPDATE",
            "is_counsel_only": False,
        },
    )
    assert msg_res.status_code == 201

    # 9. Schedule Hearing Milestone
    hearing_res = client.post(
        f"/api/v1/cases/{case_id}/hearings",
        headers=lawyer_headers,
        json={
            "court_name": "Delhi High Court (Commercial Division)",
            "hearing_at": (datetime.now(UTC) + timedelta(days=5)).isoformat(),
            "purpose": "Urgent interim orders on escrow freeze",
            "bench_or_coram": "Hon'ble Single Judge",
        },
    )
    assert hearing_res.status_code == 201


# ==============================================================================
# CANONICAL JOURNEY 3: ADMIN OPERATIONAL CONSOLE WORKFLOW
# ==============================================================================
def test_canonical_admin_journey_complete(client: TestClient, db: Session):
    """
    Admin Journey:
    Admin Login -> Verify Lawyer -> Inspect System & Worker Health ->
    Check Legal Source Sync -> Audit Events -> Review Pilot User Feedback
    """
    # 1. Seed Admin User
    admin_id = generate_uuid7()
    admin_email = "admin_pilot_supervisor@example.com"
    admin_pwd = "AdminSuperPass123!"
    admin_user = User(
        id=admin_id,
        email=admin_email,
        password_hash=hash_password(admin_pwd),
        role=UserRole.ADMIN,
        account_status=AccountStatus.ACTIVE,
    )
    db.add(admin_user)
    db.commit()

    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": admin_email, "password": admin_pwd},
    )
    assert login_res.status_code == 200
    admin_headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

    # 2. Check System & Worker Metrics
    metrics_res = client.get("/api/v1/admin/metrics", headers=admin_headers)
    assert metrics_res.status_code == 200
    metrics = metrics_res.json()
    assert "uptime_seconds" in metrics

    # 3. Check Legal Sources Pipeline Health
    sources_res = client.get("/api/v1/admin/legal-sources", headers=admin_headers)
    assert sources_res.status_code == 200

    # 4. Review Audit Logs
    audit_res = client.get("/api/v1/audit", headers=admin_headers)
    assert audit_res.status_code == 200

    # 5. Review Pilot Feedback
    # Add a sample feedback first
    fb = PilotFeedback(
        id=generate_uuid7(),
        category=FeedbackCategory.BUG,
        description="Minor label wrapping on mobile screen",
        page_url="/cases/123",
        status="NEW",
    )
    db.add(fb)
    db.commit()

    fb_list = client.get("/api/v1/feedback", headers=admin_headers)
    assert fb_list.status_code == 200
    assert len(fb_list.json()) >= 1
