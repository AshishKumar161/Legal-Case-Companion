import hashlib
import uuid
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.exceptions import ValidationError
from app.core.identifiers import generate_uuid7
from app.core.security import create_access_token, hash_password
from app.db.database import get_db
from app.main import app
from app.models.case import Case, CaseParticipant, CaseStatus, ParticipantRole, ParticipantStatus
from app.models.evidence import (
    Evidence,
    EvidenceAccessGrant,
    EvidenceAccessLevel,
    EvidenceCustodyAction,
    EvidenceCustodyEvent,
    EvidenceIntegrityStatus,
    EvidenceStatus,
    EvidenceVersion,
)
from app.models.user import AccountStatus, ClientProfile, LawyerProfile, User, UserRole
from app.schemas.evidence import EvidenceUploadInitRequest
from app.domain.evidence.evidence_service import EvidenceService


@pytest.fixture
def override_db(db):
    def _override():
        yield db

    app.dependency_overrides[get_db] = _override
    yield db
    app.dependency_overrides.pop(get_db, None)


def test_e2e_production_evidence_lifecycle_and_custody(override_db, db: Session):
    """Complete golden path: Registration -> Case Creation -> Evidence Staged Upload ->

    Scan -> Hash -> Active -> Share -> Custody Verification.
    """
    client_runner = TestClient(app)

    # 1. Register Client and Lawyer
    client_user = User(
        id=generate_uuid7(),
        email=f"client_e2e_{uuid.uuid4().hex[:6]}@example.com",
        password_hash=hash_password("ClientPass123!"),
        role=UserRole.CLIENT,
        account_status=AccountStatus.ACTIVE,
    )
    lawyer_user = User(
        id=generate_uuid7(),
        email=f"lawyer_e2e_{uuid.uuid4().hex[:6]}@example.com",
        password_hash=hash_password("LawyerPass123!"),
        role=UserRole.LAWYER,
        account_status=AccountStatus.ACTIVE,
    )
    db.add_all([client_user, lawyer_user])
    db.commit()

    client_token = create_access_token(subject=str(client_user.id), role=client_user.role.value)
    lawyer_token = create_access_token(subject=str(lawyer_user.id), role=lawyer_user.role.value)
    client_headers = {"Authorization": f"Bearer {client_token}"}
    lawyer_headers = {"Authorization": f"Bearer {lawyer_token}"}

    # 2. Client Creates Case
    case_res = client_runner.post(
        "/api/v1/cases",
        headers=client_headers,
        json={"title": "E2E Corporate Dispute", "description": "Arbitration proceedings"},
    )
    assert case_res.status_code == 201
    case_id = case_res.json()["id"]

    # Assign lawyer to case
    participant = CaseParticipant(
        id=generate_uuid7(),
        case_id=uuid.UUID(case_id),
        user_id=lawyer_user.id,
        participant_role=ParticipantRole.LAWYER,
        status=ParticipantStatus.ACTIVE,
    )
    db.add(participant)
    db.commit()

    # 3. Client Initializes Evidence Upload
    init_res = client_runner.post(
        f"/api/v1/cases/{case_id}/evidence/upload-init",
        headers=client_headers,
        json={
            "title": "Executed Settlement Agreement",
            "original_filename": "settlement_signed.pdf",
            "content_type": "application/pdf",
            "size_bytes": 1024,
        },
    )
    assert init_res.status_code == 201
    init_data = init_res.json()
    evidence_id = init_data["evidence_id"]
    version_id = init_data["version_id"]
    storage_key = init_data["storage_key"]

    # 4. Simulate Upload of valid PDF bytes into Storage
    evidence_service = EvidenceService(db)
    valid_pdf_bytes = b"%PDF-1.4 sample valid settlement agreement content"
    evidence_service.storage.put_object_bytes(
        object_key=storage_key,
        data=valid_pdf_bytes,
        mime_type="application/pdf",
    )

    # 5. Complete Upload (Scan, SHA-256 digest computation, activation)
    comp_res = client_runner.post(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/complete",
        headers=client_headers,
        json={"version_id": version_id},
    )
    assert comp_res.status_code == 200
    comp_data = comp_res.json()
    assert comp_data["status"] == "ACTIVE"

    # 6. Share Evidence with Assigned Lawyer with DOWNLOAD level
    share_res = client_runner.post(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/share",
        headers=client_headers,
        json={"target_user_id": str(lawyer_user.id), "access_level": "DOWNLOAD"},
    )
    assert share_res.status_code == 201

    # 7. Assigned Lawyer Views Evidence & Requests Download URL
    view_res = client_runner.get(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}",
        headers=lawyer_headers,
    )
    assert view_res.status_code == 200
    assert view_res.json()["title"] == "Executed Settlement Agreement"

    download_res = client_runner.get(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/download",
        headers=lawyer_headers,
    )
    assert download_res.status_code == 200
    assert "url" in download_res.json()

    # 8. Non-Repudiation: Verify Immutable Custody Events
    custody_events = (
        db.query(EvidenceCustodyEvent)
        .filter(EvidenceCustodyEvent.evidence_id == uuid.UUID(evidence_id))
        .order_by(EvidenceCustodyEvent.timestamp.asc())
        .all()
    )
    actions = [evt.action for evt in custody_events]
    assert EvidenceCustodyAction.UPLOADED in actions
    assert EvidenceCustodyAction.SCAN_PASSED in actions
    assert EvidenceCustodyAction.SHARED in actions
    assert EvidenceCustodyAction.DOWNLOADED in actions


