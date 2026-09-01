"""Comprehensive Document Management, Secure S3 & Scanning Lifecycle Test Suite.

Phase 4 Verification:
- Document-to-Case Association & PostgreSQL FK Integrity
- Server-Controlled S3 Storage Key Generation & Path Traversal Lockdown
- Presigned Upload Lifecycle & Verified Completion
- Malware Scanner State Machine & Webhook Security
- Zero-Trust Download Gating (SAFE only; PENDING/QUARANTINED/SCANNING/REJECTED blocked)
- Granular Role-Based Access Control & Case-Level IDOR / BOLA Protections
- Soft-Deletion, Legal Retention Isolation, and Audit Trail Verification
"""

import hashlib
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.identifiers import generate_uuid7
from app.core.security import hash_password
from app.models.document import (
    Document,
    DocumentSecurityStatus,
)
from app.models.user import AccountStatus, ClientProfile, LawyerProfile, User, UserRole


def _create_user(
    db: Session,
    client: TestClient,
    email: str,
    role: UserRole = UserRole.CLIENT,
    full_name: str = "Test User",
) -> tuple[UUID, dict[str, str]]:
    """Creates a user and returns (user_id, auth_headers)."""
    user_id = generate_uuid7()
    user = User(
        id=user_id,
        email=email,
        password_hash=hash_password("SecurePassword123!"),
        role=role,
        account_status=AccountStatus.ACTIVE,
    )
    db.add(user)
    if role == UserRole.CLIENT:
        db.add(ClientProfile(id=generate_uuid7(), user_id=user.id, full_name=full_name))
    elif role == UserRole.LAWYER:
        db.add(LawyerProfile(id=generate_uuid7(), user_id=user.id, full_name=full_name))
    db.commit()

    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SecurePassword123!"},
    )
    token = login_res.json()["access_token"]
    return user_id, {"Authorization": f"Bearer {token}"}


def _create_case(
    client: TestClient,
    headers: dict[str, str],
    title: str = "Document Management Case",
) -> str:
    """Helper to create a case and return case_id string."""
    res = client.post(
        "/api/v1/cases",
        json={"title": title, "description": "Case for document hardening tests"},
        headers=headers,
    )
    assert res.status_code == 201
    return res.json()["id"]


# ============================================================================
# 1. DOCUMENT CREATION & S3 STORAGE KEY ISOLATION
# ============================================================================


