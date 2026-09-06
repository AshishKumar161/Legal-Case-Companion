from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import RequireOperatorPermission, get_current_user, get_db
from app.models.commercial import CommercialEntitlement, CommercialTransaction
from app.models.operator import OperationalPermission
from app.models.user import User
from app.services.commercial_service import CommercialService

router = APIRouter(prefix="/commercial", tags=["commercial"])


class TransactionCaptureRequest(BaseModel):
    provider_payment_id: str | None = None


class TransactionRefundRequest(BaseModel):
    refund_amount: float | None = None
    reason: str = Field(default="REQUESTED_BY_CUSTOMER", min_length=3, max_length=255)


@router.get("/transactions/{transaction_id}")
def get_transaction(
    transaction_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Retrieves commercial transaction details with authorization boundary enforcement."""
    service = CommercialService(db)
    txn = service.get_transaction(transaction_id)
    if current_user.role.value != "ADMIN" and current_user.id not in (txn.payer_user_id, txn.payee_user_id):
        from app.core.exceptions import AuthorizationError
        raise AuthorizationError("Not authorized to view this transaction.")

    return {
        "transaction_id": txn.transaction_id,
        "consultation_id": str(txn.consultation_id),
        "status": txn.status.value,
        "gross_amount": float(txn.gross_amount),
        "currency": txn.currency,
        "invoice_number": txn.invoice_number,
        "created_at": txn.created_at.isoformat(),
    }


@router.post("/transactions/{transaction_id}/capture")
def capture_transaction(
    transaction_id: str,
    req: TransactionCaptureRequest,
    current_user: User = Depends(RequireOperatorPermission(OperationalPermission.BILLING_OPERATIONS)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Captures an authorized transaction and updates consultation entitlements."""
    service = CommercialService(db)
    txn = service.capture_transaction(transaction_id, provider_payment_id=req.provider_payment_id)
    return {
        "status": "CAPTURED",
        "transaction_id": txn.transaction_id,
        "invoice_number": txn.invoice_number,
    }


@router.post("/transactions/{transaction_id}/refund")
def process_refund(
    transaction_id: str,
    req: TransactionRefundRequest,
    current_user: User = Depends(RequireOperatorPermission(OperationalPermission.BILLING_OPERATIONS)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Processes a full or partial refund with audit trails and consultation cancellation."""
    service = CommercialService(db)
    txn = service.process_refund(
        transaction_id,
        refund_amount=req.refund_amount,
        reason=req.reason,
        actor=current_user,
    )
    return {
        "status": txn.status.value,
        "transaction_id": txn.transaction_id,
    }


@router.get("/transactions/{transaction_id}/invoice")
def get_invoice_record(
    transaction_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Retrieves legal accounting invoice record with SAC 9982 GST breakdown (Part N)."""
    service = CommercialService(db)
    txn = service.get_transaction(transaction_id)
    if current_user.role.value != "ADMIN" and current_user.id not in (txn.payer_user_id, txn.payee_user_id):
        from app.core.exceptions import AuthorizationError
        raise AuthorizationError("Not authorized to view this invoice.")
    return service.generate_invoice_record(transaction_id)


@router.get("/entitlements/my")
def get_my_entitlements(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """Lists current active commercial entitlements (consultation minutes, AI queries)."""
    items = (
        db.query(CommercialEntitlement)
        .filter(CommercialEntitlement.user_id == current_user.id, CommercialEntitlement.is_active.is_(True))
        .all()
    )
    return [
        {
            "entitlement_type": e.entitlement_type,
            "quota_limit": e.quota_limit,
            "quota_used": e.quota_used,
            "is_active": e.is_active,
            "valid_until": e.valid_until.isoformat() if e.valid_until else None,
        }
        for e in items
    ]


# =============================================================================
# PHASE 10: RECONCILIATION, PAYOUTS, REFUNDS & UNIT ECONOMICS
# =============================================================================

from app.models.commercial import CommercialBillingStrategy, RefundReason
from app.services.unit_economics_service import UnitEconomicsService
from app.core.exceptions import AppException, ResourceNotFoundError


class PayoutRequest(BaseModel):
    advocate_user_id: UUID
    commercial_transaction_id: UUID | None = None
    amount: float | None = None
    provider: str = "RAZORPAYX"
    metadata: dict[str, Any] = Field(default_factory=dict)


class RefundExecutionRequest(BaseModel):
    transaction_identifier: str
    reason: RefundReason
    refund_amount: float | None = None
    audit_notes: str | None = None


class StrategyUpdateRequest(BaseModel):
    strategy: CommercialBillingStrategy


@router.get("/settlements/reconciliation")
def get_settlement_reconciliation(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Returns authoritative financial reconciliation across gross, tax, platform fees, payouts, and refunds."""
    if current_user.role.value != "ADMIN":
        from app.core.exceptions import AuthorizationError
        raise AuthorizationError("Admin authorization required.")
    service = CommercialService(db)
    return service.get_settlement_reconciliation()


@router.get("/invoices/{transaction_identifier}/receipt")
def get_invoice_receipt(
    transaction_identifier: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Generates formal tax invoice and receipt for a given transaction."""
    service = CommercialService(db)
    try:
        return service.generate_receipt(transaction_identifier)
    except ResourceNotFoundError as e:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(str(e)) from e


@router.post("/payouts/process")
def process_payout(
    req: PayoutRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Creates and immediately settles an advocate payout with double-payout guards."""
    if current_user.role.value != "ADMIN":
        from app.core.exceptions import AuthorizationError
        raise AuthorizationError("Admin authorization required.")
    service = CommercialService(db)
    payout = service.create_advocate_payout(
        advocate_user_id=req.advocate_user_id,
        commercial_transaction_id=req.commercial_transaction_id,
        amount=req.amount,
        provider=req.provider,
        metadata_=req.metadata,
    )
    settled = service.settle_advocate_payout(payout.id, actor=current_user)
    return {
        "status": "SUCCESS",
        "payout_id": settled.payout_id,
        "amount": float(settled.amount),
        "currency": settled.currency,
        "settled_at": settled.settled_at.isoformat() if settled.settled_at else None,
    }


@router.post("/refunds/request")
def request_deterministic_refund(
    req: RefundExecutionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Executes a deterministic refund enforcing defined cancellation rules."""
    if current_user.role.value != "ADMIN":
        from app.core.exceptions import AuthorizationError
        raise AuthorizationError("Admin authorization required.")
    service = CommercialService(db)
    record = service.execute_deterministic_refund(
        transaction_identifier=req.transaction_identifier,
        reason=req.reason,
        refund_amount=req.refund_amount,
        audit_notes=req.audit_notes,
        actor=current_user,
    )
    return {
        "status": "SUCCESS",
        "refund_id": record.refund_id,
        "amount": float(record.amount),
        "reason": record.reason.value,
        "created_at": record.created_at.isoformat(),
    }


@router.get("/unit-economics")
def get_unit_economics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Returns commercial unit economics and cost breakdown."""
    if current_user.role.value != "ADMIN":
        from app.core.exceptions import AuthorizationError
        raise AuthorizationError("Admin authorization required.")
    service = UnitEconomicsService(db)
    return service.calculate_unit_economics()


@router.get("/strategy")
def get_billing_strategy(
    db: Session = Depends(get_db),
) -> dict[str, str]:
    service = CommercialService(db)
    return {"billing_strategy": service.get_billing_strategy().value}


@router.post("/strategy")
def update_billing_strategy(
    req: StrategyUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    if current_user.role.value != "ADMIN":
        from app.core.exceptions import AuthorizationError
        raise AuthorizationError("Admin authorization required.")
    service = CommercialService(db)
    service.set_billing_strategy(req.strategy)
    return {"billing_strategy": service.get_billing_strategy().value}

