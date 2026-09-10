import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.identifiers import generate_uuid7
from app.core.security import hash_password
from app.models.audit import AuditEvent
from app.models.base import Base
from app.models.case import (
    Case,
    CaseParticipant,
    CaseStatus,
    ParticipantRole,
    ParticipantStatus,
)
from app.models.evidence import (
    Evidence,
    EvidenceCustodyAction,
    EvidenceCustodyEvent,
    EvidenceStatus,
    EvidenceVersion,
)
from app.models.job import BackgroundJob, JobStatus, JobType
from app.models.outbox import OutboxEvent, OutboxStatus
from app.models.user import AccountStatus, ClientProfile, LawyerProfile, User, UserRole


def test_database_backup_and_restore_cycle():
    """Validates full database export/backup and restore into an isolated environment.

    Verifies users, cases, evidence, custody, outbox, and jobs are faithfully restored
    with referential integrity.
    """
    # 1. Source Database Engine
    source_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=source_engine)
    SourceSession = sessionmaker(bind=source_engine)

    with SourceSession() as db:
        # Seed Client User
        client_user = User(
            id=generate_uuid7(),
            email=f"client_backup_{uuid.uuid4().hex[:6]}@example.com",
            password_hash=hash_password("BackupTestPass123!"),
            role=UserRole.CLIENT,
            account_status=AccountStatus.ACTIVE,
        )
        db.add(client_user)
        db.flush()

        client_prof = ClientProfile(
            id=generate_uuid7(),
            user_id=client_user.id,
            full_name="Backup Test Client",
            location="New Delhi",
        )
        db.add(client_prof)

        # Seed Lawyer User
        lawyer_user = User(
            id=generate_uuid7(),
            email=f"lawyer_backup_{uuid.uuid4().hex[:6]}@example.com",
            password_hash=hash_password("BackupTestPass123!"),
            role=UserRole.LAWYER,
            account_status=AccountStatus.ACTIVE,
        )
        db.add(lawyer_user)
        db.flush()

        lawyer_prof = LawyerProfile(
            id=generate_uuid7(),
            user_id=lawyer_user.id,
            full_name="Advocate Backup",
            location="Delhi High Court",
        )
        db.add(lawyer_prof)

        # Seed Legal Case
        case = Case(
            id=generate_uuid7(),
            title="Commercial Contract Dispute",
            description="Arbitration dispute backup test.",
            status=CaseStatus.OPEN,
        )
        db.add(case)
        db.flush()

        # Seed Case Participants (Client as OWNER, Lawyer as LAWYER)
        client_participant = CaseParticipant(
            id=generate_uuid7(),
            case_id=case.id,
            user_id=client_user.id,
            participant_role=ParticipantRole.OWNER,
            status=ParticipantStatus.ACTIVE,
        )
        db.add(client_participant)

        lawyer_participant = CaseParticipant(
            id=generate_uuid7(),
            case_id=case.id,
            user_id=lawyer_user.id,
            participant_role=ParticipantRole.LAWYER,
            status=ParticipantStatus.ACTIVE,
        )
        db.add(lawyer_participant)

        # Seed Evidence & Versions
        evidence = Evidence(
            id=generate_uuid7(),
            case_id=case.id,
            created_by_user_id=client_user.id,
            title="Master Services Agreement",
            description="Executed arbitration agreement",
            original_filename="msa_signed.pdf",
            status=EvidenceStatus.ACTIVE,
            legal_hold=True,
        )
        db.add(evidence)
        db.flush()

        version = EvidenceVersion(
            id=generate_uuid7(),
            evidence_id=evidence.id,
            version_number=1,
            original_filename="msa_signed.pdf",
            storage_key=f"evidence/{case.id}/{evidence.id}/v1/msa_signed.pdf",
            size_bytes=4096,
            content_type="application/pdf",
            sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            uploaded_by_user_id=client_user.id,
        )
        db.add(version)
        db.flush()

        # Seed Custody Event
        custody = EvidenceCustodyEvent(
            id=generate_uuid7(),
            evidence_id=evidence.id,
            version_id=version.id,
            actor_user_id=client_user.id,
            action=EvidenceCustodyAction.UPLOADED,
            event_metadata={"test": "backup_validation"},
        )
        db.add(custody)

        # Seed Transactional Outbox Record
        outbox = OutboxEvent(
            id=generate_uuid7(),
            event_type="EVIDENCE_UPLOADED",
            aggregate_type="evidence",
            aggregate_id=evidence.id,
            status=OutboxStatus.PENDING,
            payload={"evidence_id": str(evidence.id)},
        )
        db.add(outbox)

        # Seed Background Job
        job = BackgroundJob(
            id=generate_uuid7(),
            job_type=JobType.EVIDENCE_INTEGRITY_AUDIT,
            status=JobStatus.PENDING,
            payload={"audit_scope": "all"},
        )
        db.add(job)

        db.commit()

        # Capture identifiers for verification
        saved_client_id = client_user.id
        saved_lawyer_id = lawyer_user.id
        saved_case_id = case.id
        saved_evidence_id = evidence.id
        saved_version_id = version.id
        saved_custody_id = custody.id
        saved_outbox_id = outbox.id
        saved_job_id = job.id

    # 2. Extract Backup Snapshot
    backup_data: dict[str, list[dict]] = {}
    with SourceSession() as db:
        for model_cls, key in [
            (User, "users"),
            (ClientProfile, "client_profiles"),
            (LawyerProfile, "lawyer_profiles"),
            (Case, "cases"),
            (CaseParticipant, "case_participants"),
            (Evidence, "evidence"),
            (EvidenceVersion, "evidence_versions"),
            (EvidenceCustodyEvent, "evidence_custody_events"),
            (OutboxEvent, "outbox_events"),
            (BackgroundJob, "background_jobs"),
        ]:
            records = db.query(model_cls).all()
            backup_data[key] = [
                {c.name: getattr(r, c.name) for c in r.__table__.columns}
                for r in records
            ]

    assert len(backup_data["users"]) == 2
    assert len(backup_data["cases"]) == 1
    assert len(backup_data["evidence"]) == 1

    # 3. Restore Into Clean, Isolated Engine
    target_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=target_engine)
    TargetSession = sessionmaker(bind=target_engine)

    with TargetSession() as target_db:
        # Restore in topological dependency order
        for row in backup_data["users"]:
            target_db.add(User(**row))
        target_db.flush()

        for row in backup_data["client_profiles"]:
            target_db.add(ClientProfile(**row))
        for row in backup_data["lawyer_profiles"]:
            target_db.add(LawyerProfile(**row))
        for row in backup_data["cases"]:
            target_db.add(Case(**row))
        target_db.flush()

        for row in backup_data["case_participants"]:
            target_db.add(CaseParticipant(**row))
        for row in backup_data["evidence"]:
            target_db.add(Evidence(**row))
        target_db.flush()

        for row in backup_data["evidence_versions"]:
            target_db.add(EvidenceVersion(**row))
        target_db.flush()

        for row in backup_data["evidence_custody_events"]:
            target_db.add(EvidenceCustodyEvent(**row))
        for row in backup_data["outbox_events"]:
            target_db.add(OutboxEvent(**row))
        for row in backup_data["background_jobs"]:
            target_db.add(BackgroundJob(**row))

        target_db.commit()

    # 4. Verify Integrity on Restored Database
    with TargetSession() as target_db:
        restored_client = target_db.query(User).filter(User.id == saved_client_id).first()
        assert restored_client is not None
        assert restored_client.client_profile.full_name == "Backup Test Client"

        restored_case = target_db.query(Case).filter(Case.id == saved_case_id).first()
        assert restored_case is not None
        assert len(restored_case.participants) == 2

        restored_evidence = target_db.query(Evidence).filter(Evidence.id == saved_evidence_id).first()
        assert restored_evidence is not None
        assert restored_evidence.legal_hold is True
        assert len(restored_evidence.versions) == 1
        assert restored_evidence.versions[0].id == saved_version_id

        restored_custody = target_db.query(EvidenceCustodyEvent).filter(EvidenceCustodyEvent.id == saved_custody_id).first()
        assert restored_custody is not None
        assert restored_custody.action == EvidenceCustodyAction.UPLOADED

        restored_outbox = target_db.query(OutboxEvent).filter(OutboxEvent.id == saved_outbox_id).first()
        assert restored_outbox is not None
        assert restored_outbox.status == OutboxStatus.PENDING

        restored_job = target_db.query(BackgroundJob).filter(BackgroundJob.id == saved_job_id).first()
        assert restored_job is not None
        assert restored_job.status == JobStatus.PENDING
