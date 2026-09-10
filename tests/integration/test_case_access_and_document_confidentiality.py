import uuid
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.document import Document, DocumentSecurityStatus
from app.models.user import (
    LawyerProfile,
    LawyerVerification,
    VerificationStatus,
)


def _setup_user(
    client: TestClient,
    email: str,
    password: str = "SecurePass123!",
    role: str = "CLIENT",
    full_name: str = "Test User",
):
    res_reg = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "role": role,
            "full_name": full_name,
        },
    )
    user_id = res_reg.json().get("id")
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    token = res.json()["access_token"]
    return user_id, {"Authorization": f"Bearer {token}"}


def _verify_lawyer(db: Session, lawyer_user_id: str):
    profile = (
        db.query(LawyerProfile)
        .filter(LawyerProfile.user_id == UUID(lawyer_user_id))
        .first()
    )
    assert profile is not None
    ver = LawyerVerification(
        lawyer_profile_id=profile.id,
        enrollment_number=f"BAR/{str(lawyer_user_id)[:6]}/2020",
        state_bar_council="Delhi",
        status=VerificationStatus.APPROVED,
    )
    db.add(ver)
    db.commit()
    db.refresh(profile)
    return profile


def test_grant_lawyer_access_full_lifecycle_and_safeguards(
    client: TestClient, db: Session
):
    # Setup users
    _owner_id, h_owner = _setup_user(client, "grant_owner@test.com", role="CLIENT")
    lawyer_id, h_lawyer = _setup_user(
        client, "grant_lawyer@test.com", role="LAWYER", full_name="Adv. Sharma"
    )
    unverif_lawyer_id, _h_unverif = _setup_user(
        client, "grant_unverif@test.com", role="LAWYER"
    )
    _other_client_id, h_other = _setup_user(
        client, "grant_other@test.com", role="CLIENT"
    )

    # 1. Create Case
    res_case = client.post(
        "/api/v1/cases",
        json={"title": "Land Dispute", "description": "Ancestral property matter"},
        headers=h_owner,
    )
    assert res_case.status_code == 201
    case_id = res_case.json()["id"]

    # 2. Attempt grant without verification or consultation -> 422
    res_grant_fail = client.post(
        f"/api/v1/cases/{case_id}/grant-lawyer-access",
        json={"lawyer_user_id": unverif_lawyer_id},
        headers=h_owner,
    )
    assert res_grant_fail.status_code == 422
    assert "verified" in res_grant_fail.json()["error"]["message"]

    # Verify lawyer
    lawyer_profile = _verify_lawyer(db, lawyer_id)

    # 3. Attempt grant without consultation -> 422
    res_no_consult = client.post(
        f"/api/v1/cases/{case_id}/grant-lawyer-access",
        json={"lawyer_user_id": lawyer_id},
        headers=h_owner,
    )
    assert res_no_consult.status_code == 422
    assert "consultation" in res_no_consult.json()["error"]["message"]

    # 4. Request and accept consultation
    # Scheduled for next day 10:00 UTC (15:30 IST)
    future_time = (datetime.now(UTC) + timedelta(days=1)).replace(
        hour=10, minute=0, second=0, microsecond=0
    )
    res_req = client.post(
        "/api/v1/consultations",
        json={
            "lawyer_id": str(lawyer_profile.id),
            "scheduled_at": future_time.isoformat(),
            "duration_minutes": 30,
            "case_id": case_id,
        },
        headers=h_owner,
    )
    assert res_req.status_code == 201
    consult_id = res_req.json()["id"]

    # Lawyer accepts consultation
    res_accept = client.post(
        f"/api/v1/consultations/{consult_id}/accept", headers=h_lawyer
    )
    assert res_accept.status_code == 200

    # 5. Non-owner cannot grant lawyer access -> 404 (BOLA protection)
    res_other_grant = client.post(
        f"/api/v1/cases/{case_id}/grant-lawyer-access",
        json={"lawyer_user_id": lawyer_id},
        headers=h_other,
    )
    assert res_other_grant.status_code == 404

    # 6. Owner grants lawyer access -> 201
    res_grant = client.post(
        f"/api/v1/cases/{case_id}/grant-lawyer-access",
        json={"lawyer_user_id": lawyer_id, "consultation_id": consult_id},
        headers=h_owner,
    )
    assert res_grant.status_code == 201
    grant_data = res_grant.json()
    assert grant_data["participant_role"] == "LAWYER"
    assert grant_data["status"] == "ACTIVE"
    assert grant_data["user_id"] == lawyer_id

    # 7. Duplicate grant attempt -> 422
    res_dup = client.post(
        f"/api/v1/cases/{case_id}/grant-lawyer-access",
        json={"lawyer_user_id": lawyer_id},
        headers=h_owner,
    )
    assert res_dup.status_code == 422
    assert "already an active participant" in res_dup.json()["error"]["message"]

    # 8. Verify lawyer can access case workspace
    res_ws = client.get(f"/api/v1/cases/{case_id}/workspace", headers=h_lawyer)
    assert res_ws.status_code == 200
    assert res_ws.json()["case"]["id"] == case_id
    assert res_ws.json()["lawyer"]["id"] == str(lawyer_profile.id)


