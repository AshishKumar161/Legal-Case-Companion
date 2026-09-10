import datetime
import enum
import uuid

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.identifiers import generate_uuid7
from app.models.ai import SQLiteCompatibleArray
from app.models.base import Base, TimestampMixin


class LegalAuthorityType(str, enum.Enum):
    PRIMARY_LEGISLATION = "PRIMARY_LEGISLATION"
    SUBORDINATE_LEGISLATION = "SUBORDINATE_LEGISLATION"
    JUDICIAL_DECISION = "JUDICIAL_DECISION"
    OFFICIAL_NOTIFICATION = "OFFICIAL_NOTIFICATION"
    OFFICIAL_CIRCULAR = "OFFICIAL_CIRCULAR"
    SECONDARY_MATERIAL = "SECONDARY_MATERIAL"


class AuthorityLevel(int, enum.Enum):
    CONSTITUTIONAL = 100
    PRIMARY_STATUTE = 90
    APEX_JUDICIAL = 85
    HIGH_COURT_BINDING = 75
    SUBORDINATE_RULE = 60
    REGULATORY_CIRCULAR = 50
    HIGH_COURT_PERSUASIVE = 40
    SECONDARY_TREATISE = 20


class LegalJurisdiction(str, enum.Enum):
    INDIA_CENTRAL = "INDIA_CENTRAL"
    SUPREME_COURT_OF_INDIA = "SUPREME_COURT_OF_INDIA"
    HIGH_COURT_DELHI = "HIGH_COURT_DELHI"
    HIGH_COURT_BOMBAY = "HIGH_COURT_BOMBAY"
    HIGH_COURT_MADRAS = "HIGH_COURT_MADRAS"
    HIGH_COURT_CALCUTTA = "HIGH_COURT_CALCUTTA"
    HIGH_COURT_KARNATAKA = "HIGH_COURT_KARNATAKA"
    STATE_MAHARASHTRA = "STATE_MAHARASHTRA"
    STATE_DELHI = "STATE_DELHI"
    ALL_INDIA = "ALL_INDIA"


class LegalSourceStatus(str, enum.Enum):
    IMPORTED = "IMPORTED"
    VALIDATED = "VALIDATED"
    PUBLISHED = "PUBLISHED"
    AMENDED = "AMENDED"
    REPEALED = "REPEALED"
    OVERRULED = "OVERRULED"


class RawLegalSource(Base, TimestampMixin):
    """Raw, unnormalized legal authority payload ingested from official/curated repositories."""

    __tablename__ = "raw_legal_sources"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    source_system: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    external_identifier: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source_type: Mapped[LegalAuthorityType] = mapped_column(
        Enum(LegalAuthorityType, name="legalauthoritytype", create_type=False),
        nullable=False,
    )
    raw_content: Mapped[str] = mapped_column(Text, nullable=False)
    raw_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    content_checksum: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    retrieval_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    retrieved_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.UTC), nullable=False
    )
    status: Mapped[str] = mapped_column(String(50), default="RAW_INGESTED", nullable=False)
    canonical_source_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("legal_sources.id", ondelete="SET NULL"), nullable=True, index=True
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    canonical_source: Mapped["LegalSource | None"] = relationship("LegalSource")


class LegalSource(Base, TimestampMixin):
    """Authoritative legal source representation (Act, Code, Regulation, or Reported Judgment)."""

    __tablename__ = "legal_sources"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    canonical_identifier: Mapped[str] = mapped_column(
        String(100), unique=True, index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    short_title: Mapped[str | None] = mapped_column(String(100), nullable=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    source_type: Mapped[LegalAuthorityType] = mapped_column(
        Enum(LegalAuthorityType, name="legalauthoritytype", create_type=False),
        default=LegalAuthorityType.PRIMARY_LEGISLATION,
        nullable=False,
    )
    authority_level: Mapped[int] = mapped_column(
        Integer, default=AuthorityLevel.PRIMARY_STATUTE.value, nullable=False
    )
    jurisdiction: Mapped[str] = mapped_column(
        String(100), nullable=False, default=LegalJurisdiction.INDIA_CENTRAL.value, index=True
    )
    issuing_body: Mapped[str | None] = mapped_column(String(255), nullable=True)
    publication_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    effective_from: Mapped[datetime.date | None] = mapped_column(Date, nullable=True, index=True)
    effective_to: Mapped[datetime.date | None] = mapped_column(Date, nullable=True, index=True)
    status: Mapped[LegalSourceStatus] = mapped_column(
        Enum(LegalSourceStatus, name="legalsourcestatus", create_type=False),
        default=LegalSourceStatus.PUBLISHED,
        nullable=False,
    )
    citation_standard: Mapped[str | None] = mapped_column(String(255), nullable=True)
    canonical_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    metadata_: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Relationships
    versions: Mapped[list["LegalSourceVersion"]] = relationship(
        "LegalSourceVersion", back_populates="source", cascade="all, delete-orphan"
    )


class LegalSourceVersion(Base, TimestampMixin):
    """Specific section, provision, or judgment paragraph with temporal versioning."""

    __tablename__ = "legal_source_versions"

    __table_args__ = (
        UniqueConstraint(
            "source_id",
            "section_number",
            "version_label",
            name="uq_legal_source_section_version",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("legal_sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    canonical_provision_id: Mapped[str] = mapped_column(
        String(150), unique=True, index=True, nullable=False
    )
    section_number: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    version_label: Mapped[str] = mapped_column(String(100), default="Current", nullable=False)
    chapter_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    effective_from: Mapped[datetime.date | None] = mapped_column(Date, nullable=True, index=True)
    effective_to: Mapped[datetime.date | None] = mapped_column(Date, nullable=True, index=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    embedding: Mapped[list[float] | None] = mapped_column(
        SQLiteCompatibleArray(Float), nullable=True
    )
    metadata_: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Relationships
    source: Mapped["LegalSource"] = relationship("LegalSource", back_populates="versions")
