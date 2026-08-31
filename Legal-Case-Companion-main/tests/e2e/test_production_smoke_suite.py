from datetime import UTC, datetime, timedelta
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.identifiers import generate_uuid7
from app.core.security import hash_password
from app.models.case import Case, CaseParticipant, ParticipantRole
from app.models.document import Document, DocumentCategory, DocumentProcessingStatus, DocumentSecurityStatus
from app.models.user import AccountStatus, User, UserRole


def _create_and_auth(client: TestClient, email: str, role: str, name: str) -> tuple[str, dict]:
    res = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "SmokeTestPass123!", "role": role, "full_name": name},
    )
    user_id = res.json()["id"]
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SmokeTestPass123!"},
    )
    token = login.json()["access_token"]
    return user_id, {"Authorization": f"Bearer {token}"}


def test_production_deployment_smoke_suite(client: TestClient, db: Session):
    """
    Comprehensive Deployment Smoke Test Suite:
    1. Root Liveness & Readiness Probes
    2. User Authentication & Token Generation
    3. Case Creation & Participant Onboarding
    4. Document Upload Initiation & Security Bounds
    5. Case Intelligence & Copilot 2.0 Query
    6. Case Task Obligation & Next Action
    7. Matter Collaboration & Structured Requests
    8. Lawyer Availability & Consultation Booking
    9. Notification Delivery Check
    10. Admin Operational Metrics & Job Queue Verification
    """
    # 1. Root Health & Readiness Probes
    live_res = client.get("/api/v1/health/live")
    assert live_res.status_code == 200
    assert live_res.json()["status"] == "alive"

    ready_res = client.get("/api/v1/health/ready")
    assert ready_res.status_code == 200
    assert ready_res.json()["status"] == "ready"

    # 2. Authentication Flow
    client_id, client_auth = _create_and_auth(
        client, "smoke_client_1@example.com", "CLIENT", "Vikram Rathore"
    )
    lawyer_id, lawyer_auth = _create_and_auth(
        client, "smoke_lawyer_1@example.com", "LAWYER", "Adv. Sunita Rao"
    )

    # 3. Case Creation & Participant Assignment
    case_res = client.post(
        "/api/v1/cases",
        headers=client_auth,
        json={
            "title": "Rathore Infrastructure v. State Logistics Corp",
            "description": "Commercial contract dispute regarding delay liquidated damages.",
        },
    )
    assert case_res.status_code == 201
    case_id = case_res.json()["id"]

    part_res = client.post(
        f"/api/v1/cases/{case_id}/participants",
        headers=client_auth,
        json={"user_id": lawyer_id, "participant_role": "LAWYER"},
    )
    assert part_res.status_code == 200

    # 4. Document Upload Initiation & Ingestion
    doc = Document(
        id=generate_uuid7(),
        case_id=uuid.UUID(case_id),
        uploaded_by=uuid.UUID(client_id),
        filename="epc_contract_agreement.pdf",
        storage_key=f"cases/{case_id}/epc_contract_agreement.pdf",
        mime_type="application/pdf",
        file_size=320000,
        document_type=DocumentCategory.CONTRACT,
        security_status=DocumentSecurityStatus.SAFE,
        processing_status=DocumentProcessingStatus.READY,
    )
    db.add(doc)
    db.commit()

    docs_res = client.get(f"/api/v1/cases/{case_id}/documents", headers=client_auth)
    assert docs_res.status_code == 200
    assert docs_res.json()["total"] >= 1

    # 5. Case Intelligence & Copilot Query
    conv_res = client.post(
        f"/api/v1/cases/{case_id}/ai/conversations",
        headers=client_auth,
        json={"title": "Smoke Copilot Session"},
    )
    assert conv_res.status_code == 201
    conv_id = conv_res.json()["id"]

    chat_res = client.post(
        f"/api/v1/cases/{case_id}/ai/conversations/{conv_id}/messages",
        headers=client_auth,
        json={"query": "What are the statutory grounds under Indian Contract Act regarding liquidated damages?"},
    )
    assert chat_res.status_code == 200
    assert "content" in chat_res.json()

    # 6. Task Obligation & Next Action
    task_res = client.post(
        f"/api/v1/cases/{case_id}/tasks",
        headers=lawyer_auth,
        json={
            "title": "Review EPC clause 42 notice requirements",
            "priority": "HIGH",
            "due_date": (datetime.now(UTC) + timedelta(days=3)).isoformat(),
        },
    )
    assert task_res.status_code == 201

    # 7. Matter Collaboration & Structured Requests
    req_res = client.post(
        f"/api/v1/cases/{case_id}/collaboration/requests",
        headers=lawyer_auth,
        json={
            "title": "Provide Completion Certificate",
            "description": "Required for damages defense rebuttal",
            "request_type": "DOCUMENT_UPLOAD",
            "assigned_user_id": client_id,
        },
    )
    assert req_res.status_code == 201
    request_id = req_res.json()["id"]

    sub_res = client.post(
        f"/api/v1/cases/{case_id}/collaboration/requests/{request_id}/submit",
        headers=client_auth,
        json={"response_notes": "Certificate attached to documents tab."},
    )
    assert sub_res.status_code == 200
    assert sub_res.json()["status"] == "SUBMITTED"

    # 8. Lawyer Availability & Consultation Booking
    avail_res = client.post(
        "/api/v1/profiles/lawyer/availability",
        headers=lawyer_auth,
        json={
            "day_of_week": 2,  # Tuesday
            "start_time": "10:00:00",
            "end_time": "18:00:00",
            "slot_duration_minutes": 30,
            "is_active": True,
        },
    )
    assert avail_res.status_code in (200, 201)

    # 9. Notification Delivery Check
    notif_res = client.get("/api/v1/notifications", headers=client_auth)
    assert notif_res.status_code == 200
    assert "items" in notif_res.json()

    # 10. Admin Operational Metrics & Job Queue Verification
    admin_id = generate_uuid7()
    admin_user = User(
        id=admin_id,
        email="smoke_admin_ops@example.com",
        password_hash=hash_password("SmokeAdminPass123!"),
        role=UserRole.ADMIN,
        account_status=AccountStatus.ACTIVE,
    )
    db.add(admin_user)
    db.commit()

    admin_login = client.post(
        "/api/v1/auth/login",
        json={"email": "smoke_admin_ops@example.com", "password": "SmokeAdminPass123!"},
    )
    admin_auth = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

    metrics_res = client.get("/api/v1/admin/metrics", headers=admin_auth)
    assert metrics_res.status_code == 200
    assert "uptime_seconds" in metrics_res.json()

    jobs_res = client.get("/api/v1/admin/jobs/stats", headers=admin_auth)
    assert jobs_res.status_code == 200