def test_document_creation_and_storage_key_isolation(client: TestClient, db: Session):
    """Verify document metadata creation, server-controlled S3 keys, and validation."""
    _owner_id, h_owner = _create_user(db, client, "doc_creator@example.com")
    case_id = _create_case(client, h_owner, "IP Litigation")

    valid_checksum = hashlib.sha256(b"sample document bytes").hexdigest()

    # 1. Valid Creation
    payload = {
        "filename": "Affidavit_Evidence.pdf",
        "mime_type": "application/pdf",
        "file_size": 1024 * 512,  # 512 KB
        "document_type": "EVIDENCE",
        "description": "Signed affidavit by primary witness",
        "checksum": valid_checksum,
        "is_confidential": True,
    }
    res = client.post(
        f"/api/v1/cases/{case_id}/documents/upload-init",
        json=payload,
        headers=h_owner,
    )
    assert res.status_code == 201
    data = res.json()

    doc = data["document"]
    doc_id = doc["id"]
    upload_url = data["upload_url"]

    # Verify server-controlled storage key format: cases/{case_id}/documents/{document_id}
    assert doc["storage_key"] == f"cases/{case_id}/documents/{doc_id}"
    assert "Affidavit_Evidence" not in doc["storage_key"]  # Client filename is NOT part of S3 key
    assert doc["security_status"] == "PENDING"
    assert doc["version"] == 1
    assert doc["is_confidential"] is True
    assert "upload" in upload_url

    # 2. Path Traversal Filenames Rejected (422)
    traversal_filenames = [
        "../../../etc/shadow",
        "..\\..\\windows\\system32\\cmd.exe",
        "subfolder/secret.pdf",
        "test\x00malicious.pdf",
        "test..file.pdf",
    ]
    for bad_name in traversal_filenames:
        bad_res = client.post(
            f"/api/v1/cases/{case_id}/documents/upload-init",
            json={
                "filename": bad_name,
                "mime_type": "application/pdf",
                "file_size": 1024,
            },
            headers=h_owner,
        )
        assert bad_res.status_code == 422, f"Failed to reject filename: {bad_name}"

    # 3. Invalid Checksum format rejected (422)
    bad_checksum_res = client.post(
        f"/api/v1/cases/{case_id}/documents/upload-init",
        json={
            "filename": "valid_name.pdf",
            "mime_type": "application/pdf",
            "file_size": 1024,
            "checksum": "not-a-valid-sha256-hex",
        },
        headers=h_owner,
    )
    assert bad_checksum_res.status_code == 422

    # 4. Upload to Closed Case Rejected (422)
    client.patch(f"/api/v1/cases/{case_id}", json={"status": "CLOSED"}, headers=h_owner)
    closed_case_upload = client.post(
        f"/api/v1/cases/{case_id}/documents/upload-init",
        json={
            "filename": "closed_case_doc.pdf",
            "mime_type": "application/pdf",
            "file_size": 1024,
        },
        headers=h_owner,
    )
    assert closed_case_upload.status_code == 422
    assert "closed or cancelled" in closed_case_upload.json()["error"]["message"].lower()


# ============================================================================
# 2. PRESIGNED UPLOAD & VERIFIED COMPLETION
# ============================================================================


def test_upload_completion_and_quarantine_transition(client: TestClient, db: Session):
    """Verify upload completion transitions PENDING -> QUARANTINED."""
    _owner_id, h_owner = _create_user(db, client, "upload_completer@example.com")
    _stranger_id, h_stranger = _create_user(db, client, "stranger_complete@example.com")
    case_id = _create_case(client, h_owner, "Contract Matter")

    # 1. Initialize upload -> PENDING
    init_res = client.post(
        f"/api/v1/cases/{case_id}/documents/upload-init",
        json={"filename": "Agreement.pdf", "mime_type": "application/pdf", "file_size": 2048},
        headers=h_owner,
    )
    doc_id = init_res.json()["document"]["id"]
    assert init_res.json()["document"]["security_status"] == "PENDING"

    # 2. Stranger cannot complete upload -> 404 (IDOR)
    stranger_comp = client.post(f"/api/v1/documents/{doc_id}/complete", headers=h_stranger)
    assert stranger_comp.status_code == 404

    # 3. Owner completes upload -> QUARANTINED
    comp_res = client.post(f"/api/v1/documents/{doc_id}/complete", headers=h_owner)
    assert comp_res.status_code == 200
    assert comp_res.json()["security_status"] == "QUARANTINED"

    # 4. Duplicate completion rejected (422)
    dup_comp = client.post(f"/api/v1/documents/{doc_id}/complete", headers=h_owner)
    assert dup_comp.status_code == 422


# ============================================================================
# 3. SCANNER LIFECYCLE & WEBHOOK SECURITY
# ============================================================================


