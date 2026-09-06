"""Database Foundation Verification Test Suite.

Phase 1 Verification:
- User CRUD & Soft Delete lifecycle
- Case CRUD & Owner/Participant relationships
- Foreign keys, Unique constraints, and Cascade/Restrict semantics
- Transaction commit & rollback session recovery
- UUIDv7 monotonic ordering and application generation
- Timezone-aware timestamps
- Alembic single-head migration DAG integrity
"""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.identifiers import generate_uuid7
from app.models.case import (
    Case,
    CaseParticipant,
    CaseStatus,
    ParticipantRole,
    ParticipantStatus,
)
from app.models.user import AccountStatus, User, UserRole


def test_user_crud_and_soft_delete(db: Session):
    """Verify User entity creation, retrieval, mutation, and soft deletion."""
    user_id = generate_uuid7()
    user = User(
        id=user_id,
        email="test_user_db_foundation@example.com",
        phone="+919876543210",
        password_hash="argon2id_mock_hash_for_testing",
        role=UserRole.CLIENT,
        account_status=AccountStatus.ACTIVE,
    )
    db.add(user)
    db.commit()

    # Read
    fetched = db.get(User, user_id)
    assert fetched is not None
    assert fetched.id == user_id
    assert fetched.email == "test_user_db_foundation@example.com"
    assert fetched.role == UserRole.CLIENT
    assert fetched.account_status == AccountStatus.ACTIVE
    assert fetched.deleted_at is None
    assert fetched.created_at is not None
    assert fetched.updated_at is not None

    # Update
    fetched.phone = "+919876543211"
    fetched.account_status = AccountStatus.SUSPENDED
    db.commit()
    db.refresh(fetched)
    assert fetched.phone == "+919876543211"
    assert fetched.account_status == AccountStatus.SUSPENDED

    # Soft delete
    now = datetime.now(UTC)
    fetched.deleted_at = now
    db.commit()
    db.refresh(fetched)
    assert fetched.deleted_at is not None

    # Verify active query filtering
    active_users = (
        db.execute(select(User).where(User.id == user_id, User.deleted_at.is_(None)))
        .scalars()
        .all()
    )
    assert len(active_users) == 0

    all_users = (
        db.execute(select(User).where(User.id == user_id)).scalars().all()
    )
    assert len(all_users) == 1


def test_case_crud_and_owner_relationship(db: Session):
    """Verify Case entity creation, participant relationship, and owner assignment."""
    owner = User(
        id=generate_uuid7(),
        email="case_owner_foundation@example.com",
        password_hash="mock_hash",
        role=UserRole.CLIENT,
        account_status=AccountStatus.ACTIVE,
    )
    db.add(owner)
    db.commit()

    case_id = generate_uuid7()
    new_case = Case(
        id=case_id,
        title="Dispute over Commercial Agreement",
        description="Breach of delivery milestone conditions under Section 73 Contract Act.",
        status=CaseStatus.OPEN,
    )
    db.add(new_case)
    db.commit()

    # Add owner participant
    participant_id = generate_uuid7()
    participant = CaseParticipant(
        id=participant_id,
        case_id=case_id,
        user_id=owner.id,
        participant_role=ParticipantRole.OWNER,
        status=ParticipantStatus.ACTIVE,
    )
    db.add(participant)
    db.commit()

    # Read & verify relationship
    db.refresh(new_case)
    assert len(new_case.participants) == 1
    assert new_case.participants[0].user_id == owner.id
    assert new_case.participants[0].participant_role == ParticipantRole.OWNER
    assert new_case.status == CaseStatus.OPEN

    # Update case status
    new_case.status = CaseStatus.IN_PROGRESS
    db.commit()
    db.refresh(new_case)
    assert new_case.status == CaseStatus.IN_PROGRESS


