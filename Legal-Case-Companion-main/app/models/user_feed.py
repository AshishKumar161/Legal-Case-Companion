import datetime
import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.identifiers import generate_uuid7
from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class UserFeedAcknowledgment(Base, TimestampMixin):
    """Tracks each user's last acknowledged checkpoint for the deterministic

    'What changed since your last visit' experience.
    """

    __tablename__ = "user_feed_acknowledgments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    last_acknowledged_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.current_timestamp(),
        nullable=False,
    )
    preferences: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=dict, nullable=True)

    # Relationship
    user: Mapped["User"] = relationship("User")
