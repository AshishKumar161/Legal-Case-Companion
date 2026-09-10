import hashlib
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.core.storage import get_storage_provider
from app.models.bundle import BundleStatus, EvidenceBundle
from app.models.case import Case, CaseParticipant, CaseTimelineEvent, ParticipantRole, ParticipantStatus
from app.models.user import (
    AccountStatus,
    ClientProfile,
    LawyerProfile,
    LawyerVerification,
    User,
    UserRole,
    VerificationStatus,
)
from app.models.workflow import CaseHearing, HearingStatus

VALID_PDF_BYTES = (
    b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
    b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R >>\nendobj\n"
    b"4 0 obj\n<< /Length 45 >>\nstream\nBT /F1 12 Tf 50 750 Td (Forensic Evidence Doc) Tj ET\nendstream\nendobj\n"
    b"xref\n0 5\n0000000000 65535 f \n0000000009 00000 n \n0000000056 00000 n \n0000000115 00000 n \n0000000210 00000 n \n"
    b"trailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n305\n%%EOF\n"
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
            practice_areas=["Litigation"],
            court_jurisdictions=["Delhi High Court"],
            languages=["English"],
            experience_years=10,
            consultation_fee=3000.0,
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


def _create_case(db: Session, owner: User) -> Case:
    case = Case(
        title="High Court Commercial Litigation",
        description="Breach of contract and recovery proceedings.",
    )
    db.add(case)
    db.flush()
    participant = CaseParticipant(
        case_id=case.id,
        user_id=owner.id,
        participant_role=ParticipantRole.OWNER,
        status=ParticipantStatus.ACTIVE,
    )
    db.add(participant)
    db.commit()
    db.refresh(case)
    return case


def _upload_and_activate_evidence(
    client: TestClient,
    token: str,
    case_id: uuid.UUID,
    title: str,
    filename: str = "document.pdf",
    content_bytes: bytes = VALID_PDF_BYTES,
) -> tuple[str, str]:
    init_res = client.post(
        f"/api/v1/cases/{case_id}/evidence/upload-init",
        json={
            "title": title,
            "original_filename": filename,
            "category": "CONTRACTUAL",
            "content_type": "application/pdf",
            "size_bytes": len(content_bytes),
        },
        headers=_auth_headers(token),
    )
    assert init_res.status_code == 201, init_res.text
    init_data = init_res.json()
    evidence_id = init_data["evidence_id"]
    version_id = init_data["version_id"]

    storage = get_storage_provider()
    storage.put_object_bytes(init_data["storage_key"], content_bytes, mime_type="application/pdf")

    sha256 = hashlib.sha256(content_bytes).hexdigest()
    complete_res = client.post(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/versions/{version_id}/complete",
        json={"sha256": sha256},
        headers=_auth_headers(token),
    )
    assert complete_res.status_code == 200, complete_res.text
    return evidence_id, version_id


class TestCourtHearingAndBundle:
    """End-to-end integration tests for Phase 11 Hearing Management and Evidentiary Bundles."""

    def test_hearing_lifecycle_adjourn_and_conclude_with_timeline(
        self, client: TestClient, db: Session
    ):
        owner, token = _create_user(db, "advocate_h", UserRole.LAWYER)
        case = _create_case(db, owner)

        # 1. Create Hearing
        hearing_dt = (datetime.now(UTC) + timedelta(days=5)).isoformat()
        res = client.post(
            f"/api/v1/cases/{case.id}/hearings",
            json={
                "court_name": "High Court of Delhi",
                "court_number": "Courtroom 4",
                "bench_or_coram": "Hon'ble Justice Sharma",
                "hearing_at": hearing_dt,
                "purpose": "Final Arguments on Injunction Application",
                "hearing_type": "FINAL_ARGUMENTS",
                "notes": "Bring original agreement copy",
            },
            headers=_auth_headers(token),
        )
        assert res.status_code == 201, res.text
        h_data = res.json()
        hearing_id = h_data["id"]
        assert h_data["status"] == "SCHEDULED"
        assert h_data["court_number"] == "Courtroom 4"

        # 2. Adjourn Hearing with next_date
        next_dt = (datetime.now(UTC) + timedelta(days=14)).isoformat()
        adjourn_res = client.post(
            f"/api/v1/cases/{case.id}/hearings/{hearing_id}/adjourn",
            json={
                "next_date": next_dt,
                "notes": "Adjourned at request of respondent advocate.",
            },
            headers=_auth_headers(token),
        )
        assert adjourn_res.status_code == 200, adjourn_res.text
        adj_data = adjourn_res.json()
        assert adj_data["status"] == "ADJOURNED"
        assert adj_data["next_date"] is not None

        # Verify timeline recorded adjournment
        tl_adj = (
            db.query(CaseTimelineEvent)
            .filter(
                CaseTimelineEvent.case_id == case.id,
                CaseTimelineEvent.event_type == "HEARING_ADJOURNED",
            )
            .first()
        )
        assert tl_adj is not None
        assert "adjourned" in tl_adj.description.lower()

        # 3. Conclude Hearing
        complete_res = client.post(
            f"/api/v1/cases/{case.id}/hearings/{hearing_id}/complete",
            json={"notes": "Order pronounced. Injunction granted."},
            headers=_auth_headers(token),
        )
        assert complete_res.status_code == 200, complete_res.text
        assert complete_res.json()["status"] == "CONCLUDED"

        tl_comp = (
            db.query(CaseTimelineEvent)
            .filter(
                CaseTimelineEvent.case_id == case.id,
                CaseTimelineEvent.event_type == "HEARING_COMPLETED",
            )
            .first()
        )
        assert tl_comp is not None

    def test_ecourts_manual_import_provenance(
        self, client: TestClient, db: Session
    ):
        owner, token = _create_user(db, "advocate_ec", UserRole.LAWYER)
        case = _create_case(db, owner)

        hearing_dt = (datetime.now(UTC) + timedelta(days=7)).isoformat()
        res = client.post(
            f"/api/v1/cases/{case.id}/hearings/import-ecourts",
            json={
                "court_name": "Tis Hazari District Court",
                "court_number": "Room 12",
                "bench_or_coram": "Sh. R.K. Mehta, DHJS",
                "hearing_at": hearing_dt,
                "purpose": "Evidence of Complainant",
                "hearing_type": "EVIDENCE",
                "source_reference": "DLCT010023452026",
                "notes": "Verified from eCourts daily cause list",
            },
            headers=_auth_headers(token),
        )
        assert res.status_code == 201, res.text
        data = res.json()
        assert data["source_type"] == "CAUSE_LIST"
        assert data["source_reference"] == "DLCT010023452026"

        hearing = db.query(CaseHearing).filter(CaseHearing.id == data["id"]).first()
        assert hearing.metadata_ is not None
        assert hearing.metadata_["source"] == "OFFICIAL_ECOURTS_PORTAL"
        assert hearing.metadata_["retrieval_method"] == "MANUAL_VERIFIED"
        assert "not constitute" in hearing.metadata_["disclaimer"]

    def test_bundle_creation_and_deterministic_exhibit_ordering(
        self, client: TestClient, db: Session
    ):
        owner, token = _create_user(db, "advocate_bndl", UserRole.LAWYER)
        case = _create_case(db, owner)

        # Upload 3 evidence files
        ev1_id, v1_id = _upload_and_activate_evidence(client, token, case.id, "Lease Agreement")
        ev2_id, v2_id = _upload_and_activate_evidence(client, token, case.id, "Bank Guarantee")
        ev3_id, v3_id = _upload_and_activate_evidence(client, token, case.id, "Legal Notice")

        # Mark exhibits out of order: ev2 is Exhibit B, ev1 is Exhibit A
        ex_b_res = client.post(
            f"/api/v1/cases/{case.id}/evidence/{ev2_id}/exhibits",
            json={"title": "Bank Guarantee Exhibit", "exhibit_number": "Exhibit B"},
            headers=_auth_headers(token),
        )
        assert ex_b_res.status_code == 201
        ex_b_id = ex_b_res.json()["id"]

        ex_a_res = client.post(
            f"/api/v1/cases/{case.id}/evidence/{ev1_id}/exhibits",
            json={"title": "Lease Agreement Exhibit", "exhibit_number": "Exhibit A"},
            headers=_auth_headers(token),
        )
        assert ex_a_res.status_code == 201
        ex_a_id = ex_a_res.json()["id"]

        # Create Draft Bundle with items out of order: ev3 first, then ev2 (B), then ev1 (A)
        bundle_res = client.post(
            f"/api/v1/cases/{case.id}/bundles",
            json={
                "title": "Trial Court Evidentiary Bundle",
                "description": "Comprehensive bundle for injunction hearing",
                "bates_prefix": "LCC",
                "bates_start": 1,
                "items": [
                    {"evidence_id": ev3_id},
                    {"evidence_id": ev2_id, "exhibit_id": ex_b_id},
                    {"evidence_id": ev1_id, "exhibit_id": ex_a_id},
                ],
            },
            headers=_auth_headers(token),
        )
        assert bundle_res.status_code == 201, bundle_res.text
        b_data = bundle_res.json()
        assert b_data["status"] == "DRAFT"
        assert len(b_data["items"]) == 3

        # Verify deterministic ordering: Exhibit A must be first, Exhibit B second, unexhibited third
        items = b_data["items"]
        assert items[0]["exhibit_number"] == "Exhibit A"
        assert items[1]["exhibit_number"] == "Exhibit B"
        assert items[2]["exhibit_number"] is None

    def test_bundle_finalization_bates_numbering_and_immutability(
        self, client: TestClient, db: Session
    ):
        owner, token = _create_user(db, "advocate_fin", UserRole.LAWYER)
        case = _create_case(db, owner)

        ev1_id, v1_id = _upload_and_activate_evidence(client, token, case.id, "Rental Contract")
        ev2_id, v2_id = _upload_and_activate_evidence(client, token, case.id, "Payment Receipt")

        # Create Exhibit A
        ex_res = client.post(
            f"/api/v1/cases/{case.id}/evidence/{ev1_id}/exhibits",
            json={"title": "Primary Contract", "exhibit_number": "Exhibit A"},
            headers=_auth_headers(token),
        )
        ex_id = ex_res.json()["id"]

        # Create bundle
        bundle_res = client.post(
            f"/api/v1/cases/{case.id}/bundles",
            json={
                "title": "Injunction Proceeding Bundle",
                "bates_prefix": "LCC",
                "bates_start": 100,
                "items": [
                    {"evidence_id": ev1_id, "exhibit_id": ex_id},
                    {"evidence_id": ev2_id},
                ],
            },
            headers=_auth_headers(token),
        )
        bundle_id = bundle_res.json()["id"]

        # Finalize bundle
        fin_res = client.post(
            f"/api/v1/cases/{case.id}/bundles/{bundle_id}/finalize",
            headers=_auth_headers(token),
        )
        assert fin_res.status_code == 200, fin_res.text
        fin_data = fin_res.json()
        assert fin_data["status"] == "FINALIZED"
        assert fin_data["sha256_hash"] is not None
        assert fin_data["total_pages"] >= 4  # Cover + Index + 2 docs + Manifest
        assert fin_data["bates_start"] == 100
        assert fin_data["bates_end"] is not None
        assert fin_data["manifest_json"] is not None

        # Verify Bates numbering on items
        items = fin_data["items"]
        assert items[0]["bates_start_page"] == 100
        assert items[0]["bates_end_page"] >= 100

        # Attempt to modify finalized bundle -> MUST FAIL with 409 Conflict
        update_res = client.put(
            f"/api/v1/cases/{case.id}/bundles/{bundle_id}",
            json={"title": "Tampered Bundle Title"},
            headers=_auth_headers(token),
        )
        assert update_res.status_code == 409, update_res.text

        # Verify timeline event
        tl_bndl = (
            db.query(CaseTimelineEvent)
            .filter(
                CaseTimelineEvent.case_id == case.id,
                CaseTimelineEvent.event_type == "BUNDLE_FINALIZED",
            )
            .first()
        )
        assert tl_bndl is not None

        # Presigned download
        dl_res = client.get(
            f"/api/v1/cases/{case.id}/bundles/{bundle_id}/download",
            headers=_auth_headers(token),
        )
        assert dl_res.status_code == 200, dl_res.text
        dl_data = dl_res.json()
        assert "url" in dl_data
        assert dl_data["expires_in"] == 60
        assert dl_data["sha256"] == fin_data["sha256_hash"]

    def test_bsa_section_63_certificate_workflow(
        self, client: TestClient, db: Session
    ):
        owner, token = _create_user(db, "advocate_bsa", UserRole.LAWYER)
        case = _create_case(db, owner)

        ev_id, v_id = _upload_and_activate_evidence(client, token, case.id, "Disputed Agreement")

        # Bundle & Finalize
        b_res = client.post(
            f"/api/v1/cases/{case.id}/bundles",
            json={"title": "Evidentiary Filing Bundle", "items": [{"evidence_id": ev_id}]},
            headers=_auth_headers(token),
        )
        bundle_id = b_res.json()["id"]
        client.post(f"/api/v1/cases/{case.id}/bundles/{bundle_id}/finalize", headers=_auth_headers(token))

        # 1. Human confirmation mandatory: is_confirmed=False must fail
        fail_res = client.post(
            f"/api/v1/cases/{case.id}/bundles/{bundle_id}/certificate",
            json={
                "record_identification": "Evidentiary Bundle for Injunction",
                "source_device_type": "Server Cloud Storage",
                "source_device_details": "AWS S3 ap-south-1 encrypted repository",
                "lawful_control_statement": "I have lawful control over the production and storage of this electronic record.",
                "operational_condition_statement": "The repository and computer system were operating properly during the relevant period.",
                "declarant_name": "Advocate Ramesh Gupta",
                "declarant_designation": "Counsel for Complainant",
                "place": "New Delhi",
                "declaration_date": datetime.now(UTC).isoformat(),
                "is_confirmed": False,
            },
            headers=_auth_headers(token),
        )
        assert fail_res.status_code in (400, 422), fail_res.text

        # 2. Valid statutory certificate generation
        cert_res = client.post(
            f"/api/v1/cases/{case.id}/bundles/{bundle_id}/certificate",
            json={
                "record_identification": "Evidentiary Bundle for Injunction",
                "source_device_type": "Server Cloud Storage",
                "source_device_details": "AWS S3 ap-south-1 encrypted repository",
                "lawful_control_statement": "I have lawful control over the production and storage of this electronic record.",
                "operational_condition_statement": "The repository and computer system were operating properly during the relevant period.",
                "declarant_name": "Advocate Ramesh Gupta",
                "declarant_designation": "Counsel for Complainant",
                "declarant_organization": "Gupta & Associates",
                "place": "New Delhi",
                "declaration_date": datetime.now(UTC).isoformat(),
                "is_confirmed": True,
            },
            headers=_auth_headers(token),
        )
        assert cert_res.status_code == 201, cert_res.text
        cert_data = cert_res.json()
        assert cert_data["status"] == "PREPARED_DRAFT"
        assert cert_data["hash_algorithm"] == "SHA-256"
        assert cert_data["hash_value"] is not None
        cert_id = cert_data["id"]

        # Download certificate
        cert_dl = client.get(
            f"/api/v1/cases/{case.id}/bundles/{bundle_id}/certificate/{cert_id}/download",
            headers=_auth_headers(token),
        )
        assert cert_dl.status_code == 200, cert_dl.text
        assert "url" in cert_dl.json()

    def test_bundle_security_and_idor_isolation(
        self, client: TestClient, db: Session
    ):
        user_a, token_a = _create_user(db, "client_a", UserRole.CLIENT)
        user_b, token_b = _create_user(db, "client_b", UserRole.CLIENT)

        case_a = _create_case(db, user_a)
        case_b = _create_case(db, user_b)

        ev_a, _ = _upload_and_activate_evidence(client, token_a, case_a.id, "Case A Asset")
        ev_b, _ = _upload_and_activate_evidence(client, token_b, case_b.id, "Case B Asset")

        # Bundle for Case A
        b_res = client.post(
            f"/api/v1/cases/{case_a.id}/bundles",
            json={"title": "Case A Bundle", "items": [{"evidence_id": ev_a}]},
            headers=_auth_headers(token_a),
        )
        assert b_res.status_code == 201
        bundle_a_id = b_res.json()["id"]

        # User B attempts to access Case A bundle -> 404 existence masking
        unauth_get = client.get(
            f"/api/v1/cases/{case_a.id}/bundles/{bundle_a_id}",
            headers=_auth_headers(token_b),
        )
        assert unauth_get.status_code == 404, unauth_get.text

        # User A attempts to include User B's evidence in Case A bundle -> fails closed
        cross_res = client.post(
            f"/api/v1/cases/{case_a.id}/bundles",
            json={"title": "Illegal Cross Bundle", "items": [{"evidence_id": ev_b}]},
            headers=_auth_headers(token_a),
        )
        assert cross_res.status_code in (403, 404), cross_res.text
