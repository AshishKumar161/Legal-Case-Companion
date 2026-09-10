import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, ROUND_HALF_EVEN
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.identifiers import generate_uuid7
from app.models.audit import AuditEvent
from app.models.commercial import (
    CommercialTransaction,
    RefundReason,
    TransactionStatus,
)
from app.models.consultation import Consultation, ConsultationStatus
from app.models.user import User, UserRole

TWOPLACES = Decimal("0.01")


def _to_decimal(val: Any) -> Decimal:
    if isinstance(val, Decimal):
        return val
    if val is None:
        return Decimal("0.00")
    return Decimal(str(val))


def _quantize(val: Decimal) -> Decimal:
    return val.quantize(TWOPLACES, rounding=ROUND_HALF_EVEN)


@dataclass(frozen=True)
class CancellationEconomicsResult:
    consultation_id: uuid.UUID
    policy_mode: str
    refund_eligible: bool
    refund_percentage: Decimal
    refund_amount: Decimal
    advocate_payout_eligible: bool
    advocate_payout_amount: Decimal
    platform_retained_amount: Decimal
    is_late_cancellation: bool
    requires_manual_review: bool
    reason_classification: str
    audit_notes: str


class CancellationPolicyService:
    """Authoritative evaluator of cancellation and no-show economics (Phase 10.2).

    Enforces deterministic commercial outcomes for:
    - Client cancellation (standard vs. late)
    - Advocate cancellation
    - Client no-show
    - Advocate no-show
    - Platform technical/infrastructure failures
    """

    def __init__(self, db: Session):
        self.db = db

    def evaluate_cancellation_economics(
        self,
        consultation: Consultation,
        actor: User | None = None,
        reason: str | None = None,
        evaluation_time: datetime | None = None,
    ) -> CancellationEconomicsResult:
        """Computes deterministic refund and payout entitlements based on consultation state and configured policy."""
        now = evaluation_time or datetime.now(UTC)
        if now.tzinfo is None:
            now = now.replace(tzinfo=UTC)
        gross_fee = _quantize(_to_decimal(consultation.fee_amount))

        # Check for linked commercial transaction if any
        txn = (
            self.db.query(CommercialTransaction)
            .filter(CommercialTransaction.consultation_id == consultation.id)
            .order_by(CommercialTransaction.created_at.desc())
            .first()
        )

        net_advocate_entitled = _quantize(
            _to_decimal(txn.net_advocate_amount)
            if txn
            else gross_fee * Decimal("0.90")  # fallback platform fee 10%
        )

        policy_mode = getattr(settings, "CANCELLATION_REFUND_POLICY_MODE", "PENDING_BUSINESS_DECISION")
        cutoff_hours = getattr(settings, "CLIENT_LATE_CANCELLATION_CUTOFF_HOURS", 2)
        late_refund_pct = Decimal(str(getattr(settings, "CLIENT_LATE_CANCELLATION_REFUND_PERCENT", 50.0)))

        is_late = False
        if consultation.scheduled_at:
            sched_time = consultation.scheduled_at
            if sched_time.tzinfo is None:
                sched_time = sched_time.replace(tzinfo=UTC)
            time_until_start = sched_time - now
            is_late = time_until_start < timedelta(hours=cutoff_hours)

        # 1. Advocate Cancellation -> 100% client refund, 0 advocate payout
        actor_role = actor.role if actor else None
        if actor_role == UserRole.LAWYER or (reason and "advocate" in reason.lower()):
            refund_amount = gross_fee
            return CancellationEconomicsResult(
                consultation_id=consultation.id,
                policy_mode=policy_mode,
                refund_eligible=refund_amount > Decimal("0.00"),
                refund_percentage=Decimal("100.00"),
                refund_amount=refund_amount,
                advocate_payout_eligible=False,
                advocate_payout_amount=Decimal("0.00"),
                platform_retained_amount=Decimal("0.00"),
                is_late_cancellation=is_late,
                requires_manual_review=False,
                reason_classification=RefundReason.ADVOCATE_CANCELLATION.value,
                audit_notes=f"Advocate cancellation: 100% client refund of {refund_amount}. Zero advocate payout.",
            )

        # 2. Platform / Technical Failure -> 100% client refund, 0 advocate payout
        if reason and any(k in reason.lower() for k in ("platform", "technical", "infrastructure", "glitch", "network")):
            refund_amount = gross_fee
            return CancellationEconomicsResult(
                consultation_id=consultation.id,
                policy_mode=policy_mode,
                refund_eligible=refund_amount > Decimal("0.00"),
                refund_percentage=Decimal("100.00"),
                refund_amount=refund_amount,
                advocate_payout_eligible=False,
                advocate_payout_amount=Decimal("0.00"),
                platform_retained_amount=Decimal("0.00"),
                is_late_cancellation=is_late,
                requires_manual_review=False,
                reason_classification=RefundReason.PLATFORM_TECHNICAL_FAILURE.value,
                audit_notes=f"Platform technical failure: 100% client refund of {refund_amount}.",
            )

        # 3. Client Cancellation
        if not is_late:
            # Full refund if cancelled with adequate advance notice
            refund_amount = gross_fee
            return CancellationEconomicsResult(
                consultation_id=consultation.id,
                policy_mode=policy_mode,
                refund_eligible=refund_amount > Decimal("0.00"),
                refund_percentage=Decimal("100.00"),
                refund_amount=refund_amount,
                advocate_payout_eligible=False,
                advocate_payout_amount=Decimal("0.00"),
                platform_retained_amount=Decimal("0.00"),
                is_late_cancellation=False,
                requires_manual_review=False,
                reason_classification=RefundReason.CLIENT_CANCELLATION.value,
                audit_notes=f"Client advance cancellation: 100% refund of {refund_amount}.",
            )
        else:
            # Late client cancellation
            if policy_mode == "AUTOMATIC_TIERED":
                refund_pct = late_refund_pct
                refund_amount = _quantize(gross_fee * (refund_pct / Decimal("100.00")))
                advocate_amount = _quantize(net_advocate_entitled * Decimal("0.50"))
                retained = _quantize(gross_fee - refund_amount - advocate_amount)
                return CancellationEconomicsResult(
                    consultation_id=consultation.id,
                    policy_mode=policy_mode,
                    refund_eligible=refund_amount > Decimal("0.00"),
                    refund_percentage=refund_pct,
                    refund_amount=refund_amount,
                    advocate_payout_eligible=advocate_amount > Decimal("0.00"),
                    advocate_payout_amount=advocate_amount,
                    platform_retained_amount=retained,
                    is_late_cancellation=True,
                    requires_manual_review=False,
                    reason_classification=RefundReason.CLIENT_CANCELLATION.value,
                    audit_notes=f"Client late cancellation under AUTOMATIC_TIERED: {refund_pct}% refund ({refund_amount}), advocate compensated {advocate_amount}.",
                )
            else:
                # Pending business decision / manual review
                return CancellationEconomicsResult(
                    consultation_id=consultation.id,
                    policy_mode=policy_mode,
                    refund_eligible=True,
                    refund_percentage=late_refund_pct,
                    refund_amount=_quantize(gross_fee * (late_refund_pct / Decimal("100.00"))),
                    advocate_payout_eligible=False,
                    advocate_payout_amount=Decimal("0.00"),
                    platform_retained_amount=Decimal("0.00"),
                    is_late_cancellation=True,
                    requires_manual_review=True,
                    reason_classification=RefundReason.CLIENT_CANCELLATION.value,
                    audit_notes="Client late cancellation flagged for manual finance/admin review under policy mode.",
                )

    def evaluate_no_show_economics(
        self,
        consultation: Consultation,
        no_show_party: str,  # "CLIENT" or "ADVOCATE"
        actor: User | None = None,
        reason: str | None = None,
    ) -> CancellationEconomicsResult:
        """Computes deterministic financial outcome for no-show events."""
        gross_fee = _quantize(_to_decimal(consultation.fee_amount))
        policy_mode = getattr(settings, "CANCELLATION_REFUND_POLICY_MODE", "PENDING_BUSINESS_DECISION")

        txn = (
            self.db.query(CommercialTransaction)
            .filter(CommercialTransaction.consultation_id == consultation.id)
            .order_by(CommercialTransaction.created_at.desc())
            .first()
        )
        net_advocate_entitled = _quantize(
            _to_decimal(txn.net_advocate_amount)
            if txn
            else gross_fee * Decimal("0.90")
        )

        if no_show_party.upper() == "ADVOCATE":
            # Advocate failed to attend -> Full refund to client, 0 advocate payout
            refund_amount = gross_fee
            return CancellationEconomicsResult(
                consultation_id=consultation.id,
                policy_mode=policy_mode,
                refund_eligible=refund_amount > Decimal("0.00"),
                refund_percentage=Decimal("100.00"),
                refund_amount=refund_amount,
                advocate_payout_eligible=False,
                advocate_payout_amount=Decimal("0.00"),
                platform_retained_amount=Decimal("0.00"),
                is_late_cancellation=False,
                requires_manual_review=False,
                reason_classification=RefundReason.ADVOCATE_NO_SHOW.value,
                audit_notes=f"Advocate no-show: 100% client refund of {refund_amount}. Zero advocate payout.",
            )
        else:
            # Client failed to attend -> Zero refund to client, advocate retained compensation for slot
            return CancellationEconomicsResult(
                consultation_id=consultation.id,
                policy_mode=policy_mode,
                refund_eligible=False,
                refund_percentage=Decimal("0.00"),
                refund_amount=Decimal("0.00"),
                advocate_payout_eligible=net_advocate_entitled > Decimal("0.00"),
                advocate_payout_amount=net_advocate_entitled,
                platform_retained_amount=_quantize(gross_fee - net_advocate_entitled),
                is_late_cancellation=False,
                requires_manual_review=False,
                reason_classification="CLIENT_NO_SHOW",
                audit_notes=f"Client no-show: 0% refund to client. Advocate entitled to {net_advocate_entitled}.",
            )
