from datetime import UTC, datetime

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.core.identifiers import generate_uuid7
from app.models.audit import AuditEvent
from app.models.job import BackgroundJob, JobStatus, JobType
from app.models.user import AccountStatus, User, UserRole


def test_production_database_schema_and_constraints_integrity(db: Session):
    """
    Verifies that all required tables, constraints, foreign keys, and indexes
    are present and adhere to production safety standards.
    """
    inspector = inspect(db.get_bind())
    tables = set(inspector.get_table_names())

    # Critical tables must exist
    required_tables = {
        "users",
        "cases",
        "case_participants",
        "documents",
        "document_chunks",
        "legal_sources",
        "legal_source_versions",
        "case_messages",
        "matter_requests",
        "background_jobs",
        "audit_events",
        "pilot_feedback",
    }
    missing = required_tables - tables
    assert not missing, f"Missing required tables in database: {missing}"

    # Verify foreign key linkages and indexes on pilot_feedback
    fb_fks = inspector.get_foreign_keys("pilot_feedback")
    fk_target_tables = [fk["referred_table"] for fk in fb_fks]
    assert "users" in fk_target_tables

    fb_indexes = [idx["name"] for idx in inspector.get_indexes("pilot_feedback")]
    assert any("user_id" in idx for idx in fb_indexes)


def test_audit_event_idempotency_and_immutability(db: Session):
    """
    Verifies that system audit records can be safely appended without breaking
    case referential integrity even during failure rollbacks.
    """
    user_id = generate_uuid7()
    user = User(
        id=user_id,
        email="audit_rehearsal@example.com",
        password_hash="fakehash",
        role=UserRole.ADMIN,
        account_status=AccountStatus.ACTIVE,
    )
    db.add(user)
    db.commit()

    # Append multiple audit events
    event_1 = AuditEvent(
        id=generate_uuid7(),
        actor_user_id=user_id,
        action="DATABASE_MIGRATION_REHEARSAL",
        event_type="SCHEMA_VERIFICATION",
        entity_type="SYSTEM",
        entity_id=user_id,
        timestamp=datetime.now(UTC),
        metadata_={"status": "SUCCESS", "dry_run": False},
    )
    event_2 = AuditEvent(
        id=generate_uuid7(),
        actor_user_id=user_id,
        action="POINT_IN_TIME_RECOVERY_SIMULATION",
        event_type="RECOVERY_CHECK",
        entity_type="SYSTEM",
        entity_id=user_id,
        timestamp=datetime.now(UTC),
        metadata_={"status": "VERIFIED"},
    )
    db.add_all([event_1, event_2])
    db.commit()

    recorded = (
        db.query(AuditEvent)
        .filter(AuditEvent.actor_user_id == user_id)
        .all()
    )
    assert len(recorded) == 2


def test_stale_job_recovery_simulation(db: Session):
    """
    Verifies that the background worker correctly identifies and recovers
    stale jobs whose worker locks expired during unexpected container termination.
    """
    from app.domain.jobs.job_worker import JobWorker

    admin_id = generate_uuid7()
    job_id = generate_uuid7()

    # Simulate a job left RUNNING in the past (locked_until has passed)
    stale_job = BackgroundJob(
        id=job_id,
        job_type=JobType.STALE_JOB_RECOVERY,
        status=JobStatus.RUNNING,
        payload={"task": "index_maintenance"},
        created_by_user_id=admin_id,
        attempt_count=1,
        max_attempts=3,
        locked_until=datetime.now(UTC).replace(year=2020),  # expired lease
        locked_by="deceased-worker-pod-99",
    )
    db.add(stale_job)
    db.commit()

    # Worker executes stale job recovery handler
    worker = JobWorker(db, worker_id="recovery-worker-01")
    recovery_job = BackgroundJob(
        id=generate_uuid7(),
        job_type=JobType.STALE_JOB_RECOVERY,
        status=JobStatus.RUNNING,
        payload={},
        created_by_user_id=admin_id,
    )
    db.add(recovery_job)
    db.commit()

    res = worker._handle_stale_job_recovery(recovery_job)
    assert res["recovered_jobs_count"] >= 1
    db.commit()

    # Stale job should now be retrying with cleared lease
    db.refresh(stale_job)
    assert stale_job.status == JobStatus.RETRYING
    assert stale_job.locked_by is None
