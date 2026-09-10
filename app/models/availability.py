import enum
import uuid
from datetime import time
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.identifiers import generate_uuid7
from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import LawyerProfile


class DayOfWeek(int, enum.Enum):
    MONDAY = 0
    TUESDAY = 1
    WEDNESDAY = 2
    THURSDAY = 3
    FRIDAY = 4
    SATURDAY = 5
    SUNDAY = 6


class LawyerAvailability(Base, TimestampMixin):
    __tablename__ = "lawyer_availabilities"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    lawyer_profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("lawyer_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    slot_duration_minutes: Mapped[int] = mapped_column(
        Integer, default=30, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    lawyer_profile: Mapped["LawyerProfile"] = relationship(
        "LawyerProfile", back_populates="availabilities"
    )
