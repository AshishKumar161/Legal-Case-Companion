from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import func, or_, String
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.api.v1.auth import limiter
from app.core.authorization import (
    authorize_case_access,
    authorize_evidence_access,
)
from app.core.exceptions import AppException, ResourceNotFoundError
from app.models.evidence import (
    CaseExhibit,
    Evidence,
    EvidenceAccessGrant,
    EvidenceCategory,
    EvidenceSensitivity,
    EvidenceStatus,
    EvidenceVersion,
)
from app.models.user import User
from app.schemas.evidence import (
    CaseExhibitCreateRequest,
    CaseExhibitResponse,
    CaseExhibitUpdateRequest,
    EvidenceAccessGrantResponse,
    EvidenceBatchRequest,
    EvidenceBatchResponse,
    EvidenceCompleteRequest,
    EvidenceCustodyEventResponse,
    EvidenceDetailResponse,
    EvidenceIntegrityVerifyResponse,
    EvidenceLegalHoldRequest,
    EvidenceResponse,
    EvidenceRevokeRequest,
    EvidenceShareRequest,
    EvidenceSignedUrlResponse,
    EvidenceUpdateRequest,
    EvidenceUploadInitRequest,
    EvidenceUploadInitResponse,
    EvidenceVersionCreateRequest,
    EvidenceVersionResponse,
    ShareableParticipantResponse,
    SharedEvidenceItemResponse,
)
from app.domain.evidence.evidence_service import EvidenceService

router = APIRouter(prefix="/cases/{case_id}", tags=["evidence-locker"])


def _format_exhibit_response(ex: CaseExhibit) -> CaseExhibitResponse:
    return CaseExhibitResponse(
        id=ex.id,
        case_id=ex.case_id,
        evidence_id=ex.evidence_id,
        version_id=ex.version_id,
        hearing_id=ex.hearing_id,
        exhibit_number=ex.exhibit_number,
        title=ex.title,
        description=ex.description,
        relevant_date=ex.relevant_date,
        created_by_user_id=ex.created_by_user_id,
        created_at=ex.created_at,
        updated_at=ex.updated_at,
        evidence_title=ex.evidence.title if ex.evidence else None,
        version_number=ex.version.version_number if ex.version else None,
        original_filename=ex.version.original_filename if ex.version else None,
        sha256=ex.version.sha256 if ex.version else None,
        hearing_purpose=ex.hearing.purpose if ex.hearing else None,
        court_name=ex.hearing.court_name if ex.hearing else None,
    )


@router.post("/evidence/upload-init", response_model=EvidenceUploadInitResponse, status_code=status.HTTP_201_CREATED)
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


@router.post("/evidence/{evidence_id}/complete", response_model=EvidenceResponse, status_code=status.HTTP_200_OK)
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
    resp = EvidenceResponse.model_validate(evidence)
    resp.exhibit_numbers = [ex.exhibit_number for ex in evidence.exhibits if ex.deleted_at is None]
    return resp


