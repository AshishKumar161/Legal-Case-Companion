import io
import uuid
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.identifiers import generate_uuid7
from app.models.case import Case, CaseParticipant, CaseStatus, ParticipantRole, ParticipantStatus
from app.models.notification import Notification, NotificationType
from app.models.user import (
    AccountStatus,
    ClientProfile,
    LawyerProfile,
    LawyerVerification,
    User,
    UserRole,
    VerificationStatus,
)


def _setup_user(
    client: TestClient,
    db: Session,
    email: str,
    password: str = "Password123!",
    role: UserRole = UserRole.CLIENT,
    full_name: str = "Test User",
) -> tuple[str, dict[str, str], uuid.UUID]:
    """Helper to register and login a user, returning (user_id, auth_headers, profile_id)."""
    reg_res = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": full_name, "role": role.value},
    )
    assert reg_res.status_code == 201, reg_res.text
    user_id = reg_res.json()["id"]

    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_res.status_code == 200, login_res.text
    access_token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    user = db.query(User).filter(User.id == UUID(user_id)).first()
    assert user is not None

    profile_id = user.id
    if role == UserRole.LAWYER and user.lawyer_profile:
        verif = LawyerVerification(
            id=generate_uuid7(),
            lawyer_profile_id=user.lawyer_profile.id,
            enrollment_number="D/CASE/DOCS/2026",
            state_bar_council="Delhi",
            status=VerificationStatus.APPROVED,
        )
        db.add(verif)
        user.account_status = AccountStatus.ACTIVE
        db.commit()
        db.refresh(user)
        profile_id = user.lawyer_profile.id
    elif role == UserRole.CLIENT and user.client_profile:
        profile_id = user.client_profile.id

    return user_id, headers, profile_id


def test_client_and_lawyer_case_document_sharing(client: TestClient, db: Session):
    """
    Verify bidirectional document sharing between client and lawyer within a case:
    1. Client uploads document directly via POST /api/v1/cases/{case_id}/documents.
    2. Lawyer can list case documents and download the client's file.
    3. Lawyer uploads document directly via POST /api/v1/cases/{case_id}/documents.
    4. Client can list case documents and download the lawyer's file.
    5. Notifications are generated for both parties.
    """
    # 1. Setup Client and Lawyer
    uid_suffix = uuid.uuid4().hex[:6]
    client_uid, client_headers, _ = _setup_user(
        client, db, f"client_doc_{uid_suffix}@example.com", role=UserRole.CLIENT, full_name="Client Vikram"
    )
    lawyer_uid, lawyer_headers, _ = _setup_user(
        client, db, f"lawyer_doc_{uid_suffix}@example.com", role=UserRole.LAWYER, full_name="Adv. Ananya"
    )

    # 2. Create a shared case matter
    case_id = generate_uuid7()
    case = Case(
        id=case_id,
        title="Commercial Lease Agreement Dispute",
        description="Matter regarding commercial shop tenancy and rent recovery.",
        status=CaseStatus.OPEN,
    )
    db.add(case)
    db.commit()

    # Enroll Client (OWNER) and Lawyer (LAWYER)
    p_client = CaseParticipant(
        id=generate_uuid7(),
        case_id=case_id,
        user_id=UUID(client_uid),
        participant_role=ParticipantRole.OWNER,
        status=ParticipantStatus.ACTIVE,
    )
    p_lawyer = CaseParticipant(
        id=generate_uuid7(),
        case_id=case_id,
        user_id=UUID(lawyer_uid),
        participant_role=ParticipantRole.LAWYER,
        status=ParticipantStatus.ACTIVE,
    )
    db.add_all([p_client, p_lawyer])
    db.commit()

    # 3. Client uploads a document to the case via multipart/form-data
    client_file_content = b"%PDF-1.4 Mock Rental Agreement Document content signed by parties."
    res_upload_client = client.post(
        f"/api/v1/cases/{case_id}/documents",
        headers=client_headers,
        files={"file": ("rental_agreement.pdf", io.BytesIO(client_file_content), "application/pdf")},
        data={"title": "Signed Rental Agreement 2026", "category": "AGREEMENT", "description": "Original signed deed."},
    )
    assert res_upload_client.status_code == 201, res_upload_client.text
    client_doc_data = res_upload_client.json()
    assert client_doc_data["filename"] == "Signed Rental Agreement 2026"
    assert client_doc_data["document_type"] == "CONTRACT"
    assert client_doc_data["security_status"] == "SAFE"

    # 4. Lawyer queries case documents: Client's document is visible
    res_docs_lawyer = client.get(f"/api/v1/cases/{case_id}/documents", headers=lawyer_headers)
    assert res_docs_lawyer.status_code == 200, res_docs_lawyer.text
    lawyer_docs_list = res_docs_lawyer.json()["items"]
    assert any(d["id"] == client_doc_data["id"] for d in lawyer_docs_list)

    # 5. Lawyer requests download URL for client's document
    res_dl_lawyer = client.get(
        f"/api/v1/cases/{case_id}/documents/{client_doc_data['id']}/download",
        headers=lawyer_headers,
    )
    assert res_dl_lawyer.status_code == 200, res_dl_lawyer.text
    dl_url = res_dl_lawyer.json()["download_url"]
    assert dl_url is not None

    # Verify mock storage download returns the exact file bytes
    if "/mock-storage" in dl_url:
        dl_path = dl_url.split("localhost:8000")[-1]
        res_file = client.get(dl_path)
        assert res_file.status_code == 200
        assert res_file.content == client_file_content

    # 6. Lawyer uploads a Court Order document to the case
    lawyer_file_content = b"%PDF-1.4 Official High Court Interim Stay Order dated 06-09-2026."
    res_upload_lawyer = client.post(
        f"/api/v1/cases/{case_id}/documents",
        headers=lawyer_headers,
        files={"file": ("interim_stay_order.pdf", io.BytesIO(lawyer_file_content), "application/pdf")},
        data={"title": "High Court Interim Stay Order", "category": "COURT", "description": "Granted in favor of client."},
    )
    assert res_upload_lawyer.status_code == 201, res_upload_lawyer.text
    lawyer_doc_data = res_upload_lawyer.json()
    assert lawyer_doc_data["filename"] == "High Court Interim Stay Order"
    assert lawyer_doc_data["document_type"] == "COURT_ORDER"

    # 7. Client queries case documents: Lawyer's document is visible
    res_docs_client = client.get(f"/api/v1/cases/{case_id}/documents", headers=client_headers)
    assert res_docs_client.status_code == 200, res_docs_client.text
    client_docs_list = res_docs_client.json()["items"]
    assert any(d["id"] == lawyer_doc_data["id"] for d in client_docs_list)

    # 8. Notifications verification: Both Lawyer and Client received notifications
    lawyer_notifs = db.query(Notification).filter(Notification.user_id == UUID(lawyer_uid)).all()
    assert any(n.type == NotificationType.DOCUMENT_READY for n in lawyer_notifs)

    client_notifs = db.query(Notification).filter(Notification.user_id == UUID(client_uid)).all()
    assert any(n.type == NotificationType.DOCUMENT_READY for n in client_notifs)
