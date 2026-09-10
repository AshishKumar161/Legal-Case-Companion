from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import RequireOperatorPermission, RequireRole, get_db
from app.core.metrics import metrics_collector
from app.models.case import CaseStatus
from app.models.consultation import ConsultationStatus
from app.models.document import DocumentSecurityStatus
from app.models.job import JobStatus, JobType
from app.models.legal_authority import LegalAuthorityType, LegalSource
from app.models.operator import OperationalPermission
from app.models.payment import PaymentStatus
from app.models.user import AccountStatus, User, UserRole, VerificationStatus
from app.domain.users.operator_service import OperatorService
from app.schemas.admin import (
    AdminCaseResponse,
    AdminConsultationResponse,
    AdminDocumentSecurityResponse,
    AdminOverviewResponse,
    AdminPaymentResponse,
    AdminSecurityEventResponse,
    AdminUserResponse,
)
from app.schemas.audit import AuditEventResponse
from app.schemas.job import JobResponse, JobStatsResponse
from app.schemas.pagination import PaginatedResponse
from app.schemas.profile import LawyerVerificationResponse
from app.schemas.user import UserResponse
from app.domain.users.admin_service import AdminService
from app.domain.jobs.job_service import JobService
from app.domain.jobs.job_worker import JobWorker
from app.domain.ai.legal_data_pipeline import LegalDataPipeline
from app.domain.ai.legal_source_providers.base import RawLegalSourcePayload

router = APIRouter(prefix="/admin", tags=["admin"])


class RejectVerificationRequest(BaseModel):
    reason: str | None = None


class SuspendUserRequest(BaseModel):
    reason: str | None = None


# --------------------------------------------------------------------------
# OPERATIONAL OVERVIEW & KPI METRICS
# --------------------------------------------------------------------------


@router.get("/overview", response_model=AdminOverviewResponse)
def get_operational_overview(
    current_user: User = Depends(RequireRole([UserRole.ADMIN])),
    db: Session = Depends(get_db),
):
    """Admin-only operational overview with platform KPIs and aggregate metrics."""
    admin_service = AdminService(db)
    return admin_service.get_operational_overview(current_user)


# --------------------------------------------------------------------------
# USER MANAGEMENT & ACCOUNT STATUS
# --------------------------------------------------------------------------


@router.get("/users", response_model=PaginatedResponse[AdminUserResponse])
def list_users(
    role: UserRole | None = None,
    account_status: AccountStatus | None = None,
    search: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(RequireRole([UserRole.ADMIN])),
    db: Session = Depends(get_db),
):
    """Admin-only endpoint to list platform users with search and filters."""
    admin_service = AdminService(db)
    return admin_service.list_users(
        current_user,
        role=role,
        account_status=account_status,
        search=search,
        skip=skip,
        limit=limit,
    )


@router.get("/users/{user_id}", response_model=AdminUserResponse)
def get_user_details(
    user_id: UUID,
    current_user: User = Depends(RequireRole([UserRole.ADMIN])),
    db: Session = Depends(get_db),
):
    """Admin-only endpoint to inspect a specific user's details."""
    admin_service = AdminService(db)
    return admin_service.get_user(current_user, user_id)


@router.post("/users/{user_id}/suspend", response_model=UserResponse)
def suspend_user(
    user_id: UUID,
    req: SuspendUserRequest | None = None,
    current_user: User = Depends(RequireRole([UserRole.ADMIN])),
    db: Session = Depends(get_db),
):
    """Admin-only endpoint to suspend a user, immediately invalidating sessions."""
    admin_service = AdminService(db)
    reason = req.reason if req else None
    return admin_service.suspend_user(current_user, user_id, reason=reason)


@router.post("/users/{user_id}/reactivate", response_model=UserResponse)
def reactivate_user(
    user_id: UUID,
    current_user: User = Depends(RequireRole([UserRole.ADMIN])),
    db: Session = Depends(get_db),
):
    """Admin-only endpoint to restore a suspended user account."""
    admin_service = AdminService(db)
    return admin_service.reactivate_user(current_user, user_id)


# --------------------------------------------------------------------------
# LAWYER VERIFICATION QUEUE
# --------------------------------------------------------------------------