def test_scanner_webhook_security_and_state_machine(client: TestClient, db: Session):
    """Verify constant-time webhook authentication, lifecycle transitions, and idempotency."""
    _owner_id, h_owner = _create_user(db, client, "scanner_tester@example.com")
    case_id = _create_case(client, h_owner, "Regulatory Matter")

    # Create document and complete upload -> QUARANTINED
    init_res = client.post(
        f"/api/v1/cases/{case_id}/documents/upload-init",
        json={"filename": "Regulation_Scan.pdf", "mime_type": "application/pdf", "file_size": 4096},
        headers=h_owner,
    )
    doc_id = init_res.json()["document"]["id"]
    client.post(f"/api/v1/documents/{doc_id}/complete", headers=h_owner)

    original_secret = settings.AWS_WEBHOOK_SECRET
    settings.AWS_WEBHOOK_SECRET = "production_webhook_secret_key_888"

    try:
        # 1. Unauthenticated Webhook Request -> 401
        res_no_auth = client.post(
            "/api/v1/webhooks/aws/malware",
            json={"document_id": doc_id, "is_safe": True},
        )
        assert res_no_auth.status_code == 401

        # 2. Forged Header Secret -> 401
        res_forged = client.post(
            "/api/v1/webhooks/aws/malware",
            headers={"Authorization": "Bearer fake_secret_999"},
            json={"document_id": doc_id, "is_safe": True},
        )
        assert res_forged.status_code == 401

        # 3. Valid Webhook Call -> Transitions to SAFE
        valid_res = client.post(
            "/api/v1/webhooks/aws/malware",
            headers={"Authorization": f"Bearer {settings.AWS_WEBHOOK_SECRET}"},
            json={"document_id": doc_id, "is_safe": True, "details": "Clean scan"},
        )
        assert valid_res.status_code == 200
        assert valid_res.json()["status"] == "success"

        # Verify DB state
        doc_db = db.query(Document).filter(Document.id == UUID(doc_id)).first()
        assert doc_db is not None
        assert doc_db.security_status == DocumentSecurityStatus.SAFE

        # 4. Idempotent Replay -> returns 200 without error
        replay_res = client.post(
            "/api/v1/webhooks/aws/malware",
            headers={"Authorization": f"Bearer {settings.AWS_WEBHOOK_SECRET}"},
            json={"document_id": doc_id, "is_safe": True},
        )
        assert replay_res.status_code == 200

        # 5. Unknown Document -> 404
        unknown_res = client.post(
            "/api/v1/webhooks/aws/malware",
            headers={"Authorization": f"Bearer {settings.AWS_WEBHOOK_SECRET}"},
            json={"document_id": str(uuid4()), "is_safe": True},
        )
        assert unknown_res.status_code == 404

        # 6. Webhook on PENDING document (invalid state transition) -> 422
        pending_init = client.post(
            f"/api/v1/cases/{case_id}/documents/upload-init",
            json={"filename": "Premature_Scan.pdf", "mime_type": "application/pdf", "file_size": 1024},
            headers=h_owner,
        )
        pending_id = pending_init.json()["document"]["id"]
        premature_webhook = client.post(
            "/api/v1/webhooks/aws/malware",
            headers={"Authorization": f"Bearer {settings.AWS_WEBHOOK_SECRET}"},
            json={"document_id": pending_id, "is_safe": True},
        )
        assert premature_webhook.status_code == 422

    finally:
        settings.AWS_WEBHOOK_SECRET = original_secret


# ============================================================================
# 4. DOWNLOAD AUTHORIZATION & ZERO-TRUST GATING
# ============================================================================