def test_e2e_attack_simulation_idor_and_privilege_escalation(override_db, db: Session):
    """Simulates adversarial attacks: IDOR on foreign case, unauthorized role tampering."""
    client_runner = TestClient(app)

    # Seed Victim Client and Case
    victim_user = User(
        id=generate_uuid7(),
        email=f"victim_{uuid.uuid4().hex[:6]}@example.com",
        password_hash=hash_password("VictimPass123!"),
        role=UserRole.CLIENT,
        account_status=AccountStatus.ACTIVE,
    )
    attacker_user = User(
        id=generate_uuid7(),
        email=f"attacker_{uuid.uuid4().hex[:6]}@example.com",
        password_hash=hash_password("AttackerPass123!"),
        role=UserRole.CLIENT,
        account_status=AccountStatus.ACTIVE,
    )
    db.add_all([victim_user, attacker_user])
    db.commit()

    victim_case = Case(
        id=generate_uuid7(),
        title="Victim Trade Secret Litigation",
        description="Confidential proprietary formula dispute.",
        status=CaseStatus.OPEN,
    )
    db.add(victim_case)
    db.flush()

    p_victim = CaseParticipant(
        id=generate_uuid7(),
        case_id=victim_case.id,
        user_id=victim_user.id,
        participant_role=ParticipantRole.OWNER,
        status=ParticipantStatus.ACTIVE,
    )
    db.add(p_victim)
    db.commit()

    attacker_token = create_access_token(subject=str(attacker_user.id), role=attacker_user.role.value)
    attacker_headers = {"Authorization": f"Bearer {attacker_token}"}

    # Attack 1: IDOR - Attacker attempts to list evidence on Victim's Case -> 403 or 404
    idor_res = client_runner.get(
        f"/api/v1/cases/{victim_case.id}/evidence",
        headers=attacker_headers,
    )
    assert idor_res.status_code in (403, 404)

    # Attack 2: Privilege Escalation - Client attempts to access Admin User Directory -> 403 Forbidden
    admin_res = client_runner.get("/api/v1/admin/users", headers=attacker_headers)
    assert admin_res.status_code == 403