@router.get(
    "/verifications", response_model=PaginatedResponse[LawyerVerificationResponse]
)
def get_verifications(
    status_filter: VerificationStatus | None = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(RequireRole([UserRole.ADMIN])),
    db: Session = Depends(get_db),
):
    """Admin-only endpoint to view lawyer Bar Council verification applications."""
    admin_service = AdminService(db)
    return admin_service.get_pending_verifications(
        current_user, status=status_filter, skip=skip, limit=limit
    )


@router.post(
    "/verifications/{verification_id}/approve",
    response_model=LawyerVerificationResponse,
)
def approve_verification(
    verification_id: UUID,
    current_user: User = Depends(RequireRole([UserRole.ADMIN])),
    db: Session = Depends(get_db),
):
    """Admin-only endpoint to approve lawyer Bar Council enrollment."""
    admin_service = AdminService(db)
    return admin_service.review_verification(
        current_user, verification_id, approve=True
    )


@router.post(
    "/verifications/{verification_id}/reject", response_model=LawyerVerificationResponse
)
def reject_verification(
    verification_id: UUID,
    req: RejectVerificationRequest | None = None,
    current_user: User = Depends(RequireRole([UserRole.ADMIN])),
    db: Session = Depends(get_db),
):
    """Admin-only endpoint to reject lawyer Bar Council enrollment with audit logging."""
    admin_service = AdminService(db)
    reason = req.reason if req else None
    return admin_service.review_verification(
        current_user, verification_id, approve=False, reason=reason
    )


# --------------------------------------------------------------------------
# CASE & WORKSPACE OVERSIGHT
# --------------------------------------------------------------------------


@router.get("/cases", response_model=PaginatedResponse[AdminCaseResponse])
def list_cases(
    case_status: CaseStatus | None = Query(None, alias="status"),
    search: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(RequireRole([UserRole.ADMIN])),
    db: Session = Depends(get_db),
):
    """Admin-only operational case oversight listing."""
    admin_service = AdminService(db)
    return admin_service.list_cases(
        current_user, status=case_status, search=search, skip=skip, limit=limit
    )


# --------------------------------------------------------------------------
# CONSULTATIONS OVERSIGHT
# --------------------------------------------------------------------------


@router.get("/consultations", response_model=PaginatedResponse[AdminConsultationResponse])
def list_consultations(
    consultation_status: ConsultationStatus | None = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(RequireRole([UserRole.ADMIN])),
    db: Session = Depends(get_db),
):
    """Admin-only consultation oversight listing."""
    admin_service = AdminService(db)
    return admin_service.list_consultations(
        current_user, status=consultation_status, skip=skip, limit=limit
    )


# --------------------------------------------------------------------------
# FINANCIAL & PAYMENT OVERSIGHT
# --------------------------------------------------------------------------


@router.get("/payments", response_model=PaginatedResponse[AdminPaymentResponse])
def list_payments(
    payment_status: PaymentStatus | None = Query(None, alias="status"),
    provider: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(RequireRole([UserRole.ADMIN])),
    db: Session = Depends(get_db),
):
    """Admin-only financial transactions oversight and reconciliation listing."""
    admin_service = AdminService(db)
    return admin_service.list_payments(
        current_user, status=payment_status, provider=provider, skip=skip, limit=limit
    )


# --------------------------------------------------------------------------
# DOCUMENT SECURITY & SCANNING OVERSIGHT
# --------------------------------------------------------------------------


@router.get(
    "/document-security", response_model=PaginatedResponse[AdminDocumentSecurityResponse]
)
def list_document_security(
    security_status: DocumentSecurityStatus | None = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(RequireRole([UserRole.ADMIN])),
    db: Session = Depends(get_db),
):
    """Admin-only document security and malware scan status oversight."""
    admin_service = AdminService(db)
    return admin_service.list_document_security(
        current_user, security_status=security_status, skip=skip, limit=limit
    )


# --------------------------------------------------------------------------
# AUDIT & SECURITY EVENTS
# --------------------------------------------------------------------------


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
    """Admin-only immutable audit trail search."""
    admin_service = AdminService(db)
    return admin_service.list_audit_logs(
        admin_user=current_user,
        event_type=event_type,
        actor_user_id=actor_user_id,
        entity_type=entity_type,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/security-events", response_model=PaginatedResponse[AdminSecurityEventResponse]
)
def get_security_events(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(RequireRole([UserRole.ADMIN])),
    db: Session = Depends(get_db),
):
    """Admin-only critical security events and policy denial log view."""
    admin_service = AdminService(db)
    return admin_service.list_security_events(
        admin_user=current_user, skip=skip, limit=limit
    )


