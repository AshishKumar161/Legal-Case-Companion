import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.identifiers import generate_uuid7
from app.models.base import Base, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.auth import RefreshTokenSession, UserExternalIdentity
    from app.models.case import CaseParticipant


class UserRole(str, enum.Enum):
    CLIENT = "CLIENT"
    LAWYER = "LAWYER"
    ADMIN = "ADMIN"


class AccountStatus(str, enum.Enum):
    REGISTERED = "REGISTERED"
    VERIFIED = "VERIFIED"
    ACTIVE = "ACTIVE"
    RESTRICTED = "RESTRICTED"
    SUSPENDED = "SUSPENDED"
    DEACTIVATED = "DEACTIVATED"


class VerificationStatus(str, enum.Enum):
    PENDING = "PENDING"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class User(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    phone: Mapped[str | None] = mapped_column(
        String, unique=True, nullable=True, index=True
    )
    password_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="userrole"), nullable=False
    )
    account_status: Mapped[AccountStatus] = mapped_column(
        Enum(AccountStatus, name="accountstatus"),
        default=AccountStatus.ACTIVE,
        nullable=False,
    )
    account_locale: Mapped[str] = mapped_column(String(20), default="en-IN", nullable=False)
    preferred_language: Mapped[str] = mapped_column(String(10), default="en", nullable=False)
    fallback_language: Mapped[str] = mapped_column(String(10), default="en", nullable=False)

    # Relationships
    client_profile: Mapped["ClientProfile | None"] = relationship(
        "ClientProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    lawyer_profile: Mapped["LawyerProfile | None"] = relationship(
        "LawyerProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    refresh_token_sessions: Mapped[list["RefreshTokenSession"]] = relationship(
        "RefreshTokenSession", back_populates="user", cascade="all, delete-orphan"
    )
    external_identities: Mapped[list["UserExternalIdentity"]] = relationship(
        "UserExternalIdentity", back_populates="user", cascade="all, delete-orphan"
    )
    case_participants: Mapped[list["CaseParticipant"]] = relationship(
        "CaseParticipant", back_populates="user", cascade="all, delete-orphan"
    )


class ClientProfile(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "client_profiles"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        unique=True,
        nullable=False,
        index=True,
    )
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    location: Mapped[str | None] = mapped_column(String, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="client_profile")
    consultations: Mapped[list["Consultation"]] = relationship(
        "Consultation", back_populates="client", cascade="all, delete-orphan"
    )

    @property
    def email(self) -> str | None:
        return self.user.email if self.user else None

    @property
    def phone(self) -> str | None:
        return self.user.phone if self.user else None


class LawyerProfile(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "lawyer_profiles"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        unique=True,
        nullable=False,
        index=True,
    )
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    bio: Mapped[str | None] = mapped_column(String, nullable=True)
    location: Mapped[str | None] = mapped_column(String, nullable=True)
    consultation_fee: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    practice_areas: Mapped[list | None] = mapped_column(JSON, nullable=True)
    experience_years: Mapped[int | None] = mapped_column(Integer, nullable=True)
    court_jurisdictions: Mapped[list | None] = mapped_column(JSON, nullable=True)
    languages: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Ephemeral runtime presence attributes (populated by PresenceService / ConsultationService)
    is_online: bool = False
    is_available: bool = False
    presence_status: str = "OFFLINE"

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="lawyer_profile")
    verifications: Mapped[list["LawyerVerification"]] = relationship(
        "LawyerVerification",
        back_populates="lawyer_profile",
        cascade="all, delete-orphan",
    )
    consultations: Mapped[list["Consultation"]] = relationship(
        "Consultation", back_populates="lawyer", cascade="all, delete-orphan"
    )
    availabilities: Mapped[list["LawyerAvailability"]] = relationship(
        "LawyerAvailability",
        back_populates="lawyer_profile",
        cascade="all, delete-orphan",
    )

    @property
    def email(self) -> str | None:
        return self.user.email if self.user else None

    @property
    def phone(self) -> str | None:
        return self.user.phone if self.user else None

    @property
    def verification_status(self) -> str:
        if not self.verifications:
            return "PENDING"
        # Check if any verification is APPROVED
        if any(v.status == VerificationStatus.APPROVED for v in self.verifications):
            return "APPROVED"
        # Check if any verification is UNDER_REVIEW
        if any(v.status == VerificationStatus.UNDER_REVIEW for v in self.verifications):
            return "UNDER_REVIEW"
        # Check if any verification is PENDING
        if any(v.status == VerificationStatus.PENDING for v in self.verifications):
            return "PENDING"
        return "REJECTED"


class LawyerVerification(Base, TimestampMixin):
    __tablename__ = "lawyer_verifications"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    lawyer_profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("lawyer_profiles.id", ondelete="RESTRICT"), nullable=False
    )
    enrollment_number: Mapped[str] = mapped_column(String, nullable=False)
    state_bar_council: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[VerificationStatus] = mapped_column(
        Enum(VerificationStatus, name="verificationstatus"),
        default=VerificationStatus.PENDING,
        nullable=False,
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    evidence_document_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason_category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_reverification: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    lawyer_profile: Mapped["LawyerProfile"] = relationship(
        "LawyerProfile", back_populates="verifications"
    )
    reviewer: Mapped["User | None"] = relationship("User")


# Avoid circular dependency by importing Consultation and LawyerAvailability at the end or conditionally
from app.models.availability import LawyerAvailability
from app.models.consultation import Consultation
