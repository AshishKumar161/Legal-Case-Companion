import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.identifiers import generate_uuid7
from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.consultation import Consultation


class VideoMeetingStatus(str, enum.Enum):
    SCHEDULED = "SCHEDULED"
    ACTIVE = "ACTIVE"
    ENDED = "ENDED"
    CANCELLED = "CANCELLED"


class VideoMeeting(Base, TimestampMixin):
    __tablename__ = "video_meetings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    consultation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("consultations.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    room_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(50), default="internal_webrtc", nullable=False)
    status: Mapped[VideoMeetingStatus] = mapped_column(
        Enum(VideoMeetingStatus, name="videomeetingstatus"),
        default=VideoMeetingStatus.SCHEDULED,
        nullable=False,
    )
    scheduled_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    scheduled_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    recording_url: Mapped[str | None] = mapped_column(String, nullable=True)
    meeting_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # Relationships
    consultation: Mapped["Consultation"] = relationship(
        "Consultation", back_populates="video_meeting"
    )