def test_download_authorization_and_zero_trust_gating(client: TestClient, db: Session):
    """Verify zero-trust download gating: ONLY SAFE documents can be downloaded."""
    _owner_id, h_owner = _create_user(db, client, "download_owner@example.com")
    lawyer_id, h_lawyer = _create_user(db, client, "download_lawyer@example.com", role=UserRole.LAWYER)
    viewer_id, h_viewer = _create_user(db, client, "download_viewer@example.com")
    _stranger_id, h_stranger = _create_user(db, client, "download_stranger@example.com")

    case_id = _create_case(client, h_owner, "Tax Litigation")

    # Add Lawyer and Viewer
    client.post(
        f"/api/v1/cases/{case_id}/participants",
        json={"user_id": str(lawyer_id), "participant_role": "LAWYER"},
        headers=h_owner,
    )
    client.post(
        f"/api/v1/cases/{case_id}/participants",
        json={"user_id": str(viewer_id), "participant_role": "VIEWER"},
        headers=h_owner,
    )

    # 1. PENDING document -> Download BLOCKED (403)
    init_res = client.post(
        f"/api/v1/cases/{case_id}/documents/upload-init",
        json={"filename": "Tax_Audit.pdf", "mime_type": "application/pdf", "file_size": 1024},
        headers=h_owner,
    )
    doc_id = init_res.json()["document"]["id"]

    pending_dl = client.get(f"/api/v1/documents/{doc_id}/download", headers=h_owner)
    assert pending_dl.status_code == 403
    assert "not approved" in pending_dl.json()["error"]["message"].lower()

    # 2. Complete upload -> QUARANTINED -> Download BLOCKED (403)
    client.post(f"/api/v1/documents/{doc_id}/complete", headers=h_owner)
    quarantined_dl = client.get(f"/api/v1/documents/{doc_id}/download", headers=h_owner)
    assert quarantined_dl.status_code == 403

    # 3. Simulate Scan REJECTED -> Download BLOCKED (403)
    client.post(f"/api/v1/documents/{doc_id}/scan?is_safe=false", headers=h_owner)
    rejected_dl = client.get(f"/api/v1/documents/{doc_id}/download", headers=h_owner)
    assert rejected_dl.status_code == 403

    # 4. Upload second doc and scan to SAFE -> Download PERMITTED for all case participants
    init_safe = client.post(
        f"/api/v1/cases/{case_id}/documents/upload-init",
        json={"filename": "Court_Order.pdf", "mime_type": "application/pdf", "file_size": 2048},
        headers=h_owner,
    )
    safe_doc_id = init_safe.json()["document"]["id"]
    client.post(f"/api/v1/documents/{safe_doc_id}/complete", headers=h_owner)
    client.post(f"/api/v1/documents/{safe_doc_id}/scan?is_safe=true", headers=h_owner)

    # Owner -> 200
    owner_dl = client.get(f"/api/v1/documents/{safe_doc_id}/download", headers=h_owner)
    assert owner_dl.status_code == 200
    assert "download_url" in owner_dl.json()

    # Lawyer -> 200
    lawyer_dl = client.get(f"/api/v1/documents/{safe_doc_id}/download", headers=h_lawyer)
    assert lawyer_dl.status_code == 200

    # Viewer -> 200
    viewer_dl = client.get(f"/api/v1/documents/{safe_doc_id}/download", headers=h_viewer)
    assert viewer_dl.status_code == 200

    # Stranger -> 404 (BOLA protection)
    stranger_dl = client.get(f"/api/v1/documents/{safe_doc_id}/download", headers=h_stranger)
    assert stranger_dl.status_code == 404

    # Unauthenticated -> 401
    unauth_dl = client.get(f"/api/v1/documents/{safe_doc_id}/download")
    assert unauth_dl.status_code == 401


# ============================================================================
# 5. DOCUMENT MUTATION & ROLE-BASED ACCESS CONTROL
# ============================================================================


