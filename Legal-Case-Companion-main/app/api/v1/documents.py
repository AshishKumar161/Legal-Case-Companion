from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.api.v1.auth import limiter
from app.core.config import settings
from app.models.document import DocumentCategory, DocumentSecurityStatus
from app.models.user import User
from app.schemas.document import (
    DocumentChunkResponse,
    DocumentCreate,
    DocumentPageResponse,
    DocumentProcessingStatusResponse,
    DocumentResponse,
    DocumentSummaryStats,
    DocumentUpdate,
    DownloadDocumentResponse,
    UploadDocumentResponse,
)
from app.schemas.pagination import PaginatedResponse
from app.services.document_service import DocumentService
from app.services.scanner_service import ScannerService

# Document operations router
router = APIRouter(tags=["documents"])


# --------------------------------------------------------------------------
# CASE-SCOPED DOCUMENT ENDPOINTS
# --------------------------------------------------------------------------


@router.post(
    "/cases/{case_id}/documents/upload-init",
    response_model=UploadDocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("20/minute")
def create_document_metadata(
    request: Request,
    case_id: UUID,
    req: DocumentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document_service = DocumentService(db)
    return document_service.create_document_metadata(current_user, case_id, req)


@router.get(
    "/cases/{case_id}/documents", response_model=PaginatedResponse[DocumentResponse]
)
def get_case_documents(
    case_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    document_type: DocumentCategory | None = Query(None),
    security_status: DocumentSecurityStatus | None = Query(None),
    search: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document_service = DocumentService(db)
    return document_service.get_case_documents(
        current_user,
        case_id,
        skip=skip,
        limit=limit,
        document_type=document_type,
        security_status=security_status,
        search=search,
    )


@router.get(
    "/cases/{case_id}/documents/summary",
    response_model=DocumentSummaryStats,
)
def get_case_documents_summary(
    case_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document_service = DocumentService(db)
    return document_service.get_case_documents_summary(current_user, case_id)


@router.get(
    "/cases/{case_id}/documents/{document_id}",
    response_model=DocumentResponse,
)
def get_case_document_by_id(
    case_id: UUID,
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document_service = DocumentService(db)
    return document_service.get_document_by_id(
        current_user, document_id, case_id=case_id
    )


@router.patch(
    "/cases/{case_id}/documents/{document_id}",
    response_model=DocumentResponse,
)
def update_case_document_metadata(
    case_id: UUID,
    document_id: UUID,
    req: DocumentUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document_service = DocumentService(db)
    return document_service.update_document_metadata(
        current_user, document_id, req, case_id=case_id
    )


@router.post(
    "/cases/{case_id}/documents/{document_id}/complete",
    response_model=DocumentResponse,
)
def complete_case_document_upload(
    case_id: UUID,
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document_service = DocumentService(db)
    return document_service.complete_upload(
        current_user, document_id, case_id=case_id
    )


@router.get(
    "/cases/{case_id}/documents/{document_id}/download",
    response_model=DownloadDocumentResponse,
)
def get_case_document_download_url(
    case_id: UUID,
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document_service = DocumentService(db)
    url = document_service.generate_download_url(
        current_user, document_id, case_id=case_id
    )
    return {"download_url": url}


@router.delete(
    "/cases/{case_id}/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_case_document(
    case_id: UUID,
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document_service = DocumentService(db)
    document_service.delete_document(
        current_user, document_id, case_id=case_id
    )


@router.get(
    "/cases/{case_id}/documents/{document_id}/processing-status",
    response_model=DocumentProcessingStatusResponse,
)
def get_case_document_processing_status(
    case_id: UUID,
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document_service = DocumentService(db)
    return document_service.get_document_processing_status(
        current_user, document_id, case_id=case_id
    )


@router.post(
    "/cases/{case_id}/documents/{document_id}/process",
    response_model=DocumentProcessingStatusResponse,
)
def trigger_case_document_processing(
    case_id: UUID,
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document_service = DocumentService(db)
    return document_service.trigger_document_processing(
        current_user, document_id, case_id=case_id
    )


@router.get(
    "/cases/{case_id}/documents/{document_id}/pages",
    response_model=PaginatedResponse[DocumentPageResponse],
)
def get_case_document_pages(
    case_id: UUID,
    document_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document_service = DocumentService(db)
    return document_service.get_document_pages(
        current_user, document_id, case_id=case_id, skip=skip, limit=limit
    )


@router.get(
    "/cases/{case_id}/documents/{document_id}/chunks",
    response_model=PaginatedResponse[DocumentChunkResponse],
)
def get_case_document_chunks(
    case_id: UUID,
    document_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document_service = DocumentService(db)
    return document_service.get_document_chunks(
        current_user, document_id, case_id=case_id, skip=skip, limit=limit
    )


# --------------------------------------------------------------------------
# TOP-LEVEL DOCUMENT ENDPOINTS
# --------------------------------------------------------------------------


@router.get("/documents/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document_service = DocumentService(db)
    return document_service.get_document_by_id(current_user, document_id)


@router.patch("/documents/{document_id}", response_model=DocumentResponse)
def update_document(
    document_id: UUID,
    req: DocumentUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document_service = DocumentService(db)
    return document_service.update_document_metadata(current_user, document_id, req)


@router.post("/documents/{document_id}/complete", response_model=DocumentResponse)
def complete_document_upload(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document_service = DocumentService(db)
    return document_service.complete_upload(current_user, document_id)


@router.get(
    "/documents/{document_id}/download", response_model=DownloadDocumentResponse
)
def get_document_download_url(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document_service = DocumentService(db)
    url = document_service.generate_download_url(current_user, document_id)
    return {"download_url": url}


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document_service = DocumentService(db)
    document_service.delete_document(current_user, document_id)


@router.get(
    "/documents/{document_id}/processing-status",
    response_model=DocumentProcessingStatusResponse,
)
def get_document_processing_status(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document_service = DocumentService(db)
    return document_service.get_document_processing_status(
        current_user, document_id
    )


@router.post(
    "/documents/{document_id}/process",
    response_model=DocumentProcessingStatusResponse,
)
def trigger_document_processing(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document_service = DocumentService(db)
    return document_service.trigger_document_processing(
        current_user, document_id
    )


@router.get(
    "/documents/{document_id}/pages",
    response_model=PaginatedResponse[DocumentPageResponse],
)
def get_document_pages(
    document_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document_service = DocumentService(db)
    return document_service.get_document_pages(
        current_user, document_id, skip=skip, limit=limit
    )


@router.get(
    "/documents/{document_id}/chunks",
    response_model=PaginatedResponse[DocumentChunkResponse],
)
def get_document_chunks(
    document_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document_service = DocumentService(db)
    return document_service.get_document_chunks(
        current_user, document_id, skip=skip, limit=limit
    )


@router.post("/documents/{document_id}/scan")
def simulate_malware_scan(
    document_id: UUID,
    is_safe: bool = True,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if settings.ENVIRONMENT == "production":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")

    from app.core.authorization import authorize_document_modification

    doc = authorize_document_modification(db, current_user, document_id)
    if doc.security_status == DocumentSecurityStatus.PENDING:
        doc.security_status = DocumentSecurityStatus.QUARANTINED
        db.commit()

    scanner_service = ScannerService(db)
    scanner_service.simulate_scan(document_id, is_safe)
    return {"message": "Scan simulated successfully"}


