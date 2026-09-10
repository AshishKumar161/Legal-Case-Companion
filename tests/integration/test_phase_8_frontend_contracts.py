"""Phase 8: Frontend-to-Backend Contract Integration Tests.

Validates the contracts, payload schemas, error envelopes, enums,
and data flows between the Next.js TypeScript frontend and FastAPI backend.
"""

import uuid
from datetime import datetime, UTC, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User, UserRole, AccountStatus, LawyerProfile
from app.models.consultation import Consultation, ConsultationStatus
from app.models.case import Case, CaseStatus, ParticipantRole, CaseParticipant, ParticipantStatus
from app.core.identifiers import generate_uuid7


def _register_and_login(client: TestClient, db: Session, email: str, role: UserRole = UserRole.CLIENT) -> tuple[dict[str, str], User]:
    reg_res = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Password123!", "full_name": "Test Contract User", "role": role.value},
    )
    assert reg_res.status_code == 201, reg_res.text
    user_id = reg_res.json()["id"]

    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    assert login_res.status_code == 200, login_res.text
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    user = db.query(User).filter(User.id == user_id).first()
    assert user is not None
    return headers, user


class TestFrontendBackendContracts:
    """Contract verification between TypeScript client and FastAPI endpoints."""

    def test_error_response_envelope_contract(self, client: TestClient):
        """Frontend ApiError expects either standard error envelope or detail message."""
        # 1. Test 401 Unauthorized
        res_401 = client.get("/api/v1/auth/me")
        assert res_401.status_code == 401
        data_401 = res_401.json()
        assert "error" in data_401 or "detail" in data_401

        # 2. Test 404 Not Found
        res_404 = client.get("/api/v1/cases/00000000-0000-0000-0000-000000000000")
        assert res_404.status_code in (401, 404)

        # 3. Test 422 Validation Error
        res_422 = client.post("/api/v1/auth/login", json={"email": "not-an-email"})
        assert res_422.status_code == 422
        data_422 = res_422.json()
        assert "detail" in data_422 or "error" in data_422

    def test_auth_login_contract_matches_frontend_type(self, client: TestClient, db: Session):
        """Frontend authApi.login expects LoginResponse with user object."""
        email = f"contract_test_{uuid.uuid4().hex[:8]}@example.com"
        headers, user = _register_and_login(client, db, email, UserRole.CLIENT)

        res = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "Password123!"},
        )
        assert res.status_code == 200
        data = res.json()

        # Check LoginResponse contract: access_token, refresh_token, token_type
        assert "access_token" in data
        assert "refresh_token" in data
        assert data.get("token_type") == "bearer"

        # Contract: Frontend AuthProvider hydrates UserItem from /api/v1/auth/me
        me_headers = {"Authorization": f"Bearer {data['access_token']}"}
        me_res = client.get("/api/v1/auth/me", headers=me_headers)
        assert me_res.status_code == 200
        user_data = me_res.json()
        # Check UserItem contract: id, email, role, account_status
        assert user_data["email"] == email
        assert user_data["role"] == "CLIENT"
        assert user_data["account_status"] in ("ACTIVE", "REGISTERED")

    def test_case_workspace_contract_matches_frontend_type(self, client: TestClient, db: Session):
        """Frontend casesApi.getWorkspace expects CaseWorkspaceResponse."""
        headers, user = _register_and_login(client, db, f"ws_{uuid.uuid4().hex[:8]}@example.com", UserRole.CLIENT)

        case = Case(
            title="Contract Verification Matter",
            description="Testing schema alignment",
            status=CaseStatus.OPEN,
        )
        db.add(case)
        db.flush()

        part = CaseParticipant(
            case_id=case.id,
            user_id=user.id,
            participant_role=ParticipantRole.OWNER,
            status=ParticipantStatus.ACTIVE,
        )
        db.add(part)
        db.commit()

        res = client.get(f"/api/v1/cases/{case.id}/workspace", headers=headers)
        assert res.status_code == 200
        data = res.json()

        # Check CaseWorkspaceResponse fields
        assert "case" in data
        assert str(data["case"]["id"]) == str(case.id)
        assert data["case"]["title"] == "Contract Verification Matter"
        assert data["case"]["status"] == "OPEN"
        assert "effective_permissions" in data
        assert isinstance(data["effective_permissions"], list)
        assert "participants" in data
        assert isinstance(data["participants"], list)
        assert "document_count" in data
        assert "tasks_summary" in data
        assert "upcoming_deadlines" in data
        assert "notes_count" in data
        assert "recent_activities" in data

    def test_case_status_enums_contract(self):
        """Ensure all backend CaseStatus enum values are accepted by frontend CaseItem['status']."""
        frontend_statuses = {
            "DRAFT",
            "OPEN",
            "IN_REVIEW",
            "PENDING_COURT",
            "IN_PROGRESS",
            "CLOSED",
            "CANCELLED",
            "ARCHIVED",
        }
        backend_statuses = {s.value for s in CaseStatus}
        assert backend_statuses.issubset(frontend_statuses)

    def test_participant_role_enums_contract(self):
        """Ensure backend ParticipantRole enum values are accepted by frontend CaseParticipantItem['participant_role']."""
        frontend_roles = {
            "OWNER",
            "CLIENT",
            "PRIMARY_LAWYER",
            "COLLABORATING_LAWYER",
            "LAWYER",
            "PARALEGAL",
            "VIEWER",
            "OBSERVER",
        }
        backend_roles = {r.value for r in ParticipantRole}
        assert backend_roles.issubset(frontend_roles)

    def test_download_report_binary_blob_contract(self, client: TestClient, db: Session):
        """Frontend casesApi.downloadReport expects a downloadable binary stream."""
        headers, user = _register_and_login(client, db, f"rep_{uuid.uuid4().hex[:8]}@example.com", UserRole.CLIENT)

        case = Case(
            title="Download Report Case",
            description="Testing binary report streaming",
            status=CaseStatus.OPEN,
        )
        db.add(case)
        db.flush()

        part = CaseParticipant(
            case_id=case.id,
            user_id=user.id,
            participant_role=ParticipantRole.OWNER,
            status=ParticipantStatus.ACTIVE,
        )
        db.add(part)
        db.commit()

        # Download Markdown Report
        res_md = client.get(
            f"/api/v1/cases/{case.id}/report?format=markdown&download=true",
            headers=headers,
        )
        assert res_md.status_code == 200
        assert "text/markdown" in res_md.headers.get("content-type", "")
        assert "attachment" in res_md.headers.get("content-disposition", "")
        assert len(res_md.content) > 0

        # Download JSON Report
        res_json = client.get(
            f"/api/v1/cases/{case.id}/report?format=json&download=true",
            headers=headers,
        )
        assert res_json.status_code == 200
        assert "application/json" in res_json.headers.get("content-type", "")
        assert "attachment" in res_json.headers.get("content-disposition", "")

    def test_legal_authorities_hybrid_search_contract(self, client: TestClient, db: Session):
        """Frontend aiApi.searchLegalAuthorities expects results list with metadata."""
        headers, user = _register_and_login(client, db, f"kan_{uuid.uuid4().hex[:8]}@example.com", UserRole.LAWYER)

        res = client.post(
            "/api/v1/legal-authorities/search",
            headers=headers,
            json={"query": "Section 138 Negotiable Instruments Act dishonour of cheque", "top_k": 3, "search_mode": "HYBRID"},
        )
        assert res.status_code == 200
        data = res.json()
        assert "results" in data
        assert isinstance(data["results"], list)

    def test_consultation_video_join_contract(self, client: TestClient, db: Session):
        """Frontend consultationsApi.joinVideoMeeting expects room_id, token, provider, ice_servers."""
        client_headers, client_user = _register_and_login(
            client, db, f"con_cl_{uuid.uuid4().hex[:8]}@example.com", UserRole.CLIENT
        )
        lawyer_headers, lawyer_user = _register_and_login(
            client, db, f"con_lw_{uuid.uuid4().hex[:8]}@example.com", UserRole.LAWYER
        )

        consultation = Consultation(
            id=generate_uuid7(),
            client_id=client_user.client_profile.id,
            lawyer_id=lawyer_user.lawyer_profile.id,
            scheduled_at=datetime.now(UTC) + timedelta(minutes=15),
            duration_minutes=30,
            status=ConsultationStatus.ACCEPTED,
            fee_amount=1500.0,
            currency="INR",
        )
        db.add(consultation)
        db.commit()

        # 1. Test access-status
        res_status = client.get(
            f"/api/v1/consultations/{consultation.id}/video/access-status?bypass_time=true",
            headers=client_headers,
        )
        assert res_status.status_code == 200
        status_data = res_status.json()
        assert "can_join" in status_data
        assert "is_authorized" in status_data
        assert "scheduled_at_ist" in status_data

        # 2. Test video join
        res = client.get(
            f"/api/v1/consultations/{consultation.id}/video/join?bypass_time=true",
            headers=client_headers,
        )
        assert res.status_code == 200
        data = res.json()
        assert "room_id" in data
        assert "token" in data
        assert "provider" in data
        assert "ice_servers" in data
        assert "is_live" in data