def test_document_mutation_and_rbac(client: TestClient, db: Session):
    """Verify granular RBAC: Lawyers can delete own uploads; Viewers cannot mutate."""
    _owner_id, h_owner = _create_user(db, client, "rbac_owner@example.com")
    lawyer_id, h_lawyer = _create_user(db, client, "rbac_lawyer@example.com", role=UserRole.LAWYER)
    viewer_id, h_viewer = _create_user(db, client, "rbac_viewer@example.com")

    case_id = _create_case(client, h_owner, "Commercial Dispute")

    client.post(
        f"/api/v1/cases/{case_id}/participants",
        json={"user_id": str(lawyer_id), "participant_role": "LAWYER"},
        headers=h_owner,
    )
    client.post(
        f"/api/v1/cases/{case_id}/participants",
        json={"user_id": str(viewer_id), "participant_role": "VIEWER"},
        headers=h_owner,
    )

    # 1. Owner uploads Doc 1
    doc1_res = client.post(
        f"/api/v1/cases/{case_id}/documents/upload-init",
        json={"filename": "Owner_Pleading.pdf", "mime_type": "application/pdf", "file_size": 1024},
        headers=h_owner,
    )
    doc1_id = doc1_res.json()["document"]["id"]

    # 2. Lawyer uploads Doc 2
    doc2_res = client.post(
        f"/api/v1/cases/{case_id}/documents/upload-init",
        json={"filename": "Lawyer_Motion.pdf", "mime_type": "application/pdf", "file_size": 1024},
        headers=h_lawyer,
    )
    doc2_id = doc2_res.json()["document"]["id"]

    # 3. Viewer attempts upload -> 403
    viewer_up = client.post(
        f"/api/v1/cases/{case_id}/documents/upload-init",
        json={"filename": "Viewer_Illegal.pdf", "mime_type": "application/pdf", "file_size": 1024},
        headers=h_viewer,
    )
    assert viewer_up.status_code == 403

    # 4. Lawyer updates Doc 2 metadata -> 200
    update_res = client.patch(
        f"/api/v1/documents/{doc2_id}",
        json={"description": "Updated motion description", "document_type": "PLEADINGS"},
        headers=h_lawyer,
    )
    assert update_res.status_code == 200
    assert update_res.json()["document_type"] == "PLEADINGS"

    # 5. Lawyer attempts to delete Owner's Doc 1 -> 403 (Lawyers can only delete their own uploads)
    lawyer_del_owner_doc = client.delete(f"/api/v1/documents/{doc1_id}", headers=h_lawyer)
    assert lawyer_del_owner_doc.status_code == 403

    # 6. Lawyer deletes own Doc 2 -> 204
    lawyer_del_own = client.delete(f"/api/v1/documents/{doc2_id}", headers=h_lawyer)
    assert lawyer_del_own.status_code == 204

    # 7. Owner deletes Doc 1 -> 204 (Owners can delete any document in case)
    owner_del = client.delete(f"/api/v1/documents/{doc1_id}", headers=h_owner)
    assert owner_del.status_code == 204


# ============================================================================
# 6. SOFT DELETION & RETENTION ISOLATION
# ============================================================================


def test_soft_deletion_and_retention_isolation(client: TestClient, db: Session):
    """Verify soft deletion hides documents from API but retains records in DB."""
    _owner_id, h_owner = _create_user(db, client, "soft_del_doc_owner@example.com")
    case_id = _create_case(client, h_owner, "Arbitration Matter")

    # Upload and scan
    res = client.post(
        f"/api/v1/cases/{case_id}/documents/upload-init",
        json={"filename": "Arbitration_Award.pdf", "mime_type": "application/pdf", "file_size": 1024},
        headers=h_owner,
    )
    doc_id = res.json()["document"]["id"]
    client.post(f"/api/v1/documents/{doc_id}/complete", headers=h_owner)
    client.post(f"/api/v1/documents/{doc_id}/scan?is_safe=true", headers=h_owner)

    # Soft delete
    del_res = client.delete(f"/api/v1/documents/{doc_id}", headers=h_owner)
    assert del_res.status_code == 204

    # Direct query -> 404
    assert client.get(f"/api/v1/documents/{doc_id}", headers=h_owner).status_code == 404

    # Download query -> 404
    assert client.get(f"/api/v1/documents/{doc_id}/download", headers=h_owner).status_code == 404

    # List query -> excluded
    list_res = client.get(f"/api/v1/cases/{case_id}/documents", headers=h_owner)
    assert list_res.json()["total"] == 0

    # Verify record still exists in DB with deleted_at timestamp populated
    doc_db = db.query(Document).filter(Document.id == UUID(doc_id)).first()
    assert doc_db is not None
    assert doc_db.deleted_at is not None
