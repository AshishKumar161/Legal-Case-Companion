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
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.identifiers import generate_uuid7
from app.models.base import Base, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.case import Case
    from app.models.evidence import CaseExhibit, Evidence, EvidenceVersion
    from app.models.user import User
    from app.models.workflow import CaseHearing


class BundleStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    GENERATING = "GENERATING"
    FINALIZED = "FINALIZED"
    FAILED = "FAILED"


class EvidenceBundle(Base, TimestampMixin, SoftDeleteMixin):
    """Authoritative evidentiary court bundle containing version-pinned exhibits and metadata."""

    __tablename__ = "evidence_bundles"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    hearing_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("case_hearings.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[BundleStatus] = mapped_column(
        Enum(BundleStatus, name="bundlestatus"),
        default=BundleStatus.DRAFT,
        nullable=False,
        index=True,
    )
    bates_prefix: Mapped[str] = mapped_column(String(20), default="LCC", nullable=False)
    bates_start: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    bates_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_pages: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_items: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    storage_key: Mapped[str | None] = mapped_column(
        String(512), unique=True, nullable=True, index=True
    )
    file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    sha256_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    manifest_json: Mapped[dict | None] = mapped_column("manifest", JSON, nullable=True)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    finalized_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    case: Mapped["Case"] = relationship("Case")
    hearing: Mapped["CaseHearing | None"] = relationship("CaseHearing")
    created_by: Mapped["User"] = relationship("User", foreign_keys=[created_by_user_id])
    items: Mapped[list["EvidenceBundleItem"]] = relationship(
        "EvidenceBundleItem",
        back_populates="bundle",
        cascade="all, delete-orphan",
        order_by="EvidenceBundleItem.order_index.asc()",
    )
    certificates: Mapped[list["BSACertificateDraft"]] = relationship(
        "BSACertificateDraft", back_populates="bundle", cascade="all, delete-orphan"
    )


class EvidenceBundleItem(Base, TimestampMixin):
    """Individual evidence version included in an evidentiary bundle with deterministic ordering."""

    __tablename__ = "evidence_bundle_items"
    __table_args__ = (
        UniqueConstraint("bundle_id", "order_index", name="uq_bundle_item_order"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    bundle_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evidence_bundles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    evidence_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evidence.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evidence_versions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    exhibit_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("case_exhibits.id", ondelete="SET NULL"), nullable=True, index=True
    )
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    exhibit_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    custom_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bates_start_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bates_end_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sha256_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)

    # Relationships
    bundle: Mapped["EvidenceBundle"] = relationship("EvidenceBundle", back_populates="items")
    evidence: Mapped["Evidence"] = relationship("Evidence")
    version: Mapped["EvidenceVersion"] = relationship("EvidenceVersion")
    exhibit: Mapped["CaseExhibit | None"] = relationship("CaseExhibit")


class BSACertificateDraft(Base, TimestampMixin):
    """Prepared draft certificate under Section 63(4) of the Bharatiya Sakshya Adhiniyam, 2023.

    Requires explicit human confirmation and declarant attestation before submission in court.
    """

    __tablename__ = "bsa_certificate_drafts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    bundle_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("evidence_bundles.id", ondelete="SET NULL"), nullable=True, index=True
    )
    evidence_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("evidence.id", ondelete="SET NULL"), nullable=True, index=True
    )
    version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("evidence_versions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    record_identification: Mapped[str] = mapped_column(String(500), nullable=False)
    source_device_type: Mapped[str] = mapped_column(String(255), nullable=False)
    source_device_details: Mapped[str | None] = mapped_column(Text, nullable=True)
    lawful_control_statement: Mapped[str] = mapped_column(Text, nullable=False)
    operational_condition_statement: Mapped[str] = mapped_column(Text, nullable=False)
    hash_value: Mapped[str] = mapped_column(String(64), nullable=False)
    hash_algorithm: Mapped[str] = mapped_column(String(20), default="SHA-256", nullable=False)
    declarant_name: Mapped[str] = mapped_column(String(255), nullable=False)
    declarant_designation: Mapped[str] = mapped_column(String(255), nullable=False)
    declarant_organization: Mapped[str | None] = mapped_column(String(255), nullable=True)
    place: Mapped[str] = mapped_column(String(255), nullable=False)
    declaration_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="DRAFT", nullable=False)
    storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    # Relationships
    case: Mapped["Case"] = relationship("Case")
    bundle: Mapped["EvidenceBundle | None"] = relationship(
        "EvidenceBundle", back_populates="certificates"
    )
    evidence: Mapped["Evidence | None"] = relationship("Evidence")
    version: Mapped["EvidenceVersion | None"] = relationship("EvidenceVersion")
    created_by: Mapped["User"] = relationship("User", foreign_keys=[created_by_user_id])
