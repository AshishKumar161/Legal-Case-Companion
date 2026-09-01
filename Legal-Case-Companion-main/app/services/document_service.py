import logging
import re
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.authorization import (
    authorize_case_access,
    authorize_case_modification,
    authorize_document_access,
    authorize_document_deletion,
    authorize_document_modification,
)
from app.core.exceptions import (
    AuthorizationError,
    ValidationError,
)
from app.core.identifiers import generate_uuid7
from app.core.storage import get_storage_provider
from app.models.ai import DocumentChunk
from app.models.case import CaseStatus
from app.models.document import (
    ALLOWED_MIME_TYPES,
    MAX_FILE_SIZE_BYTES,
    Document,
    DocumentCategory,
    DocumentSecurityStatus,
)
from app.models.document_page import DocumentPage
from app.models.user import User
from app.schemas.document import DocumentCreate, DocumentUpdate
from app.services.auth_service import AuthService
from app.services.case_service import CaseService
from app.services.document_processor import DocumentProcessor

logger = logging.getLogger(__name__)


class DocumentService:
    def __init__(self, db: Session):
        self.db = db
        self.auth_service = AuthService(db)
        self.storage = get_storage_provider()

    def _log_audit(self, event_type: str, user_id: uuid.UUID, metadata: dict):
        self.auth_service.log_audit_event(
            event_type, user_id, metadata, action="document_mutation"
        )

    def _validate_filename(self, filename: str) -> None:
        if (
            not filename
            or not filename.strip()
            or len(filename) > 255
            or "/" in filename
            or "\\" in filename
            or "\x00" in filename
            or ".." in filename
        ):
            raise ValidationError("Invalid filename")

    def create_document_metadata(
        self, user: User, case_id: uuid.UUID, req: DocumentCreate
    ) -> dict[str, Any]:
        # Ensure user can access and modify the case to attach a document to it
        case_ = authorize_case_modification(self.db, user, case_id)

        if case_.status in (CaseStatus.CLOSED, CaseStatus.CANCELLED):
            raise ValidationError("Cannot upload documents to a closed or cancelled case")

        # MIME type validation
        if req.mime_type not in ALLOWED_MIME_TYPES:
            raise ValidationError(
                f"Unsupported file type. Allowed types: {', '.join(sorted(ALLOWED_MIME_TYPES))}"
            )

        # File size validation (max 10 MB)
        if req.file_size <= 0:
            raise ValidationError("File size must be greater than zero")
        if req.file_size > MAX_FILE_SIZE_BYTES:
            raise ValidationError(
                f"File exceeds maximum allowed size of {MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB"
            )

        # Strict filename validation
        self._validate_filename(req.filename)

        # Checksum format validation (if supplied, must be 64-char hex string)
        if req.checksum:
            cleaned_checksum = req.checksum.strip()
            if not re.fullmatch(r"^[a-fA-F0-9]{64}$", cleaned_checksum):
                raise ValidationError("Checksum must be a valid 64-character SHA-256 hex string")

        document_id = generate_uuid7()

        # System-generated private storage key — strictly partitioned by case and document UUID
        storage_key = f"cases/{case_id}/documents/{document_id}"

        doc = Document(
            id=document_id,
            case_id=case_id,
            uploaded_by=user.id,
            filename=req.filename.strip(),
            storage_key=storage_key,
            mime_type=req.mime_type,
            file_size=req.file_size,
            security_status=DocumentSecurityStatus.PENDING,
            document_type=req.document_type,
            description=req.description.strip() if req.description else None,
            checksum=req.checksum.strip() if req.checksum else None,
            version=1,
            is_confidential=req.is_confidential,
        )
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)

        self._log_audit(
            "DOCUMENT_UPLOAD_REQUESTED",
            user.id,
            {
                "case_id": str(case_id),
                "document_id": str(doc.id),
                "filename": doc.filename,
                "document_type": doc.document_type.value,
            },
        )

        case_service = CaseService(self.db)
        case_service.record_case_activity(
            case_id,
            user.id,
            "DOCUMENT_UPLOADED",
            f"Document {req.filename} was uploaded ({doc.document_type.value})",
            {"document_id": str(doc.id), "filename": req.filename, "document_type": doc.document_type.value},
        )

        upload_url = self.storage.generate_presigned_upload_url(
            object_key=storage_key,
            mime_type=req.mime_type,
            expires_in=900,  # 15 minutes
        )

        return {"document": doc, "upload_url": upload_url}

    def update_document_metadata(
        self,
        user: User,
        document_id: uuid.UUID,
        req: DocumentUpdate,
        case_id: uuid.UUID | None = None,
    ) -> Document:
        doc = authorize_document_modification(self.db, user, document_id, case_id=case_id)

        if doc.case and doc.case.status in (CaseStatus.CLOSED, CaseStatus.CANCELLED):
            raise ValidationError("Cannot update documents in a closed or cancelled case")

        updated_fields: dict[str, Any] = {}
        if req.filename is not None:
            self._validate_filename(req.filename)
            doc.filename = req.filename.strip()
            updated_fields["filename"] = doc.filename

        if req.document_type is not None:
            doc.document_type = req.document_type
            updated_fields["document_type"] = doc.document_type.value

        if req.description is not None:
            doc.description = req.description.strip() if req.description else None
            updated_fields["description"] = doc.description

        if req.is_confidential is not None:
            doc.is_confidential = req.is_confidential
            updated_fields["is_confidential"] = doc.is_confidential

        if updated_fields:
            self.db.commit()
            self.db.refresh(doc)

            self._log_audit(
                "DOCUMENT_METADATA_UPDATED",
                user.id,
                {"document_id": str(document_id), "updated_fields": updated_fields},
            )

            case_service = CaseService(self.db)
            case_service.record_case_activity(
                doc.case_id,
                user.id,
                "DOCUMENT_UPDATED",
                f"Metadata for document {doc.filename} was updated",
                {"document_id": str(doc.id), "updated_fields": updated_fields},
            )

        return doc

    def get_case_documents(
        self,
        user: User,
        case_id: uuid.UUID,
        skip: int = 0,
        limit: int = 20,
        document_type: DocumentCategory | None = None,
        security_status: DocumentSecurityStatus | None = None,
        search: str | None = None,
    ) -> dict:
        authorize_case_access(self.db, user, case_id)
        query = (
            self.db.query(Document)
            .filter(Document.case_id == case_id, Document.deleted_at.is_(None))
        )

        if document_type is not None:
            query = query.filter(Document.document_type == document_type)

        if security_status is not None:
            query = query.filter(Document.security_status == security_status)

        if search:
            search_clean = search.strip()
            if search_clean:
                query = query.filter(Document.filename.ilike(f"%{search_clean}%"))

        query = query.order_by(Document.created_at.desc(), Document.id.desc())

        total = query.count()
        items = query.offset(skip).limit(limit).all()
        return {"items": items, "total": total, "skip": skip, "limit": limit}

    def get_document_by_id(
        self,
        user: User,
        document_id: uuid.UUID,
        case_id: uuid.UUID | None = None,
    ) -> Document:
        doc = authorize_document_access(self.db, user, document_id, case_id=case_id)
        self._log_audit("DOCUMENT_ACCESSED", user.id, {"document_id": str(document_id)})
        return doc

    def complete_upload(
        self,
        user: User,
        document_id: uuid.UUID,
        case_id: uuid.UUID | None = None,
    ) -> Document:
        doc = authorize_document_modification(self.db, user, document_id, case_id=case_id)

        if doc.security_status != DocumentSecurityStatus.PENDING:
            raise ValidationError(
                f"Document cannot be completed from status {doc.security_status.name}"
            )

        if not self.storage.object_exists(doc.storage_key):
            raise ValidationError("Uploaded file not found in storage")

        doc.security_status = DocumentSecurityStatus.QUARANTINED
        self.db.commit()
        self.db.refresh(doc)

        self._log_audit(
            "DOCUMENT_UPLOAD_COMPLETED", user.id, {"document_id": str(document_id)}
        )
        return doc

    def generate_download_url(
        self,
        user: User,
        document_id: uuid.UUID,
        case_id: uuid.UUID | None = None,
    ) -> str:
        doc = authorize_document_access(self.db, user, document_id, case_id=case_id)

        # Only SAFE documents can be downloaded
        if doc.security_status != DocumentSecurityStatus.SAFE:
            self._log_audit(
                "SECURITY_FAILURE",
                user.id,
                {
                    "document_id": str(document_id),
                    "reason": "Attempted to download non-approved document",
                    "current_status": doc.security_status.value,
                },
            )
            raise AuthorizationError("Document is not approved for download.")

        download_url = self.storage.generate_presigned_download_url(
            object_key=doc.storage_key,
            expires_in=300,  # 5 minutes
        )
        self._log_audit(
            "DOCUMENT_DOWNLOAD_URL_GENERATED",
            user.id,
            {"document_id": str(document_id)},
        )

        return download_url

    def delete_document(
        self,
        user: User,
        document_id: uuid.UUID,
        case_id: uuid.UUID | None = None,
    ) -> bool:
        doc = authorize_document_deletion(self.db, user, document_id, case_id=case_id)

        if doc.case and doc.case.status in (CaseStatus.CLOSED, CaseStatus.CANCELLED):
            raise ValidationError("Cannot delete documents from a closed or cancelled case")

        self._log_audit(
            "DOCUMENT_DELETION_REQUESTED", user.id, {"document_id": str(document_id)}
        )

        # Soft delete in application ONLY.
        # Do NOT immediately delete from S3 — legal retention requirements.
        doc.deleted_at = datetime.now(UTC)
        self.db.commit()

        self._log_audit(
            "DOCUMENT_SOFT_DELETED", user.id, {"document_id": str(document_id)}
        )

        case_service = CaseService(self.db)
        case_service.record_case_activity(
            doc.case_id,
            user.id,
            "DOCUMENT_DELETED",
            f"Document {doc.filename} was deleted",
            {"document_id": str(doc.id), "filename": doc.filename},
        )
        return True

    def get_case_documents_summary(
        self, user: User, case_id: uuid.UUID
    ) -> dict[str, Any]:
        authorize_case_access(self.db, user, case_id)

        docs = (
            self.db.query(Document.security_status, Document.document_type)
            .filter(Document.case_id == case_id, Document.deleted_at.is_(None))
            .all()
        )

        total = len(docs)
        safe = sum(1 for d in docs if d[0] == DocumentSecurityStatus.SAFE)
        pending = sum(1 for d in docs if d[0] in (DocumentSecurityStatus.PENDING, DocumentSecurityStatus.VALIDATING))
        quarantined = sum(1 for d in docs if d[0] in (DocumentSecurityStatus.QUARANTINED, DocumentSecurityStatus.SCANNING))
        rejected = sum(1 for d in docs if d[0] == DocumentSecurityStatus.REJECTED)

        by_category: dict[str, int] = {}
        for d in docs:
            cat_name = d[1].value if hasattr(d[1], "value") else str(d[1])
            by_category[cat_name] = by_category.get(cat_name, 0) + 1

        return {
            "total": total,
            "safe": safe,
            "pending": pending,
            "quarantined": quarantined,
            "rejected": rejected,
            "by_category": by_category,
        }

    def get_document_processing_status(
        self,
        user: User,
        document_id: uuid.UUID,
        case_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        doc =  authorize_document_access(self.db, user, document_id, case_id=case_id)

        chunk_count = (
            self.db.query(DocumentChunk)
            .filter(
                DocumentChunk.document_id == doc.id,
                DocumentChunk.deleted_at.is_(None),
            )
            .count()
        )

        return {
            "document_id": doc.id,
            "case_id": doc.case_id,
            "security_status": doc.security_status.value,
            "processing_status": doc.processing_status.value,
            "processing_error": doc.processing_error,
            "page_count": doc.page_count,
            "word_count": doc.word_count,
            "character_count": doc.character_count,
            "chunk_count": chunk_count,
            "version": doc.version,
            "processed_at": doc.processed_at,
        }

    def get_document_pages(
        self,
        user: User,
        document_id: uuid.UUID,
        case_id: uuid.UUID | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> dict[str, Any]:
        doc = authorize_document_access(self.db, user, document_id, case_id=case_id)

        query = (
            self.db.query(DocumentPage)
            .filter(
                DocumentPage.document_id == doc.id,
                DocumentPage.deleted_at.is_(None),
            )
            .order_by(DocumentPage.page_number.asc())
        )

        total = query.count()
        items = query.offset(skip).limit(limit).all()
        return {"items": items, "total": total, "skip": skip, "limit": limit}

    def get_document_chunks(
        self,
        user: User,
        document_id: uuid.UUID,
        case_id: uuid.UUID | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> dict[str, Any]:
        doc = authorize_document_access(self.db, user, document_id, case_id=case_id)

        query = (
            self.db.query(DocumentChunk)
            .filter(
                DocumentChunk.document_id == doc.id,
                DocumentChunk.deleted_at.is_(None),
            )
            .order_by(DocumentChunk.created_at.asc(), DocumentChunk.id.asc())
        )

        total = query.count()
        items = query.offset(skip).limit(limit).all()
        return {"items": items, "total": total, "skip": skip, "limit": limit}

    def trigger_document_processing(
        self,
        user: User,
        document_id: uuid.UUID,
        case_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        doc = authorize_document_modification(self.db, user, document_id, case_id=case_id)

        if doc.case and doc.case.status in (CaseStatus.CLOSED, CaseStatus.CANCELLED):
            raise ValidationError("Cannot process documents in a closed or cancelled case")

        if doc.security_status != DocumentSecurityStatus.SAFE:
            raise ValidationError("Only SAFE documents can be processed for evidence extraction")

        processor = DocumentProcessor(self.db)
        processor.process_document(doc.id)

        return self.get_document_processing_status(user, document_id, case_id=case_id)
