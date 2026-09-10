import uuid
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.identifiers import generate_uuid7
from app.models.case import Case, CaseParticipant, ParticipantRole, ParticipantStatus
from app.models.evidence import (
    Evidence,
    EvidenceAccessGrant,
    EvidenceAccessLevel,
    EvidenceCategory,
    EvidenceIntegrityStatus,
    EvidenceScanStatus,
    EvidenceSensitivity,
    EvidenceStatus,
    EvidenceVersion,
)
from app.models.user import User, UserRole


def _create_test_user(
    client: TestClient,
    db: Session,
    email: str,
    role: UserRole = UserRole.CLIENT,
    full_name: str = "Test User",
) -> tuple[dict[str, str], UUID, User]:
    reg_res = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Password123!", "full_name": full_name, "role": role.value},
    )
    assert reg_res.status_code == 201, reg_res.text
    user_id = UUID(reg_res.json()["id"])

    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    assert login_res.status_code == 200, login_res.text
    headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

    user = db.query(User).filter(User.id == user_id).first()
    assert user is not None
    return headers, user_id, user


def _setup_case_with_evidence(
    db: Session,
    owner_user: User,
    participant_user: User,
) -> tuple[Case, Evidence, EvidenceVersion]:
    case_id = generate_uuid7()
    case = Case(
        id=case_id,
        title="Test Matter Alpha v Beta",
        description="Confidential dispute matter",
    )
    db.add(case)

    # Owner participant
    part_owner = CaseParticipant(
        id=generate_uuid7(),
        case_id=case_id,
        user_id=owner_user.id,
        participant_role=ParticipantRole.OWNER,
        status=ParticipantStatus.ACTIVE,
    )
    db.add(part_owner)

    # Co-participant (e.g. client or advocate)
    part_member = CaseParticipant(
        id=generate_uuid7(),
        case_id=case_id,
        user_id=participant_user.id,
        participant_role=ParticipantRole.VIEWER,
        status=ParticipantStatus.ACTIVE,
    )
    db.add(part_member)

    # Evidence item
    ev_id = generate_uuid7()
    ver_id = generate_uuid7()
    storage_key = f"cases/{case_id}/evidence/{ev_id}/versions/{ver_id}"

    version = EvidenceVersion(
        id=ver_id,
        evidence_id=ev_id,
        version_number=1,
        uploaded_by_user_id=owner_user.id,
        storage_key=storage_key,
        original_filename="Contract_Exhibit_A.pdf",
        content_type="application/pdf",
        size_bytes=1024,
        sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        scan_status=EvidenceScanStatus.PASSED,
        integrity_status=EvidenceIntegrityStatus.VERIFIED_MATCH,
    )
    db.add(version)

    evidence = Evidence(
        id=ev_id,
        case_id=case_id,
        created_by_user_id=owner_user.id,
        title="Key Contract Exhibit A",
        description="Signed copy of main agreement",
        category=EvidenceCategory.CONTRACTUAL,
        sensitivity=EvidenceSensitivity.CONFIDENTIAL,
        status=EvidenceStatus.ACTIVE,
        original_filename="Contract_Exhibit_A.pdf",
        current_version_id=ver_id,
    )
    db.add(evidence)
    db.commit()
    db.refresh(case)
    db.refresh(evidence)
    db.refresh(version)

    return case, evidence, version


def test_document_share_and_view_lifecycle(client: TestClient, db: Session):
    """Authorized owner shares document; recipient can view/download; grants list is populated."""
    owner_headers, owner_id, owner_user = _create_test_user(client, db, f"advocate_{uuid.uuid4().hex[:6]}@example.com", UserRole.LAWYER)
    client_headers, client_id, client_user = _create_test_user(client, db, f"client_{uuid.uuid4().hex[:6]}@example.com", UserRole.CLIENT)

    case, evidence, version = _setup_case_with_evidence(db, owner_user, client_user)

    # 1. Check shareable participants
    part_res = client.get(
        f"/api/v1/cases/{case.id}/evidence/{evidence.id}/shareable-participants",
        headers=owner_headers,
    )
    assert part_res.status_code == 200, part_res.text
    participants = part_res.json()
    assert len(participants) >= 1
    target = next((p for p in participants if p["user_id"] == str(client_id)), None)
    assert target is not None
    assert target["has_access"] is False

    # 2. Share evidence with client with DOWNLOAD access
    share_res = client.post(
        f"/api/v1/cases/{case.id}/evidence/{evidence.id}/share",
        headers=owner_headers,
        json={
            "target_user_id": str(client_id),
            "access_level": "DOWNLOAD",
        },
    )
    assert share_res.status_code == 201, share_res.text
    grant_data = share_res.json()
    assert grant_data["access_level"] == "DOWNLOAD"

    # 3. Recipient views active grants list
    grants_res = client.get(
        f"/api/v1/cases/{case.id}/evidence/{evidence.id}/grants",
        headers=client_headers,
    )
    assert grants_res.status_code == 200, grants_res.text
    grants = grants_res.json()
    assert len(grants) >= 1
    assert grants[0]["grantee_name"] is not None

    # 4. Recipient views "shared with me" in case
    case_shared_res = client.get(
        f"/api/v1/cases/{case.id}/evidence-shared-with-me",
        headers=client_headers,
    )
    assert case_shared_res.status_code == 200, case_shared_res.text
    case_shared = case_shared_res.json()
    assert len(case_shared) == 1
    assert case_shared[0]["id"] == str(evidence.id)
    assert case_shared[0]["case_title"] == case.title
    assert case_shared[0]["access_level"] == "DOWNLOAD"

    # 5. Recipient views "shared with me" globally
    global_shared_res = client.get(
        "/api/v1/documents/shared-with-me",
        headers=client_headers,
    )
    assert global_shared_res.status_code == 200, global_shared_res.text
    global_shared = global_shared_res.json()
    assert any(item["id"] == str(evidence.id) for item in global_shared)

    # 6. Recipient requests short-lived view URL
    view_url_res = client.get(
        f"/api/v1/cases/{case.id}/evidence/{evidence.id}/view-url",
        headers=client_headers,
    )
    assert view_url_res.status_code == 200, view_url_res.text
    assert "url" in view_url_res.json()
    assert view_url_res.json()["expires_in"] == 60

    # 7. Recipient requests short-lived download URL
    dl_url_res = client.get(
        f"/api/v1/cases/{case.id}/evidence/{evidence.id}/download",
        headers=client_headers,
    )
    assert dl_url_res.status_code == 200, dl_url_res.text
    assert "url" in dl_url_res.json()


