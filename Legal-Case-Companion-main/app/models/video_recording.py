import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.identifiers import generate_uuid7
from app.models.base import Base, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.case import Case
    from app.models.consultation import Consultation
    from app.models.user import User


class VideoRecordingStatus(str, enum.Enum):
    PENDING = "PENDING"
    CONSENTED = "CONSENTED"
    RECORDING = "RECORDING"
    UPLOADING = "UPLOADING"
    PROCESSING = "PROCESSING"
    AVAILABLE = "AVAILABLE"
    FAILED = "FAILED"


class VideoRecording(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "video_recordings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    consultation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("consultations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    case_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cases.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    recording_type: Mapped[str] = mapped_column(
        String(50),
        default="BROWSER_MEDIA_RECORDER",
        nullable=False,
    )
    status: Mapped[VideoRecordingStatus] = mapped_column(
        Enum(VideoRecordingStatus, name="videorecordingstatus"),
        default=VideoRecordingStatus.PENDING,
        nullable=False,
        index=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    duration_seconds: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    file_size_bytes: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )
    mime_type: Mapped[str] = mapped_column(
        String(100),
        default="video/webm",
        nullable=False,
    )
    checksum_sha256: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
    storage_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    # Relationships
    consultation: Mapped["Consultation"] = relationship(
        "Consultation",
        back_populates="recordings",
    )
    case: Mapped["Case | None"] = relationship("Case")
    consents: Mapped[list["VideoRecordingConsent"]] = relationship(
        "VideoRecordingConsent",
        back_populates="recording",
        cascade="all, delete-orphan",
    )


class VideoRecordingConsent(Base, TimestampMixin):
    __tablename__ = "video_recording_consents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    consultation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("consultations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    recording_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("video_recordings.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    consented: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    consented_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("consultation_id", "user_id", name="uq_consultation_user_consent"),
    )

    # Relationships
    consultation: Mapped["Consultation"] = relationship(
        "Consultation",
        back_populates="recording_consents",
    )
    recording: Mapped["VideoRecording | None"] = relationship(
        "VideoRecording",
        back_populates="consents",
    )
    user: Mapped["User"] = relationship("User")
