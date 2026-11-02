import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Integer, JSON, Numeric, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.identifiers import generate_uuid7
from app.models.base import Base, TimestampMixin


class TransactionType(str, enum.Enum):
    PAYMENT = "PAYMENT"
    REFUND = "REFUND"
    PARTIAL_REFUND = "PARTIAL_REFUND"
    DISPUTE_HOLD = "DISPUTE_HOLD"


class CommercialBillingStrategy(str, enum.Enum):
    CONSULTATION_COMMISSION = "CONSULTATION_COMMISSION"
    ADVOCATE_SUBSCRIPTION = "ADVOCATE_SUBSCRIPTION"
    LAW_FIRM_SUBSCRIPTION = "LAW_FIRM_SUBSCRIPTION"
    HYBRID = "HYBRID"


class AdvocatePayoutStatus(str, enum.Enum):
    ELIGIBLE = "ELIGIBLE"
    PENDING = "PENDING"
    PAID = "PAID"
    FAILED = "FAILED"
    REVERSED = "REVERSED"


class RefundReason(str, enum.Enum):
    CLIENT_CANCELLATION = "CLIENT_CANCELLATION"
    ADVOCATE_CANCELLATION = "ADVOCATE_CANCELLATION"
    ADVOCATE_NO_SHOW = "ADVOCATE_NO_SHOW"
    PLATFORM_TECHNICAL_FAILURE = "PLATFORM_TECHNICAL_FAILURE"
    DUPLICATE_PAYMENT = "DUPLICATE_PAYMENT"


class RefundStatus(str, enum.Enum):
    PENDING = "PENDING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    REJECTED = "REJECTED"


class TransactionStatus(str, enum.Enum):
    PENDING = "PENDING"
    AUTHORIZED = "AUTHORIZED"
    CAPTURED = "CAPTURED"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"
    PARTIALLY_REFUNDED = "PARTIALLY_REFUNDED"
    DISPUTED = "DISPUTED"
    CANCELLED = "CANCELLED"


class CommercialTransaction(Base, TimestampMixin):
    __tablename__ = "commercial_transactions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    transaction_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    consultation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("consultations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    payer_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    payee_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    transaction_type: Mapped[TransactionType] = mapped_column(
        Enum(TransactionType, name="transactiontype"),
        default=TransactionType.PAYMENT,
        nullable=False,
    )
    status: Mapped[TransactionStatus] = mapped_column(
        Enum(TransactionStatus, name="transactionstatus"),
        default=TransactionStatus.PENDING,
        nullable=False,
        index=True,
    )
    gross_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    platform_fee: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0, nullable=False)
    tax_amount: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0, nullable=False)
    net_advocate_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="INR", nullable=False)
    provider: Mapped[str] = mapped_column(String(50), default="STRIPE", nullable=False)
    provider_transaction_id: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    invoice_number: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    reconciliation_status: Mapped[str] = mapped_column(String(50), default="PENDING", nullable=False)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)

    __table_args__ = (
        Index("ix_commercial_tx_status_created", "status", "created_at"),
    )


class CommercialEntitlement(Base, TimestampMixin):
    __tablename__ = "commercial_entitlements"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entitlement_type: Mapped[str] = mapped_column(String(100), nullable=False)
    quota_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    quota_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)

    __table_args__ = (
        Index("ix_entitlement_user_type", "user_id", "entitlement_type"),
    )


class AdvocatePayout(Base, TimestampMixin):
    __tablename__ = "advocate_payouts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    payout_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    advocate_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    commercial_transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("commercial_transactions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="INR", nullable=False)
    status: Mapped[AdvocatePayoutStatus] = mapped_column(
        Enum(AdvocatePayoutStatus, name="advocatepayoutstatus"),
        default=AdvocatePayoutStatus.PENDING,
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(50), default="RAZORPAYX", nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    provider_payout_id: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    audit_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)

    __table_args__ = (
        Index(
            "uq_advocate_payout_active_commercial_txn",
            "commercial_transaction_id",
            unique=True,
            postgresql_where=text("commercial_transaction_id IS NOT NULL AND status IN ('PENDING', 'PAID')"),
            sqlite_where=text("commercial_transaction_id IS NOT NULL AND status IN ('PENDING', 'PAID')"),
        ),
    )


class RefundRecord(Base, TimestampMixin):
    __tablename__ = "refund_records"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    refund_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    commercial_transaction_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("commercial_transactions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="INR", nullable=False)
    reason: Mapped[RefundReason] = mapped_column(
        Enum(RefundReason, name="refundreason"),
        nullable=False,
        index=True,
    )
    status: Mapped[RefundStatus] = mapped_column(
        Enum(RefundStatus, name="refundstatus"),
        default=RefundStatus.PENDING,
        nullable=False,
        index=True,
    )
    processed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    gateway_refund_id: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    audit_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)
