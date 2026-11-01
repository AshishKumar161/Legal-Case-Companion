import logging
import secrets
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import settings
from app.domain.payments.payment_service import PaymentService
from app.domain.evidence.scanner_service import ScannerService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


class MalwareScanEvent(BaseModel):
    document_id: UUID
    is_safe: bool
    details: str | None = None


@router.post("/aws/malware")
def aws_malware_webhook(
    event: MalwareScanEvent,
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
):
    """
    Internal Webhook for AWS EventBridge / Lambda to report malware scan results.
    Authorizes via a shared secret (AWS_WEBHOOK_SECRET) with constant-time verification.
    Fails safely without disclosing internal configuration state.
    """
    if not settings.AWS_WEBHOOK_SECRET:
        logger.error("AWS_WEBHOOK_SECRET is not configured. Webhook request rejected.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Webhook service unavailable",
        )

    expected_header = f"Bearer {settings.AWS_WEBHOOK_SECRET}"
    if not authorization or not secrets.compare_digest(authorization, expected_header):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook signature"
        )

    scanner_service = ScannerService(db)
    # The simulate_scan method is repurposed here as handle_scan_result
    # because it performs exactly the required DB transitions.
    scanner_service.simulate_scan(event.document_id, event.is_safe)

    return {"status": "success"}


@router.post("/stripe")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """
    External Webhook for Stripe events (payment_intent.succeeded, etc.).
    """
    sig_header = request.headers.get("Stripe-Signature")
    raw_body = await request.body()
    service = PaymentService(db)
    return service.handle_webhook(raw_body, signature_header=sig_header)
