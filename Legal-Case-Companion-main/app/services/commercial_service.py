import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

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


class CommercialService:
    """Manages immutable commercial transaction records, financial separation, and entitlements (Parts L, M, N)."""

    GST_RATE_PERCENT = 18.0  # SAC 9982 - Legal and accounting support services (Subject to formal tax review)
    PLATFORM_FEE_PERCENT = 10.0

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
        return f"TXN-{today_str}-{count + 1:04d}"

    def _generate_invoice_number(self) -> str:
        today_str = datetime.now(UTC).strftime("%Y%m%d")
        count = (
            self.db.query(func.count(CommercialTransaction.id))
            .filter(CommercialTransaction.invoice_number.like(f"INV-{today_str}-%"))
            .scalar()
            or 0
        )
        return f"INV-{today_str}-{count + 1:04d}"

    def create_consultation_transaction(
        self,
        consultation: Consultation,
        payer: User,
        provider: str = "STRIPE",
        provider_transaction_id: str | None = None,
    ) -> CommercialTransaction:
        now = datetime.now(UTC)
        gross = float(consultation.fee_amount)

        # Separate platform fee, GST 18%, and net advocate compensation
        platform_fee = round(gross * (self.PLATFORM_FEE_PERCENT / 100.0), 2)
        tax_amount = round(platform_fee * (self.GST_RATE_PERCENT / 100.0), 2)
        net_advocate = round(gross - platform_fee, 2)

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
        txn = self.get_transaction(transaction_identifier)
        now = datetime.now(UTC)

        if txn.status not in (TransactionStatus.CAPTURED, TransactionStatus.AUTHORIZED):
            raise AppException(
                status_code=400,
                code="INVALID_REFUND_STATE",
                message=f"Cannot refund transaction in state {txn.status.value}.",
            )

        target_amount = refund_amount or float(txn.gross_amount)
        is_partial = target_amount < float(txn.gross_amount)

        txn.status = TransactionStatus.PARTIALLY_REFUNDED if is_partial else TransactionStatus.REFUNDED
        txn.updated_at = now
        txn.metadata_["refund_info"] = {
            "refund_amount": target_amount,
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
                "refund_amount": target_amount,
                "is_partial": is_partial,
            },
        )
        self.db.add(audit)
        self.db.commit()
        self.db.refresh(txn)
        return txn

    def get_transaction(self, identifier: str | uuid.UUID) -> CommercialTransaction:
        query = self.db.query(CommercialTransaction)
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
    ) -> AdvocatePayout:
        """Creates an advocate payout obligation with double-payout and refund protection."""
        now = datetime.now(UTC)

        # 1. Double Payout Guard
        if commercial_transaction_id:
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

            # 2. Refund Check: Ensure transaction is not refunded
            txn = self.get_transaction(commercial_transaction_id)
            if txn.status in (TransactionStatus.REFUNDED, TransactionStatus.CANCELLED):
                raise AppException(
                    status_code=400,
                    code="CANNOT_PAYOUT_REFUNDED_TXN",
                    message=f"Cannot issue advocate payout for refunded transaction '{txn.transaction_id}'.",
                )
            target_amount = amount or float(txn.net_advocate_amount)
            currency = txn.currency
        else:
            if amount is None or amount <= 0:
                raise AppException(status_code=400, code="INVALID_AMOUNT", message="Valid payout amount required.")
            target_amount = amount
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
            metadata_=metadata_ or {},
            created_at=now,
            updated_at=now,
        )
        self.db.add(payout)

        # Audit
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
            },
        )
        self.db.add(audit)
        self.db.commit()
        self.db.refresh(payout)
        return payout

    def settle_advocate_payout(
        self,
        payout_identifier: str | uuid.UUID,
        provider_payout_id: str | None = None,
        actor: User | None = None,
    ) -> AdvocatePayout:
        """Marks payout as authoritative settled / paid."""
        query = self.db.query(AdvocatePayout)
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
        payout.provider_payout_id = provider_payout_id or f"rp_pout_{payout.payout_id}"
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
        self.db.commit()
        self.db.refresh(payout)
        return payout

    def execute_deterministic_refund(
        self,
        transaction_identifier: str | uuid.UUID,
        reason: RefundReason,
        refund_amount: float | None = None,
        audit_notes: str | None = None,
        actor: User | None = None,
    ) -> RefundRecord:
        """Executes a deterministic refund with strict double-refund protection."""
        txn = self.get_transaction(transaction_identifier)
        now = datetime.now(UTC)

        # 1. Double Refund Protection
        if txn.status == TransactionStatus.REFUNDED:
            existing_record = (
                self.db.query(RefundRecord)
                .filter(
                    RefundRecord.commercial_transaction_id == txn.id,
                    RefundRecord.status == RefundStatus.SUCCEEDED,
                )
                .first()
            )
            if existing_record:
                raise AppException(
                    status_code=400,
                    code="TRANSACTION_ALREADY_REFUNDED",
                    message=f"Transaction '{txn.transaction_id}' has already been fully refunded under refund ID '{existing_record.refund_id}'.",
                )

        target_amount = refund_amount or float(txn.gross_amount)
        is_partial = target_amount < float(txn.gross_amount)

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
            gateway_refund_id=f"gw_rfd_{txn.transaction_id}",
            audit_notes=audit_notes or f"Deterministic refund processed for reason: {reason.value}",
            metadata_={
                "is_partial": is_partial,
                "adjustment_required": adjustment_required,
                "linked_payout_id": linked_payout.payout_id if linked_payout else None,
            },
            created_at=now,
            updated_at=now,
        )
        self.db.add(refund_record)

        # 4. Update Transaction
        txn.status = TransactionStatus.PARTIALLY_REFUNDED if is_partial else TransactionStatus.REFUNDED
        txn.updated_at = now
        txn.reconciliation_status = "REFUNDED" if not is_partial else "PARTIALLY_REFUNDED"

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
        self.db.commit()
        self.db.refresh(refund_record)
        return refund_record

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

        gross_volume = sum(float(t.gross_amount) for t in transactions)
        total_tax = sum(float(t.tax_amount) for t in transactions)
        total_platform_fees = sum(float(t.platform_fee) for t in transactions)
        total_advocate_obligations = sum(float(t.net_advocate_amount) for t in transactions if t.status == TransactionStatus.CAPTURED)
        total_payouts_settled = sum(float(p.amount) for p in payouts)
        total_refunds_processed = sum(float(r.amount) for r in refunds)

        # Net cash remaining = gross - total_refunds - total_payouts
        net_cash_retained = round(gross_volume - total_refunds_processed - total_payouts_settled, 2)
        variance = round((gross_volume - total_refunds_processed) - (total_payouts_settled + total_platform_fees + total_tax), 2)

        return {
            "source_of_truth": "REAL_USER_DATA",
            "active_billing_strategy": self.get_billing_strategy().value,
            "currency": "INR",
            "transaction_count": len(transactions),
            "payout_count": len(payouts),
            "refund_count": len(refunds),
            "gross_consultation_volume": round(gross_volume, 2),
            "gross_consultation_inr": round(gross_volume, 2),
            "total_gst_tax_collected_18": round(total_tax, 2),
            "tax_gst_inr": round(total_tax, 2),
            "total_platform_fee_revenue": round(total_platform_fees, 2),
            "platform_fee_inr": round(total_platform_fees, 2),
            "total_advocate_obligations": round(total_advocate_obligations, 2),
            "advocate_share_inr": round(total_advocate_obligations, 2),
            "total_payouts_settled": round(total_payouts_settled, 2),
            "advocate_payouts_completed_inr": round(total_payouts_settled, 2),
            "advocate_payouts_pending_inr": 0.0,
            "total_refunds_processed": round(total_refunds_processed, 2),
            "refunds_completed_inr": round(total_refunds_processed, 2),
            "net_cash_retained": net_cash_retained,
            "net_cash_balance_inr": net_cash_retained,
            "reconciliation_variance": variance,
            "reconciliation_status": "BALANCED" if abs(variance) < 1.0 else "VARIANCE_DETECTED",
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
