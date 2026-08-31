import datetime
import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.identifiers import generate_uuid7
from app.models.base import Base, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.ai import AIMessage, DocumentChunk
    from app.models.case import Case
    from app.models.document import Document


class FactVerificationStatus(str, enum.Enum):
    AI_SUGGESTED = "AI_SUGGESTED"
    AI_VERIFIED = "AI_VERIFIED"
    HUMAN_CONFIRMED = "HUMAN_CONFIRMED"
    CONTESTED = "CONTESTED"
    USER_REPORTED = "USER_REPORTED"
    UNVERIFIED = "UNVERIFIED"


class FactSourceType(str, enum.Enum):
    CASE_EVIDENCE = "CASE_EVIDENCE"
    LEGAL_AUTHORITY = "LEGAL_AUTHORITY"
    USER_REPORTED = "USER_REPORTED"
    CONVERSATION_FINDING = "CONVERSATION_FINDING"


class IssueStatus(str, enum.Enum):
    IDENTIFIED = "IDENTIFIED"
    ANALYZING = "ANALYZING"
    SUPPORTED = "SUPPORTED"
    CONTESTED = "CONTESTED"
    UNRESOLVED = "UNRESOLVED"


class ClaimPositionType(str, enum.Enum):
    CLAIM = "CLAIM"
    DEFENSE = "DEFENSE"
    COUNTERCLAIM = "COUNTERCLAIM"


class ClaimDefenseStatus(str, enum.Enum):
    ASSERTED = "ASSERTED"
    SUPPORTED = "SUPPORTED"
    CONTESTED = "CONTESTED"
    REFUTED = "REFUTED"
    UNVERIFIED = "UNVERIFIED"


class DatePrecision(str, enum.Enum):
    EXACT_DATE = "EXACT_DATE"
    MONTH_YEAR = "MONTH_YEAR"
    YEAR_ONLY = "YEAR_ONLY"
    APPROXIMATE = "APPROXIMATE"
    UNKNOWN = "UNKNOWN"


class EvidenceGapType(str, enum.Enum):
    MISSING_DOCUMENT = "MISSING_DOCUMENT"
    MISSING_SIGNATURE = "MISSING_SIGNATURE"
    MISSING_PAYMENT_PROOF = "MISSING_PAYMENT_PROOF"
    UNVERIFIED_CLAIM = "UNVERIFIED_CLAIM"
    TEMPORAL_GAP = "TEMPORAL_GAP"


class EvidenceGapStatus(str, enum.Enum):
    IDENTIFIED = "IDENTIFIED"
    RESOLVED = "RESOLVED"
    WAIVED = "WAIVED"
    NOT_FOUND_IN_AVAILABLE_MATERIALS = "NOT_FOUND_IN_AVAILABLE_MATERIALS"


class RiskSeverity(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class CaseFact(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "case_facts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    fact_text: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(100), default="GENERAL", nullable=False)
    verification_status: Mapped[FactVerificationStatus] = mapped_column(
        Enum(FactVerificationStatus, name="factverificationstatus"),
        default=FactVerificationStatus.AI_SUGGESTED,
        nullable=False,
    )
    source_type: Mapped[FactSourceType] = mapped_column(
        Enum(FactSourceType, name="factsourcetype"),
        default=FactSourceType.CASE_EVIDENCE,
        nullable=False,
    )
    source_chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("document_chunks.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_authority_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_message_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ai_messages.id", ondelete="SET NULL"), nullable=True, index=True
    )
    document_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confidence_score: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)

    # Relationships
    case: Mapped["Case"] = relationship("Case")
    source_chunk: Mapped["DocumentChunk | None"] = relationship("DocumentChunk")
    source_document: Mapped["Document | None"] = relationship("Document")
    source_message: Mapped["AIMessage | None"] = relationship("AIMessage")


class LegalIssue(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "legal_issues"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    issue_text: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(100), default="GENERAL", nullable=False)
    status: Mapped[IssueStatus] = mapped_column(
        Enum(IssueStatus, name="issuestatus"),
        default=IssueStatus.IDENTIFIED,
        nullable=False,
    )
    verification_status: Mapped[FactVerificationStatus] = mapped_column(
        Enum(FactVerificationStatus, name="factverificationstatus"),
        default=FactVerificationStatus.AI_SUGGESTED,
        nullable=False,
    )
    supporting_fact_ids: Mapped[list | None] = mapped_column(JSON, default=list)
    relevant_authority_ids: Mapped[list | None] = mapped_column(JSON, default=list)
    uncertainties: Mapped[list | None] = mapped_column(JSON, default=list)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)

    # Relationships
    case: Mapped["Case"] = relationship("Case")


