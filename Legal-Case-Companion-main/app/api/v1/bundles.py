import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.api.v1.auth import limiter
from app.models.bundle import BundleStatus
from app.models.user import User
from app.schemas.bundle import (
    BSACertificateCreateRequest,
    BSACertificateResponse,
    BundleCreateRequest,
    BundleDetailResponse,
    BundleItemResponse,
    BundleResponse,
    BundleUpdateRequest,
)
from app.services.bundle_service import BundleService

router = APIRouter(prefix="/cases/{case_id}/bundles", tags=["evidentiary-bundles"])


def _to_detail_response(bundle: Any) -> BundleDetailResponse:
    items_dto = [BundleItemResponse.model_validate(item) for item in bundle.items]
    base_dto = BundleResponse.model_validate(bundle)
    return BundleDetailResponse(
        **base_dto.model_dump(),
        items=items_dto,
        manifest_json=bundle.manifest_json,
    )


@router.get("", response_model=list[BundleResponse])
@limiter.limit("60/minute")
def list_bundles(
    request: Request,
    case_id: uuid.UUID,
    status: BundleStatus | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lists court evidentiary bundles for a case with bounded pagination."""
    service = BundleService(db)
    bundles = service.list_bundles(current_user, case_id, status=status, limit=limit, offset=offset)
    return [BundleResponse.model_validate(b) for b in bundles]


@router.post("", response_model=BundleDetailResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute")
def create_bundle(
    request: Request,
    case_id: uuid.UUID,
    req: BundleCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Creates a new draft evidentiary bundle with deterministic exhibit ordering."""
    service = BundleService(db)
    bundle = service.create_bundle(current_user, case_id, req)
    return _to_detail_response(bundle)


@router.get("/{bundle_id}", response_model=BundleDetailResponse)
@limiter.limit("60/minute")
def get_bundle(
    request: Request,
    case_id: uuid.UUID,
    bundle_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieves full details and manifest for an evidentiary bundle."""
    service = BundleService(db)
    bundle = service.get_bundle(current_user, case_id, bundle_id)
    return _to_detail_response(bundle)


@router.put("/{bundle_id}", response_model=BundleDetailResponse)
@limiter.limit("20/minute")
def update_bundle(
    request: Request,
    case_id: uuid.UUID,
    bundle_id: uuid.UUID,
    req: BundleUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Updates a draft bundle. Finalized bundles are strictly immutable."""
    service = BundleService(db)
    bundle = service.update_bundle(current_user, case_id, bundle_id, req)
    return _to_detail_response(bundle)


@router.post("/{bundle_id}/finalize", response_model=BundleDetailResponse)
@limiter.limit("10/minute")
def finalize_bundle(
    request: Request,
    case_id: uuid.UUID,
    bundle_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Compiles the bundle PDF with Bates numbering, generates hash manifest, and finalizes immutably."""
    service = BundleService(db)
    bundle = service.finalize_bundle(current_user, case_id, bundle_id)
    return _to_detail_response(bundle)


@router.get("/{bundle_id}/download")
@limiter.limit("30/minute")
def get_bundle_download(
    request: Request,
    case_id: uuid.UUID,
    bundle_id: uuid.UUID,
    expires_in: int = Query(60, ge=15, le=300),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generates a short-lived presigned download URL for the finalized court bundle PDF."""
    service = BundleService(db)
    return service.get_bundle_download_url(current_user, case_id, bundle_id, expires_in=expires_in)


@router.post("/{bundle_id}/certificate", response_model=BSACertificateResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
def prepare_bsa_certificate(
    request: Request,
    case_id: uuid.UUID,
    bundle_id: uuid.UUID,
    req: BSACertificateCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Prepares a Section 63(4) Bharatiya Sakshya Adhiniyam, 2023 certificate draft for a finalized bundle."""
    service = BundleService(db)
    cert = service.prepare_bsa_certificate(current_user, case_id, bundle_id, req)
    return BSACertificateResponse.model_validate(cert)


@router.get("/{bundle_id}/certificate/{certificate_id}/download")
@limiter.limit("30/minute")
def get_certificate_download(
    request: Request,
    case_id: uuid.UUID,
    bundle_id: uuid.UUID,
    certificate_id: uuid.UUID,
    expires_in: int = Query(60, ge=15, le=300),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generates a short-lived presigned download URL for the prepared BSA Section 63 certificate PDF."""
    service = BundleService(db)
    return service.get_certificate_download_url(current_user, case_id, certificate_id, expires_in=expires_in)
