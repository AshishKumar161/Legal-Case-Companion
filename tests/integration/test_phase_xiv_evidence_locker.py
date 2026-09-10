import hashlib
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.core.storage import get_storage_provider
from app.models.case import Case, CaseParticipant, ParticipantRole, ParticipantStatus
from app.models.evidence import (
    Evidence,
    EvidenceAccessLevel,
    EvidenceCategory,
    EvidenceCustodyAction,
    EvidenceIntegrityStatus,
    EvidenceScanStatus,
    EvidenceSensitivity,
    EvidenceStatus,
    EvidenceVersion,
)
from app.models.user import (
    AccountStatus,
    ClientProfile,
    LawyerProfile,
    LawyerVerification,
    User,
    UserRole,
    VerificationStatus,
)

VALID_PDF_BYTES = (
    b"%PDF-1.5\n%Valid forensic document container\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF"
)
TAMPERED_PDF_BYTES = (
    b"%PDF-1.5\n%TAMPERED bytes with modified contract clauses\n1 0 obj\n<< >>\nendobj\n%%EOF"
)
EICAR_MALWARE_BYTES = (
    b"%PDF-1.4\nX5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*\n%%EOF"
)


def _create_user(
    db: Session,
    prefix: str,
    role: UserRole,
    password: str = "SecurePass123!",
) -> tuple[User, str]:
    uid = uuid.uuid4().hex[:6]
    user = User(
        email=f"{prefix}_{uid}@example.com",
        password_hash=hash_password(password),
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
            practice_areas=["Commercial Law"],
            court_jurisdictions=["Delhi High Court"],
            languages=["English"],
            experience_years=7,
            consultation_fee=1500.0,
        )
        db.add(profile)
        db.flush()
        verif = LawyerVerification(
            lawyer_profile_id=profile.id,
            enrollment_number=f"D/{uuid.uuid4().hex[:4].upper()}/2021",
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


class TestPhaseXIVEvidenceLockerIntegration:
    """Integration test suite verifying the Evidence Locker lifecycle, versioning,

    cryptographic SHA-256 integrity, chain of custody, controlled sharing, and legal hold.
    """

    def test_evidence_staged_upload_scan_and_activation(self, client: TestClient, db: Session):
        """Test 1: Client deposits evidence -> bytes scanned -> SHA-256 stored -> ACTIVE -> custody logged."""
        client_user, client_token = _create_user(db, "client_u1", UserRole.CLIENT)
        storage = get_storage_provider()

        # 1. Create case
        c_res = client.post(
            "/api/v1/cases",
            headers=_auth_headers(client_token),
            json={"title": "Securities Fraud Investigation", "description": "Financial investigation"},
        )
        assert c_res.status_code == 201
        case_id = c_res.json()["id"]

        # 2. Initialize staged upload
        init_res = client.post(
            f"/api/v1/cases/{case_id}/evidence/upload-init",
            headers=_auth_headers(client_token),
            json={
                "title": "Audited Financial Statements 2024",
                "description": "Primary forensic exhibit",
                "category": "FINANCIAL",
                "sensitivity": "HIGHLY_CONFIDENTIAL",
                "original_filename": "audited_statements.pdf",
                "content_type": "application/pdf",
                "size_bytes": len(VALID_PDF_BYTES),
            },
        )
        assert init_res.status_code == 201
        init_data = init_res.json()
        evidence_id = init_data["evidence_id"]
        version_id = init_data["version_id"]
        storage_key = init_data["storage_key"]

        # 3. Simulate file upload to storage
        storage.put_object_bytes(storage_key, VALID_PDF_BYTES, mime_type="application/pdf")

        # 4. Complete verification pipeline
        complete_res = client.post(
            f"/api/v1/cases/{case_id}/evidence/{evidence_id}/complete",
            headers=_auth_headers(client_token),
            json={"version_id": version_id},
        )
        assert complete_res.status_code == 200
        comp_data = complete_res.json()
        assert comp_data["status"] == "ACTIVE"
        assert comp_data["category"] == "FINANCIAL"
        assert comp_data["sensitivity"] == "HIGHLY_CONFIDENTIAL"

        # 5. Verify recorded version and SHA-256 digest
        expected_hash = hashlib.sha256(VALID_PDF_BYTES).hexdigest()
        ver_res = client.get(
            f"/api/v1/cases/{case_id}/evidence/{evidence_id}/versions/{version_id}",
            headers=_auth_headers(client_token),
        )
        assert ver_res.status_code == 200
        ver_data = ver_res.json()
        assert ver_data["sha256"] == expected_hash
        assert ver_data["scan_status"] == "PASSED"
        assert ver_data["integrity_status"] == "VERIFIED_MATCH"

        # 6. Verify chain of custody logged UPLOADED and SCAN_PASSED
        custody_res = client.get(
            f"/api/v1/cases/{case_id}/evidence/{evidence_id}/custody",
            headers=_auth_headers(client_token),
        )
        assert custody_res.status_code == 200
        actions = [event["action"] for event in custody_res.json()]
        assert "UPLOADED" in actions
        assert "SCAN_PASSED" in actions

    def test_evidence_malware_scan_rejection(self, client: TestClient, db: Session):
        """Test 14: Uploading malware test signature fails scan, moves to QUARANTINED, custody logged."""
        client_user, client_token = _create_user(db, "client_malware", UserRole.CLIENT)
        storage = get_storage_provider()

        c_res = client.post(
            "/api/v1/cases",
            headers=_auth_headers(client_token),
            json={"title": "Malware Detection Matter", "description": "Malware test"},
        )
        case_id = c_res.json()["id"]

        init_res = client.post(
            f"/api/v1/cases/{case_id}/evidence/upload-init",
            headers=_auth_headers(client_token),
            json={
                "title": "Suspicious Attachment",
                "category": "DIGITAL",
                "sensitivity": "STANDARD",
                "original_filename": "suspicious.pdf",
                "content_type": "application/pdf",
                "size_bytes": len(EICAR_MALWARE_BYTES),
            },
        )
        evidence_id = init_res.json()["evidence_id"]
        version_id = init_res.json()["version_id"]
        storage_key = init_res.json()["storage_key"]

        # Put EICAR payload into storage
        storage.put_object_bytes(storage_key, EICAR_MALWARE_BYTES, mime_type="application/pdf")

        # Complete upload -> must fail with 422
        comp_res = client.post(
            f"/api/v1/cases/{case_id}/evidence/{evidence_id}/complete",
            headers=_auth_headers(client_token),
            json={"version_id": version_id},
        )
        assert comp_res.status_code == 422

        # Verify evidence item is QUARANTINED in database
        ev = db.query(Evidence).filter(Evidence.id == uuid.UUID(evidence_id)).first()
        assert ev.status == EvidenceStatus.QUARANTINED

        # Custody event recorded SCAN_FAILED
        custody_res = client.get(
            f"/api/v1/cases/{case_id}/evidence/{evidence_id}/custody",
            headers=_auth_headers(client_token),
        )
        actions = [event["action"] for event in custody_res.json()]
        assert "SCAN_FAILED" in actions

    def test_controlled_sharing_and_immediate_revocation(self, client: TestClient, db: Session):
        """Tests 3, 5, 7, 10: Client shares with case lawyer -> lawyer accesses -> revoke -> denied."""
        client_u, client_token = _create_user(db, "client_share", UserRole.CLIENT)
        lawyer_u, lawyer_token = _create_user(db, "lawyer_share", UserRole.LAWYER)
        storage = get_storage_provider()

        # Create case & add lawyer as participant
        c_res = client.post(
            "/api/v1/cases",
            headers=_auth_headers(client_token),
            json={"title": "Shared Contract Matter", "description": "Contract dispute"},
        )
        case_id = c_res.json()["id"]

        add_part = client.post(
            f"/api/v1/cases/{case_id}/participants",
            headers=_auth_headers(client_token),
            json={"user_id": str(lawyer_u.id), "participant_role": "LAWYER"},
        )
        assert add_part.status_code == 200

        # Upload evidence
        init_res = client.post(
            f"/api/v1/cases/{case_id}/evidence/upload-init",
            headers=_auth_headers(client_token),
            json={
                "title": "Executed Master Agreement",
                "category": "CONTRACTUAL",
                "sensitivity": "PRIVILEGED",
                "original_filename": "master_agreement.pdf",
                "content_type": "application/pdf",
                "size_bytes": len(VALID_PDF_BYTES),
            },
        )
        evidence_id = init_res.json()["evidence_id"]
        version_id = init_res.json()["version_id"]
        storage.put_object_bytes(init_res.json()["storage_key"], VALID_PDF_BYTES, mime_type="application/pdf")
        client.post(
            f"/api/v1/cases/{case_id}/evidence/{evidence_id}/complete",
            headers=_auth_headers(client_token),
            json={"version_id": version_id},
        )

        # Before sharing, Lawyer cannot access evidence (404)
        assert (
            client.get(
                f"/api/v1/cases/{case_id}/evidence/{evidence_id}",
                headers=_auth_headers(lawyer_token),
            ).status_code
            == 404
        )

        # Client shares Evidence with Lawyer (grant level: DOWNLOAD)
        share_res = client.post(
            f"/api/v1/cases/{case_id}/evidence/{evidence_id}/share",
            headers=_auth_headers(client_token),
            json={
                "target_user_id": str(lawyer_u.id),
                "access_level": "DOWNLOAD",
            },
        )
        assert share_res.status_code == 201

        # Lawyer can now view and download
        assert (
            client.get(
                f"/api/v1/cases/{case_id}/evidence/{evidence_id}",
                headers=_auth_headers(lawyer_token),
            ).status_code
            == 200
        )
        dl_res = client.get(
            f"/api/v1/cases/{case_id}/evidence/{evidence_id}/download",
            headers=_auth_headers(lawyer_token),
        )
        assert dl_res.status_code == 200
        assert "url" in dl_res.json()

        # Client revokes Lawyer access
        revoke_res = client.post(
            f"/api/v1/cases/{case_id}/evidence/{evidence_id}/revoke",
            headers=_auth_headers(client_token),
            json={"target_user_id": str(lawyer_u.id), "reason": "Consultation concluded"},
        )
        assert revoke_res.status_code == 200

        # Subsequent Lawyer access is immediately blocked (404)
        assert (
            client.get(
                f"/api/v1/cases/{case_id}/evidence/{evidence_id}",
                headers=_auth_headers(lawyer_token),
            ).status_code
            == 404
        )
        assert (
            client.get(
                f"/api/v1/cases/{case_id}/evidence/{evidence_id}/download",
                headers=_auth_headers(lawyer_token),
            ).status_code
            == 404
        )

    def test_immutable_version_2_upload(self, client: TestClient, db: Session):
        """Test 8: Version 2 upload preserves Version 1 immutability and updates current version."""
        client_u, client_token = _create_user(db, "client_ver", UserRole.CLIENT)
        storage = get_storage_provider()

        c_res = client.post(
            "/api/v1/cases",
            headers=_auth_headers(client_token),
            json={"title": "Patent Dispute", "description": "Patent evidence"},
        )
        case_id = c_res.json()["id"]

        # 1. Deposit Version 1
        init_1 = client.post(
            f"/api/v1/cases/{case_id}/evidence/upload-init",
            headers=_auth_headers(client_token),
            json={
                "title": "Patent Schematics",
                "category": "FORENSIC",
                "sensitivity": "HIGHLY_CONFIDENTIAL",
                "original_filename": "schematic_v1.pdf",
                "content_type": "application/pdf",
                "size_bytes": len(VALID_PDF_BYTES),
            },
        )
        evidence_id = init_1.json()["evidence_id"]
        v1_id = init_1.json()["version_id"]
        storage.put_object_bytes(init_1.json()["storage_key"], VALID_PDF_BYTES, mime_type="application/pdf")
        client.post(
            f"/api/v1/cases/{case_id}/evidence/{evidence_id}/complete",
            headers=_auth_headers(client_token),
            json={"version_id": v1_id},
        )

        v1_hash = hashlib.sha256(VALID_PDF_BYTES).hexdigest()

        # 2. Deposit Version 2
        v2_bytes = VALID_PDF_BYTES + b"\n%Version 2 supplementary forensic additions\n"
        v2_hash = hashlib.sha256(v2_bytes).hexdigest()

        init_2 = client.post(
            f"/api/v1/cases/{case_id}/evidence/{evidence_id}/versions/upload-init",
            headers=_auth_headers(client_token),
            json={
                "original_filename": "schematic_v2.pdf",
                "content_type": "application/pdf",
                "size_bytes": len(v2_bytes),
            },
        )
        assert init_2.status_code == 201
        v2_id = init_2.json()["version_id"]
        storage.put_object_bytes(init_2.json()["storage_key"], v2_bytes, mime_type="application/pdf")

        complete_2 = client.post(
            f"/api/v1/cases/{case_id}/evidence/{evidence_id}/versions/{v2_id}/complete",
            headers=_auth_headers(client_token),
        )
        assert complete_2.status_code == 200

        # Verify evidence current_version_id is now V2
        detail = client.get(
            f"/api/v1/cases/{case_id}/evidence/{evidence_id}",
            headers=_auth_headers(client_token),
        ).json()
        assert detail["current_version_id"] == v2_id
        assert detail["current_version"]["version_number"] == 2
        assert detail["current_version"]["sha256"] == v2_hash

        # Verify Version 1 remains completely immutable
        v1_check = client.get(
            f"/api/v1/cases/{case_id}/evidence/{evidence_id}/versions/{v1_id}",
            headers=_auth_headers(client_token),
        ).json()
        assert v1_check["version_number"] == 1
        assert v1_check["sha256"] == v1_hash

    def test_cryptographic_integrity_verification_and_tamper_detection(
        self, client: TestClient, db: Session
    ):
        """Test 9: Matching bytes pass verification; modified bytes detect TAMPER_DETECTED."""
        client_u, client_token = _create_user(db, "client_tamper", UserRole.CLIENT)
        storage = get_storage_provider()

        c_res = client.post(
            "/api/v1/cases",
            headers=_auth_headers(client_token),
            json={"title": "Forensic Integrity Case", "description": "Integrity validation"},
        )
        case_id = c_res.json()["id"]

        init_res = client.post(
            f"/api/v1/cases/{case_id}/evidence/upload-init",
            headers=_auth_headers(client_token),
            json={
                "title": "Chain of Custody Exhibit",
                "category": "FORENSIC",
                "sensitivity": "CONFIDENTIAL",
                "original_filename": "exhibit.pdf",
                "content_type": "application/pdf",
                "size_bytes": len(VALID_PDF_BYTES),
            },
        )
        evidence_id = init_res.json()["evidence_id"]
        version_id = init_res.json()["version_id"]
        storage_key = init_res.json()["storage_key"]

        storage.put_object_bytes(storage_key, VALID_PDF_BYTES, mime_type="application/pdf")
        client.post(
            f"/api/v1/cases/{case_id}/evidence/{evidence_id}/complete",
            headers=_auth_headers(client_token),
            json={"version_id": version_id},
        )

        # 1. Unmodified bytes -> VERIFIED_MATCH
        verify_1 = client.post(
            f"/api/v1/cases/{case_id}/evidence/{evidence_id}/verify-integrity",
            headers=_auth_headers(client_token),
        )
        assert verify_1.status_code == 200
        assert verify_1.json()["match"] is True
        assert verify_1.json()["integrity_status"] == "VERIFIED_MATCH"

        # 2. Simulate storage tampering (out-of-band byte replacement)
        storage.put_object_bytes(storage_key, TAMPERED_PDF_BYTES, mime_type="application/pdf")

        # 3. Verification now detects tamper
        verify_2 = client.post(
            f"/api/v1/cases/{case_id}/evidence/{evidence_id}/verify-integrity",
            headers=_auth_headers(client_token),
        )
        assert verify_2.status_code == 200
        assert verify_2.json()["match"] is False
        assert verify_2.json()["integrity_status"] == "TAMPER_DETECTED"

        # 4. Verify custody event logged INTEGRITY_FAILED
        custody = client.get(
            f"/api/v1/cases/{case_id}/evidence/{evidence_id}/custody",
            headers=_auth_headers(client_token),
        ).json()
        actions = [evt["action"] for evt in custody]
        assert "INTEGRITY_FAILED" in actions

    def test_legal_hold_and_retention_deletion_block(self, client: TestClient, db: Session):
        """Test 13: Evidence under legal hold or active retention cannot be deleted."""
        client_u, client_token = _create_user(db, "client_hold", UserRole.CLIENT)
        storage = get_storage_provider()

        c_res = client.post(
            "/api/v1/cases",
            headers=_auth_headers(client_token),
            json={"title": "Litigation Hold Matter", "description": "Legal hold tests"},
        )
        case_id = c_res.json()["id"]

        future_retention = (datetime.now(UTC) + timedelta(days=365)).isoformat()

        init_res = client.post(
            f"/api/v1/cases/{case_id}/evidence/upload-init",
            headers=_auth_headers(client_token),
            json={
                "title": "Subpoenaed Records",
                "category": "REGULATORY",
                "sensitivity": "PRIVILEGED",
                "original_filename": "subpoena.pdf",
                "content_type": "application/pdf",
                "size_bytes": len(VALID_PDF_BYTES),
                "retention_until": future_retention,
            },
        )
        evidence_id = init_res.json()["evidence_id"]
        version_id = init_res.json()["version_id"]
        storage.put_object_bytes(init_res.json()["storage_key"], VALID_PDF_BYTES, mime_type="application/pdf")
        client.post(
            f"/api/v1/cases/{case_id}/evidence/{evidence_id}/complete",
            headers=_auth_headers(client_token),
            json={"version_id": version_id},
        )

        # 1. Apply technical Legal Hold
        hold_res = client.post(
            f"/api/v1/cases/{case_id}/evidence/{evidence_id}/legal-hold",
            headers=_auth_headers(client_token),
            json={"legal_hold": True, "reason": "High Court Injunction Order"},
        )
        assert hold_res.status_code == 200
        assert hold_res.json()["legal_hold"] is True

        # 2. Attempt deletion -> blocked with 403 (LEGAL_HOLD_ACTIVE)
        del_1 = client.delete(
            f"/api/v1/cases/{case_id}/evidence/{evidence_id}",
            headers=_auth_headers(client_token),
        )
        assert del_1.status_code == 403
        assert del_1.json()["error"]["code"] == "LEGAL_HOLD_ACTIVE"

        # 3. Lift legal hold
        client.post(
            f"/api/v1/cases/{case_id}/evidence/{evidence_id}/legal-hold",
            headers=_auth_headers(client_token),
            json={"legal_hold": False},
        )

        # 4. Attempt deletion -> still blocked with 403 due to active retention_until (RETENTION_ACTIVE)
        del_2 = client.delete(
            f"/api/v1/cases/{case_id}/evidence/{evidence_id}",
            headers=_auth_headers(client_token),
        )
        assert del_2.status_code == 403
        assert del_2.json()["error"]["code"] == "RETENTION_ACTIVE"
