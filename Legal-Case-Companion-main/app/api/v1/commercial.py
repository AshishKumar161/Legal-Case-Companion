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
