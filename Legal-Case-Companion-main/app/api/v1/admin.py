from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import RequireRole, get_db
from app.models.job import JobStatus, JobType
from app.models.user import User, UserRole
from app.schemas.audit import AuditEventResponse
from app.schemas.job import JobResponse, JobStatsResponse
from app.schemas.pagination import PaginatedResponse
from app.schemas.profile import LawyerVerificationResponse
from app.schemas.user import UserResponse
from app.services.admin_service import AdminService
from app.services.job_service import JobService
from app.services.job_worker import JobWorker

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get(
    "/verifications", response_model=PaginatedResponse[LawyerVerificationResponse]
)
def get_verifications(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(RequireRole([UserRole.ADMIN])),
    db: Session = Depends(get_db),
):
    admin_service = AdminService(db)
    return admin_service.get_pending_verifications(current_user, skip, limit)


@router.post(
    "/verifications/{verification_id}/approve",
    response_model=LawyerVerificationResponse,
)
def approve_verification(
    verification_id: UUID,
    current_user: User = Depends(RequireRole([UserRole.ADMIN])),
    db: Session = Depends(get_db),
):
    admin_service = AdminService(db)
    return admin_service.review_verification(
        current_user, verification_id, approve=True
    )


@router.post(
    "/verifications/{verification_id}/reject", response_model=LawyerVerificationResponse
)
def reject_verification(
    verification_id: UUID,
    current_user: User = Depends(RequireRole([UserRole.ADMIN])),
    db: Session = Depends(get_db),
):
    admin_service = AdminService(db)
    return admin_service.review_verification(
        current_user, verification_id, approve=False
    )


@router.post("/users/{user_id}/suspend", response_model=UserResponse)
def suspend_user(
    user_id: UUID,
    current_user: User = Depends(RequireRole([UserRole.ADMIN])),
    db: Session = Depends(get_db),
):
    admin_service = AdminService(db)
    return admin_service.suspend_user(current_user, user_id)


@router.post("/users/{user_id}/reactivate", response_model=UserResponse)
def reactivate_user(
    user_id: UUID,
    current_user: User = Depends(RequireRole([UserRole.ADMIN])),
    db: Session = Depends(get_db),
):
    admin_service = AdminService(db)
    return admin_service.reactivate_user(current_user, user_id)


@router.get("/audit", response_model=PaginatedResponse[AuditEventResponse])
def get_audit_logs(
    event_type: str | None = None,
    actor_user_id: UUID | None = None,
    entity_type: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(RequireRole([UserRole.ADMIN])),
    db: Session = Depends(get_db),
):
    admin_service = AdminService(db)
    return admin_service.list_audit_logs(
        admin_user=current_user,
        event_type=event_type,
        actor_user_id=actor_user_id,
        entity_type=entity_type,
        skip=skip,
        limit=limit,
    )


# --------------------------------------------------------------------------
# BACKGROUND JOB OPERATIONS (ADMIN ONLY)
# --------------------------------------------------------------------------


@router.get("/jobs", response_model=PaginatedResponse[JobResponse])
def list_background_jobs(
    status: JobStatus | None = None,
    job_type: JobType | None = None,
    case_id: UUID | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(RequireRole([UserRole.ADMIN])),
    db: Session = Depends(get_db),
):
    """Admin-only endpoint to list background jobs with status/type filtering."""
    service = JobService(db)
    return service.list_jobs(
        status=status, job_type=job_type, case_id=case_id, skip=skip, limit=limit
    )


@router.get("/jobs/stats", response_model=JobStatsResponse)
def get_job_stats(
    current_user: User = Depends(RequireRole([UserRole.ADMIN])),
    db: Session = Depends(get_db),
):
    """Admin-only endpoint to retrieve job queue counts and statuses."""
    service = JobService(db)
    return service.get_job_stats()


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job_by_id(
    job_id: UUID,
    current_user: User = Depends(RequireRole([UserRole.ADMIN])),
    db: Session = Depends(get_db),
):
    """Admin-only endpoint to inspect job details and failure diagnostics."""
    service = JobService(db)
    return service.get_job_by_id(job_id)


