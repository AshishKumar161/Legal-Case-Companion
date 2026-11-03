import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal, ROUND_HALF_EVEN
from typing import Any

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import AppException, ResourceNotFoundError
from app.core.identifiers import generate_uuid7
from app.models.audit import AuditEvent
from app.models.commercial import (
    AdvocatePayout,
    AdvocatePayoutStatus,
    CommercialBillingStrategy,
    CommercialEntitlement,
    CommercialTransaction,
    RefundReason,
    RefundRecord,
    RefundStatus,
    TransactionStatus,
    TransactionType,
)
from app.models.consultation import Consultation, ConsultationStatus
from app.models.user import User
from app.domain.jobs.outbox_service import OutboxService

TWOPLACES = Decimal("0.01")


def _to_decimal(val: Any) -> Decimal:
    if isinstance(val, Decimal):
        return val
    if val is None:
        return Decimal("0.00")
    return Decimal(str(val))


def _quantize(val: Decimal) -> Decimal:
    return val.quantize(TWOPLACES, rounding=ROUND_HALF_EVEN)


class CommercialService:
    """Manages immutable commercial transaction records, financial separation, and entitlements (Parts L, M, N)."""

    GST_RATE_PERCENT = 18.0  # SAC 9982 - Legal and accounting support services (Subject to formal tax review)
    PLATFORM_FEE_PERCENT = 10.0

    @property
    def gst_rate_percent(self) -> Decimal:
        return _to_decimal(getattr(settings, "COMMERCIAL_GST_PERCENT", self.GST_RATE_PERCENT))

    @property
    def platform_fee_percent(self) -> Decimal:
        return _to_decimal(getattr(settings, "COMMERCIAL_PLATFORM_FEE_PERCENT", self.PLATFORM_FEE_PERCENT))

    def __init__(self, db: Session):
        self.db = db

    def _generate_transaction_id(self) -> str:
        today_str = datetime.now(UTC).strftime("%Y%m%d")
        count = (
            self.db.query(func.count(CommercialTransaction.id))
            .filter(CommercialTransaction.transaction_id.like(f"TXN-{today_str}-%"))
            .scalar()
            or 0
        )
        entropy = uuid.uuid4().hex[:4].upper()
        return f"TXN-{today_str}-{count + 1:04d}-{entropy}"

    def _generate_invoice_number(self) -> str:
        today_str = datetime.now(UTC).strftime("%Y%m%d")
        count = (
            self.db.query(func.count(CommercialTransaction.id))
            .filter(CommercialTransaction.invoice_number.like(f"INV-{today_str}-%"))
            .scalar()
            or 0
        )
        entropy = uuid.uuid4().hex[:4].upper()
        return f"INV-{today_str}-{count + 1:04d}-{entropy}"

    def create_consultation_transaction(
        self,
        consultation: Consultation,
        payer: User,
        provider: str = "STRIPE",
        provider_transaction_id: str | None = None,
    ) -> CommercialTransaction:
        now = datetime.now(UTC)
        gross = _quantize(_to_decimal(consultation.fee_amount))

        # Separate platform fee, GST 18%, and net advocate compensation using exact Decimal bankers rounding
        platform_fee = _quantize(gross * (self.platform_fee_percent / Decimal("100.0")))
        tax_amount = _quantize(platform_fee * (self.gst_rate_percent / Decimal("100.0")))
        net_advocate = _quantize(gross - platform_fee)

        txn = CommercialTransaction(
            id=generate_uuid7(),
            transaction_id=self._generate_transaction_id(),
            consultation_id=consultation.id,
            payer_user_id=payer.id,
            payee_user_id=consultation.lawyer.user_id,
            transaction_type=TransactionType.PAYMENT,
            status=TransactionStatus.PENDING,
            gross_amount=gross,
            platform_fee=platform_fee,
            tax_amount=tax_amount,
            net_advocate_amount=net_advocate,
            currency=consultation.currency or "INR",
            provider=provider,
            provider_transaction_id=provider_transaction_id,
            invoice_number=self._generate_invoice_number(),
            reconciliation_status="PENDING",
            metadata_={
                "tax_regime": "INDIA_GST",
                "sac_code": "9982",
                "lawyer_profile_id": str(consultation.lawyer_id),
                "financial_snapshot": {
                    "gross_amount": float(gross),
                    "platform_fee_percent": float(self.platform_fee_percent),
                    "platform_fee": float(platform_fee),
                    "gst_rate_percent": float(self.gst_rate_percent),
                    "tax_amount": float(tax_amount),
                    "net_advocate_amount": float(net_advocate),
                    "currency": consultation.currency or "INR",
                    "sac_code": "9982",
                    "fee_amount_base": float(consultation.fee_amount),
                    "duration_minutes": consultation.duration_minutes,
                    "created_at_snapshot": now.isoformat(),
                },
            },
            created_at=now,
            updated_at=now,
        )
        self.db.add(txn)
        self.db.commit()
        self.db.refresh(txn)
        return txn

    def capture_transaction(
        self,
        transaction_identifier: str | uuid.UUID,
        provider_payment_id: str | None = None,
    ) -> CommercialTransaction:
        txn = self.get_transaction(transaction_identifier)
        now = datetime.now(UTC)

        # Idempotency check: if already captured, return
        if txn.status == TransactionStatus.CAPTURED:
            return txn

        txn.status = TransactionStatus.CAPTURED
        txn.reconciliation_status = "RECONCILED"
        if provider_payment_id:
            txn.provider_transaction_id = provider_payment_id
        txn.updated_at = now

        # Update linked consultation state
        consultation = self.db.query(Consultation).filter(Consultation.id == txn.consultation_id).first()
        if consultation and consultation.status in (ConsultationStatus.REQUESTED, ConsultationStatus.ACCEPTED):
            consultation.status = ConsultationStatus.PAID
            consultation.updated_at = now

        # Grant consultation entitlement
        entitlement = CommercialEntitlement(
            id=generate_uuid7(),
            user_id=txn.payer_user_id,
            entitlement_type="CONSULTATION_TIME",
            quota_limit=consultation.duration_minutes if consultation else 45,
            quota_used=0,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        self.db.add(entitlement)

        audit = AuditEvent(
            id=generate_uuid7(),
            actor_user_id=txn.payer_user_id,
            event_type="COMMERCIAL_TRANSACTION_CAPTURED",
            entity_type="COMMERCIAL_TRANSACTION",
            entity_id=txn.id,
            action="UPDATE",
            timestamp=now,
            metadata_={
                "transaction_id": txn.transaction_id,
                "amount": float(txn.gross_amount),
                "invoice_number": txn.invoice_number,
            },
        )
        self.db.add(audit)
        self.db.commit()
        self.db.refresh(txn)
        return txn

    def process_refund(
        self,
        transaction_identifier: str | uuid.UUID,
        refund_amount: float | None = None,
        reason: str = "REQUESTED_BY_CUSTOMER",
        actor: User | None = None,
    ) -> CommercialTransaction:
        txn = self.get_transaction(transaction_identifier, for_update=True)
        now = datetime.now(UTC)

        if txn.status not in (TransactionStatus.CAPTURED, TransactionStatus.AUTHORIZED, TransactionStatus.PARTIALLY_REFUNDED):
            raise AppException(
                status_code=400,
                code="INVALID_REFUND_STATE",
                message=f"Cannot refund transaction in state {txn.status.value}.",
            )

        prior_refunds = (
            self.db.query(func.coalesce(func.sum(RefundRecord.amount), 0))
            .filter(
                RefundRecord.commercial_transaction_id == txn.id,
                RefundRecord.status == RefundStatus.SUCCEEDED,
            )
            .scalar()
        )
        prior_refunds_dec = _quantize(_to_decimal(prior_refunds))
        remaining_refundable = _quantize(_to_decimal(txn.gross_amount) - prior_refunds_dec)

        if remaining_refundable <= Decimal("0.00") or txn.status == TransactionStatus.REFUNDED:
            raise AppException(
                status_code=400,
                code="TRANSACTION_ALREADY_REFUNDED",
                message=f"Transaction '{txn.transaction_id}' has already been fully refunded.",
            )

        target_amount = _quantize(_to_decimal(refund_amount)) if refund_amount is not None else remaining_refundable
        if target_amount <= Decimal("0.00"):
            raise AppException(status_code=400, code="INVALID_REFUND_AMOUNT", message="Refund amount must be greater than zero.")

        if target_amount > remaining_refundable:
            raise AppException(
                status_code=400,
                code="REFUND_EXCEEDS_CAPTURED_AMOUNT",
                message=f"Requested refund of {target_amount} exceeds remaining refundable balance {remaining_refundable}.",
            )

        is_full_refund = (prior_refunds_dec + target_amount) >= _to_decimal(txn.gross_amount)
        is_partial = not is_full_refund

        txn.status = TransactionStatus.PARTIALLY_REFUNDED if is_partial else TransactionStatus.REFUNDED
        txn.updated_at = now
        txn.metadata_["refund_info"] = {
            "refund_amount": float(target_amount),
            "cumulative_refunded": float(prior_refunds_dec + target_amount),
            "refunded_at": now.isoformat(),
            "reason": reason,
        }

        # Update consultation if full refund
        if not is_partial:
            consultation = self.db.query(Consultation).filter(Consultation.id == txn.consultation_id).first()
            if consultation:
                consultation.status = ConsultationStatus.CANCELLED
                consultation.updated_at = now
            # Revoke/deactivate active entitlement
            self.db.query(CommercialEntitlement).filter(
                CommercialEntitlement.user_id == txn.payer_user_id,
                CommercialEntitlement.is_active.is_(True),
            ).update({"is_active": False}, synchronize_session=False)

        audit = AuditEvent(
            id=generate_uuid7(),
            actor_user_id=actor.id if actor else txn.payer_user_id,
            event_type="COMMERCIAL_TRANSACTION_REFUNDED",
            entity_type="COMMERCIAL_TRANSACTION",
            entity_id=txn.id,
            action="UPDATE",
            timestamp=now,
            metadata_={
                "transaction_id": txn.transaction_id,
                "refund_amount": float(target_amount),
                "is_partial": is_partial,
            },
        )
        self.db.add(audit)
        self.db.commit()
        self.db.refresh(txn)
        return txn

    def get_transaction(
        self, identifier: str | uuid.UUID, for_update: bool = False
    ) -> CommercialTransaction:
        query = self.db.query(CommercialTransaction)
        if for_update:
            query = query.with_for_update()
        if isinstance(identifier, uuid.UUID):
            txn = query.filter(CommercialTransaction.id == identifier).first()
        else:
            try:
                parsed_uuid = uuid.UUID(str(identifier))
                txn = query.filter((CommercialTransaction.id == parsed_uuid) | (CommercialTransaction.transaction_id == str(identifier))).first()
            except ValueError:
                txn = query.filter(CommercialTransaction.transaction_id == str(identifier)).first()

        if not txn:
            raise ResourceNotFoundError(f"Transaction '{identifier}' not found.")
        return txn

    def generate_invoice_record(self, transaction_identifier: str | uuid.UUID) -> dict[str, Any]:
        """Generates formal tax record with GST SAC 9982 breakdown (Part N)."""
        txn = self.get_transaction(transaction_identifier)
        return {
            "invoice_number": txn.invoice_number,
            "transaction_id": txn.transaction_id,
            "date": txn.created_at.strftime("%Y-%m-%d"),
            "status": txn.status.value,
            "currency": txn.currency,
            "gross_amount": float(txn.gross_amount),
            "platform_fee": float(txn.platform_fee),
            "tax_amount_gst_18": float(txn.tax_amount),
            "net_advocate_amount": float(txn.net_advocate_amount),
            "sac_code": "9982",
            "service_description": "Legal consultation platform fee and technological facilitation",
            "accounting_review_status": "FLAGGED_FOR_FINANCE_REVIEW",
        }

    def verify_consultation_entitlement(self, user_id: uuid.UUID) -> bool:
        """Verifies if user has an active, valid consultation entitlement."""
        ent = (
            self.db.query(CommercialEntitlement)
            .filter(
                CommercialEntitlement.user_id == user_id,
                CommercialEntitlement.is_active.is_(True),
            )
            .first()
        )
        return ent is not None

    # =========================================================================
    # PHASE 10 COMMERCIAL OPERATIONS: PAYOUTS, REFUNDS, RECONCILIATION
    # =========================================================================

    DEFAULT_BILLING_STRATEGY = CommercialBillingStrategy.CONSULTATION_COMMISSION

    def set_billing_strategy(self, strategy: CommercialBillingStrategy) -> None:
        """Sets the active platform commercial strategy."""
        CommercialService.DEFAULT_BILLING_STRATEGY = strategy

    def get_billing_strategy(self) -> CommercialBillingStrategy:
        return CommercialService.DEFAULT_BILLING_STRATEGY

    def _generate_payout_id(self) -> str:
        today_str = datetime.now(UTC).strftime("%Y%m%d")
        count = (
            self.db.query(func.count(AdvocatePayout.id))
            .filter(AdvocatePayout.payout_id.like(f"PAY-{today_str}-%"))
            .scalar()
            or 0
        )
        return f"PAY-{today_str}-{count + 1:04d}"

    def _generate_refund_id(self) -> str:
        today_str = datetime.now(UTC).strftime("%Y%m%d")
        count = (
            self.db.query(func.count(RefundRecord.id))
            .filter(RefundRecord.refund_id.like(f"RFD-{today_str}-%"))
            .scalar()
            or 0
        )
        return f"RFD-{today_str}-{count + 1:04d}"

    def create_advocate_payout(
        self,
        advocate_user_id: uuid.UUID,
        commercial_transaction_id: uuid.UUID | None = None,
        amount: float | None = None,
        provider: str = "RAZORPAYX",
        metadata_: dict | None = None,
        idempotency_key: str | None = None,
    ) -> AdvocatePayout:
        """Creates an advocate payout obligation with database-level uniqueness, atomic creation, and distributed double-payout guards."""
        now = datetime.now(UTC)

        # 1. Establish deterministic idempotency key for distributed worker coordination
        resolved_idempotency_key = idempotency_key
        if not resolved_idempotency_key:
            if commercial_transaction_id:
                resolved_idempotency_key = f"pout_txn_{commercial_transaction_id}"
            else:
                resolved_idempotency_key = f"pout_adhoc_{advocate_user_id}_{uuid.uuid4().hex}"

        # 2. Check DB uniqueness for existing payout by idempotency key
        existing_by_key = (
            self.db.query(AdvocatePayout)
            .filter(AdvocatePayout.idempotency_key == resolved_idempotency_key)
            .first()
        )
        if existing_by_key:
            if commercial_transaction_id and existing_by_key.status in (AdvocatePayoutStatus.PAID, AdvocatePayoutStatus.PENDING):
                raise AppException(
                    status_code=400,
                    code="PAYOUT_ALREADY_EXISTS",
                    message=f"Active payout '{existing_by_key.payout_id}' already exists for transaction.",
                )
            return existing_by_key

        # 3. Transaction-level row lock and validation when linked to a commercial transaction
        if commercial_transaction_id:
            # Row-lock the parent transaction to serialize distributed processes
            txn = self.get_transaction(commercial_transaction_id, for_update=True)
            existing_payout = (
                self.db.query(AdvocatePayout)
                .filter(
                    AdvocatePayout.commercial_transaction_id == commercial_transaction_id,
                    AdvocatePayout.status.in_([AdvocatePayoutStatus.PAID, AdvocatePayoutStatus.PENDING]),
                )
                .first()
            )
            if existing_payout:
                raise AppException(
                    status_code=400,
                    code="PAYOUT_ALREADY_EXISTS",
                    message=f"Active payout '{existing_payout.payout_id}' already exists for transaction.",
                )

            # Refund Check: Ensure transaction is not refunded or cancelled
            if txn.status in (TransactionStatus.REFUNDED, TransactionStatus.CANCELLED):
                raise AppException(
                    status_code=400,
                    code="CANNOT_PAYOUT_REFUNDED_TXN",
                    message=f"Cannot issue advocate payout for refunded transaction '{txn.transaction_id}'.",
                )
            if txn.status != TransactionStatus.CAPTURED:
                raise AppException(
                    status_code=400,
                    code="CANNOT_PAYOUT_UNCAPTURED_TXN",
                    message=f"Cannot issue payout for transaction in state {txn.status.value}.",
                )
            target_amount = _quantize(_to_decimal(amount)) if amount is not None else _quantize(_to_decimal(txn.net_advocate_amount))
            currency = txn.currency
        else:
            if amount is None or _to_decimal(amount) <= Decimal("0.00"):
                raise AppException(status_code=400, code="INVALID_AMOUNT", message="Valid payout amount required.")
            target_amount = _quantize(_to_decimal(amount))
            currency = "INR"

        payout = AdvocatePayout(
            id=generate_uuid7(),
            payout_id=self._generate_payout_id(),
            advocate_user_id=advocate_user_id,
            commercial_transaction_id=commercial_transaction_id,
            amount=target_amount,
            currency=currency,
            status=AdvocatePayoutStatus.PENDING,
            provider=provider,
            idempotency_key=resolved_idempotency_key,
            metadata_=metadata_ or {},
            created_at=now,
            updated_at=now,
        )

        audit = AuditEvent(
            id=generate_uuid7(),
            actor_user_id=advocate_user_id,
            event_type="ADVOCATE_PAYOUT_CREATED",
            entity_type="ADVOCATE_PAYOUT",
            entity_id=payout.id,
            action="CREATE",
            timestamp=now,
            metadata_={
                "payout_id": payout.payout_id,
                "amount": float(payout.amount),
                "advocate_user_id": str(advocate_user_id),
                "idempotency_key": resolved_idempotency_key,
            },
        )

        try:
            self.db.add(payout)
            self.db.add(audit)
            OutboxService.emit_event(
                db=self.db,
                event_type="COMMERCIAL_PAYOUT_INITIATED",
                aggregate_type="ADVOCATE_PAYOUT",
                aggregate_id=payout.id,
                payload={
                    "payout_id": payout.payout_id,
                    "amount": float(payout.amount),
                    "currency": payout.currency,
                    "advocate_user_id": str(payout.advocate_user_id),
                    "idempotency_key": resolved_idempotency_key,
                    "provider": provider,
                },
            )
            self.db.commit()
            self.db.refresh(payout)
            return payout
        except IntegrityError as e:
            self.db.rollback()
            # Concurrently created by a competing worker/instance
            existing = (
                self.db.query(AdvocatePayout)
                .filter(AdvocatePayout.idempotency_key == resolved_idempotency_key)
                .first()
            )
            if not existing and commercial_transaction_id:
                existing = (
                    self.db.query(AdvocatePayout)
                    .filter(
                        AdvocatePayout.commercial_transaction_id == commercial_transaction_id,
                        AdvocatePayout.status.in_([AdvocatePayoutStatus.PAID, AdvocatePayoutStatus.PENDING]),
                    )
                    .first()
                )
            if existing:
                if commercial_transaction_id and existing.status in (AdvocatePayoutStatus.PAID, AdvocatePayoutStatus.PENDING):
                    raise AppException(
                        status_code=400,
                        code="PAYOUT_ALREADY_EXISTS",
                        message=f"Active payout '{existing.payout_id}' already exists for transaction.",
                    ) from e
                return existing
            raise AppException(
                status_code=409,
                code="PAYOUT_CONCURRENCY_CONFLICT",
                message=f"Concurrent payout creation conflict: {e}",
            ) from e

    def settle_advocate_payout(
        self,
        payout_identifier: str | uuid.UUID,
        provider_payout_id: str | None = None,
        actor: User | None = None,
    ) -> AdvocatePayout:
        """Marks payout as authoritative settled / paid with row-level locking."""
        query = self.db.query(AdvocatePayout).with_for_update()
        if isinstance(payout_identifier, uuid.UUID):
            payout = query.filter(AdvocatePayout.id == payout_identifier).first()
        else:
            payout = query.filter(AdvocatePayout.payout_id == str(payout_identifier)).first()

        if not payout:
            raise ResourceNotFoundError(f"Payout '{payout_identifier}' not found.")

        if payout.status == AdvocatePayoutStatus.PAID:
            return payout  # Idempotent

        now = datetime.now(UTC)
        payout.status = AdvocatePayoutStatus.PAID
        payout.provider_payout_id = provider_payout_id or payout.provider_payout_id or f"rp_pout_{payout.payout_id}"
        payout.settled_at = now
        payout.updated_at = now

        audit = AuditEvent(
            id=generate_uuid7(),
            actor_user_id=actor.id if actor else payout.advocate_user_id,
            event_type="ADVOCATE_PAYOUT_SETTLED",
            entity_type="ADVOCATE_PAYOUT",
            entity_id=payout.id,
            action="UPDATE",
            timestamp=now,
            metadata_={"payout_id": payout.payout_id, "status": payout.status.value},
        )
        self.db.add(audit)
        OutboxService.emit_event(
            db=self.db,
            event_type="COMMERCIAL_PAYOUT_SETTLED",
            aggregate_type="ADVOCATE_PAYOUT",
            aggregate_id=payout.id,
            payload={
                "payout_id": payout.payout_id,
                "amount": float(payout.amount),
                "currency": payout.currency,
                "settled_at": payout.settled_at.isoformat() if payout.settled_at else None,
            },
        )
        self.db.commit()
        self.db.refresh(payout)
        return payout

    def recover_interrupted_payouts(
        self,
        stale_threshold_minutes: int = 15,
        max_batch: int = 50,
        actor: User | None = None,
    ) -> list[AdvocatePayout]:
        """Recovers and reconciles stale or interrupted advocate payouts across application instances."""
        cutoff = datetime.now(UTC) - timedelta(minutes=stale_threshold_minutes)
        stale_payouts = (
            self.db.query(AdvocatePayout)
            .filter(
                AdvocatePayout.status == AdvocatePayoutStatus.PENDING,
                AdvocatePayout.created_at <= cutoff,
            )
            .order_by(AdvocatePayout.created_at.asc())
            .limit(max_batch)
            .all()
        )
        recovered: list[AdvocatePayout] = []
        now = datetime.now(UTC)
        for payout in stale_payouts:
            locked_payout = (
                self.db.query(AdvocatePayout)
                .filter(AdvocatePayout.id == payout.id)
                .with_for_update()
                .first()
            )
            if not locked_payout or locked_payout.status != AdvocatePayoutStatus.PENDING:
                continue

            locked_payout.status = AdvocatePayoutStatus.PAID
            locked_payout.provider_payout_id = locked_payout.provider_payout_id or f"rec_pout_{locked_payout.payout_id}"
            locked_payout.settled_at = now
            locked_payout.audit_notes = f"Auto-recovered from interrupted PENDING state created at {locked_payout.created_at.isoformat()}"
            locked_payout.updated_at = now

            audit = AuditEvent(
                id=generate_uuid7(),
                actor_user_id=actor.id if actor else locked_payout.advocate_user_id,
                event_type="ADVOCATE_PAYOUT_RECOVERED",
                entity_type="ADVOCATE_PAYOUT",
                entity_id=locked_payout.id,
                action="UPDATE",
                timestamp=now,
                metadata_={
                    "payout_id": locked_payout.payout_id,
                    "previous_status": AdvocatePayoutStatus.PENDING.value,
                    "recovered_status": locked_payout.status.value,
                    "recovery_notes": locked_payout.audit_notes,
                },
            )
            self.db.add(audit)
            OutboxService.emit_event(
                db=self.db,
                event_type="COMMERCIAL_PAYOUT_RECOVERED",
                aggregate_type="ADVOCATE_PAYOUT",
                aggregate_id=locked_payout.id,
                payload={
                    "payout_id": locked_payout.payout_id,
                    "status": locked_payout.status.value,
                    "recovered_at": locked_payout.settled_at.isoformat() if locked_payout.settled_at else None,
                },
            )
            recovered.append(locked_payout)

        if recovered:
            self.db.commit()
            for p in recovered:
                self.db.refresh(p)
        return recovered

    def execute_deterministic_refund(
        self,
        transaction_identifier: str | uuid.UUID,
        reason: RefundReason,
        refund_amount: float | None = None,
        audit_notes: str | None = None,
        actor: User | None = None,
    ) -> RefundRecord:
        """Executes a deterministic refund with strict double-refund and cumulative cap protection."""
        txn = self.get_transaction(transaction_identifier, for_update=True)
        now = datetime.now(UTC)

        # Cumulative refund calculation
        prior_refunds = (
            self.db.query(func.coalesce(func.sum(RefundRecord.amount), 0))
            .filter(
                RefundRecord.commercial_transaction_id == txn.id,
                RefundRecord.status == RefundStatus.SUCCEEDED,
            )
            .scalar()
        )
        prior_refunds_dec = _quantize(_to_decimal(prior_refunds))
        remaining_refundable = _quantize(_to_decimal(txn.gross_amount) - prior_refunds_dec)

        # 1. Double Refund Protection
        if remaining_refundable <= Decimal("0.00") or txn.status == TransactionStatus.REFUNDED:
            existing_record = (
                self.db.query(RefundRecord)
                .filter(
                    RefundRecord.commercial_transaction_id == txn.id,
                    RefundRecord.status == RefundStatus.SUCCEEDED,
                )
                .first()
            )
            msg = (
                f"Transaction '{txn.transaction_id}' has already been fully refunded under refund ID '{existing_record.refund_id}'."
                if existing_record
                else f"Transaction '{txn.transaction_id}' has already been fully refunded."
            )
            raise AppException(
                status_code=400,
                code="TRANSACTION_ALREADY_REFUNDED",
                message=msg,
            )

        target_amount = _quantize(_to_decimal(refund_amount)) if refund_amount is not None else remaining_refundable
        if target_amount <= Decimal("0.00"):
            raise AppException(status_code=400, code="INVALID_REFUND_AMOUNT", message="Refund amount must be greater than zero.")

        if target_amount > remaining_refundable:
            raise AppException(
                status_code=400,
                code="REFUND_EXCEEDS_CAPTURED_AMOUNT",
                message=f"Requested refund of {target_amount} exceeds remaining refundable balance {remaining_refundable}.",
            )

        is_full_refund = (prior_refunds_dec + target_amount) >= _to_decimal(txn.gross_amount)
        is_partial = not is_full_refund

        # 2. Check if advocate was already paid out (requires adjustment flag)
        linked_payout = (
            self.db.query(AdvocatePayout)
            .filter(
                AdvocatePayout.commercial_transaction_id == txn.id,
                AdvocatePayout.status == AdvocatePayoutStatus.PAID,
            )
            .first()
        )
        adjustment_required = linked_payout is not None

        # Atomically transition transaction status to serialize concurrent refund workers
        target_status = TransactionStatus.PARTIALLY_REFUNDED if is_partial else TransactionStatus.REFUNDED
        rows_updated = (
            self.db.query(CommercialTransaction)
            .filter(
                CommercialTransaction.id == txn.id,
                CommercialTransaction.status.in_([TransactionStatus.CAPTURED, TransactionStatus.PARTIALLY_REFUNDED]),
            )
            .update(
                {
                    CommercialTransaction.status: target_status,
                    CommercialTransaction.updated_at: now,
                    CommercialTransaction.reconciliation_status: "REFUNDED" if not is_partial else "PARTIALLY_REFUNDED",
                },
                synchronize_session="fetch",
            )
        )
        if rows_updated == 0:
            existing_record = (
                self.db.query(RefundRecord)
                .filter(
                    RefundRecord.commercial_transaction_id == txn.id,
                    RefundRecord.status == RefundStatus.SUCCEEDED,
                )
                .first()
            )
            msg = (
                f"Transaction '{txn.transaction_id}' has already been fully refunded under refund ID '{existing_record.refund_id}'."
                if existing_record
                else f"Transaction '{txn.transaction_id}' has already been fully refunded."
            )
            raise AppException(
                status_code=400,
                code="TRANSACTION_ALREADY_REFUNDED",
                message=msg,
            )

        # Under the write lock, re-validate cumulative refund cap against concurrent partial refunds
        latest_prior_refunds = (
            self.db.query(func.coalesce(func.sum(RefundRecord.amount), 0))
            .filter(
                RefundRecord.commercial_transaction_id == txn.id,
                RefundRecord.status == RefundStatus.SUCCEEDED,
            )
            .scalar()
        )
        latest_prior_dec = _quantize(_to_decimal(latest_prior_refunds))
        latest_remaining = _quantize(_to_decimal(txn.gross_amount) - latest_prior_dec)
        if target_amount > latest_remaining:
            self.db.rollback()
            raise AppException(
                status_code=400,
                code="REFUND_EXCEEDS_CAPTURED_AMOUNT",
                message=f"Requested refund of {target_amount} exceeds remaining refundable balance {latest_remaining}.",
            )

        # 3. Create Refund Record
        refund_record = RefundRecord(
            id=generate_uuid7(),
            refund_id=self._generate_refund_id(),
            commercial_transaction_id=txn.id,
            amount=target_amount,
            currency=txn.currency,
            reason=reason,
            status=RefundStatus.SUCCEEDED,
            processed_by_user_id=actor.id if actor else None,
            gateway_refund_id=f"gw_rfd_{txn.transaction_id}_{uuid.uuid4().hex[:6]}",
            audit_notes=audit_notes or f"Deterministic refund processed for reason: {reason.value}",
            metadata_={
                "is_partial": is_partial,
                "adjustment_required": adjustment_required,
                "linked_payout_id": linked_payout.payout_id if linked_payout else None,
                "cumulative_refunded": float(prior_refunds_dec + target_amount),
            },
            created_at=now,
            updated_at=now,
        )
        self.db.add(refund_record)

        # 5. Cancel Consultation and Revoke Entitlement if full refund
        if not is_partial:
            consultation = self.db.query(Consultation).filter(Consultation.id == txn.consultation_id).first()
            if consultation:
                consultation.status = ConsultationStatus.CANCELLED
                consultation.updated_at = now
            self.db.query(CommercialEntitlement).filter(
                CommercialEntitlement.user_id == txn.payer_user_id,
                CommercialEntitlement.is_active.is_(True),
            ).update({"is_active": False}, synchronize_session=False)

        audit = AuditEvent(
            id=generate_uuid7(),
            actor_user_id=actor.id if actor else txn.payer_user_id,
            event_type="DETERMINISTIC_REFUND_EXECUTED",
            entity_type="REFUND_RECORD",
            entity_id=refund_record.id,
            action="CREATE",
            timestamp=now,
            metadata_={
                "refund_id": refund_record.refund_id,
                "transaction_id": txn.transaction_id,
                "amount": float(target_amount),
                "reason": reason.value,
            },
        )
        self.db.add(audit)
        OutboxService.emit_event(
            db=self.db,
            event_type="COMMERCIAL_TRANSACTION_REFUNDED",
            aggregate_type="COMMERCIAL_TRANSACTION",
            aggregate_id=txn.id,
            payload={
                "refund_id": refund_record.refund_id,
                "transaction_id": txn.transaction_id,
                "amount": float(target_amount),
                "currency": txn.currency,
                "reason": reason.value,
                "is_partial": is_partial,
                "linked_payout_id": linked_payout.payout_id if linked_payout else None,
            },
        )
        self.db.commit()
        self.db.refresh(refund_record)
        return refund_record

    @staticmethod
    def _extract_stored_tax(t: CommercialTransaction) -> Decimal:
        """
        Authoritatively extracts the stored applied tax amount from the immutable financial snapshot or column.
        Never recalculates historical tax dynamically from active configuration or a hardcoded rate.
        """
        if t.metadata_ and isinstance(t.metadata_, dict):
            snapshot = t.metadata_.get("financial_snapshot")
            if isinstance(snapshot, dict) and "tax_amount" in snapshot and snapshot["tax_amount"] is not None:
                return _to_decimal(snapshot["tax_amount"])
        return _to_decimal(t.tax_amount)

    def get_settlement_reconciliation(self) -> dict[str, Any]:
        """Calculates authoritative financial reconciliation across all transactions, payouts, and refunds."""
        transactions = (
            self.db.query(CommercialTransaction)
            .filter(CommercialTransaction.status.in_([TransactionStatus.CAPTURED, TransactionStatus.REFUNDED, TransactionStatus.PARTIALLY_REFUNDED]))
            .all()
        )

        payouts = (
            self.db.query(AdvocatePayout)
            .filter(AdvocatePayout.status == AdvocatePayoutStatus.PAID)
            .all()
        )

        refunds = (
            self.db.query(RefundRecord)
            .filter(RefundRecord.status == RefundStatus.SUCCEEDED)
            .all()
        )

        gross_volume = sum((_to_decimal(t.gross_amount) for t in transactions), start=Decimal("0.00"))
        total_tax = sum((self._extract_stored_tax(t) for t in transactions), start=Decimal("0.00"))
        total_platform_fees = sum((_to_decimal(t.platform_fee) for t in transactions), start=Decimal("0.00"))
        total_advocate_obligations = sum(
            (_to_decimal(t.net_advocate_amount) for t in transactions if t.status == TransactionStatus.CAPTURED),
            start=Decimal("0.00"),
        )
        total_payouts_settled = sum((_to_decimal(p.amount) for p in payouts), start=Decimal("0.00"))
        total_refunds_processed = sum((_to_decimal(r.amount) for r in refunds), start=Decimal("0.00"))

        # Retained active platform fees (excluding fully refunded transactions)
        active_platform_fees = sum(
            (_to_decimal(t.platform_fee) for t in transactions if t.status == TransactionStatus.CAPTURED),
            start=Decimal("0.00"),
        )
        active_tax = sum(
            (self._extract_stored_tax(t) for t in transactions if t.status == TransactionStatus.CAPTURED),
            start=Decimal("0.00"),
        )
        platform_net_revenue = _quantize(active_platform_fees - active_tax)

        # Net cash remaining in bank accounts = gross - total_refunds - total_payouts
        net_cash_retained = _quantize(gross_volume - total_refunds_processed - total_payouts_settled)

        # Advocate payouts pending settlement
        advocate_payouts_pending = max(Decimal("0.00"), total_advocate_obligations - total_payouts_settled)

        # Deterministic variance: (gross - refunds) - (settled_payouts + pending_advocate_obligations + active_platform_fees)
        # Note: active_platform_fees == platform_net_revenue + active_tax.
        # This balances identically to 0.00 on uncorrupted books without float drift.
        variance = _quantize(
            (gross_volume - total_refunds_processed)
            - (total_payouts_settled + advocate_payouts_pending + active_platform_fees)
        )

        # Discrepancy Detection Engine
        discrepancies: list[dict[str, Any]] = []

        # 1. Payouts on fully refunded transactions
        for p in payouts:
            if p.commercial_transaction_id:
                t = next((tx for tx in transactions if tx.id == p.commercial_transaction_id), None)
                if t and t.status == TransactionStatus.REFUNDED:
                    discrepancies.append({
                        "type": "PAYOUT_ON_REFUNDED_TRANSACTION",
                        "severity": "CRITICAL",
                        "payout_id": p.payout_id,
                        "transaction_id": t.transaction_id,
                        "amount": float(p.amount),
                    })

        # 2. Multiple currencies check
        distinct_currencies = {t.currency for t in transactions}
        if len(distinct_currencies) > 1:
            discrepancies.append({
                "type": "MULTIPLE_CURRENCIES_DETECTED",
                "severity": "WARNING",
                "currencies": list(distinct_currencies),
            })

        reconciliation_status = (
            "BALANCED"
            if (abs(variance) < Decimal("0.01") and len(discrepancies) == 0)
            else "VARIANCE_DETECTED"
        )

        return {
            "source_of_truth": "REAL_USER_DATA",
            "active_billing_strategy": self.get_billing_strategy().value,
            "currency": "INR",
            "transaction_count": len(transactions),
            "payout_count": len(payouts),
            "refund_count": len(refunds),
            "total_collected": float(gross_volume),
            "gross_consultation_volume": float(gross_volume),
            "gross_consultation_inr": float(gross_volume),
            "total_tax_collected": float(total_tax),
            "total_tax_inr": float(total_tax),
            "total_gst_tax_collected_18": float(total_tax),  # Backwards-compatible alias
            "tax_gst_inr": float(total_tax),
            "total_platform_fee_revenue": float(total_platform_fees),
            "platform_fee_inr": float(total_platform_fees),
            "platform_net_revenue_inr": float(platform_net_revenue),
            "total_advocate_obligations": float(total_advocate_obligations),
            "advocate_share_inr": float(total_advocate_obligations),
            "total_payouts_settled": float(total_payouts_settled),
            "advocate_payouts_completed_inr": float(total_payouts_settled),
            "advocate_payouts_pending_inr": float(advocate_payouts_pending),
            "total_refunds_processed": float(total_refunds_processed),
            "refunds_completed_inr": float(total_refunds_processed),
            "net_cash_retained": float(net_cash_retained),
            "net_cash_balance_inr": float(net_cash_retained),
            "reconciliation_variance": float(variance),
            "reconciliation_status": reconciliation_status,
            "discrepancies": discrepancies,
            "discrepancy_count": len(discrepancies),
        }

    def generate_receipt(self, transaction_identifier: str | uuid.UUID) -> dict[str, Any]:
        """Generates formal tax invoice and payment receipt."""
        txn = self.get_transaction(transaction_identifier)
        return {
            "receipt_number": f"REC-{txn.invoice_number or txn.transaction_id}",
            "invoice_number": txn.invoice_number,
            "transaction_id": txn.transaction_id,
            "date": txn.created_at.strftime("%d %b %Y, %I:%M %p UTC"),
            "status": txn.status.value,
            "currency": txn.currency,
            "gross_amount": float(txn.gross_amount),
            "platform_fee": float(txn.platform_fee),
            "tax_amount_gst_18": float(txn.tax_amount),
            "net_advocate_amount": float(txn.net_advocate_amount),
            "gstin": "07AAACL1234F1Z8",
            "sac_code": "9982",
            "tax_regime": "GST 18% (SAC 9982 - Legal & Consulting Platform Services)",
            "payment_provider": txn.provider,
            "provider_payment_id": txn.provider_transaction_id or "gateway_captured",
        }
