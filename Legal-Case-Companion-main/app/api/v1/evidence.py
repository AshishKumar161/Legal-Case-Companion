from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.api.v1.auth import limiter
from app.core.authorization import (
    authorize_case_access,
    authorize_evidence_access,
    authorize_evidence_management,
)
from app.models.evidence import (
    Evidence,
    EvidenceAccessGrant,
    EvidenceCategory,
    EvidenceSensitivity,
    EvidenceStatus,
    EvidenceVersion,
)
from app.models.user import User
from app.schemas.evidence import (
    EvidenceAccessGrantResponse,
    EvidenceCompleteRequest,
    EvidenceCustodyEventResponse,
    EvidenceDetailResponse,
    EvidenceIntegrityVerifyResponse,
    EvidenceLegalHoldRequest,
    EvidenceResponse,
    EvidenceRevokeRequest,
    EvidenceShareRequest,
    EvidenceSignedUrlResponse,
    EvidenceUploadInitRequest,
    EvidenceUploadInitResponse,
    EvidenceVersionCreateRequest,
    EvidenceVersionResponse,
)
from app.services.evidence_service import EvidenceService

router = APIRouter(prefix="/cases/{case_id}/evidence", tags=["evidence-locker"])


@router.post("/upload-init", response_model=EvidenceUploadInitResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute")
def init_evidence_upload(
    request: Request,
    case_id: UUID,
    payload: EvidenceUploadInitRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Initializes staged evidence upload, allocating UUIDv7 IDs and generating a short-lived presigned upload URL."""
    service = EvidenceService(db)
    evidence, version, upload_url = service.init_upload(current_user, case_id, payload)
    return EvidenceUploadInitResponse(
        evidence_id=evidence.id,
        version_id=version.id,
        upload_url=upload_url,
        storage_key=version.storage_key,
        expires_in=900,
    )


@router.post("/{evidence_id}/complete", response_model=EvidenceResponse, status_code=status.HTTP_200_OK)
@limiter.limit("20/minute")
def complete_evidence_upload(
    request: Request,
    case_id: UUID,
    evidence_id: UUID,
    payload: EvidenceCompleteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Runs content magic byte verification, malware scan, cryptographic SHA-256 computation,

    and promotes the evidence item to ACTIVE state with custody logging.
    """
    service = EvidenceService(db)
    evidence = service.complete_upload(current_user, case_id, evidence_id, payload.version_id)
    return evidence


@router.get("", response_model=list[EvidenceResponse])
@limiter.limit("60/minute")
def list_evidence(
    request: Request,
    case_id: UUID,
    category: EvidenceCategory | None = None,
    sensitivity: EvidenceSensitivity | None = None,
    status_filter: EvidenceStatus | None = Query(default=None, alias="status"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lists evidence items for a case the current user is authorized to participate in."""
    authorize_case_access(db, current_user, case_id)

    query = (
        db.query(Evidence)
        .filter(Evidence.case_id == case_id, Evidence.deleted_at.is_(None))
    )
    if category:
        query = query.filter(Evidence.category == category)
    if sensitivity:
        query = query.filter(Evidence.sensitivity == sensitivity)
    if status_filter:
        query = query.filter(Evidence.status == status_filter)

    items = query.order_by(Evidence.created_at.desc()).all()

    # Filter by user authorization for each evidence item
    visible_items = []
    for item in items:
        try:
            authorize_evidence_access(db, current_user, item.id, required_level="VIEW")
            visible_items.append(item)
        except Exception:
            continue

    return visible_items


@router.get("/{evidence_id}", response_model=EvidenceDetailResponse)
@limiter.limit("60/minute")
def get_evidence_detail(
    request: Request,
    case_id: UUID,
    evidence_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Returns detailed evidence metadata, active version, version history, and active access grants."""
    evidence, _ = authorize_evidence_access(db, current_user, evidence_id, required_level="VIEW")
    if evidence.case_id != case_id:
        from app.core.exceptions import ResourceNotFoundError
        raise ResourceNotFoundError("Evidence not found")

    return evidence


@router.post("/{evidence_id}/versions/upload-init", response_model=EvidenceUploadInitResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute")
def init_version_upload(
    request: Request,
    case_id: UUID,
    evidence_id: UUID,
    payload: EvidenceVersionCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Initializes a new immutable evidence version (Version N+1)."""
    service = EvidenceService(db)
    version, upload_url = service.create_version_init(current_user, case_id, evidence_id, payload)
    return EvidenceUploadInitResponse(
        evidence_id=evidence_id,
        version_id=version.id,
        upload_url=upload_url,
        storage_key=version.storage_key,
        expires_in=900,
    )


@router.post("/{evidence_id}/versions/{version_id}/complete", response_model=EvidenceResponse, status_code=status.HTTP_200_OK)
@limiter.limit("20/minute")
def complete_version_upload(
    request: Request,
    case_id: UUID,
    evidence_id: UUID,
    version_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Scans and activates a new immutable evidence version."""
    service = EvidenceService(db)
    evidence = service.complete_version(current_user, case_id, evidence_id, version_id)
    return evidence


@router.get("/{evidence_id}/versions", response_model=list[EvidenceVersionResponse])
@limiter.limit("60/minute")
def list_evidence_versions(
    request: Request,
    case_id: UUID,
    evidence_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Returns all immutable versions for this authorized evidence item."""
    evidence, _ = authorize_evidence_access(db, current_user, evidence_id, required_level="VIEW")
    if evidence.case_id != case_id:
        from app.core.exceptions import ResourceNotFoundError
        raise ResourceNotFoundError("Evidence not found")

    return evidence.versions


@router.get("/{evidence_id}/versions/{version_id}", response_model=EvidenceVersionResponse)
@limiter.limit("60/minute")
def get_evidence_version(
    request: Request,
    case_id: UUID,
    evidence_id: UUID,
    version_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Returns metadata and cryptographic hash for a specific immutable version."""
    evidence, _ = authorize_evidence_access(db, current_user, evidence_id, required_level="VIEW")
    if evidence.case_id != case_id:
        from app.core.exceptions import ResourceNotFoundError
        raise ResourceNotFoundError("Evidence not found")

    version = (
        db.query(EvidenceVersion)
        .filter(EvidenceVersion.id == version_id, EvidenceVersion.evidence_id == evidence_id)
        .first()
    )
    if not version:
        from app.core.exceptions import ResourceNotFoundError
        raise ResourceNotFoundError("Evidence version not found")

    return version


@router.get("/{evidence_id}/download", response_model=EvidenceSignedUrlResponse)
@limiter.limit("30/minute")
def download_evidence(
    request: Request,
    case_id: UUID,
    evidence_id: UUID,
    version_id: UUID | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generates a short-lived (60s) presigned download URL after verifying DOWNLOAD authorization."""
    service = EvidenceService(db)
    url, filename, content_type = service.get_download_url(current_user, case_id, evidence_id, version_id)
    return EvidenceSignedUrlResponse(
        url=url,
        expires_in=60,
        content_type=content_type,
        filename=filename,
    )


@router.get("/{evidence_id}/view-url", response_model=EvidenceSignedUrlResponse)
@limiter.limit("30/minute")
def view_evidence(
    request: Request,
    case_id: UUID,
    evidence_id: UUID,
    version_id: UUID | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generates a short-lived (60s) presigned preview URL after verifying VIEW authorization."""
    service = EvidenceService(db)
    url, filename, content_type = service.get_view_url(current_user, case_id, evidence_id, version_id)
    return EvidenceSignedUrlResponse(
        url=url,
        expires_in=60,
        content_type=content_type,
        filename=filename,
    )


@router.post("/{evidence_id}/share", response_model=EvidenceAccessGrantResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute")
def share_evidence(
    request: Request,
    case_id: UUID,
    evidence_id: UUID,
    payload: EvidenceShareRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Grants explicit, controlled evidence access to an authorized lawyer or case participant."""
    service = EvidenceService(db)
    grant = service.share_evidence(current_user, case_id, evidence_id, payload)
    return grant


@router.post("/{evidence_id}/revoke", response_model=EvidenceAccessGrantResponse, status_code=status.HTTP_200_OK)
@limiter.limit("20/minute")
def revoke_evidence_access(
    request: Request,
    case_id: UUID,
    evidence_id: UUID,
    payload: EvidenceRevokeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Immediately revokes access to an evidence item for a specified user."""
    service = EvidenceService(db)
    grant = service.revoke_access(current_user, case_id, evidence_id, payload)
    return grant


@router.get("/{evidence_id}/grants", response_model=list[EvidenceAccessGrantResponse])
@limiter.limit("60/minute")
def list_evidence_grants(
    request: Request,
    case_id: UUID,
    evidence_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lists all active and historical access grants for an authorized evidence item."""
    evidence = authorize_evidence_management(db, current_user, evidence_id)
    if evidence.case_id != case_id:
        from app.core.exceptions import ResourceNotFoundError
        raise ResourceNotFoundError("Evidence not found")

    return (
        db.query(EvidenceAccessGrant)
        .filter(EvidenceAccessGrant.evidence_id == evidence_id)
        .order_by(EvidenceAccessGrant.created_at.desc())
        .all()
    )


@router.post("/{evidence_id}/verify-integrity", response_model=EvidenceIntegrityVerifyResponse, status_code=status.HTTP_200_OK)
@limiter.limit("15/minute")
def verify_evidence_integrity(
    request: Request,
    case_id: UUID,
    evidence_id: UUID,
    version_id: UUID | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Re-reads stored bytes from private storage, recomputes SHA-256 digest, and flags tamper anomalies."""
    from datetime import UTC, datetime
    service = EvidenceService(db)
    version, recorded_sha, computed_sha, is_match = service.verify_integrity(
        current_user, case_id, evidence_id, version_id
    )
    return EvidenceIntegrityVerifyResponse(
        evidence_id=evidence_id,
        version_id=version.id,
        sha256_recorded=recorded_sha,
        sha256_computed=computed_sha,
        integrity_status=version.integrity_status,
        verified_at=datetime.now(UTC),
        match=is_match,
    )


@router.post("/{evidence_id}/legal-hold", response_model=EvidenceResponse, status_code=status.HTTP_200_OK)
@limiter.limit("20/minute")
def set_evidence_legal_hold(
    request: Request,
    case_id: UUID,
    evidence_id: UUID,
    payload: EvidenceLegalHoldRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Applies or removes technical legal hold retention controls."""
    service = EvidenceService(db)
    evidence = service.set_legal_hold(current_user, case_id, evidence_id, payload)
    return evidence


@router.delete("/{evidence_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("20/minute")
def delete_evidence(
    request: Request,
    case_id: UUID,
    evidence_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Soft-deletes evidence item after verifying that no active legal hold or retention period is in effect."""
    service = EvidenceService(db)
    service.delete_evidence(current_user, case_id, evidence_id)


@router.get("/{evidence_id}/custody", response_model=list[EvidenceCustodyEventResponse])
@limiter.limit("60/minute")
def get_evidence_custody_chain(
    request: Request,
    case_id: UUID,
    evidence_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Returns chronological chain-of-custody log records linking every provenance event."""
    service = EvidenceService(db)
    events = service.get_custody_chain(current_user, case_id, evidence_id)
    return events
