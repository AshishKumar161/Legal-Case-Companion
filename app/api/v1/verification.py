import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import RequireRole, get_current_user, get_db
from app.api.v1.auth import limiter
from app.models.user import AdvocateDocumentType, User, UserRole, VerificationStatus
from app.schemas.profile import (
    LawyerVerificationCreate,
    LawyerVerificationResponse,
    LawyerVerificationReviewRequest,
)
from app.schemas.verification import (
    AdvocateVerificationDetailResponse,
    AdvocateVerificationDocumentResponse,
    AdvocateVerificationDocumentUploadResponse,
    AdvocateVerificationSubmitRequest,
    LawyerVerificationApproveRequest,
    LawyerVerificationQueueResponse,
    LawyerVerificationRejectRequest,
    LawyerVerificationRequestInfoRequest,
    LawyerVerificationRevokeRequest,
    LawyerVerificationStartReviewRequest,
    PublicAdvocateVerificationBadgeResponse,
)
from app.domain.verification.lawyer_verification_service import LawyerVerificationService
from app.domain.users.profile_service import ProfileService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/verification", tags=["verification"])


# ==============================================================================
# Advocate Verification Pipeline Endpoints
# ==============================================================================

@router.post(
    "/advocate/documents",
    response_model=AdvocateVerificationDocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload professional credential document",
)
@router.post(
    "/application/documents",
    response_model=AdvocateVerificationDocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
@limiter.limit("20/minute")
async def upload_advocate_document(
    request: Request,
    file: UploadFile = File(...),
    document_type: AdvocateDocumentType = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Uploads and cryptographically binds an advocate verification document.
    Performs filename sanitization, magic byte validation, and SHA-256 digest computation.
    """
    file_bytes = await file.read()
    service = LawyerVerificationService(db)
    doc = service.upload_document(
        user=current_user,
        document_type=document_type,
        file_bytes=file_bytes,
        original_filename=file.filename or "credential.pdf",
        mime_type=file.content_type or "application/octet-stream",
    )
    return AdvocateVerificationDocumentUploadResponse(
        id=doc.id,
        document_id=doc.id,
        document_type=doc.document_type.value,
        original_filename=doc.original_filename,
        sha256_hash=doc.sha256_hash,
        scan_status=doc.scan_status.value,
        verification_status=doc.verification_status.value,
        message="Document uploaded and cryptographically bound successfully.",
    )


@router.get(
    "/advocate/documents/{document_id}/download",
    summary="Generate secure short-lived presigned URL for verification document",
)
@router.get(
    "/documents/{document_id}/download-url",
    include_in_schema=False,
)
@limiter.limit("30/minute")
def get_verification_document_download_url(
    request: Request,
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Generates a secure, short-lived presigned download link for an authorized reviewer or the owner.
    """
    service = LawyerVerificationService(db)
    url = service.get_document_download_url(user=current_user, document_id=document_id)
    return {"download_url": url, "expires_in_seconds": 300}


@router.post(
    "/advocate/submit",
    response_model=AdvocateVerificationDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit complete advocate verification application",
)
@router.post(
    "/application/submit",
    response_model=AdvocateVerificationDetailResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
@limiter.limit("10/minute")
def submit_advocate_verification_application(
    request: Request,
    payload: AdvocateVerificationSubmitRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Submits an advocate's complete professional credential application for human reviewer inspection.
    Validates State Bar Council enrollment formatting and presence of mandatory credentials.
    """
    service = LawyerVerificationService(db)
    verif = service.submit_verification(user=current_user, payload=payload)
    return service.get_verification_detail(user=current_user, verification_id=verif.id)


@router.get(
    "/advocate/status",
    response_model=AdvocateVerificationDetailResponse,
    summary="Get current advocate verification status and submitted documents",
)
@router.get(
    "/application/status",
    response_model=AdvocateVerificationDetailResponse,
    include_in_schema=False,
)
@limiter.limit("60/minute")
def get_advocate_verification_status(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieves the submitting advocate's current verification dossier, review events, and checklist.
    """
    service = LawyerVerificationService(db)
    draft = service.get_or_create_draft_verification(current_user)
    return service.get_verification_detail(user=current_user, verification_id=draft.id)


# ==============================================================================
# Administrative Review Queue & Decision Endpoints (RBAC Enforced)
# ==============================================================================

@router.get(
    "/admin/queue",
    response_model=LawyerVerificationQueueResponse,
    summary="Get paginated advocate verification review queue",
)
@limiter.limit("60/minute")
def get_admin_verification_queue(
    request: Request,
    status: VerificationStatus | None = Query(None, description="Filter by status (PENDING, UNDER_REVIEW, NEEDS_INFO)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    current_user: User = Depends(RequireRole([UserRole.ADMIN])),
    db: Session = Depends(get_db),
):
    """
    Returns bounded, paginated list of pending advocate applications for authorized administrative reviewers.
    """
    service = LawyerVerificationService(db)
    return service.get_review_queue(
        reviewer=current_user,
        status_filter=status,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/admin/{verification_id}/detail",
    response_model=AdvocateVerificationDetailResponse,
    summary="Get complete advocate application dossier for administrative review",
)
@router.get(
    "/admin/{verification_id}",
    response_model=AdvocateVerificationDetailResponse,
    include_in_schema=False,
)
@router.get(
    "/{verification_id}",
    response_model=AdvocateVerificationDetailResponse,
    include_in_schema=False,
)
@limiter.limit("60/minute")
def get_admin_verification_detail(
    request: Request,
    verification_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieves full dossier, document checksums, and historical review trail for an administrator.
    """
    service = LawyerVerificationService(db)
    return service.get_verification_detail(user=current_user, verification_id=verification_id)


@router.post(
    "/admin/{verification_id}/start-review",
    response_model=AdvocateVerificationDetailResponse,
    summary="Start reviewing an advocate verification application",
)
@router.post(
    "/{verification_id}/start-review",
    response_model=AdvocateVerificationDetailResponse,
    include_in_schema=False,
)
@limiter.limit("30/minute")
def start_admin_review(
    request: Request,
    verification_id: uuid.UUID,
    payload: LawyerVerificationStartReviewRequest = LawyerVerificationStartReviewRequest(),
    current_user: User = Depends(RequireRole([UserRole.ADMIN])),
    db: Session = Depends(get_db),
):
    """
    Transitions application to UNDER_REVIEW. Enforces self-approval block and row locking.
    """
    service = LawyerVerificationService(db)
    service.start_review(reviewer=current_user, verification_id=verification_id, notes=payload.notes)
    return service.get_verification_detail(user=current_user, verification_id=verification_id)


@router.post(
    "/admin/{verification_id}/approve",
    response_model=AdvocateVerificationDetailResponse,
    summary="Approve advocate verification with official Bar Council roll provenance",
)
@router.post(
    "/{verification_id}/approve",
    response_model=AdvocateVerificationDetailResponse,
    include_in_schema=False,
)
@limiter.limit("30/minute")
def approve_admin_verification(
    request: Request,
    verification_id: uuid.UUID,
    payload: LawyerVerificationApproveRequest,
    current_user: User = Depends(RequireRole([UserRole.ADMIN])),
    db: Session = Depends(get_db),
):
    """
    Formally approves advocate credentials, setting verification source provenance and validity window.
    Promotes advocate account status and activates public verification badge.
    """
    service = LawyerVerificationService(db)
    service.approve_verification(
        reviewer=current_user,
        verification_id=verification_id,
        verification_source=payload.verification_source,
        source_reference=payload.source_reference,
        verification_method=payload.verification_method,
        validity_days=payload.validity_days,
        notes=payload.notes,
    )
    return service.get_verification_detail(user=current_user, verification_id=verification_id)


@router.post(
    "/admin/{verification_id}/reject",
    response_model=AdvocateVerificationDetailResponse,
    summary="Reject advocate verification with structured category and reasoning",
)
@router.post(
    "/{verification_id}/reject",
    response_model=AdvocateVerificationDetailResponse,
    include_in_schema=False,
)
@limiter.limit("30/minute")
def reject_admin_verification(
    request: Request,
    verification_id: uuid.UUID,
    payload: LawyerVerificationRejectRequest,
    current_user: User = Depends(RequireRole([UserRole.ADMIN])),
    db: Session = Depends(get_db),
):
    """
    Rejects advocate verification with structured rejection taxonomy and professional reasoning.
    """
    service = LawyerVerificationService(db)
    service.reject_verification(
        reviewer=current_user,
        verification_id=verification_id,
        rejection_category=payload.rejection_category or "OTHER",
        reason=payload.reason or "No reason provided",
        notes=payload.notes,
    )
    return service.get_verification_detail(user=current_user, verification_id=verification_id)


@router.post(
    "/admin/{verification_id}/request-information",
    response_model=AdvocateVerificationDetailResponse,
    summary="Request additional verification documents or clarification",
)
@router.post(
    "/{verification_id}/request-information",
    response_model=AdvocateVerificationDetailResponse,
    include_in_schema=False,
)
@limiter.limit("30/minute")
def request_admin_verification_info(
    request: Request,
    verification_id: uuid.UUID,
    payload: LawyerVerificationRequestInfoRequest,
    current_user: User = Depends(RequireRole([UserRole.ADMIN])),
    db: Session = Depends(get_db),
):
    """
    Transitions application to NEEDS_INFO and marks specified documents for resubmission.
    """
    service = LawyerVerificationService(db)
    service.request_information(
        reviewer=current_user,
        verification_id=verification_id,
        requested_documents=payload.requested_documents,
        explanation=payload.explanation,
        notes=payload.notes,
    )
    return service.get_verification_detail(user=current_user, verification_id=verification_id)


@router.post(
    "/admin/{verification_id}/revoke",
    response_model=AdvocateVerificationDetailResponse,
    summary="Revoke previously approved advocate verification",
)
@router.post(
    "/{verification_id}/revoke",
    response_model=AdvocateVerificationDetailResponse,
    include_in_schema=False,
)
@limiter.limit("30/minute")
def revoke_admin_verification(
    request: Request,
    verification_id: uuid.UUID,
    payload: LawyerVerificationRevokeRequest,
    current_user: User = Depends(RequireRole([UserRole.ADMIN])),
    db: Session = Depends(get_db),
):
    """
    Revokes an existing advocate verification (e.g. upon Bar Council disciplinary action).
    Demotes account status and strips public verified badge.
    """
    service = LawyerVerificationService(db)
    service.revoke_verification(
        reviewer=current_user,
        verification_id=verification_id,
        revocation_reason=payload.revocation_reason,
        notes=payload.notes,
    )
    return service.get_verification_detail(user=current_user, verification_id=verification_id)


# ==============================================================================
# Public-Facing Verification Representation (BCI Rule 36 Compliant)
# ==============================================================================

@router.get(
    "/advocate/{lawyer_id}/badge",
    response_model=PublicAdvocateVerificationBadgeResponse,
    summary="Get factual, tamper-resistant public verification badge",
)
@router.get(
    "/badge/{lawyer_id}",
    response_model=PublicAdvocateVerificationBadgeResponse,
    include_in_schema=False,
)
@limiter.limit("60/minute")
def get_public_advocate_badge(
    request: Request,
    lawyer_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """
    Returns public-facing verification representation strictly adhering to Bar Council of India Rule 36.
    Displays verified State Bar Council and enrollment number without misleading commercial claims.
    """
    service = LawyerVerificationService(db)
    return service.get_public_verification_badge(lawyer_id=lawyer_id)


# ==============================================================================
# Backwards-Compatible Legacy Endpoints
# ==============================================================================

@router.post(
    "/lawyer/submit",
    response_model=LawyerVerificationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit advocate Bar Council verification (legacy)",
)
def submit_lawyer_verification_legacy(
    payload: LawyerVerificationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile_service = ProfileService(db)
    verif = profile_service.submit_verification(user=current_user, req=payload)
    return LawyerVerificationResponse(
        id=verif.id,
        lawyer_profile_id=verif.lawyer_profile_id,
        enrollment_number=verif.enrollment_number,
        state_bar_council=verif.state_bar_council,
        status=verif.status.value,
        evidence_document_id=verif.evidence_document_id,
        expires_at=verif.expires_at,
        rejection_reason_category=verif.rejection_reason_category,
    )


@router.post(
    "/admin/{verification_id}/review",
    response_model=LawyerVerificationResponse,
    summary="Review and approve/reject advocate verification (legacy)",
)
def review_lawyer_verification_legacy(
    verification_id: uuid.UUID,
    payload: LawyerVerificationReviewRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = LawyerVerificationService(db)
    if payload.approved:
        verif = service.approve_verification(
            reviewer=current_user,
            verification_id=verification_id,
            verification_source="State Bar Council Roll (Legacy Verification)",
            source_reference="Verified via legacy administrative review",
            validity_days=payload.validity_days,
        )
    else:
        verif = service.reject_verification(
            reviewer=current_user,
            verification_id=verification_id,
            rejection_category=payload.rejection_category or "DOCUMENTS_ILLEGIBLE",
            reason=payload.rejection_category or "Application rejected by reviewer.",
        )
    return LawyerVerificationResponse(
        id=verif.id,
        lawyer_profile_id=verif.lawyer_profile_id,
        enrollment_number=verif.enrollment_number,
        state_bar_council=verif.state_bar_council,
        status=verif.status.value,
        evidence_document_id=verif.evidence_document_id,
        expires_at=verif.expires_at,
        rejection_reason_category=verif.rejection_reason_category,
    )


@router.get(
    "/discovery/transparency",
    summary="Explainable discovery ranking transparency information",
)
def get_discovery_ranking_transparency(
    db: Session = Depends(get_db),
):
    service = LawyerVerificationService(db)
    return service.get_discovery_ranking_explanation()