# --------------------------------------------------------------------------
# BACKGROUND JOB OPERATIONS (ADMIN ONLY)
# --------------------------------------------------------------------------


@router.get("/jobs", response_model=PaginatedResponse[JobResponse])
def list_background_jobs(
    status_filter: JobStatus | None = Query(None, alias="status"),
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
        status=status_filter, job_type=job_type, case_id=case_id, skip=skip, limit=limit
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


@router.post(
    "/jobs/{job_id}/execute",
    response_model=JobResponse,
    status_code=status.HTTP_200_OK,
)
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
    return metrics_collector.get_metrics_snapshot()


# --------------------------------------------------------------------------
# LEGAL DATA PIPELINE OPERATIONS (ADMIN ONLY)
# --------------------------------------------------------------------------


@router.get("/legal-sources", status_code=status.HTTP_200_OK)
def list_legal_sources(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(RequireRole([UserRole.ADMIN])),
    db: Session = Depends(get_db),
):
    """Admin-only endpoint to inspect indexed legal authorities and statutory sources."""
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
            "title": s.name,
            "short_name": s.short_title,
            "jurisdiction": (
                s.jurisdiction
                if isinstance(s.jurisdiction, str)
                else s.jurisdiction.value
            ),
            "source_type": (
                s.source_type.value
                if hasattr(s.source_type, "value")
                else str(s.source_type)
            ),
            "status": s.status.value if hasattr(s.status, "value") else str(s.status),
            "enactment_date": (
                s.publication_date.isoformat() if s.publication_date else None
            ),
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
    pipeline = LegalDataPipeline(db)
    return pipeline.sync_curated_fixtures()


@router.post("/legal-sources/import-raw", status_code=status.HTTP_201_CREATED)
def import_raw_legal_source(
    payload: dict,
    current_user: User = Depends(RequireRole([UserRole.ADMIN])),
    db: Session = Depends(get_db),
):
    """Admin-only endpoint to ingest, validate, and index a raw legal source payload."""
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
    pipeline = LegalDataPipeline(db)
    count = pipeline.reindex_source(source_id)
    return {
        "source_id": str(source_id),
        "reindexed_count": count,
        "status": "SUCCESS",
    }


# --------------------------------------------------------------------------
# OPERATOR PERMISSIONS & CONTROL PLANE
# --------------------------------------------------------------------------


class GrantOperatorPermissionRequest(BaseModel):
    permission: OperationalPermission


@router.post("/operators/{user_id}/permissions", status_code=status.HTTP_201_CREATED)
def grant_operator_permission(
    user_id: UUID,
    req: GrantOperatorPermissionRequest,
    current_user: User = Depends(RequireOperatorPermission(OperationalPermission.SYSTEM_OPERATIONS)),
    db: Session = Depends(get_db),
):
    """Assigns an explicit operational permission to an administrative user."""
    service = OperatorService(db)
    grant = service.grant_permission(current_user, user_id, req.permission)
    return {
        "id": str(grant.id),
        "user_id": str(grant.user_id),
        "permission": grant.permission.value,
        "granted_by_user_id": str(grant.granted_by_user_id),
        "created_at": grant.created_at.isoformat(),
    }


@router.delete("/operators/{user_id}/permissions/{permission}", status_code=status.HTTP_200_OK)
def revoke_operator_permission(
    user_id: UUID,
    permission: OperationalPermission,
    current_user: User = Depends(RequireOperatorPermission(OperationalPermission.SYSTEM_OPERATIONS)),
    db: Session = Depends(get_db),
):
    """Revokes an operational permission from an administrative user."""
    service = OperatorService(db)
    service.revoke_permission(current_user, user_id, permission)
    return {"status": "REVOKED", "user_id": str(user_id), "permission": permission.value}


@router.get("/operators/{user_id}/permissions")
def list_operator_permissions(
    user_id: UUID,
    current_user: User = Depends(RequireOperatorPermission(OperationalPermission.SYSTEM_OPERATIONS)),
    db: Session = Depends(get_db),
):
    """Lists all active operational permissions held by an administrator."""
    service = OperatorService(db)
    perms = service.list_user_permissions(user_id)
    return {"user_id": str(user_id), "permissions": [p.value for p in perms]}

