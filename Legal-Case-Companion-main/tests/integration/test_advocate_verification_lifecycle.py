import io
import uuid
from datetime import UTC, datetime

import pytest

from app.core.identifiers import generate_uuid7
from app.core.security import create_access_token
from app.models.user import (
    AccountStatus,
    AdvocateDocumentType,
    DocumentScanStatus,
    DocumentVerificationStatus,
    LawyerProfile,
    User,
    UserRole,
    VerificationReviewEvent,
    VerificationStatus,
)


@pytest.fixture
def advocate_user(db):
    user = User(
        id=generate_uuid7(),
        email=f"advocate_{uuid.uuid4().hex[:6]}@example.com",
        role=UserRole.LAWYER,
        account_status=AccountStatus.REGISTERED,
    )
    db.add(user)
    db.flush()

    profile = LawyerProfile(
        id=generate_uuid7(),
        user_id=user.id,
        full_name="Adv. Vikramaditya Sen",
        experience_years=8,
        location="New Delhi",
    )
    db.add(profile)
    db.commit()
    db.refresh(user)
    db.refresh(profile)
    return user, profile


@pytest.fixture
def admin_user(db):
    user = User(
        id=generate_uuid7(),
        email=f"admin_{uuid.uuid4().hex[:6]}@example.com",
        role=UserRole.ADMIN,
        account_status=AccountStatus.ACTIVE,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def client_user(db):
    user = User(
        id=generate_uuid7(),
        email=f"client_{uuid.uuid4().hex[:6]}@example.com",
        role=UserRole.CLIENT,
        account_status=AccountStatus.ACTIVE,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def auth_header(user: User):
    token = create_access_token(subject=str(user.id), role=user.role.value)
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# 1. Document Upload & Magic Bytes Integrity Tests
# ---------------------------------------------------------------------------


def test_upload_document_valid_magic_bytes(client, db, advocate_user):
    user, profile = advocate_user
    headers = auth_header(user)

    # Legitimate PDF header (%PDF-1.4 ...)
    valid_pdf_bytes = b"%PDF-1.4\n%test legitimate bar council certificate bytes content\n%%EOF"
    file_payload = {
        "file": ("bar_council_cert.pdf", io.BytesIO(valid_pdf_bytes), "application/pdf"),
    }
    data = {
        "document_type": AdvocateDocumentType.BAR_COUNCIL_ENROLLMENT_CERT.value,
    }

    res = client.post(
        "/api/v1/verification/application/documents",
        headers=headers,
        data=data,
        files=file_payload,
    )
    assert res.status_code == 201
    doc_data = res.json()
    assert doc_data["document_type"] == AdvocateDocumentType.BAR_COUNCIL_ENROLLMENT_CERT.value
    assert doc_data["scan_status"] == DocumentScanStatus.PASSED.value
    assert doc_data["verification_status"] == DocumentVerificationStatus.SUBMITTED.value
    assert len(doc_data["sha256_hash"]) == 64


def test_upload_document_invalid_magic_bytes_rejected(client, db, advocate_user):
    user, profile = advocate_user
    headers = auth_header(user)

    # Spoofed file: .pdf extension with plain text content
    fake_pdf_bytes = b"Hello world, I am not a real PDF document!"
    file_payload = {
        "file": ("malicious.pdf", io.BytesIO(fake_pdf_bytes), "application/pdf"),
    }
    data = {
        "document_type": AdvocateDocumentType.BAR_COUNCIL_ENROLLMENT_CERT.value,
    }

    res = client.post(
        "/api/v1/verification/application/documents",
        headers=headers,
        data=data,
        files=file_payload,
    )
    assert res.status_code == 422
    assert "signature does not match" in res.text or "spoofing" in res.text


# ---------------------------------------------------------------------------
# 2. Application Submission & Missing Document Enforcement
# ---------------------------------------------------------------------------


def test_submit_application_without_enrollment_doc_fails(client, db, advocate_user):
    user, profile = advocate_user
    headers = auth_header(user)

    payload = {
        "enrollment_number": "D/1842/2016",
        "state_bar_council": "Bar Council of Delhi",
        "declared_practice_jurisdictions": ["High Court of Delhi"],
    }
    res = client.post(
        "/api/v1/verification/application/submit",
        headers=headers,
        json=payload,
    )
    assert res.status_code == 422
    assert "Mandatory professional credential missing" in res.text


def test_submit_application_invalid_enrollment_format_fails(client, db, advocate_user):
    user, profile = advocate_user
    headers = auth_header(user)

    # First upload enrollment doc
    valid_pdf_bytes = b"%PDF-1.4\n%test legitimate bar council certificate bytes content\n%%EOF"
    upload_res = client.post(
        "/api/v1/verification/application/documents",
        headers=headers,
        data={"document_type": AdvocateDocumentType.BAR_COUNCIL_ENROLLMENT_CERT.value},
        files={"file": ("cert.pdf", io.BytesIO(valid_pdf_bytes), "application/pdf")},
    )
    assert upload_res.status_code == 201

    # Invalid enrollment format without slash
    payload = {
        "enrollment_number": "INVALID12345",
        "state_bar_council": "Bar Council of Delhi",
    }
    res = client.post(
        "/api/v1/verification/application/submit",
        headers=headers,
        json=payload,
    )
    assert res.status_code == 422
    assert "Invalid Bar Council enrollment number format" in res.text


def test_successful_application_submission(client, db, advocate_user):
    user, profile = advocate_user
    headers = auth_header(user)

    # Upload enrollment doc
    valid_pdf_bytes = b"%PDF-1.4\n%enrollment certificate\n%%EOF"
    upload_res = client.post(
        "/api/v1/verification/application/documents",
        headers=headers,
        data={"document_type": AdvocateDocumentType.BAR_COUNCIL_ENROLLMENT_CERT.value},
        files={"file": ("cert.pdf", io.BytesIO(valid_pdf_bytes), "application/pdf")},
    )
    assert upload_res.status_code == 201

    payload = {
        "enrollment_number": "D/1842/2016",
        "state_bar_council": "Bar Council of Delhi",
        "declared_practice_jurisdictions": ["High Court of Delhi", "Delhi District Courts"],
    }
    res = client.post(
        "/api/v1/verification/application/submit",
        headers=headers,
        json=payload,
    )
    assert res.status_code == 200
    app_data = res.json()
    assert app_data["status"] == VerificationStatus.PENDING.value
    assert app_data["enrollment_number"] == "D/1842/2016"
    assert "High Court of Delhi" in app_data["declared_practice_jurisdictions"]


# ---------------------------------------------------------------------------
# 3. RBAC & Security Boundaries
# ---------------------------------------------------------------------------


def test_client_cannot_access_verification_queue(client, db, client_user):
    headers = auth_header(client_user)
    res = client.get("/api/v1/verification/admin/queue", headers=headers)
    assert res.status_code == 403


def test_advocate_cannot_access_verification_queue(client, db, advocate_user):
    user, _ = advocate_user
    headers = auth_header(user)
    res = client.get("/api/v1/verification/admin/queue", headers=headers)
    assert res.status_code == 403


def test_admin_can_access_verification_queue(client, db, admin_user, advocate_user):
    user, profile = advocate_user
    advocate_headers = auth_header(user)

    # Submit application
    valid_pdf = b"%PDF-1.4\n%test\n%%EOF"
    upload_res = client.post(
        "/api/v1/verification/application/documents",
        headers=advocate_headers,
        data={"document_type": AdvocateDocumentType.BAR_COUNCIL_ENROLLMENT_CERT.value},
        files={"file": ("cert.pdf", io.BytesIO(valid_pdf), "application/pdf")},
    )
    assert upload_res.status_code == 201

    sub_res = client.post(
        "/api/v1/verification/application/submit",
        headers=advocate_headers,
        json={"enrollment_number": "D/1842/2016", "state_bar_council": "Bar Council of Delhi"},
    )
    assert sub_res.status_code == 200

    admin_headers = auth_header(admin_user)
    res = client.get("/api/v1/verification/admin/queue", headers=admin_headers)
    assert res.status_code == 200
    queue = res.json()
    assert queue["total"] >= 1
    found = any(item["enrollment_number"] == "D/1842/2016" for item in queue["items"])
    assert found is True


# ---------------------------------------------------------------------------
# 4. Self-Approval Protection (Section 10)
# ---------------------------------------------------------------------------


def test_self_approval_protection(client, db):
    # Create an Advocate who also holds ADMIN role
    dual_user = User(
        id=generate_uuid7(),
        email=f"dual_role_{uuid.uuid4().hex[:6]}@example.com",
        role=UserRole.LAWYER,
        account_status=AccountStatus.ACTIVE,
    )
    db.add(dual_user)
    db.flush()

    dual_profile = LawyerProfile(
        id=generate_uuid7(),
        user_id=dual_user.id,
        full_name="Adv. Rogue Admin",
    )
    db.add(dual_profile)
    db.commit()

    lawyer_headers = auth_header(dual_user)

    # Upload doc & submit as LAWYER
    valid_pdf = b"%PDF-1.4\n%test\n%%EOF"
    upload_res = client.post(
        "/api/v1/verification/application/documents",
        headers=lawyer_headers,
        data={"document_type": AdvocateDocumentType.BAR_COUNCIL_ENROLLMENT_CERT.value},
        files={"file": ("cert.pdf", io.BytesIO(valid_pdf), "application/pdf")},
    )
    assert upload_res.status_code == 201

    sub_res = client.post(
        "/api/v1/verification/application/submit",
        headers=lawyer_headers,
        json={"enrollment_number": "MAH/9999/2019", "state_bar_council": "Bar Council of Maharashtra & Goa"},
    )
    assert sub_res.status_code == 200
    verif_id = sub_res.json()["id"]

    # Now promote dual_user to ADMIN (e.g. an advocate who is also a platform admin)
    dual_user.role = UserRole.ADMIN
    db.commit()
    admin_headers = auth_header(dual_user)

    # Attempt to start review on OWN application -> MUST FAIL 403
    start_res = client.post(f"/api/v1/verification/{verif_id}/start-review", headers=admin_headers)
    assert start_res.status_code == 403
    assert "Self-approval prohibited" in start_res.text

    # Attempt to approve OWN application -> MUST FAIL 403
    approve_res = client.post(
        f"/api/v1/verification/{verif_id}/approve",
        headers=admin_headers,
        json={
            "verification_source": "Fake Portal",
            "source_reference": "Self-Verified",
            "verification_method": "STATE_BAR_COUNCIL_PORTAL_CHECK",
        },
    )
    assert approve_res.status_code == 403
    assert "Self-approval prohibited" in approve_res.text


# ---------------------------------------------------------------------------
# 5. Full Human Review Workflow & Provenance Recording (Zero-AI)
# ---------------------------------------------------------------------------


def test_full_review_approval_lifecycle(client, db, advocate_user, admin_user):
    user, profile = advocate_user
    advocate_headers = auth_header(user)
    admin_headers = auth_header(admin_user)

    # Step 1: Upload and submit
    valid_pdf = b"%PDF-1.4\n%enrollment doc\n%%EOF"
    doc_res = client.post(
        "/api/v1/verification/application/documents",
        headers=advocate_headers,
        data={"document_type": AdvocateDocumentType.BAR_COUNCIL_ENROLLMENT_CERT.value},
        files={"file": ("enrollment.pdf", io.BytesIO(valid_pdf), "application/pdf")},
    )
    assert doc_res.status_code == 201
    doc_id = doc_res.json()["id"]

    sub_res = client.post(
        "/api/v1/verification/application/submit",
        headers=advocate_headers,
        json={"enrollment_number": "D/1842/2016", "state_bar_council": "Bar Council of Delhi"},
    )
    assert sub_res.status_code == 200
    verif_id = sub_res.json()["id"]

    # Step 2: Admin generates document download preview URL (audited)
    dl_res = client.get(f"/api/v1/verification/documents/{doc_id}/download-url", headers=admin_headers)
    assert dl_res.status_code == 200
    assert "download_url" in dl_res.json()

    # Step 3: Admin starts review
    start_res = client.post(f"/api/v1/verification/{verif_id}/start-review", headers=admin_headers)
    assert start_res.status_code == 200
    assert start_res.json()["status"] == VerificationStatus.UNDER_REVIEW.value

    # Step 4: Admin approves with official Bar Council roll provenance
    approve_payload = {
        "verification_source": "Bar Council of Delhi Official Roll Portal",
        "source_reference": "Roll Entry No. 1842 of 2016 Verified",
        "verification_method": "STATE_BAR_COUNCIL_PORTAL_CHECK",
        "notes": "Advocate identity and roll registration verified against BCD roll records.",
    }
    approve_res = client.post(
        f"/api/v1/verification/{verif_id}/approve",
        headers=admin_headers,
        json=approve_payload,
    )
    assert approve_res.status_code == 200
    appr_data = approve_res.json()
    assert appr_data["status"] == VerificationStatus.APPROVED.value
    assert appr_data["verification_source"] == approve_payload["verification_source"]
    assert appr_data["source_reference"] == approve_payload["source_reference"]
    assert appr_data["verification_method"] == approve_payload["verification_method"]

    # Verify user account promoted to VERIFIED
    db.refresh(user)
    assert user.account_status == AccountStatus.VERIFIED

    # Step 5: Check Public Verification Badge (BCI Rule 36 compliant)
    badge_res = client.get(f"/api/v1/verification/badge/{profile.user_id}")
    assert badge_res.status_code == 200
    badge = badge_res.json()
    assert badge["is_verified"] is True
    assert badge["verification_badge_text"] == "✓ Professional Enrollment Verified"
    assert badge["state_bar_council"] == "Bar Council of Delhi"
    assert "D/****/2016" in badge["enrollment_number_masked"]
    assert "BCI Rule 36 proviso" in badge["compliance_declaration"]

    # Verify immutable audit history
    history = db.query(VerificationReviewEvent).filter(
        VerificationReviewEvent.verification_id == uuid.UUID(verif_id)
    ).all()
    assert len(history) >= 2  # START_REVIEW + APPROVE
    decisions = [ev.decision for ev in history]
    assert "START_REVIEW" in decisions
    assert "APPROVE" in decisions


# ---------------------------------------------------------------------------
# 6. Request Information & Rejection Workflows
# ---------------------------------------------------------------------------


def test_request_information_and_rejection(client, db, advocate_user, admin_user):
    user, profile = advocate_user
    advocate_headers = auth_header(user)
    admin_headers = auth_header(admin_user)

    # Submit
    valid_pdf = b"%PDF-1.4\n%enrollment doc\n%%EOF"
    upload_res = client.post(
        "/api/v1/verification/application/documents",
        headers=advocate_headers,
        data={"document_type": AdvocateDocumentType.BAR_COUNCIL_ENROLLMENT_CERT.value},
        files={"file": ("enrollment.pdf", io.BytesIO(valid_pdf), "application/pdf")},
    )
    assert upload_res.status_code == 201

    sub_res = client.post(
        "/api/v1/verification/application/submit",
        headers=advocate_headers,
        json={"enrollment_number": "D/1842/2016", "state_bar_council": "Bar Council of Delhi"},
    )
    assert sub_res.status_code == 200
    verif_id = sub_res.json()["id"]

    # Start review
    client.post(f"/api/v1/verification/{verif_id}/start-review", headers=admin_headers)

    # Request Information
    req_res = client.post(
        f"/api/v1/verification/{verif_id}/request-information",
        headers=admin_headers,
        json={
            "requested_documents": ["BAR_COUNCIL_ENROLLMENT_CERT"],
            "explanation": "Uploaded certificate is blurred. Please upload a clear scan of the enrollment certificate.",
        },
    )
    assert req_res.status_code == 200
    assert req_res.json()["status"] == VerificationStatus.NEEDS_INFO.value

    # Reject application
    rej_res = client.post(
        f"/api/v1/verification/{verif_id}/reject",
        headers=admin_headers,
        json={
            "rejection_reason_category": "UNVERIFIABLE_RECORD",
            "rejection_reason": "No corresponding enrollment record exists in Bar Council registry.",
        },
    )
    assert rej_res.status_code == 200
    assert rej_res.json()["status"] == VerificationStatus.REJECTED.value

    # Public badge remains unverified
    badge_res = client.get(f"/api/v1/verification/badge/{profile.user_id}")
    assert badge_res.json()["is_verified"] is False


# ---------------------------------------------------------------------------
# 7. Credential Change Re-Verification / Invalidation (Section 21)
# ---------------------------------------------------------------------------


def test_credential_modification_invalidates_verified_status(client, db, advocate_user, admin_user):
    user, profile = advocate_user
    advocate_headers = auth_header(user)
    admin_headers = auth_header(admin_user)

    # Submit and approve
    valid_pdf = b"%PDF-1.4\n%enrollment doc\n%%EOF"
    upload_res = client.post(
        "/api/v1/verification/application/documents",
        headers=advocate_headers,
        data={"document_type": AdvocateDocumentType.BAR_COUNCIL_ENROLLMENT_CERT.value},
        files={"file": ("enrollment.pdf", io.BytesIO(valid_pdf), "application/pdf")},
    )
    assert upload_res.status_code == 201

    sub_res = client.post(
        "/api/v1/verification/application/submit",
        headers=advocate_headers,
        json={"enrollment_number": "D/1842/2016", "state_bar_council": "Bar Council of Delhi"},
    )
    assert sub_res.status_code == 200
    verif_id = sub_res.json()["id"]

    client.post(
        f"/api/v1/verification/{verif_id}/approve",
        headers=admin_headers,
        json={
            "verification_source": "BCD Portal",
            "source_reference": "Entry 1842/2016",
            "verification_method": "STATE_BAR_COUNCIL_PORTAL_CHECK",
        },
    )

    # Verify badge is active
    badge1 = client.get(f"/api/v1/verification/badge/{profile.user_id}").json()
    assert badge1["is_verified"] is True

    # Call service method directly to test credential change invalidation
    from app.services.lawyer_verification_service import LawyerVerificationService
    verif_svc = LawyerVerificationService(db)
    invalidated = verif_svc.invalidate_on_credential_change(
        profile_id=profile.id,
        new_enrollment="MAH/9999/2021",
        new_state_bar="Bar Council of Maharashtra & Goa",
    )
    assert invalidated is True

    # Verification MUST now be REVOKED/invalidated
    db.refresh(user)
    assert user.account_status != AccountStatus.VERIFIED

    badge2 = client.get(f"/api/v1/verification/badge/{profile.user_id}").json()
    assert badge2["is_verified"] is False
    assert "Unverified" in badge2["verification_badge_text"]


# ---------------------------------------------------------------------------
# 8. Revocation by Admin Flow (Section 29)
# ---------------------------------------------------------------------------


def test_revocation_by_authorized_admin(client, db, advocate_user, admin_user):
    user, profile = advocate_user
    advocate_headers = auth_header(user)
    admin_headers = auth_header(admin_user)

    # Submit and approve
    valid_pdf = b"%PDF-1.4\n%enrollment doc\n%%EOF"
    upload_res = client.post(
        "/api/v1/verification/application/documents",
        headers=advocate_headers,
        data={"document_type": AdvocateDocumentType.BAR_COUNCIL_ENROLLMENT_CERT.value},
        files={"file": ("enrollment.pdf", io.BytesIO(valid_pdf), "application/pdf")},
    )
    assert upload_res.status_code == 201

    sub_res = client.post(
        "/api/v1/verification/application/submit",
        headers=advocate_headers,
        json={"enrollment_number": "D/1842/2016", "state_bar_council": "Bar Council of Delhi"},
    )
    assert sub_res.status_code == 200
    verif_id = sub_res.json()["id"]

    client.post(
        f"/api/v1/verification/{verif_id}/approve",
        headers=admin_headers,
        json={
            "verification_source": "BCD Portal",
            "source_reference": "Entry 1842/2016",
            "verification_method": "STATE_BAR_COUNCIL_PORTAL_CHECK",
        },
    )

    # Admin revokes verification
    revoke_res = client.post(
        f"/api/v1/verification/{verif_id}/revoke",
        headers=admin_headers,
        json={"revocation_reason": "State Bar Council disciplinary suspension notification received."},
    )
    assert revoke_res.status_code == 200
    assert revoke_res.json()["status"] == VerificationStatus.REVOKED.value

    badge = client.get(f"/api/v1/verification/badge/{profile.user_id}").json()
    assert badge["is_verified"] is False


# ---------------------------------------------------------------------------
# 9. Mass Assignment Protection (Section 38)
# ---------------------------------------------------------------------------


def test_mass_assignment_protection(client, db, advocate_user):
    user, profile = advocate_user
    headers = auth_header(user)

    # Attempt to submit with privileged status fields
    malicious_payload = {
        "enrollment_number": "D/1842/2016",
        "state_bar_council": "Bar Council of Delhi",
        "status": "APPROVED",
        "verification_status": "APPROVED",
        "reviewed_by": str(uuid.uuid4()),
        "verified_at": datetime.now(UTC).isoformat(),
    }
    res = client.post(
        "/api/v1/verification/application/submit",
        headers=headers,
        json=malicious_payload,
    )
    # Extra fields are forbidden by schema model_config = {"extra": "forbid"} -> 422
    assert res.status_code in [422, 400]
