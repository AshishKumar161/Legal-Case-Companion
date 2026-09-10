import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.identifiers import generate_uuid7
from app.models.base import Base, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.ai import DocumentChunk
    from app.models.case import Case
    from app.models.document_page import DocumentPage
    from app.models.user import User

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "text/plain",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "image/png",
    "image/jpeg",
    "image/jpg",
}

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


class DocumentSecurityStatus(str, enum.Enum):
    PENDING = "PENDING"
    QUARANTINED = "QUARANTINED"
    VALIDATING = "VALIDATING"
    SCANNING = "SCANNING"
    SAFE = "SAFE"
    REJECTED = "REJECTED"


class DocumentProcessingStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    READY = "READY"
    FAILED = "FAILED"
    UNSUPPORTED_FORMAT = "UNSUPPORTED_FORMAT"
    CORRUPTED_FILE = "CORRUPTED_FILE"
    EMPTY_DOCUMENT = "EMPTY_DOCUMENT"
    OCR_REQUIRED = "OCR_REQUIRED"


class DocumentCategory(str, enum.Enum):
    EVIDENCE = "EVIDENCE"
    PLEADINGS = "PLEADINGS"
    COURT_ORDER = "COURT_ORDER"
    CONTRACT = "CONTRACT"
    NOTICE = "NOTICE"
    ID_PROOF = "ID_PROOF"
    MISCELLANEOUS = "MISCELLANEOUS"


# Alias for flexibility
DocumentType = DocumentCategory


class Document(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), unique=True, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    security_status: Mapped[DocumentSecurityStatus] = mapped_column(
        Enum(DocumentSecurityStatus, name="documentsecuritystatus"),
        default=DocumentSecurityStatus.QUARANTINED,
        nullable=False,
    )
    processing_status: Mapped[DocumentProcessingStatus] = mapped_column(
        Enum(DocumentProcessingStatus, name="documentprocessingstatus"),
        default=DocumentProcessingStatus.PENDING,
        nullable=False,
        index=True,
    )
    processing_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    word_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    character_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    document_type: Mapped[DocumentCategory] = mapped_column(
        Enum(DocumentCategory, name="documentcategory"),
        default=DocumentCategory.MISCELLANEOUS,
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_confidential: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    # Relationships
    case: Mapped["Case"] = relationship("Case", back_populates="documents")
    uploader: Mapped["User"] = relationship("User")
    pages: Mapped[list["DocumentPage"]] = relationship(
        "DocumentPage", back_populates="document", cascade="all, delete-orphan", order_by="DocumentPage.page_number.asc()"
    )
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        "DocumentChunk", back_populates="document", cascade="all, delete-orphan"
    )