class CaseClaimDefense(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "case_claims_defenses"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position_type: Mapped[ClaimPositionType] = mapped_column(
        Enum(ClaimPositionType, name="claimpositiontype"),
        default=ClaimPositionType.CLAIM,
        nullable=False,
    )
    party_role: Mapped[str] = mapped_column(String(100), default="CLIENT", nullable=False)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ClaimDefenseStatus] = mapped_column(
        Enum(ClaimDefenseStatus, name="claimdefensestatus"),
        default=ClaimDefenseStatus.ASSERTED,
        nullable=False,
    )
    verification_status: Mapped[FactVerificationStatus] = mapped_column(
        Enum(FactVerificationStatus, name="factverificationstatus"),
        default=FactVerificationStatus.AI_SUGGESTED,
        nullable=False,
    )
    supporting_chunk_ids: Mapped[list | None] = mapped_column(JSON, default=list)
    opposing_chunk_ids: Mapped[list | None] = mapped_column(JSON, default=list)
    relevant_authority_ids: Mapped[list | None] = mapped_column(JSON, default=list)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)

    # Relationships
    case: Mapped["Case"] = relationship("Case")


class CaseChronologyEvent(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "case_chronology_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True, index=True)
    date_text: Mapped[str | None] = mapped_column(String(100), nullable=True)
    date_precision: Mapped[DatePrecision] = mapped_column(
        Enum(DatePrecision, name="dateprecision"),
        default=DatePrecision.EXACT_DATE,
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    is_conflicting: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    conflicting_source_details: Mapped[list | None] = mapped_column(JSON, nullable=True)
    source_chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("document_chunks.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    verification_status: Mapped[FactVerificationStatus] = mapped_column(
        Enum(FactVerificationStatus, name="factverificationstatus"),
        default=FactVerificationStatus.AI_SUGGESTED,
        nullable=False,
    )
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)

    # Relationships
    case: Mapped["Case"] = relationship("Case")
    source_chunk: Mapped["DocumentChunk | None"] = relationship("DocumentChunk")
    source_document: Mapped["Document | None"] = relationship("Document")


class CaseEvidenceGap(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "case_evidence_gaps"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    gap_type: Mapped[EvidenceGapType] = mapped_column(
        Enum(EvidenceGapType, name="evidencegaptype"),
        default=EvidenceGapType.MISSING_DOCUMENT,
        nullable=False,
    )
    severity: Mapped[RiskSeverity] = mapped_column(
        Enum(RiskSeverity, name="riskseverity"),
        default=RiskSeverity.MEDIUM,
        nullable=False,
    )
    status: Mapped[EvidenceGapStatus] = mapped_column(
        Enum(EvidenceGapStatus, name="evidencegapstatus"),
        default=EvidenceGapStatus.NOT_FOUND_IN_AVAILABLE_MATERIALS,
        nullable=False,
    )
    related_issue_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("legal_issues.id", ondelete="SET NULL"), nullable=True, index=True
    )
    related_claim_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("case_claims_defenses.id", ondelete="SET NULL"), nullable=True, index=True
    )
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)

    # Relationships
    case: Mapped["Case"] = relationship("Case")
    related_issue: Mapped["LegalIssue | None"] = relationship("LegalIssue")
    related_claim: Mapped["CaseClaimDefense | None"] = relationship("CaseClaimDefense")


class CaseRiskIndicator(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "case_risk_indicators"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    risk_title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[RiskSeverity] = mapped_column(
        Enum(RiskSeverity, name="riskseverity"),
        default=RiskSeverity.MEDIUM,
        nullable=False,
    )
    mitigation_hint: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_sources: Mapped[list | None] = mapped_column(JSON, default=list)
    verification_status: Mapped[FactVerificationStatus] = mapped_column(
        Enum(FactVerificationStatus, name="factverificationstatus"),
        default=FactVerificationStatus.AI_SUGGESTED,
        nullable=False,
    )
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)

    # Relationships
    case: Mapped["Case"] = relationship("Case")