@router.get("/evidence", response_model=list[EvidenceResponse])
@limiter.limit("60/minute")
def list_evidence(
    request: Request,
    case_id: UUID,
    q: str | None = Query(default=None, max_length=100),
    tag: str | None = Query(default=None, max_length=50),
    category: EvidenceCategory | None = None,
    sensitivity: EvidenceSensitivity | None = None,
    status_filter: EvidenceStatus | None = Query(default=None, alias="status"),
    is_exhibit: bool | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lists evidence items for a case the current user is authorized to participate in,

    with server-side metadata search, category, tag, exhibit, and status filtering.
    """
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

    # Server-side metadata search
    if q and q.strip():
        term = f"%{q.strip().lower()}%"
        query = query.filter(
            or_(
                func.lower(Evidence.title).like(term),
                func.lower(Evidence.description).like(term),
                func.lower(Evidence.original_filename).like(term),
                func.cast(Evidence.tags, String).ilike(term),
            )
        )

    # Tag containment filter
    if tag and tag.strip():
        clean_tag = tag.strip().lower()
        query = query.filter(func.cast(Evidence.tags, String).ilike(f'%"{clean_tag}"%'))

    # Exhibit association filter
    if is_exhibit is True:
        query = query.filter(Evidence.exhibits.any(CaseExhibit.deleted_at.is_(None)))
    elif is_exhibit is False:
        query = query.filter(~Evidence.exhibits.any(CaseExhibit.deleted_at.is_(None)))

    items = query.order_by(Evidence.created_at.desc()).offset(skip).limit(limit).all()

    # Filter by user authorization for each evidence item
    visible_items: list[EvidenceResponse] = []
    for item in items:
        try:
            authorize_evidence_access(db, current_user, item.id, required_level="VIEW")
            resp = EvidenceResponse.model_validate(item)
            resp.exhibit_numbers = [ex.exhibit_number for ex in item.exhibits if ex.deleted_at is None]
            visible_items.append(resp)
        except AppException:
            continue

    return visible_items


@router.post("/evidence/batch", response_model=EvidenceBatchResponse, status_code=status.HTTP_200_OK)
@limiter.limit("20/minute")
def batch_evidence_actions(
    request: Request,
    case_id: UUID,
    payload: EvidenceBatchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Executes atomic batch operations (assign category, add/remove tags, archive, restore)

    with per-item authorization and legal-hold validation.
    """
    service = EvidenceService(db)
    count, affected_ids, details = service.batch_execute(current_user, case_id, payload)
    return EvidenceBatchResponse(
        affected_count=count,
        action=payload.action,
        evidence_ids=affected_ids,
        details=details,
    )


@router.get("/evidence/{evidence_id}", response_model=EvidenceDetailResponse)
@limiter.limit("60/minute")
def get_evidence_detail(
    request: Request,
    case_id: UUID,
    evidence_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Returns detailed evidence metadata, active version, version history, exhibits, and access grants."""
    evidence, _ = authorize_evidence_access(db, current_user, evidence_id, required_level="VIEW")
    if evidence.case_id != case_id:
        raise ResourceNotFoundError("Evidence not found")

    detail = EvidenceDetailResponse.model_validate(evidence)
    detail.exhibits = [
        _format_exhibit_response(ex)
        for ex in evidence.exhibits
        if ex.deleted_at is None
    ]
    detail.exhibit_numbers = [ex.exhibit_number for ex in detail.exhibits]
    return detail


@router.patch("/evidence/{evidence_id}", response_model=EvidenceResponse)
@limiter.limit("30/minute")
def update_evidence_metadata(
    request: Request,
    case_id: UUID,
    evidence_id: UUID,
    payload: EvidenceUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Updates mutable evidence metadata (title, description, category, sensitivity, tags)."""
    service = EvidenceService(db)
    evidence = service.update_evidence(current_user, case_id, evidence_id, payload)
    resp = EvidenceResponse.model_validate(evidence)
    resp.exhibit_numbers = [ex.exhibit_number for ex in evidence.exhibits if ex.deleted_at is None]
    return resp


@router.post("/evidence/{evidence_id}/archive", response_model=EvidenceResponse)
@limiter.limit("20/minute")
def archive_evidence(
    request: Request,
    case_id: UUID,
    evidence_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Archives an evidence item, verifying that no active legal hold prevents retention."""
    service = EvidenceService(db)
    evidence = service.archive_evidence(current_user, case_id, evidence_id)
    resp = EvidenceResponse.model_validate(evidence)
    resp.exhibit_numbers = [ex.exhibit_number for ex in evidence.exhibits if ex.deleted_at is None]
    return resp


@router.post("/evidence/{evidence_id}/restore", response_model=EvidenceResponse)
@limiter.limit("20/minute")
def restore_evidence(
    request: Request,
    case_id: UUID,
    evidence_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Restores an archived evidence item to ACTIVE state."""
    service = EvidenceService(db)
    evidence = service.restore_evidence(current_user, case_id, evidence_id)
    resp = EvidenceResponse.model_validate(evidence)
    resp.exhibit_numbers = [ex.exhibit_number for ex in evidence.exhibits if ex.deleted_at is None]
    return resp


@router.post("/evidence/{evidence_id}/versions/upload-init", response_model=EvidenceUploadInitResponse, status_code=status.HTTP_201_CREATED)
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


@router.post("/evidence/{evidence_id}/versions/{version_id}/complete", response_model=EvidenceResponse, status_code=status.HTTP_200_OK)
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
    resp = EvidenceResponse.model_validate(evidence)
    resp.exhibit_numbers = [ex.exhibit_number for ex in evidence.exhibits if ex.deleted_at is None]
    return resp


@router.get("/evidence/{evidence_id}/versions", response_model=list[EvidenceVersionResponse])
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
        raise ResourceNotFoundError("Evidence not found")

    return evidence.versions


@router.get("/evidence/{evidence_id}/versions/{version_id}", response_model=EvidenceVersionResponse)
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
        raise ResourceNotFoundError("Evidence not found")

    version = (
        db.query(EvidenceVersion)
        .filter(EvidenceVersion.id == version_id, EvidenceVersion.evidence_id == evidence_id)
        .first()
    )
    if not version:
        raise ResourceNotFoundError("Evidence version not found")

    return version


@router.get("/evidence/{evidence_id}/download", response_model=EvidenceSignedUrlResponse)
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


@router.get("/evidence/{evidence_id}/view-url", response_model=EvidenceSignedUrlResponse)
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


@router.post("/evidence/{evidence_id}/share", response_model=EvidenceAccessGrantResponse, status_code=status.HTTP_201_CREATED)
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


@router.post("/evidence/{evidence_id}/revoke", response_model=EvidenceAccessGrantResponse, status_code=status.HTTP_200_OK)
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


@router.get("/evidence/{evidence_id}/grants", response_model=list[EvidenceAccessGrantResponse])
@limiter.limit("60/minute")
def list_evidence_grants(
    request: Request,
    case_id: UUID,
    evidence_id: UUID,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lists all active and historical access grants for an authorized evidence item."""
    service = EvidenceService(db)
    authorize_evidence_access(db, current_user, evidence_id, required_level="VIEW")
    evidence = service.db.query(Evidence).filter(Evidence.id == evidence_id, Evidence.case_id == case_id).first()
    if not evidence:
        raise ResourceNotFoundError("Evidence not found")

    grants = (
        db.query(EvidenceAccessGrant)
        .filter(EvidenceAccessGrant.evidence_id == evidence_id)
        .order_by(EvidenceAccessGrant.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    result = []
    for g in grants:
        res = EvidenceAccessGrantResponse.model_validate(g)
        if g.grantee:
            res.grantee_name = g.grantee.full_name or g.grantee.email.split("@")[0]
            res.grantee_email = g.grantee.email
        result.append(res)
    return result


@router.get("/evidence/{evidence_id}/shareable-participants", response_model=list[ShareableParticipantResponse])
@limiter.limit("60/minute")
def get_shareable_participants(
    request: Request,
    case_id: UUID,
    evidence_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Resolves eligible case participants who can receive an evidence access grant."""
    service = EvidenceService(db)
    return service.get_shareable_participants(current_user, case_id, evidence_id)


@router.get("/evidence-shared-with-me", response_model=list[SharedEvidenceItemResponse])
@limiter.limit("60/minute")
def list_case_shared_with_me(
    request: Request,
    case_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lists evidence items explicitly shared with current user in this specific case."""
    service = EvidenceService(db)
    return service.list_shared_with_me(current_user, case_id=case_id)


@router.post("/evidence/{evidence_id}/verify-integrity", response_model=EvidenceIntegrityVerifyResponse, status_code=status.HTTP_200_OK)
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


@router.post("/evidence/{evidence_id}/legal-hold", response_model=EvidenceResponse, status_code=status.HTTP_200_OK)
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
    resp = EvidenceResponse.model_validate(evidence)
    resp.exhibit_numbers = [ex.exhibit_number for ex in evidence.exhibits if ex.deleted_at is None]
    return resp


@router.delete("/evidence/{evidence_id}", status_code=status.HTTP_204_NO_CONTENT)
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


@router.get("/evidence/{evidence_id}/custody", response_model=list[EvidenceCustodyEventResponse])
@limiter.limit("60/minute")
def get_evidence_custody_chain(
    request: Request,
    case_id: UUID,
    evidence_id: UUID,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Returns chronological chain-of-custody log records linking every provenance event."""
    service = EvidenceService(db)
    events = service.get_custody_chain(current_user, case_id, evidence_id, skip=skip, limit=limit)
    return events


# Exhibit Management Endpoints
@router.post("/evidence/{evidence_id}/exhibits", response_model=CaseExhibitResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute")
def create_case_exhibit(
    request: Request,
    case_id: UUID,
    evidence_id: UUID,
    payload: CaseExhibitCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Creates a formal, version-aware case exhibit linking an evidence item to a case and hearing."""
    service = EvidenceService(db)
    exhibit = service.create_exhibit(current_user, case_id, evidence_id, payload)
    return _format_exhibit_response(exhibit)


@router.get("/evidence/{evidence_id}/exhibits", response_model=list[CaseExhibitResponse])
@limiter.limit("60/minute")
def list_exhibits_for_evidence(
    request: Request,
    case_id: UUID,
    evidence_id: UUID,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lists all active exhibits created from a specific evidence item."""
    service = EvidenceService(db)
    exhibits = service.list_exhibits(current_user, case_id, evidence_id=evidence_id, skip=skip, limit=limit)
    return [_format_exhibit_response(ex) for ex in exhibits]


@router.get("/exhibits", response_model=list[CaseExhibitResponse])
@limiter.limit("60/minute")
def list_case_exhibits(
    request: Request,
    case_id: UUID,
    hearing_id: UUID | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lists all exhibits for the case, with optional court hearing filtering."""
    service = EvidenceService(db)
    exhibits = service.list_exhibits(current_user, case_id, hearing_id=hearing_id, skip=skip, limit=limit)
    return [_format_exhibit_response(ex) for ex in exhibits]


@router.get("/exhibits/{exhibit_id}", response_model=CaseExhibitResponse)
@limiter.limit("60/minute")
def get_case_exhibit(
    request: Request,
    case_id: UUID,
    exhibit_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieves an individual exhibit by ID."""
    service = EvidenceService(db)
    exhibit = service.get_exhibit(current_user, case_id, exhibit_id)
    return _format_exhibit_response(exhibit)


@router.patch("/exhibits/{exhibit_id}", response_model=CaseExhibitResponse)
@limiter.limit("20/minute")
def update_case_exhibit(
    request: Request,
    case_id: UUID,
    exhibit_id: UUID,
    payload: CaseExhibitUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Updates exhibit title, description, hearing association, or exhibit number with collision protection."""
    service = EvidenceService(db)
    exhibit = service.update_exhibit(current_user, case_id, exhibit_id, payload)
    return _format_exhibit_response(exhibit)


@router.delete("/exhibits/{exhibit_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("20/minute")
def delete_case_exhibit(
    request: Request,
    case_id: UUID,
    exhibit_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Soft-deletes a case exhibit and records the event in the custody ledger."""
    service = EvidenceService(db)
    service.delete_exhibit(current_user, case_id, exhibit_id)