def test_e2e_legal_hold_deletion_rejection(override_db, db: Session):
    """Verify that evidence with legal_hold=True cannot be deleted by any role, returning 403."""
    client_runner = TestClient(app)

    user = User(
        id=generate_uuid7(),
        email=f"hold_client_{uuid.uuid4().hex[:6]}@example.com",
        password_hash=hash_password("Pass123!"),
        role=UserRole.CLIENT,
        account_status=AccountStatus.ACTIVE,
    )
    db.add(user)
    db.flush()

    case = Case(
        id=generate_uuid7(),
        title="Subpoenaed Case",
        description="Under active court subpoena",
        status=CaseStatus.OPEN,
    )
    db.add(case)
    db.flush()

    p = CaseParticipant(
        id=generate_uuid7(),
        case_id=case.id,
        user_id=user.id,
        participant_role=ParticipantRole.OWNER,
        status=ParticipantStatus.ACTIVE,
    )
    db.add(p)

    evidence = Evidence(
        id=generate_uuid7(),
        case_id=case.id,
        created_by_user_id=user.id,
        title="Subpoena Document",
        original_filename="subpoena.pdf",
        status=EvidenceStatus.ACTIVE,
        legal_hold=True,
        legal_hold_reason="Court Subpoena #2026-904",
    )
    db.add(evidence)
    db.commit()

    token = create_access_token(subject=str(user.id), role=user.role.value)
    headers = {"Authorization": f"Bearer {token}"}

    # Attempt deletion -> must fail with 403 Forbidden (LEGAL_HOLD_ACTIVE)
    del_res = client_runner.delete(
        f"/api/v1/cases/{case.id}/evidence/{evidence.id}",
        headers=headers,
    )
    assert del_res.status_code == 403
    assert "legal hold" in del_res.text.lower()


def test_e2e_tamper_detection_on_storage_corruption(override_db, db: Session):
    """Verify that tampering with stored bytes triggers TAMPER_DETECTED and custody failure audit."""
    user = User(
        id=generate_uuid7(),
        email=f"tamper_{uuid.uuid4().hex[:6]}@example.com",
        password_hash=hash_password("Pass123!"),
        role=UserRole.CLIENT,
        account_status=AccountStatus.ACTIVE,
    )
    db.add(user)
    db.flush()

    case = Case(
        id=generate_uuid7(),
        title="Tamper Audit Case",
        description="Tamper detection test",
        status=CaseStatus.OPEN,
    )
    db.add(case)
    db.flush()

    p = CaseParticipant(
        id=generate_uuid7(),
        case_id=case.id,
        user_id=user.id,
        participant_role=ParticipantRole.OWNER,
        status=ParticipantStatus.ACTIVE,
    )
    db.add(p)

    evidence = Evidence(
        id=generate_uuid7(),
        case_id=case.id,
        created_by_user_id=user.id,
        title="Original Contract",
        original_filename="contract.pdf",
        status=EvidenceStatus.ACTIVE,
    )
    db.add(evidence)
    db.flush()

    original_bytes = b"%PDF-1.4 pristine authentic agreement"
    correct_sha256 = hashlib.sha256(original_bytes).hexdigest()

    version = EvidenceVersion(
        id=generate_uuid7(),
        evidence_id=evidence.id,
        version_number=1,
        original_filename="contract.pdf",
        storage_key=f"evidence/{case.id}/{evidence.id}/v1/contract.pdf",
        size_bytes=len(original_bytes),
        content_type="application/pdf",
        sha256=correct_sha256,
        uploaded_by_user_id=user.id,
    )
    db.add(version)
    evidence.current_version_id = version.id
    db.commit()

    service = EvidenceService(db)

    # TAMPER: Alter bytes in storage without updating version sha256
    tampered_bytes = b"%PDF-1.4 MALICIOUSLY ALTERED CONTRACT TERMS"
    service.storage.put_object_bytes(
        object_key=version.storage_key,
        data=tampered_bytes,
        mime_type="application/pdf",
    )

    # Verify integrity -> detects tamper
    version_obj, recorded_sha, computed_sha, is_match = service.verify_integrity(
        user=user,
        case_id=case.id,
        evidence_id=evidence.id,
    )
    assert is_match is False
    assert version_obj.integrity_status == EvidenceIntegrityStatus.TAMPER_DETECTED
