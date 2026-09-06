from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
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
from app.schemas.evidence import SharedEvidenceItemResponse
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


@router.post(
    "/cases/{case_id}/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("30/minute")
async def upload_case_document_direct(
    request: Request,
    case_id: UUID,
    file: UploadFile = File(...),
    title: str | None = Form(None),
    category: str = Form("MISCELLANEOUS"),
    description: str | None = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Direct multipart/form-data document upload to a case matter.
    Saves file to storage, creates Document record, records case activity, and notifies participants.
    """
    import hashlib
    import logging
    from app.core.authorization import authorize_case_modification
    from app.core.exceptions import ValidationError
    from app.core.file_validation import validate_filename_security
    from app.core.identifiers import generate_uuid7
    from app.core.storage import get_storage_provider
    from app.models.case import CaseParticipant, CaseStatus, ParticipantStatus
    from app.models.document import (
        Document,
        DocumentCategory,
        DocumentProcessingStatus,
        DocumentSecurityStatus,
        MAX_FILE_SIZE_BYTES,
    )
    from app.models.notification import NotificationType
    from app.services.case_service import CaseService
    from app.services.notification_service import NotificationService

    logger = logging.getLogger(__name__)

    case_ = authorize_case_modification(db, current_user, case_id)
    if case_.status in (CaseStatus.CLOSED, CaseStatus.CANCELLED):
        raise ValidationError("Cannot upload documents to a closed or cancelled case")

    file_bytes = await file.read()
    if not file_bytes or len(file_bytes) == 0:
        raise ValidationError("Uploaded file cannot be empty")
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise ValidationError(
            f"File exceeds maximum allowed size of {MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB"
        )

    # Safe category mapping supporting both frontend short names and enum values
    category_map = {
        "AGREEMENT": DocumentCategory.CONTRACT,
        "CONTRACT": DocumentCategory.CONTRACT,
        "COURT": DocumentCategory.COURT_ORDER,
        "COURT_ORDER": DocumentCategory.COURT_ORDER,
        "ID": DocumentCategory.ID_PROOF,
        "ID_PROOF": DocumentCategory.ID_PROOF,
        "NOTICE": DocumentCategory.NOTICE,
        "EVIDENCE": DocumentCategory.EVIDENCE,
        "PLEADINGS": DocumentCategory.PLEADINGS,
        "OTHER": DocumentCategory.MISCELLANEOUS,
        "MISCELLANEOUS": DocumentCategory.MISCELLANEOUS,
    }
    cleaned_cat = category.strip().upper() if category else "MISCELLANEOUS"
    doc_category = category_map.get(cleaned_cat, DocumentCategory.MISCELLANEOUS)

    raw_filename = file.filename or "document.pdf"
    clean_filename = validate_filename_security(raw_filename)
    mime_type = file.content_type or "application/octet-stream"

    checksum = hashlib.sha256(file_bytes).hexdigest()
    document_id = generate_uuid7()
    storage_key = f"cases/{case_id}/documents/{document_id}_{clean_filename}"

    storage = get_storage_provider()
    storage.put_object_bytes(storage_key, file_bytes, mime_type)

    display_title = title.strip() if (title and title.strip()) else clean_filename

    doc = Document(
        id=document_id,
        case_id=case_id,
        uploaded_by=current_user.id,
        filename=display_title,
        storage_key=storage_key,
        mime_type=mime_type,
        file_size=len(file_bytes),
        security_status=DocumentSecurityStatus.SAFE,
        processing_status=DocumentProcessingStatus.READY,
        document_type=doc_category,
        description=description.strip() if description else None,
        checksum=checksum,
        version=1,
        is_confidential=False,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    case_service = CaseService(db)
    case_service.record_case_activity(
        case_id,
        current_user.id,
        "DOCUMENT_UPLOADED",
        f"Document '{display_title}' was shared with the case ({doc_category.value})",
        {
            "document_id": str(doc.id),
            "filename": display_title,
            "document_type": doc_category.value,
            "file_size": len(file_bytes),
        },
    )

    # Automatically notify other case participants (Lawyer or Client)
    other_participants = (
        db.query(CaseParticipant)
        .filter(
            CaseParticipant.case_id == case_id,
            CaseParticipant.user_id != current_user.id,
            CaseParticipant.status == ParticipantStatus.ACTIVE,
        )
        .all()
    )
    uploader_name = current_user.full_name or "Participant"
    notification_service = NotificationService(db)
    for p in other_participants:
        try:
            notification_service.create_notification(
                user_id=p.user_id,
                type=NotificationType.DOCUMENT_READY,
                title=f"New Document Shared in {case_.title}",
                message=f"{uploader_name} shared document '{display_title}' ({doc_category.value}) with you.",
                case_id=case_id,
                document_id=doc.id,
                send_email=False,
            )
        except Exception as e:
            logger.warning(f"Failed to dispatch document notification to {p.user_id}: {e}")

    return doc


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


@router.get(
    "/documents/shared-with-me",
    response_model=list[SharedEvidenceItemResponse],
)
def get_documents_shared_with_me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Returns all private documents and evidence explicitly shared with the current authenticated user."""
    from app.services.evidence_service import EvidenceService

    service = EvidenceService(db)
    return service.list_shared_with_me(current_user)


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


