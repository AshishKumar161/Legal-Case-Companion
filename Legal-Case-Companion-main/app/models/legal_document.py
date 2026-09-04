import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.identifiers import generate_uuid7
from app.models.base import Base, TimestampMixin


class LegalDocumentType(str, enum.Enum):
    TERMS_OF_SERVICE = "TERMS_OF_SERVICE"
    ADVOCATE_TERMS = "ADVOCATE_TERMS"
    PRIVACY_NOTICE = "PRIVACY_NOTICE"
    AI_DISCLOSURE = "AI_DISCLOSURE"
    EVIDENCE_STORAGE_DISCLOSURE = "EVIDENCE_STORAGE_DISCLOSURE"
    CONSULTATION_DISCLOSURE = "CONSULTATION_DISCLOSURE"
    COOKIE_NOTICE = "COOKIE_NOTICE"


class LegalDocumentVersion(Base, TimestampMixin):
    __tablename__ = "legal_document_versions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    document_type: Mapped[LegalDocumentType] = mapped_column(
        Enum(LegalDocumentType, name="legaldocumenttype"),
        nullable=False,
        index=True,
    )
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    locale: Mapped[str] = mapped_column(String(20), default="en-IN", nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    summary_of_changes: Mapped[str | None] = mapped_column(Text, nullable=True)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    supersedes_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("legal_document_versions.id", ondelete="SET NULL"), nullable=True
    )
    approval_status: Mapped[str] = mapped_column(String(50), default="DRAFT", nullable=False)
    publication_status: Mapped[str] = mapped_column(String(50), default="DRAFT", nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)

    __table_args__ = (
        Index("ix_legal_doc_type_ver_locale", "document_type", "version", "locale", unique=True),
        Index("ix_legal_doc_publication", "publication_status"),
    )


class UserDocumentConsent(Base, TimestampMixin):
    __tablename__ = "user_document_consents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("legal_document_versions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    document_type: Mapped[LegalDocumentType] = mapped_column(
        Enum(LegalDocumentType, name="legaldocumenttype"), nullable=False
    )
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    locale: Mapped[str] = mapped_column(String(20), default="en-IN", nullable=False)
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    ip_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)

    __table_args__ = (
        Index("ix_user_consent_user_doc", "user_id", "document_type", "version"),
    )
