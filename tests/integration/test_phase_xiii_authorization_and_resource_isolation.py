import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.models.case import (
    Case,
    CaseParticipant,
    CaseStatus,
    ParticipantRole,
    ParticipantStatus,
)
from app.models.consultation import Consultation, ConsultationStatus
from app.models.document import Document, DocumentSecurityStatus
from app.models.user import (
    AccountStatus,
    ClientProfile,
    LawyerProfile,
    LawyerVerification,
    User,
    UserRole,
    VerificationStatus,
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
        profile = ClientProfile(
            user_id=user.id,
            full_name=f"Client {prefix.capitalize()}",
        )
        db.add(profile)
    elif role == UserRole.LAWYER:
        profile = LawyerProfile(
            user_id=user.id,
            full_name=f"Advocate {prefix.capitalize()}",
            practice_areas=["Corporate Law", "Litigation"],
            court_jurisdictions=["Delhi High Court"],
            languages=["English"],
            experience_years=5,
            consultation_fee=1000.0,
        )
        db.add(profile)
        db.flush()
        verif = LawyerVerification(
            lawyer_profile_id=profile.id,
            enrollment_number=f"D/{uuid.uuid4().hex[:4].upper()}/2022",
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


class TestPhaseXIIIAuthorizationAndResourceIsolation:
    """Comprehensive Phase XIII Authorization Boundary and Resource Isolation Test Suite."""

    def test_cross_tenant_case_bola_isolation(self, client: TestClient, db: Session):
        """User B cannot read, modify, delete, or inspect User A's private case (returns 404 IDOR defense)."""
        client_a, token_a = _create_user(db, "client_a", UserRole.CLIENT)
        client_b, token_b = _create_user(db, "client_b", UserRole.CLIENT)

        # Client A creates Case A
        create_res = client.post(
            "/api/v1/cases",
            headers=_auth_headers(token_a),
            json={
                "title": "Confidential IP Dispute",
                "description": "Sensitive client confidential matter",
            },
        )
        assert create_res.status_code == 201
        case_a_id = create_res.json()["id"]

        # Client B attempts BOLA access against Case A -> All must return 404
        assert (
            client.get(f"/api/v1/cases/{case_a_id}", headers=_auth_headers(token_b)).status_code
            == 404
        )
        assert (
            client.patch(
                f"/api/v1/cases/{case_a_id}",
                headers=_auth_headers(token_b),
                json={"title": "Hacked Title"},
            ).status_code
            == 404
        )
        assert (
            client.delete(f"/api/v1/cases/{case_a_id}", headers=_auth_headers(token_b)).status_code
            == 404
        )
        assert (
            client.get(
                f"/api/v1/cases/{case_a_id}/workspace", headers=_auth_headers(token_b)
            ).status_code
            == 404
        )
        assert (
            client.get(
                f"/api/v1/cases/{case_a_id}/timeline", headers=_auth_headers(token_b)
            ).status_code
            == 404
        )
        assert (
            client.get(
                f"/api/v1/cases/{case_a_id}/report", headers=_auth_headers(token_b)
            ).status_code
            == 404
        )
        assert (
            client.post(
                f"/api/v1/cases/{case_a_id}/participants",
                headers=_auth_headers(token_b),
                json={"user_id": str(client_b.id), "participant_role": "OWNER"},
            ).status_code
            == 404
        )

    def test_lawyer_case_isolation_and_grant_access(self, client: TestClient, db: Session):
        """Unassociated lawyer cannot access case; associated lawyer gains authorized access."""
        client_a, token_client = _create_user(db, "client_a", UserRole.CLIENT)
        lawyer_1, token_lawyer_1 = _create_user(db, "lawyer_1", UserRole.LAWYER)
        lawyer_2, token_lawyer_2 = _create_user(db, "lawyer_2", UserRole.LAWYER)

        # Client creates case
        create_res = client.post(
            "/api/v1/cases",
            headers=_auth_headers(token_client),
            json={"title": "Commercial Arbitration", "description": "Arbitration matter"},
        )
        assert create_res.status_code == 201
        case_id = create_res.json()["id"]

        # Neither lawyer has access initially
        assert (
            client.get(f"/api/v1/cases/{case_id}", headers=_auth_headers(token_lawyer_1)).status_code
            == 404
        )
        assert (
            client.get(f"/api/v1/cases/{case_id}", headers=_auth_headers(token_lawyer_2)).status_code
            == 404
        )

        # Client grants access to Lawyer 1
        grant_res = client.post(
            f"/api/v1/cases/{case_id}/participants",
            headers=_auth_headers(token_client),
            json={"user_id": str(lawyer_1.id), "participant_role": "LAWYER"},
        )
        assert grant_res.status_code == 200

        # Lawyer 1 can now access
        res_l1 = client.get(f"/api/v1/cases/{case_id}", headers=_auth_headers(token_lawyer_1))
        assert res_l1.status_code == 200
        assert res_l1.json()["title"] == "Commercial Arbitration"

        # Lawyer 2 remains blocked
        assert (
            client.get(f"/api/v1/cases/{case_id}", headers=_auth_headers(token_lawyer_2)).status_code
            == 404
        )

    def test_viewer_role_read_only_and_mutation_forbidden(self, client: TestClient, db: Session):
        """Viewer can read case resources but receives 403 Forbidden on all mutation endpoints."""
        owner, token_owner = _create_user(db, "owner", UserRole.CLIENT)
        viewer, token_viewer = _create_user(db, "viewer", UserRole.CLIENT)

        # Create case
        c_res = client.post(
            "/api/v1/cases",
            headers=_auth_headers(token_owner),
            json={"title": "Shareholder Dispute", "description": "Corporate matter"},
        )
        assert c_res.status_code == 201
        case_id = c_res.json()["id"]

        # Add viewer participant
        part_res = client.post(
            f"/api/v1/cases/{case_id}/participants",
            headers=_auth_headers(token_owner),
            json={"user_id": str(viewer.id), "participant_role": "VIEWER"},
        )
        assert part_res.status_code == 200

        # 1. Read operations succeed for VIEWER
        assert (
            client.get(f"/api/v1/cases/{case_id}", headers=_auth_headers(token_viewer)).status_code
            == 200
        )
        assert (
            client.get(
                f"/api/v1/cases/{case_id}/workspace", headers=_auth_headers(token_viewer)
            ).status_code
            == 200
        )
        assert (
            client.get(
                f"/api/v1/cases/{case_id}/deadlines", headers=_auth_headers(token_viewer)
            ).status_code
            == 200
        )
        assert (
            client.get(
                f"/api/v1/cases/{case_id}/hearings", headers=_auth_headers(token_viewer)
            ).status_code
            == 200
        )
        assert (
            client.get(
                f"/api/v1/cases/{case_id}/workflow", headers=_auth_headers(token_viewer)
            ).status_code
            == 200
        )

        # 2. Case mutations forbidden for VIEWER (403)
        assert (
            client.patch(
                f"/api/v1/cases/{case_id}",
                headers=_auth_headers(token_viewer),
                json={"title": "Viewer Cannot Rename"},
            ).status_code
            == 403
        )
        assert (
            client.delete(f"/api/v1/cases/{case_id}", headers=_auth_headers(token_viewer)).status_code
            == 403
        )
        assert (
            client.post(
                f"/api/v1/cases/{case_id}/participants",
                headers=_auth_headers(token_viewer),
                json={"user_id": str(viewer.id), "participant_role": "OWNER"},
            ).status_code
            == 403
        )

        # 3. Workflow mutations forbidden for VIEWER (403)
        assert (
            client.post(
                f"/api/v1/cases/{case_id}/tasks",
                headers=_auth_headers(token_viewer),
                json={"title": "Viewer Task", "priority": "MEDIUM"},
            ).status_code
            == 403
        )
        assert (
            client.post(
                f"/api/v1/cases/{case_id}/deadlines",
                headers=_auth_headers(token_viewer),
                json={
                    "title": "Viewer Deadline",
                    "deadline_at": (datetime.now(UTC) + timedelta(days=2)).isoformat(),
                    "deadline_type": "COURT_FILING",
                },
            ).status_code
            == 403
        )
        assert (
            client.post(
                f"/api/v1/cases/{case_id}/hearings",
                headers=_auth_headers(token_viewer),
                json={
                    "court_name": "Court 4",
                    "hearing_at": (datetime.now(UTC) + timedelta(days=5)).isoformat(),
                    "purpose": "Hearing",
                },
            ).status_code
            == 403
        )
        assert (
            client.post(
                f"/api/v1/cases/{case_id}/workflow/suggestions/generate",
                headers=_auth_headers(token_viewer),
            ).status_code
            == 403
        )

        # 4. Intelligence mutations forbidden for VIEWER (403)
        assert (
            client.post(
                f"/api/v1/cases/{case_id}/intelligence/refresh",
                headers=_auth_headers(token_viewer),
                json={},
            ).status_code
            == 403
        )
        assert (
            client.post(
                f"/api/v1/cases/{case_id}/intelligence/facts",
                headers=_auth_headers(token_viewer),
                json={"fact_text": "Illegal mutation", "category": "GENERAL"},
            ).status_code
            == 403
        )
        assert (
            client.post(
                f"/api/v1/cases/{case_id}/intelligence/issues",
                headers=_auth_headers(token_viewer),
                json={"issue_text": "Viewer Issue", "category": "BREACH"},
            ).status_code
            == 403
        )

    def test_document_access_and_download_isolation(self, client: TestClient, db: Session):
        """Cross-tenant document access and presigned URL downloads are strictly isolated."""
        client_a, token_a = _create_user(db, "doc_owner", UserRole.CLIENT)
        client_b, token_b = _create_user(db, "unrelated_user", UserRole.CLIENT)

        # Create case
        c_res = client.post(
            "/api/v1/cases",
            headers=_auth_headers(token_a),
            json={"title": "Contract Matter", "description": "Contractual dispute"},
        )
        assert c_res.status_code == 201
        case_id = uuid.UUID(c_res.json()["id"])

        # Create Document directly in DB for Case A
        doc = Document(
            id=uuid.uuid4(),
            case_id=case_id,
            uploaded_by=client_a.id,
            filename="confidential_agreement.pdf",
            file_size=1024,
            mime_type="application/pdf",
            storage_key=f"cases/{case_id}/documents/{uuid.uuid4()}.pdf",
            security_status=DocumentSecurityStatus.SAFE,
        )
        db.add(doc)
        db.commit()

        # Client B cannot get document metadata or download URL -> 404
        assert (
            client.get(f"/api/v1/documents/{doc.id}", headers=_auth_headers(token_b)).status_code
            == 404
        )
        assert (
            client.get(
                f"/api/v1/documents/{doc.id}/download", headers=_auth_headers(token_b)
            ).status_code
            == 404
        )

        # Client A (owner) CAN access
        assert (
            client.get(f"/api/v1/documents/{doc.id}", headers=_auth_headers(token_a)).status_code
            == 200
        )

    def test_consultation_bola_and_link_case_protection(self, client: TestClient, db: Session):
        """Consultation access is restricted to participants; linking requires participant management."""
        client_a, token_a = _create_user(db, "cons_client", UserRole.CLIENT)
        lawyer_a, token_lawyer = _create_user(db, "cons_lawyer", UserRole.LAWYER)
        client_b, token_b = _create_user(db, "foreign_client", UserRole.CLIENT)

        # Fetch lawyer profile id
        l_prof = db.query(LawyerProfile).filter(LawyerProfile.user_id == lawyer_a.id).first()
        c_prof = db.query(ClientProfile).filter(ClientProfile.user_id == client_a.id).first()

        # Create consultation
        con = Consultation(
            id=uuid.uuid4(),
            client_id=c_prof.id,
            lawyer_id=l_prof.id,
            scheduled_at=datetime.now(UTC) + timedelta(days=1),
            duration_minutes=30,
            fee_amount=1000.0,
            currency="INR",
            status=ConsultationStatus.REQUESTED,
        )
        db.add(con)
        db.commit()

        # Foreign Client B receives 404 on consultation endpoints
        assert (
            client.get(f"/api/v1/consultations/{con.id}", headers=_auth_headers(token_b)).status_code
            == 404
        )
        assert (
            client.post(
                f"/api/v1/consultations/{con.id}/accept", headers=_auth_headers(token_b)
            ).status_code
            == 404
        )
        assert (
            client.post(
                f"/api/v1/consultations/{con.id}/join-token", headers=_auth_headers(token_b)
            ).status_code
            == 404
        )

        # Case linking security: Client A creates Case A
        case_res = client.post(
            "/api/v1/cases",
            headers=_auth_headers(token_a),
            json={"title": "Consultation Linked Case", "description": "Matter description"},
        )
        assert case_res.status_code == 201
        case_id = case_res.json()["id"]

        # Client A links consultation to Case A -> 200
        link_res = client.post(
            f"/api/v1/consultations/{con.id}/link-case",
            headers=_auth_headers(token_a),
            json={"case_id": case_id, "assign_lawyer": True},
        )
        assert link_res.status_code == 200

        # Now lawyer is assigned as participant to Case A
        part = (
            db.query(CaseParticipant)
            .filter(
                CaseParticipant.case_id == uuid.UUID(case_id),
                CaseParticipant.user_id == lawyer_a.id,
            )
            .first()
        )
        assert part is not None
        assert part.participant_role == ParticipantRole.LAWYER

    def test_profile_horizontal_isolation_and_admin_boundary(
        self, client: TestClient, db: Session
    ):
        """Cross-role profile mutation and non-admin access to admin endpoints are strictly blocked."""
        client_u, token_client = _create_user(db, "prof_client", UserRole.CLIENT)
        lawyer_u, token_lawyer = _create_user(db, "prof_lawyer", UserRole.LAWYER)
        admin_u, token_admin = _create_user(db, "admin_user", UserRole.ADMIN)

        # Client cannot update lawyer profile (403)
        assert (
            client.patch(
                "/api/v1/profiles/lawyer",
                headers=_auth_headers(token_client),
                json={"bio": "Should fail"},
            ).status_code
            == 403
        )

        # Lawyer cannot update client profile (403)
        assert (
            client.patch(
                "/api/v1/profiles/client",
                headers=_auth_headers(token_lawyer),
                json={"location": "Should fail"},
            ).status_code
            == 403
        )

        # Non-admin users cannot access admin overview or users (403)
        assert (
            client.get("/api/v1/admin/overview", headers=_auth_headers(token_client)).status_code
            == 403
        )
        assert (
            client.get("/api/v1/admin/users", headers=_auth_headers(token_lawyer)).status_code
            == 403
        )

        # Admin user CAN access
        admin_res = client.get("/api/v1/admin/overview", headers=_auth_headers(token_admin))
        assert admin_res.status_code == 200

    def test_mass_assignment_and_role_tampering_prevention(
        self, client: TestClient, db: Session
    ):
        """Attempts to escalate role or tamper with verification status via request bodies fail."""
        # 1. Registration cannot specify ADMIN role (403)
        reg_res = client.post(
            "/api/v1/auth/register",
            json={
                "email": f"hacker_{uuid.uuid4().hex[:4]}@example.com",
                "password": "Password123!",
                "full_name": "Privilege Escalation",
                "role": "ADMIN",
            },
        )
        assert reg_res.status_code == 403

        # 2. Schema extra fields protection (extra="forbid") on profiles
        _, token_client = _create_user(db, "safe_client", UserRole.CLIENT)
        res_tamper = client.patch(
            "/api/v1/profiles/client",
            headers=_auth_headers(token_client),
            json={"full_name": "Clean Name", "role": "ADMIN"},
        )
        assert res_tamper.status_code == 422  # Unprocessable Content (extra fields forbidden)

    def test_analytics_case_access_enforcement(self, client: TestClient, db: Session):
        """User cannot log product events referencing foreign cases they do not participate in."""
        client_a, token_a = _create_user(db, "analytics_a", UserRole.CLIENT)
        client_b, token_b = _create_user(db, "analytics_b", UserRole.CLIENT)

        # Client A creates case
        case_res = client.post(
            "/api/v1/cases",
            headers=_auth_headers(token_a),
            json={"title": "Analytics Case", "description": "For tracking metrics"},
        )
        assert case_res.status_code == 201
        case_id = case_res.json()["id"]

        # Client B attempts to forge analytics event referencing Case A -> 404
        assert (
            client.post(
                "/api/v1/analytics/events",
                headers=_auth_headers(token_b),
                json={"event_type": "CASE_UPDATED", "case_id": case_id},
            ).status_code
            == 404
        )

        # Client A logs event referencing their own case -> 201 RECORDED
        res_ok = client.post(
            "/api/v1/analytics/events",
            headers=_auth_headers(token_a),
            json={"event_type": "CASE_UPDATED", "case_id": case_id},
        )
        assert res_ok.status_code == 201
        assert res_ok.json()["status"] == "RECORDED"
