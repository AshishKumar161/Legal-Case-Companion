import datetime
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.identifiers import generate_uuid7
from app.models.base import Base, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.case import Case
    from app.models.user import User


class CourtCase(Base, TimestampMixin, SoftDeleteMixin):
    """Authoritative court case record tracked across Indian High Courts and District Courts.

    Integrates with eCourts registries and NJDG cause-lists while preserving complete provenance.
    """

    __tablename__ = "court_cases"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    cnr: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    case_number: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    case_type: Mapped[str] = mapped_column(String(50), nullable=False)
    filing_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    filing_date: Mapped[str | None] = mapped_column(String(50), nullable=True)
    registration_date: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Court Forum
    court_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    bench: Mapped[str | None] = mapped_column(String(255), nullable=True)
    court_room: Mapped[str | None] = mapped_column(String(50), nullable=True)
    item_number: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Parties & Advocates
    petitioner: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    petitioner_advocate: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    respondent: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    respondent_advocate: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)

    # Legal Substantive Details
    acts_and_sections: Mapped[str | None] = mapped_column(Text, nullable=True)
    technical_status: Mapped[str] = mapped_column(String(100), nullable=False)
    human_status: Mapped[str] = mapped_column(Text, nullable=False)

    # Upcoming Hearing
    next_hearing_date: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    next_hearing_purpose: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Provenance & Synchronisation Metadata
    source_provenance: Mapped[str] = mapped_column(
        String(100), default="OFFICIAL COURT DATA", nullable=False
    )
    last_synchronized_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.current_timestamp(), nullable=False
    )
    sync_status: Mapped[str] = mapped_column(String(50), default="SYNCED", nullable=False)

    # Optional Linkage to Internal LCC Matter Workspace
    case_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cases.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Structured Payloads for Bounded History & Daily Boards
    history_json: Mapped[list | None] = mapped_column(JSON, default=list, nullable=True)
    cause_list_json: Mapped[dict | None] = mapped_column(JSON, default=dict, nullable=True)
    orders_json: Mapped[list | None] = mapped_column(JSON, default=list, nullable=True)

    # Relationships
    case: Mapped["Case | None"] = relationship("Case")
    followers: Mapped[list["UserFollowedCase"]] = relationship(
        "UserFollowedCase", back_populates="court_case", cascade="all, delete-orphan"
    )


class UserFollowedCase(Base, TimestampMixin):
    """Subscription record indicating a user is following court updates for a specific case."""

    __tablename__ = "user_followed_cases"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    court_case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("court_cases.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Relationships
    user: Mapped["User"] = relationship("User")
    court_case: Mapped["CourtCase"] = relationship("CourtCase", back_populates="followers")
