"""
Model: General Legal AI Advisor Chat
User-scoped (not case-bound) persistent chat sessions for the Legal AI Advisor feature.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING

from app.core.identifiers import generate_uuid7
from app.models.base import Base, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class AdvisorSession(Base, TimestampMixin, SoftDeleteMixin):
    """Persistent general-purpose legal AI chat session (user-scoped, not case-scoped)."""

    __tablename__ = "advisor_sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="ACTIVE", nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User")
    messages: Mapped[list["AdvisorMessage"]] = relationship(
        "AdvisorMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="AdvisorMessage.created_at.asc()",
    )


class AdvisorMessage(Base):
    """A single message in a Legal AI Advisor session."""

    __tablename__ = "advisor_messages"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("advisor_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # "user" or "assistant"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    model_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    latency_ms: Mapped[float | None] = mapped_column(nullable=True)
    extra: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.current_timestamp()
    )

    # Relationships
    session: Mapped["AdvisorSession"] = relationship("AdvisorSession", back_populates="messages")
