import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Enum, Index, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.identifiers import generate_uuid7
from app.models.base import Base, TimestampMixin


class TranslationStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    REVIEW = "REVIEW"
    APPROVED = "APPROVED"
    DEPRECATED = "DEPRECATED"


class TranslationMessage(Base, TimestampMixin):
    __tablename__ = "translation_messages"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    source_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source_text: Mapped[str] = mapped_column(Text, nullable=False)
    locale: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    translation: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[TranslationStatus] = mapped_column(
        Enum(TranslationStatus, name="translationstatus"),
        default=TranslationStatus.DRAFT,
        nullable=False,
    )
    review_status: Mapped[str] = mapped_column(String(50), default="PENDING", nullable=False)
    version: Mapped[str] = mapped_column(String(50), default="1.0.0", nullable=False)
    reviewed_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)

    __table_args__ = (
        Index("ix_translation_locale_key", "locale", "source_key", unique=True),
        Index("ix_translation_status", "status"),
    )
