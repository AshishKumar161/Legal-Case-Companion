import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.identifiers import generate_uuid7
from app.models.base import Base, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.case import Case
    from app.models.user import User


class EvidenceCategory(str, enum.Enum):
    FORENSIC = "FORENSIC"
    FINANCIAL = "FINANCIAL"
    CONTRACTUAL = "CONTRACTUAL"
    DIGITAL = "DIGITAL"
    TESTIMONIAL = "TESTIMONIAL"
    REGULATORY = "REGULATORY"
    PHYSICAL_SCAN = "PHYSICAL_SCAN"
    MISCELLANEOUS = "MISCELLANEOUS"


class EvidenceStatus(str, enum.Enum):
    UPLOADING = "UPLOADING"
    QUARANTINED = "QUARANTINED"
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"
    DELETION_PENDING = "DELETION_PENDING"
    DELETED = "DELETED"


class EvidenceSensitivity(str, enum.Enum):
    STANDARD = "STANDARD"
    CONFIDENTIAL = "CONFIDENTIAL"
    HIGHLY_CONFIDENTIAL = "HIGHLY_CONFIDENTIAL"
    PRIVILEGED = "PRIVILEGED"


class EvidenceScanStatus(str, enum.Enum):
    PENDING = "PENDING"
    VALIDATING = "VALIDATING"
    SCANNING = "SCANNING"
    PASSED = "PASSED"
    FAILED = "FAILED"


class EvidenceIntegrityStatus(str, enum.Enum):
    UNVERIFIED = "UNVERIFIED"
    VERIFIED_MATCH = "VERIFIED_MATCH"
    TAMPER_DETECTED = "TAMPER_DETECTED"


class EvidenceAccessLevel(str, enum.Enum):
    VIEW = "VIEW"
    DOWNLOAD = "DOWNLOAD"
    MANAGE = "MANAGE"


class EvidenceCustodyAction(str, enum.Enum):
    UPLOADED = "UPLOADED"
    SCAN_PASSED = "SCAN_PASSED"
    SCAN_FAILED = "SCAN_FAILED"
    SHARED = "SHARED"
    ACCESS_REVOKED = "ACCESS_REVOKED"
    VIEWED = "VIEWED"
    DOWNLOADED = "DOWNLOADED"
    INTEGRITY_VERIFIED = "INTEGRITY_VERIFIED"
    INTEGRITY_FAILED = "INTEGRITY_FAILED"
    VERSION_CREATED = "VERSION_CREATED"
    LEGAL_HOLD_APPLIED = "LEGAL_HOLD_APPLIED"
    LEGAL_HOLD_REMOVED = "LEGAL_HOLD_REMOVED"
    DELETION_REQUESTED = "DELETION_REQUESTED"
    DELETED = "DELETED"


class Evidence(Base, TimestampMixin, SoftDeleteMixin):
    """High-security Evidence Locker object providing non-repudiation, versioning, and custody tracking."""

    __tablename__ = "evidence"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(
            "evidence_versions.id",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_evidence_current_version_id",
        ),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    category: Mapped[EvidenceCategory] = mapped_column(
        Enum(EvidenceCategory, name="evidencecategory"),
        default=EvidenceCategory.MISCELLANEOUS,
        nullable=False,
    )
    status: Mapped[EvidenceStatus] = mapped_column(
        Enum(EvidenceStatus, name="evidencestatus"),
        default=EvidenceStatus.UPLOADING,
        nullable=False,
        index=True,
    )
    sensitivity: Mapped[EvidenceSensitivity] = mapped_column(
        Enum(EvidenceSensitivity, name="evidencesensitivity"),
        default=EvidenceSensitivity.STANDARD,
        nullable=False,
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    legal_hold: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    legal_hold_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    retention_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    case: Mapped["Case"] = relationship("Case", backref="evidence_items")
    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by_user_id])
    versions: Mapped[list["EvidenceVersion"]] = relationship(
        "EvidenceVersion",
        foreign_keys="[EvidenceVersion.evidence_id]",
        back_populates="evidence",
        cascade="all, delete-orphan",
        order_by="desc(EvidenceVersion.version_number)",
    )
    current_version: Mapped["EvidenceVersion | None"] = relationship(
        "EvidenceVersion",
        foreign_keys=[current_version_id],
        post_update=True,
    )
    grants: Mapped[list["EvidenceAccessGrant"]] = relationship(
        "EvidenceAccessGrant",
        back_populates="evidence",
        cascade="all, delete-orphan",
    )
    custody_events: Mapped[list["EvidenceCustodyEvent"]] = relationship(
        "EvidenceCustodyEvent",
        back_populates="evidence",
        cascade="all, delete-orphan",
        order_by="asc(EvidenceCustodyEvent.timestamp)",
    )


