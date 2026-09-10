from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.api.deps import RequireRole, get_current_user, get_db
from app.api.v1.auth import limiter
from app.core.exceptions import ResourceNotFoundError
from app.models.legal_authority import LegalSource
from app.models.user import User, UserRole
from app.schemas.legal_authority import (
    LegalAuthorityIngestRequest,
    LegalAuthorityResponse,
    LegalAuthoritySearchRequest,
    LegalAuthoritySearchResponse,
)
from app.domain.ai.legal_authority_ingestion import LegalAuthorityIngestionService
from app.domain.ai.legal_authority_retrieval import LegalAuthorityRetrievalService

router = APIRouter(prefix="/legal-authorities", tags=["legal-authorities"])


@router.post("/search", response_model=LegalAuthoritySearchResponse)
@limiter.limit("30/minute")
def search_legal_authorities(
    request: Request,
    payload: LegalAuthoritySearchRequest,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> LegalAuthoritySearchResponse:
    """Searches authoritative Indian legal provisions, statutes, and judicial decisions

    with temporal validity filtering, citation recognition, and hierarchy ranking.
    """
    service = LegalAuthorityRetrievalService(db)
    return service.search_legal_authorities(payload)


@router.post("/ingest", response_model=LegalAuthorityResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
def ingest_legal_authority(
    request: Request,
    payload: LegalAuthorityIngestRequest,
    db: Session = Depends(get_db),
    _current_admin: User = Depends(RequireRole([UserRole.ADMIN])),
) -> LegalAuthorityResponse:
    """Idempotently ingests or updates an authoritative legal source and its provisions.

    Restricted to system administrators.
    """
    service = LegalAuthorityIngestionService(db)
    return service.ingest_legal_authority(payload)


@router.get("/{canonical_id}", response_model=LegalAuthorityResponse)
@limiter.limit("30/minute")
def get_legal_authority(
    request: Request,
    canonical_id: str,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> LegalAuthorityResponse:
    """Retrieves an authoritative legal source with all its temporal provision versions."""
    source = (
        db.query(LegalSource)
        .filter(LegalSource.canonical_identifier == canonical_id, LegalSource.is_active.is_(True))
        .first()
    )
    if not source:
        raise ResourceNotFoundError(f"Legal authority '{canonical_id}' not found")
    return LegalAuthorityResponse.model_validate(source)