def test_document_share_revocation(client: TestClient, db: Session):
    """Owner revokes document access; recipient immediately loses download and view capability."""
    owner_headers, owner_id, owner_user = _create_test_user(client, db, f"advocate_{uuid.uuid4().hex[:6]}@example.com", UserRole.LAWYER)
    client_headers, client_id, client_user = _create_test_user(client, db, f"client_{uuid.uuid4().hex[:6]}@example.com", UserRole.CLIENT)

    case, evidence, version = _setup_case_with_evidence(db, owner_user, client_user)

    # Share
    client.post(
        f"/api/v1/cases/{case.id}/evidence/{evidence.id}/share",
        headers=owner_headers,
        json={"target_user_id": str(client_id), "access_level": "DOWNLOAD"},
    )

    # Verify access is present
    pre_res = client.get(f"/api/v1/cases/{case.id}/evidence/{evidence.id}/download", headers=client_headers)
    assert pre_res.status_code == 200

    # Revoke
    rev_res = client.post(
        f"/api/v1/cases/{case.id}/evidence/{evidence.id}/revoke",
        headers=owner_headers,
        json={"target_user_id": str(client_id), "reason": "Settlement concluded"},
    )
    assert rev_res.status_code == 200, rev_res.text
    assert rev_res.json()["revoked_at"] is not None

    # Post-revocation: download URL acquisition must be rejected (404/403)
    post_res = client.get(f"/api/v1/cases/{case.id}/evidence/{evidence.id}/download", headers=client_headers)
    assert post_res.status_code in (403, 404)

    # Post-revocation: not listed in shared-with-me
    shared_res = client.get("/api/v1/documents/shared-with-me", headers=client_headers)
    assert not any(item["id"] == str(evidence.id) for item in shared_res.json())


def test_document_share_unauthorized_user_blocked(client: TestClient, db: Session):
    """An unrelated user cannot share, view, or download private evidence (BOLA/IDOR defense)."""
    owner_headers, owner_id, owner_user = _create_test_user(client, db, f"advocate_{uuid.uuid4().hex[:6]}@example.com", UserRole.LAWYER)
    client_headers, client_id, client_user = _create_test_user(client, db, f"client_{uuid.uuid4().hex[:6]}@example.com", UserRole.CLIENT)
    unrelated_headers, unrelated_id, unrelated_user = _create_test_user(client, db, f"stranger_{uuid.uuid4().hex[:6]}@example.com", UserRole.CLIENT)

    case, evidence, version = _setup_case_with_evidence(db, owner_user, client_user)

    # Unrelated user cannot share
    share_res = client.post(
        f"/api/v1/cases/{case.id}/evidence/{evidence.id}/share",
        headers=unrelated_headers,
        json={"target_user_id": str(client_id), "access_level": "VIEW"},
    )
    assert share_res.status_code in (403, 404)

    # Unrelated user cannot view grants
    grants_res = client.get(
        f"/api/v1/cases/{case.id}/evidence/{evidence.id}/grants",
        headers=unrelated_headers,
    )
    assert grants_res.status_code in (403, 404)

    # Unrelated user cannot download
    dl_res = client.get(
        f"/api/v1/cases/{case.id}/evidence/{evidence.id}/download",
        headers=unrelated_headers,
    )
    assert dl_res.status_code in (403, 404)


def test_document_share_cannot_share_with_arbitrary_user(client: TestClient, db: Session):
    """Owner cannot share document with arbitrary third-party not associated with the case."""
    owner_headers, owner_id, owner_user = _create_test_user(client, db, f"advocate_{uuid.uuid4().hex[:6]}@example.com", UserRole.LAWYER)
    client_headers, client_id, client_user = _create_test_user(client, db, f"client_{uuid.uuid4().hex[:6]}@example.com", UserRole.CLIENT)
    arbitrary_headers, arbitrary_id, arbitrary_user = _create_test_user(client, db, f"arbitrary_{uuid.uuid4().hex[:6]}@example.com", UserRole.CLIENT)

    case, evidence, version = _setup_case_with_evidence(db, owner_user, client_user)

    # Attempt to share with arbitrary user who is NOT in the case
    res = client.post(
        f"/api/v1/cases/{case.id}/evidence/{evidence.id}/share",
        headers=owner_headers,
        json={"target_user_id": str(arbitrary_id), "access_level": "VIEW"},
    )
    assert res.status_code == 403
    assert "not associated with this case" in str(res.json())
