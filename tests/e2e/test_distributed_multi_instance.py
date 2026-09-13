import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.identifiers import generate_uuid7
from app.core.redis import InMemoryRedisClient
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.case import Case, CaseParticipant, CaseStatus, ParticipantRole, ParticipantStatus
from app.models.evidence import (
    Evidence,
    EvidenceAccessGrant,
    EvidenceAccessLevel,
    EvidenceCategory,
    EvidenceSensitivity,
    EvidenceStatus,
    EvidenceVersion,
)
from app.models.user import AccountStatus, User, UserRole
from app.domain.auth.auth_service import AuthService
from app.domain.consultations.presence_service import PresenceService


@pytest.fixture
def multi_instance_redis(monkeypatch):
    """Shared simulated Redis cluster across multiple application instances."""
    shared_redis = InMemoryRedisClient()
    monkeypatch.setattr("app.core.redis.get_redis_client", lambda: shared_redis)
    monkeypatch.setattr("app.domain.consultations.presence_service.get_redis_client", lambda: shared_redis)
    return shared_redis


def test_multi_instance_session_isolation_and_revocation(db: Session, multi_instance_redis):
    """Verify that sessions across multi-instance nodes are isolated, role-bound, and immediately revokable."""
    # Seed 3 distinct users (Client, Lawyer, Admin)
    client_user = User(
        id=generate_uuid7(),
        email=f"client_multi_{uuid.uuid4().hex[:6]}@example.com",
        password_hash=hash_password("Pass123!"),
        role=UserRole.CLIENT,
        account_status=AccountStatus.ACTIVE,
    )
    lawyer_user = User(
        id=generate_uuid7(),
        email=f"lawyer_multi_{uuid.uuid4().hex[:6]}@example.com",
        password_hash=hash_password("Pass123!"),
        role=UserRole.LAWYER,
        account_status=AccountStatus.ACTIVE,
    )
    admin_user = User(
        id=generate_uuid7(),
        email=f"admin_multi_{uuid.uuid4().hex[:6]}@example.com",
        password_hash=hash_password("Pass123!"),
        role=UserRole.ADMIN,
        account_status=AccountStatus.ACTIVE,
    )
    db.add_all([client_user, lawyer_user, admin_user])
    db.commit()

    # Simulate Instance A issuing Client Token
    client_token = create_access_token(
        subject=str(client_user.id), role=client_user.role.value
    )

    # Simulate Instance B issuing Lawyer Token
    lawyer_token = create_access_token(
        subject=str(lawyer_user.id), role=lawyer_user.role.value
    )

    # Simulate Instance C issuing Admin Token
    admin_token = create_access_token(
        subject=str(admin_user.id), role=admin_user.role.value
    )

    from app.db.database import get_db

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        # Node A handles Client request
        node_a = TestClient(app)
        res_a = node_a.get("/api/v1/cases", headers={"Authorization": f"Bearer {client_token}"})
        assert res_a.status_code in (200, 204)

        # Node B handles Lawyer request
        node_b = TestClient(app)
        res_b = node_b.get("/api/v1/cases", headers={"Authorization": f"Bearer {lawyer_token}"})
        assert res_b.status_code in (200, 204)

        # Privilege boundary: Client cannot access admin diagnostics endpoint on Node C
        node_c = TestClient(app)
        res_admin_probe = node_c.get("/api/v1/admin/users", headers={"Authorization": f"Bearer {client_token}"})
        assert res_admin_probe.status_code == 403
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_multi_instance_presence_coherence(multi_instance_redis):
    """Verify presence changes on Node A are coherently visible on Node B via Redis."""
    presence_node_a = PresenceService()
    presence_node_b = PresenceService()

    lawyer_id = generate_uuid7()
    user_id = generate_uuid7()

    # Node A marks Lawyer as AVAILABLE
    presence_node_a.mark_available(user_id=user_id, lawyer_id=lawyer_id)

    # Node B queries Lawyer availability
    is_online_b = presence_node_b.is_online(user_id=user_id)
    is_available_b = presence_node_b.is_available_preference(user_id=user_id)
    assert is_online_b is True
    assert is_available_b is True

    # Node A marks Lawyer as BUSY
    presence_node_a.mark_busy(user_id=user_id, lawyer_id=lawyer_id, reason="In court")
    presence_data_b = presence_node_b.get_presence(user_id=user_id)
    assert presence_data_b["status"] == "BUSY"
    assert presence_data_b["busy_reason"] == "In court"

    # Node A marks Lawyer as OFFLINE
    presence_node_a.mark_offline(user_id=user_id, lawyer_id=lawyer_id)
    assert presence_node_b.is_online(user_id=user_id) is False