def test_document_confidentiality_and_granular_authorization(
    client: TestClient, db: Session
):
    _owner_id, h_owner = _setup_user(client, "doc_owner@test.com", role="CLIENT")
    lawyer_id, h_lawyer = _setup_user(
        client, "doc_lawyer@test.com", role="LAWYER", full_name="Adv. Verma"
    )
    _unassigned_lawyer_id, h_unassigned = _setup_user(
        client, "doc_unassigned@test.com", role="LAWYER"
    )
    viewer_id, h_viewer = _setup_user(client, "doc_viewer@test.com", role="CLIENT")

    # Create Case
    res_case = client.post(
        "/api/v1/cases",
        json={"title": "Contract Review", "description": "Commercial agreement breach"},
        headers=h_owner,
    )
    case_id = res_case.json()["id"]

    # Add lawyer and viewer as participants
    client.post(
        f"/api/v1/cases/{case_id}/participants",
        json={"user_id": lawyer_id, "participant_role": "LAWYER"},
        headers=h_owner,
    )
    client.post(
        f"/api/v1/cases/{case_id}/participants",
        json={"user_id": viewer_id, "participant_role": "VIEWER"},
        headers=h_owner,
    )

    # 1. Owner uploads Document A
    res_up_a = client.post(
        f"/api/v1/cases/{case_id}/documents/upload-init",
        json={
            "filename": "Agreement.pdf",
            "mime_type": "application/pdf",
            "file_size": 2048,
        },
        headers=h_owner,
    )
    assert res_up_a.status_code == 201
    doc_a_id = res_up_a.json()["document"]["id"]

    # 2. Assigned Lawyer uploads Document B
    res_up_b = client.post(
        f"/api/v1/cases/{case_id}/documents/upload-init",
        json={
            "filename": "Legal_Opinion.pdf",
            "mime_type": "application/pdf",
            "file_size": 4096,
        },
        headers=h_lawyer,
    )
    assert res_up_b.status_code == 201
    doc_b_id = res_up_b.json()["document"]["id"]

    # 3. Viewer attempts to upload document -> 403 Forbidden
    res_up_v = client.post(
        f"/api/v1/cases/{case_id}/documents/upload-init",
        json={
            "filename": "Malicious.pdf",
            "mime_type": "application/pdf",
            "file_size": 1024,
        },
        headers=h_viewer,
    )
    assert res_up_v.status_code == 403

    # 4. Unassigned lawyer attempts to upload document -> 404 (Obscured)
    res_up_un = client.post(
        f"/api/v1/cases/{case_id}/documents/upload-init",
        json={
            "filename": "Spy.pdf",
            "mime_type": "application/pdf",
            "file_size": 1024,
        },
        headers=h_unassigned,
    )
    assert res_up_un.status_code == 404

    # 5. Download permission: Pending document download must be rejected
    res_dl_pending = client.get(
        f"/api/v1/documents/{doc_a_id}/download", headers=h_owner
    )
    assert res_dl_pending.status_code == 403  # Not approved/SAFE yet

    # Mark Doc A and Doc B as SAFE directly in DB (simulating scan completion)
    doc_a = db.query(Document).filter(Document.id == UUID(doc_a_id)).first()
    assert doc_a is not None
    doc_a.security_status = DocumentSecurityStatus.SAFE

    doc_b = db.query(Document).filter(Document.id == UUID(doc_b_id)).first()
    assert doc_b is not None
    doc_b.security_status = DocumentSecurityStatus.SAFE
    db.commit()

    # 6. Authorized participants can download SAFE documents
    res_dl_owner = client.get(f"/api/v1/documents/{doc_a_id}/download", headers=h_owner)
    assert res_dl_owner.status_code == 200
    assert "download_url" in res_dl_owner.json()

    res_dl_lawyer = client.get(
        f"/api/v1/documents/{doc_a_id}/download", headers=h_lawyer
    )
    assert res_dl_lawyer.status_code == 200
    assert "download_url" in res_dl_lawyer.json()

    res_dl_viewer = client.get(
        f"/api/v1/documents/{doc_a_id}/download", headers=h_viewer
    )
    assert res_dl_viewer.status_code == 200

    # 7. Unassigned lawyer / random UUID IDOR check -> 404
    res_dl_unassigned = client.get(
        f"/api/v1/documents/{doc_a_id}/download", headers=h_unassigned
    )
    assert res_dl_unassigned.status_code == 404

    res_dl_random = client.get(
        f"/api/v1/documents/{uuid.uuid4()}/download", headers=h_lawyer
    )
    assert res_dl_random.status_code == 404

    # 8. Deletion Authorization:
    # Viewer tries to delete Doc A -> 403
    res_del_v = client.delete(f"/api/v1/documents/{doc_a_id}", headers=h_viewer)
    assert res_del_v.status_code == 403

    # Lawyer tries to delete Owner's Doc A -> 403
    res_del_l_a = client.delete(f"/api/v1/documents/{doc_a_id}", headers=h_lawyer)
    assert res_del_l_a.status_code == 403
    assert "uploaded themselves" in res_del_l_a.json()["error"]["message"]

    # Lawyer deletes their OWN Doc B -> 204
    res_del_l_b = client.delete(f"/api/v1/documents/{doc_b_id}", headers=h_lawyer)
    assert res_del_l_b.status_code == 204

    # Owner deletes Doc A -> 204
    res_del_o_a = client.delete(f"/api/v1/documents/{doc_a_id}", headers=h_owner)
    assert res_del_o_a.status_code == 204