class EvidenceVersion(Base, TimestampMixin):
    """Immutable evidence version with cryptographic SHA-256 digest and storage reference."""

    __tablename__ = "evidence_versions"
    __table_args__ = (
        UniqueConstraint("evidence_id", "version_number", name="uq_evidence_version_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    evidence_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evidence.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    uploaded_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    storage_key: Mapped[str] = mapped_column(String(512), unique=True, nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    scan_status: Mapped[EvidenceScanStatus] = mapped_column(
        Enum(EvidenceScanStatus, name="evidencescanstatus"),
        default=EvidenceScanStatus.PENDING,
        nullable=False,
        index=True,
    )
    scan_details: Mapped[str | None] = mapped_column(String(500), nullable=True)
    integrity_status: Mapped[EvidenceIntegrityStatus] = mapped_column(
        Enum(EvidenceIntegrityStatus, name="evidenceintegritystatus"),
        default=EvidenceIntegrityStatus.UNVERIFIED,
        nullable=False,
    )
    last_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    evidence: Mapped["Evidence"] = relationship(
        "Evidence", foreign_keys=[evidence_id], back_populates="versions"
    )
    uploader: Mapped["User"] = relationship("User", foreign_keys=[uploaded_by_user_id])


class EvidenceAccessGrant(Base, TimestampMixin):
    """Explicit access control grant enabling controlled client/lawyer evidence sharing."""

    __tablename__ = "evidence_access_grants"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    evidence_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evidence.id", ondelete="CASCADE"), nullable=False, index=True
    )
    grantee_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    granted_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    access_level: Mapped[EvidenceAccessLevel] = mapped_column(
        Enum(EvidenceAccessLevel, name="evidenceaccesslevel"),
        default=EvidenceAccessLevel.VIEW,
        nullable=False,
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revocation_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Relationships
    evidence: Mapped["Evidence"] = relationship("Evidence", back_populates="grants")
    grantee: Mapped["User"] = relationship("User", foreign_keys=[grantee_user_id])
    granted_by: Mapped["User"] = relationship("User", foreign_keys=[granted_by_user_id])


class EvidenceCustodyEvent(Base):
    """Immutable, chronological chain-of-custody audit record for evidence provenance."""

    __tablename__ = "evidence_custody_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    evidence_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evidence.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("evidence_versions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    action: Mapped[EvidenceCustodyAction] = mapped_column(
        Enum(EvidenceCustodyAction, name="evidencecustodyaction"),
        nullable=False,
        index=True,
    )
    previous_event_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("evidence_custody_events.id", ondelete="SET NULL"), nullable=True
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.current_timestamp(), nullable=False, index=True
    )
    event_metadata: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)

    # Relationships
    evidence: Mapped["Evidence"] = relationship("Evidence", back_populates="custody_events")
    version: Mapped["EvidenceVersion | None"] = relationship("EvidenceVersion")
    actor: Mapped["User | None"] = relationship("User")
    previous_event: Mapped["EvidenceCustodyEvent | None"] = relationship(
        "EvidenceCustodyEvent", remote_side=[id]
    )