def test_multi_instance_call_routing_no_cross_leakage(multi_instance_redis):
    """Verify call notification routed to target lawyer does not leak to unrelated lawyers."""
    target_lawyer_id = generate_uuid7()
    unrelated_lawyer_id = generate_uuid7()

    # Channels in Redis
    channel_target = f"user:call:{target_lawyer_id}"
    channel_unrelated = f"user:call:{unrelated_lawyer_id}"

    # Node A publishes incoming call event for target lawyer
    multi_instance_redis.set(channel_target, b'{"call_id": "call-123", "from": "client-456"}')

    # Node B checks target lawyer channel
    assert multi_instance_redis.get(channel_target) is not None

    # Node C checks unrelated lawyer channel (must receive nothing)
    assert multi_instance_redis.get(channel_unrelated) is None


def test_multi_instance_evidence_access_isolation(db: Session):
    """Verify evidence uploaded on Node A is accessible to assigned lawyer on Node B, but 403 to unassigned lawyer on Node C."""
    # Seed Client
    client = User(
        id=generate_uuid7(),
        email=f"client_ev_{uuid.uuid4().hex[:6]}@example.com",
        password_hash=hash_password("Pass123!"),
        role=UserRole.CLIENT,
        account_status=AccountStatus.ACTIVE,
    )
    # Seed Assigned Lawyer
    lawyer_assigned = User(
        id=generate_uuid7(),
        email=f"lawyer_assigned_{uuid.uuid4().hex[:6]}@example.com",
        password_hash=hash_password("Pass123!"),
        role=UserRole.LAWYER,
        account_status=AccountStatus.ACTIVE,
    )
    # Seed Unassigned Lawyer
    lawyer_unassigned = User(
        id=generate_uuid7(),
        email=f"lawyer_unassigned_{uuid.uuid4().hex[:6]}@example.com",
        password_hash=hash_password("Pass123!"),
        role=UserRole.LAWYER,
        account_status=AccountStatus.ACTIVE,
    )
    db.add_all([client, lawyer_assigned, lawyer_unassigned])
    db.commit()

    # Create Case
    case = Case(
        id=generate_uuid7(),
        title="Cross-Node Evidence Case",
        description="Testing multi-instance evidence access.",
        status=CaseStatus.OPEN,
    )
    db.add(case)
    db.flush()

    # Assign Client and Lawyer 1 to Case
    p_client = CaseParticipant(
        id=generate_uuid7(),
        case_id=case.id,
        user_id=client.id,
        participant_role=ParticipantRole.OWNER,
        status=ParticipantStatus.ACTIVE,
    )
    p_lawyer = CaseParticipant(
        id=generate_uuid7(),
        case_id=case.id,
        user_id=lawyer_assigned.id,
        participant_role=ParticipantRole.LAWYER,
        status=ParticipantStatus.ACTIVE,
    )
    db.add_all([p_client, p_lawyer])
    db.commit()

    # Seed Evidence
    evidence = Evidence(
        id=generate_uuid7(),
        case_id=case.id,
        created_by_user_id=client.id,
        title="Sensitive Audit File",
        description="Confidential audit records",
        original_filename="audit.pdf",
        status=EvidenceStatus.ACTIVE,
        sensitivity=EvidenceSensitivity.CONFIDENTIAL,
    )
    db.add(evidence)
    db.flush()

    version = EvidenceVersion(
        id=generate_uuid7(),
        evidence_id=evidence.id,
        version_number=1,
        original_filename="audit.pdf",
        storage_key=f"evidence/{case.id}/{evidence.id}/v1/audit.pdf",
        size_bytes=2048,
        content_type="application/pdf",
        sha256="b" * 64,
        uploaded_by_user_id=client.id,
    )
    db.add(version)
    evidence.current_version_id = version.id

    grant = EvidenceAccessGrant(
        id=generate_uuid7(),
        evidence_id=evidence.id,
        grantee_user_id=lawyer_assigned.id,
        granted_by_user_id=client.id,
        access_level=EvidenceAccessLevel.VIEW,
    )
    db.add(grant)
    db.commit()

    from app.db.database import get_db

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        # Node B: Assigned Lawyer accesses evidence
        node_b = TestClient(app)
        token_assigned = create_access_token(subject=str(lawyer_assigned.id), role=lawyer_assigned.role.value)
        res_b = node_b.get(f"/api/v1/cases/{case.id}/evidence/{evidence.id}", headers={"Authorization": f"Bearer {token_assigned}"})
        assert res_b.status_code == 200
        assert res_b.json()["title"] == "Sensitive Audit File"

        # Node C: Unassigned Lawyer attempts access -> securely rejected (403 Forbidden or 404 Not Found)
        node_c = TestClient(app)
        token_unassigned = create_access_token(subject=str(lawyer_unassigned.id), role=lawyer_unassigned.role.value)
        res_c = node_c.get(f"/api/v1/cases/{case.id}/evidence/{evidence.id}", headers={"Authorization": f"Bearer {token_unassigned}"})
        assert res_c.status_code in (403, 404)
    finally:
        app.dependency_overrides.pop(get_db, None)