@router.post("/jobs/{job_id}/execute", response_model=JobResponse, status_code=status.HTTP_200_OK)
def trigger_job_execution(
    job_id: UUID,
    current_user: User = Depends(RequireRole([UserRole.ADMIN])),
    db: Session = Depends(get_db),
):
    """Admin-only endpoint to immediately execute or retry a background job."""
    worker = JobWorker(db, worker_id=f"admin-{current_user.id}")
    return worker.execute_job(job_id)


@router.get("/metrics")
def get_operational_metrics(
    current_user: User = Depends(RequireRole([UserRole.ADMIN])),
):
    """Admin-only operational metrics endpoint exposing request throughput, status codes, latency and AI stats."""
    from app.core.metrics import metrics_collector

    return metrics_collector.get_metrics_snapshot()


# --------------------------------------------------------------------------
# LEGAL DATA PIPELINE OPERATIONS (ADMIN ONLY)
@router.get("/legal-sources", status_code=status.HTTP_200_OK)
def list_legal_sources(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(RequireRole([UserRole.ADMIN])),
    db: Session = Depends(get_db),
):
    """Admin-only endpoint to inspect indexed legal authorities and statutory sources."""
    from app.models.legal_authority import LegalSource

    sources = (
        db.query(LegalSource)
        .order_by(LegalSource.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [
        {
            "id": str(s.id),
            "canonical_identifier": s.canonical_identifier,
            "title": s.title,
            "short_name": s.short_name,
            "jurisdiction": s.jurisdiction.value,
            "source_type": s.source_type.value,
            "status": s.status.value,
            "enactment_date": s.enactment_date.isoformat() if s.enactment_date else None,
            "created_at": s.created_at.isoformat(),
        }
        for s in sources
    ]


@router.post("/legal-sources/sync-fixtures", status_code=status.HTTP_200_OK)
def sync_curated_legal_fixtures(
    current_user: User = Depends(RequireRole([UserRole.ADMIN])),
    db: Session = Depends(get_db),
):
    """Admin-only endpoint to idempotently sync verified Indian statutory and judicial fixtures."""
    from app.services.legal_data_pipeline import LegalDataPipeline

    pipeline = LegalDataPipeline(db)
    return pipeline.sync_curated_fixtures()


@router.post("/legal-sources/import-raw", status_code=status.HTTP_201_CREATED)
def import_raw_legal_source(
    payload: dict,
    current_user: User = Depends(RequireRole([UserRole.ADMIN])),
    db: Session = Depends(get_db),
):
    """Admin-only endpoint to ingest, validate, and index a raw legal source payload."""
    from app.models.legal_authority import LegalAuthorityType
    from app.services.legal_data_pipeline import LegalDataPipeline
    from app.services.legal_source_providers.base import RawLegalSourcePayload

    pipeline = LegalDataPipeline(db)
    raw_payload = RawLegalSourcePayload(
        source_system=payload.get("source_system", "ADMIN_RAW_IMPORT"),
        external_identifier=payload["external_identifier"],
        source_type=LegalAuthorityType(
            payload.get("source_type", LegalAuthorityType.PRIMARY_LEGISLATION.value)
        ),
        raw_content=payload["raw_content"],
        raw_metadata=payload.get("raw_metadata", {}),
        retrieval_url=payload.get("retrieval_url"),
    )
    raw_record = pipeline.ingest_raw_payload(raw_payload)
    source = pipeline.process_raw_source(raw_record.id)
    return {
        "raw_source_id": str(raw_record.id),
        "source_id": str(source.id),
        "canonical_identifier": source.canonical_identifier,
        "status": "INDEXED",
    }


@router.post("/legal-sources/{source_id}/reindex", status_code=status.HTTP_200_OK)
def reindex_legal_source(
    source_id: UUID,
    current_user: User = Depends(RequireRole([UserRole.ADMIN])),
    db: Session = Depends(get_db),
):
    """Admin-only endpoint to re-generate vector embeddings and re-index a legal authority."""
    from app.services.legal_data_pipeline import LegalDataPipeline

    pipeline = LegalDataPipeline(db)
    count = pipeline.reindex_source(source_id)
    return {"source_id": str(source_id), "reindexed_count": count, "status": "SUCCESS"}