def test_revocation_and_immediate_document_access_cutoff(
    client: TestClient, db: Session
):
    _owner_id, h_owner = _setup_user(client, "rev_owner@test.com", role="CLIENT")
    lawyer_id, h_lawyer = _setup_user(
        client, "rev_lawyer@test.com", role="LAWYER", full_name="Adv. Gupta"
    )

    # 1. Create Case
    res_case = client.post(
        "/api/v1/cases",
        json={"title": "Corporate Compliance", "description": "Statutory audit defense"},
        headers=h_owner,
    )
    case_id = res_case.json()["id"]

    # 2. Add lawyer as participant
    client.post(
        f"/api/v1/cases/{case_id}/participants",
        json={"user_id": lawyer_id, "participant_role": "LAWYER"},
        headers=h_owner,
    )

    # 3. Upload Doc
    res_up = client.post(
        f"/api/v1/cases/{case_id}/documents/upload-init",
        json={
            "filename": "Audit_Report.pdf",
            "mime_type": "application/pdf",
            "file_size": 3000,
        },
        headers=h_owner,
    )
    doc_id = res_up.json()["document"]["id"]

    doc = db.query(Document).filter(Document.id == UUID(doc_id)).first()
    assert doc is not None
    doc.security_status = DocumentSecurityStatus.SAFE
    db.commit()

    # 4. Lawyer currently has access
    res_doc_get = client.get(f"/api/v1/documents/{doc_id}", headers=h_lawyer)
    assert res_doc_get.status_code == 200
    res_doc_dl = client.get(f"/api/v1/documents/{doc_id}/download", headers=h_lawyer)
    assert res_doc_dl.status_code == 200

    # 5. Owner removes / revokes lawyer participation
    res_rem = client.delete(
        f"/api/v1/cases/{case_id}/participants/{lawyer_id}", headers=h_owner
    )
    assert res_rem.status_code == 204

    # 6. Immediate Cutoff Verification:
    # Lawyer immediately receives 404 on case, workspace, document, and download endpoints
    assert client.get(f"/api/v1/cases/{case_id}", headers=h_lawyer).status_code == 404
    assert (
        client.get(f"/api/v1/cases/{case_id}/workspace", headers=h_lawyer).status_code
        == 404
    )
    assert (
        client.get(f"/api/v1/cases/{case_id}/documents", headers=h_lawyer).status_code
        == 404
    )
    assert client.get(f"/api/v1/documents/{doc_id}", headers=h_lawyer).status_code == 404
    assert (
        client.get(f"/api/v1/documents/{doc_id}/download", headers=h_lawyer).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/v1/cases/{case_id}/documents/upload-init",
            json={
                "filename": "Revoked.pdf",
                "mime_type": "application/pdf",
                "file_size": 1000,
            },
            headers=h_lawyer,
        ).status_code
        == 404
    )