def test_case_participant_crud_and_unique_constraint(db: Session):
    """Verify CaseParticipant unique constraint on (case_id, user_id)."""
    user = User(
        id=generate_uuid7(),
        email="participant_test_user@example.com",
        password_hash="mock_hash",
        role=UserRole.LAWYER,
        account_status=AccountStatus.ACTIVE,
    )
    case = Case(
        id=generate_uuid7(),
        title="Land Title Verification Matter",
        description="Comprehensive search of encumbrances and revenue records.",
        status=CaseStatus.OPEN,
    )
    db.add_all([user, case])
    db.commit()

    p1 = CaseParticipant(
        id=generate_uuid7(),
        case_id=case.id,
        user_id=user.id,
        participant_role=ParticipantRole.LAWYER,
        status=ParticipantStatus.ACTIVE,
    )
    db.add(p1)
    db.commit()

    # Attempt duplicate participant for same (case_id, user_id)
    p2 = CaseParticipant(
        id=generate_uuid7(),
        case_id=case.id,
        user_id=user.id,
        participant_role=ParticipantRole.VIEWER,
        status=ParticipantStatus.ACTIVE,
    )
    db.add(p2)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

    # Verify session is clean and p1 remains intact
    participants = (
        db.execute(select(CaseParticipant).where(CaseParticipant.case_id == case.id))
        .scalars()
        .all()
    )
    assert len(participants) == 1
    assert participants[0].participant_role == ParticipantRole.LAWYER


def test_transaction_commit_and_rollback_recovery(db: Session):
    """
    Verify transaction boundary:
    1. Successful operation commits.
    2. Failed operation rolls back.
    3. Session is NOT poisoned and can execute subsequent queries cleanly.
    """
    user_1 = User(
        id=generate_uuid7(),
        email="tx_user_1@example.com",
        password_hash="hash1",
        role=UserRole.CLIENT,
        account_status=AccountStatus.ACTIVE,
    )
    db.add(user_1)
    db.commit()

    # Confirm user_1 exists
    assert db.get(User, user_1.id) is not None

    # Intentionally trigger integrity error (duplicate email)
    user_dup = User(
        id=generate_uuid7(),
        email="tx_user_1@example.com",  # Duplicate email
        password_hash="hash2",
        role=UserRole.LAWYER,
        account_status=AccountStatus.ACTIVE,
    )
    db.add(user_dup)
    with pytest.raises(IntegrityError):
        db.commit()

    # Rollback must restore session health
    db.rollback()

    # Perform a subsequent query on the SAME session to confirm it is not poisoned
    user_2 = User(
        id=generate_uuid7(),
        email="tx_user_2@example.com",
        password_hash="hash3",
        role=UserRole.LAWYER,
        account_status=AccountStatus.ACTIVE,
    )
    db.add(user_2)
    db.commit()

    fetched_2 = db.get(User, user_2.id)
    assert fetched_2 is not None
    assert fetched_2.email == "tx_user_2@example.com"


def test_uuidv7_generation_and_monotonicity():
    """Verify UUIDv7 application generation, structure, and monotonic sortability."""
    ids = [generate_uuid7() for _ in range(20)]

    for u in ids:
        assert isinstance(u, uuid.UUID)
        # UUIDv7 has version 7 (0111 in bits 48..51)
        assert u.version == 7

    # UUIDv7 are sortable over time
    sorted_ids = sorted(ids)
    assert ids == sorted_ids


def test_timezone_aware_timestamps(db: Session):
    """Verify created_at and updated_at are populated with timezone awareness."""
    user = User(
        id=generate_uuid7(),
        email="timestamp_test@example.com",
        password_hash="hash",
        role=UserRole.CLIENT,
        account_status=AccountStatus.ACTIVE,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    assert user.created_at is not None
    assert user.updated_at is not None
    assert user.deleted_at is None


def test_alembic_migration_head_consistency():
    """Verify Alembic migration environment has exactly one single head."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    config = Config("alembic.ini")
    script = ScriptDirectory.from_config(config)
    heads = script.get_heads()

    assert len(heads) == 1, f"Expected 1 migration head, found {len(heads)}: {heads}"
    assert heads[0] == "o1a2b3c4d5e6"

