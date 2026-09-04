import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.core.storage import get_storage_provider
from app.models.user import (
    AccountStatus,
    ClientProfile,
    LawyerProfile,
    LawyerVerification,
    User,
    UserRole,
    VerificationStatus,
)

VALID_PDF_BYTES = b"%PDF-1.5\n%Security test evidence\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF"


def _create_user(
    db: Session,
    prefix: str,
    role: UserRole,
) -> tuple[User, str]:
    uid = uuid.uuid4().hex[:6]
    user = User(
        email=f"{prefix}_{uid}@example.com",
        password_hash=hash_password("SecurePass123!"),
        role=role,
        account_status=AccountStatus.ACTIVE,
    )
    db.add(user)
    db.flush()

    if role == UserRole.CLIENT:
        profile = ClientProfile(user_id=user.id, full_name=f"Client {prefix.capitalize()}")
        db.add(profile)
    elif role == UserRole.LAWYER:
        profile = LawyerProfile(
            user_id=user.id,
            full_name=f"Advocate {prefix.capitalize()}",
            practice_areas=["Litigation"],
            court_jurisdictions=["Supreme Court"],
            languages=["English"],
            experience_years=10,
            consultation_fee=2000.0,
        )
        db.add(profile)
        db.flush()
        verif = LawyerVerification(
            lawyer_profile_id=profile.id,
            enrollment_number=f"D/{uuid.uuid4().hex[:4].upper()}/2020",
            state_bar_council="Bar Council of Delhi",
            status=VerificationStatus.APPROVED,
        )
        db.add(verif)

    db.commit()
    db.refresh(user)
    token = create_access_token(str(user.id), user.role.value)
    return user, token


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


