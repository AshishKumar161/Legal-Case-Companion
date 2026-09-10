import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, ForeignKey, Integer, JSON, Numeric, String, Text
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
    DRAFT = "DRAFT"
    PENDING = "PENDING"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    NEEDS_INFO = "NEEDS_INFO"
    REVOKED = "REVOKED"


class AdvocateDocumentType(str, enum.Enum):
    BAR_COUNCIL_ENROLLMENT_CERT = "BAR_COUNCIL_ENROLLMENT_CERT"
    BAR_COUNCIL_ID_CARD = "BAR_COUNCIL_ID_CARD"
    GOVERNMENT_PHOTO_ID = "GOVERNMENT_PHOTO_ID"
    CERTIFICATE_OF_PRACTICE = "CERTIFICATE_OF_PRACTICE"


class DocumentVerificationStatus(str, enum.Enum):
    NOT_SUBMITTED = "NOT_SUBMITTED"
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    NEEDS_RESUBMISSION = "NEEDS_RESUBMISSION"


class DocumentScanStatus(str, enum.Enum):
    PENDING = "PENDING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    QUARANTINED = "QUARANTINED"


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

    @property
    def full_name(self) -> str:
        if self.client_profile and self.client_profile.full_name:
            return self.client_profile.full_name
        if self.lawyer_profile and self.lawyer_profile.full_name:
            return self.lawyer_profile.full_name
        return self.email.split("@")[0] if self.email else "User"


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

    # Ephemeral runtime presence attributes (populated by PresenceService / ConsultationService / ProfileService)
    is_online: bool = False
    is_available: bool = False
    presence_status: str = "OFFLINE"
    match_reasons: list[str] = []

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
        latest = sorted(self.verifications, key=lambda v: v.created_at or datetime.min, reverse=True)[0]
        return latest.status.value

    @property
    def enrollment_number(self) -> str | None:
        if not self.verifications:
            return None
        latest = sorted(self.verifications, key=lambda v: v.created_at or datetime.min, reverse=True)[0]
        return latest.enrollment_number

    @property
    def state_bar_council(self) -> str | None:
        if not self.verifications:
            return None
        latest = sorted(self.verifications, key=lambda v: v.created_at or datetime.min, reverse=True)[0]
        return latest.state_bar_council


class LawyerVerification(Base, TimestampMixin):
    __tablename__ = "lawyer_verifications"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    lawyer_profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("lawyer_profiles.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    enrollment_number: Mapped[str] = mapped_column(String(100), nullable=False)
    state_bar_council: Mapped[str] = mapped_column(String(150), nullable=False)
    status: Mapped[VerificationStatus] = mapped_column(
        Enum(VerificationStatus, name="verificationstatus"),
        default=VerificationStatus.PENDING,
        nullable=False,
        index=True,
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    evidence_document_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason_category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_reverification: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Phase 14 Provenance & Governance Extensions
    verification_source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    verification_method: Mapped[str | None] = mapped_column(String(100), nullable=True)
    declared_practice_jurisdictions: Mapped[list | None] = mapped_column(JSON, nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    lawyer_profile: Mapped["LawyerProfile"] = relationship(
        "LawyerProfile", back_populates="verifications"
    )
    reviewer: Mapped["User | None"] = relationship("User")
    documents: Mapped[list["AdvocateVerificationDocument"]] = relationship(
        "AdvocateVerificationDocument", back_populates="verification", cascade="all, delete-orphan"
    )
    review_events: Mapped[list["VerificationReviewEvent"]] = relationship(
        "VerificationReviewEvent",
        back_populates="verification",
        cascade="all, delete-orphan",
        order_by="desc(VerificationReviewEvent.created_at)",
    )


class AdvocateVerificationDocument(Base, TimestampMixin):
    """
    Authoritative professional credential document for advocate verification.
    Maintains cryptographic SHA-256 integrity hash, magic byte scanning status, and independent verification lifecycle.
    """
    __tablename__ = "advocate_verification_documents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    verification_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("lawyer_verifications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_type: Mapped[AdvocateDocumentType] = mapped_column(
        Enum(AdvocateDocumentType, name="advocatedocumenttype"), nullable=False
    )
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    sha256_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    scan_status: Mapped[DocumentScanStatus] = mapped_column(
        Enum(DocumentScanStatus, name="documentscanstatus_v2"),
        default=DocumentScanStatus.PENDING,
        nullable=False,
    )
    verification_status: Mapped[DocumentVerificationStatus] = mapped_column(
        Enum(DocumentVerificationStatus, name="documentverificationstatus"),
        default=DocumentVerificationStatus.SUBMITTED,
        nullable=False,
    )
    rejection_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Relationships
    verification: Mapped["LawyerVerification"] = relationship(
        "LawyerVerification", back_populates="documents"
    )

    @property
    def uploaded_at(self) -> datetime:
        return self.created_at


class VerificationReviewEvent(Base, TimestampMixin):
    """
    Immutable chronological audit trail of advocate verification reviews and state transitions.
    """
    __tablename__ = "verification_review_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    verification_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("lawyer_verifications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    from_status: Mapped[str] = mapped_column(String(50), nullable=False)
    to_status: Mapped[str] = mapped_column(String(50), nullable=False)
    decision: Mapped[str] = mapped_column(String(50), nullable=False)
    verification_method: Mapped[str | None] = mapped_column(String(100), nullable=True)
    verification_source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    verification: Mapped["LawyerVerification"] = relationship(
        "LawyerVerification", back_populates="review_events"
    )
    reviewer: Mapped["User | None"] = relationship("User")


# Avoid circular dependency by importing Consultation and LawyerAvailability at the end or conditionally
from app.models.availability import LawyerAvailability
from app.models.consultation import Consultation