class TestEvidenceAuthorizationAndIDOR:
    """Security test suite validating BOLA/IDOR isolation, cross-tenant protection,

    and sharing boundaries for the Evidence Locker.
    """

    def test_cross_tenant_evidence_idor_defense(self, client: TestClient, db: Session):
        """Test 2 & 11: Client B cannot view, download, or mutate Client A's evidence (404 IDOR defense)."""
        client_a, token_a = _create_user(db, "client_a", UserRole.CLIENT)
        client_b, token_b = _create_user(db, "client_b", UserRole.CLIENT)
        storage = get_storage_provider()

        # Client A creates Case A
        c_res = client.post(
            "/api/v1/cases",
            headers=_auth_headers(token_a),
            json={"title": "Client A Confidential Matter", "description": "Confidential"},
        )
        case_a_id = c_res.json()["id"]

        # Client A uploads Evidence A
        init_res = client.post(
            f"/api/v1/cases/{case_a_id}/evidence/upload-init",
            headers=_auth_headers(token_a),
            json={
                "title": "Secret Trade Secret",
                "category": "CONTRACTUAL",
                "sensitivity": "PRIVILEGED",
                "original_filename": "secret.pdf",
                "content_type": "application/pdf",
                "size_bytes": len(VALID_PDF_BYTES),
            },
        )
        evidence_id = init_res.json()["evidence_id"]
        version_id = init_res.json()["version_id"]
        storage.put_object_bytes(init_res.json()["storage_key"], VALID_PDF_BYTES, mime_type="application/pdf")
        client.post(
            f"/api/v1/cases/{case_a_id}/evidence/{evidence_id}/complete",
            headers=_auth_headers(token_a),
            json={"version_id": version_id},
        )

        # Client B attempts direct IDOR access -> All must return 404
        assert (
            client.get(
                f"/api/v1/cases/{case_a_id}/evidence/{evidence_id}",
                headers=_auth_headers(token_b),
            ).status_code
            == 404
        )
        assert (
            client.get(
                f"/api/v1/cases/{case_a_id}/evidence/{evidence_id}/download",
                headers=_auth_headers(token_b),
            ).status_code
            == 404
        )
        assert (
            client.get(
                f"/api/v1/cases/{case_a_id}/evidence/{evidence_id}/view-url",
                headers=_auth_headers(token_b),
            ).status_code
            == 404
        )
        assert (
            client.get(
                f"/api/v1/cases/{case_a_id}/evidence/{evidence_id}/custody",
                headers=_auth_headers(token_b),
            ).status_code
            == 404
        )
        assert (
            client.delete(
                f"/api/v1/cases/{case_a_id}/evidence/{evidence_id}",
                headers=_auth_headers(token_b),
            ).status_code
            == 404
        )

    def test_unassociated_lawyer_access_and_sharing_boundary(
        self, client: TestClient, db: Session
    ):
        """Tests 4 & 6: Lawyer outside case cannot access evidence, and Client cannot share with unrelated lawyer."""
        client_a, token_a = _create_user(db, "client_share", UserRole.CLIENT)
        lawyer_ext, token_lawyer_ext = _create_user(db, "lawyer_ext", UserRole.LAWYER)
        storage = get_storage_provider()

        c_res = client.post(
            "/api/v1/cases",
            headers=_auth_headers(token_a),
            json={"title": "Private Injunction", "description": "Matter"},
        )
        case_id = c_res.json()["id"]

        init_res = client.post(
            f"/api/v1/cases/{case_id}/evidence/upload-init",
            headers=_auth_headers(token_a),
            json={
                "title": "Private Agreement",
                "category": "CONTRACTUAL",
                "sensitivity": "CONFIDENTIAL",
                "original_filename": "agreement.pdf",
                "content_type": "application/pdf",
                "size_bytes": len(VALID_PDF_BYTES),
            },
        )
        evidence_id = init_res.json()["evidence_id"]
        version_id = init_res.json()["version_id"]
        storage.put_object_bytes(init_res.json()["storage_key"], VALID_PDF_BYTES, mime_type="application/pdf")
        client.post(
            f"/api/v1/cases/{case_id}/evidence/{evidence_id}/complete",
            headers=_auth_headers(token_a),
            json={"version_id": version_id},
        )

        # 1. Unassociated lawyer receives 404 on direct evidence query
        assert (
            client.get(
                f"/api/v1/cases/{case_id}/evidence/{evidence_id}",
                headers=_auth_headers(token_lawyer_ext),
            ).status_code
            == 404
        )

        # 2. Client attempts to share evidence with an unassociated lawyer -> Must be rejected (403)
        share_res = client.post(
            f"/api/v1/cases/{case_id}/evidence/{evidence_id}/share",
            headers=_auth_headers(token_a),
            json={
                "target_user_id": str(lawyer_ext.id),
                "access_level": "VIEW",
            },
        )
        assert share_res.status_code == 403
        assert share_res.json()["error"]["code"] == "FORBIDDEN"

    def test_cross_version_idor_defense(self, client: TestClient, db: Session):
        """Test 12: Requesting Version X belonging to Evidence B under Evidence A's URL fails."""
        client_a, token_a = _create_user(db, "client_versions", UserRole.CLIENT)
        storage = get_storage_provider()

        c_res = client.post(
            "/api/v1/cases",
            headers=_auth_headers(token_a),
            json={"title": "Multi-Evidence Matter", "description": "Multiple items"},
        )
        case_id = c_res.json()["id"]

        # Deposit Evidence 1
        init_1 = client.post(
            f"/api/v1/cases/{case_id}/evidence/upload-init",
            headers=_auth_headers(token_a),
            json={
                "title": "Evidence 1",
                "category": "DIGITAL",
                "sensitivity": "STANDARD",
                "original_filename": "ev1.pdf",
                "content_type": "application/pdf",
                "size_bytes": len(VALID_PDF_BYTES),
            },
        )
        ev1_id = init_1.json()["evidence_id"]
        v1_id = init_1.json()["version_id"]
        storage.put_object_bytes(init_1.json()["storage_key"], VALID_PDF_BYTES, mime_type="application/pdf")
        client.post(f"/api/v1/cases/{case_id}/evidence/{ev1_id}/complete", headers=_auth_headers(token_a), json={"version_id": v1_id})

        # Deposit Evidence 2
        init_2 = client.post(
            f"/api/v1/cases/{case_id}/evidence/upload-init",
            headers=_auth_headers(token_a),
            json={
                "title": "Evidence 2",
                "category": "FORENSIC",
                "sensitivity": "STANDARD",
                "original_filename": "ev2.pdf",
                "content_type": "application/pdf",
                "size_bytes": len(VALID_PDF_BYTES),
            },
        )
        ev2_id = init_2.json()["evidence_id"]
        v2_id = init_2.json()["version_id"]
        storage.put_object_bytes(init_2.json()["storage_key"], VALID_PDF_BYTES, mime_type="application/pdf")
        client.post(f"/api/v1/cases/{case_id}/evidence/{ev2_id}/complete", headers=_auth_headers(token_a), json={"version_id": v2_id})

        # Attempt to query Version 2 under Evidence 1's path -> Must return 404
        cross_res = client.get(
            f"/api/v1/cases/{case_id}/evidence/{ev1_id}/versions/{v2_id}",
            headers=_auth_headers(token_a),
        )
        assert cross_res.status_code == 404
