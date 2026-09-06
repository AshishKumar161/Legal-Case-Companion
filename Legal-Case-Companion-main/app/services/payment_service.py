import hashlib
import hmac
import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Any, Protocol

from fastapi import HTTPException
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import (
    AuthorizationError,
    ResourceNotFoundError,
    ValidationError,
)
from app.core.identifiers import generate_uuid7
from app.models.consultation import ConsultationStatus
from app.models.notification import NotificationType
from app.models.payment import Payment, PaymentStatus
from app.models.user import User, UserRole
from app.models.webhook import ProcessedWebhookEvent, WebhookProcessingStatus
from app.schemas.payment import PaymentIntentResponse
from app.services.auth_service import AuthService
from app.services.case_service import CaseService
from app.services.consultation_service import ConsultationService
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)


def verify_stripe_webhook_signature(
    raw_payload: bytes,
    signature_header: str | None,
    secret: str,
    tolerance_seconds: int = 300,
) -> dict[str, Any]:
    """Cryptographically verifies Stripe webhook HMAC-SHA256 signatures with replay protection."""
    if not signature_header or not secret:
        raise HTTPException(status_code=401, detail="Invalid or missing signature")

    pairs = signature_header.split(",")
    timestamp: int | None = None
    signatures: list[str] = []
    for pair in pairs:
        parts = pair.strip().split("=", 1)
        if len(parts) == 2:
            key, val = parts[0].strip(), parts[1].strip()
            if key == "t":
                try:
                    timestamp = int(val)
                except ValueError:
                    pass
            elif key == "v1":
                signatures.append(val)

    if timestamp is None or not signatures:
        raise HTTPException(status_code=401, detail="Invalid signature header format")

    now = int(datetime.now(UTC).timestamp())
    if abs(now - timestamp) > tolerance_seconds:
        raise HTTPException(
            status_code=401, detail="Webhook signature timestamp expired"
        )

    signed_payload = f"{timestamp}.".encode() + raw_payload
    expected_signature = hmac.new(
        secret.encode(), signed_payload, hashlib.sha256
    ).hexdigest()

    matched = any(hmac.compare_digest(expected_signature, sig) for sig in signatures)
    if not matched:
        raise HTTPException(status_code=401, detail="Signature verification failed")

    try:
        data: dict[str, Any] = json.loads(raw_payload.decode("utf-8"))
    except Exception as e:
        raise HTTPException(status_code=400, detail="Malformed JSON payload") from e

    return data


class PaymentProvider(Protocol):
    def create_payment_intent(
        self, amount: float, currency: str, payment_id: uuid.UUID
    ) -> tuple[str, str]: ...


class StripePaymentProvider:
    """Production Stripe payment provider."""

    def create_payment_intent(
        self, amount: float, currency: str, payment_id: uuid.UUID
    ) -> tuple[str, str]:
        if not settings.STRIPE_API_KEY:
            raise ValidationError("Stripe API key not configured")
        amount_minor = round(amount * 100)
        try:
            import stripe

            stripe.api_key = settings.STRIPE_API_KEY
            pi = stripe.PaymentIntent.create(
                amount=amount_minor,
                currency=currency.lower(),
                metadata={"payment_id": str(payment_id)},
            )
            return str(pi.client_secret or ""), str(pi.id)
        except ImportError as e:
            raise ValidationError(
                "Stripe library is not installed in the environment for production Stripe."
            ) from e


class MockPaymentProvider:
    """DEVELOPMENT AND TEST ONLY mock payment provider."""

    def create_payment_intent(
        self, amount: float, currency: str, payment_id: uuid.UUID
    ) -> tuple[str, str]:
        return f"pi_mock_{payment_id}_secret_test", f"pi_mock_{payment_id}"


def get_payment_provider() -> PaymentProvider:
    if settings.ENVIRONMENT == "production":
        return StripePaymentProvider()
    return MockPaymentProvider()


class PaymentService:
    def __init__(self, db: Session):
        self.db = db
        self.consultation_service = ConsultationService(db)
        self.case_service = CaseService(db)
        self.auth_service = AuthService(db)
        self.notification_service = NotificationService(db)
        self.provider = get_payment_provider()

    def _log_audit(self, event_type: str, user_id: uuid.UUID | None, metadata: dict):
        self.auth_service.log_audit_event(
            event_type, user_id, metadata, action="payment_mutation"
        )
        self.db.commit()

    def create_payment_intent(
        self, user: User, consultation_id: uuid.UUID
    ) -> PaymentIntentResponse:
        if user.role != UserRole.CLIENT:
            raise AuthorizationError("Only clients can create payments")

        consultation = self.consultation_service._get_consultation(consultation_id)
        self.consultation_service._authorize_consultation_access(user, consultation)

        # Enforce that only the client who owns the consultation can pay
        if consultation.client.user_id != user.id and user.role != UserRole.ADMIN:
            raise AuthorizationError("Only the consultation client can create payments")

        if consultation.status not in (
            ConsultationStatus.REQUESTED,
            ConsultationStatus.ACCEPTED,
        ):
            raise ValidationError(
                f"Cannot create payment for consultation in {consultation.status.value} state"
            )

        amount = float(consultation.fee_amount)
        currency = (consultation.currency or "INR").upper()

        if currency not in ("INR", "USD", "EUR", "GBP"):
            raise ValidationError(f"Unsupported payment currency: {currency}")

        if amount <= 0:
            raise ValidationError("Consultation fee is zero, no payment required.")

        # Idempotency / Active Payment Reuse:
        # If an active payment intent already exists for this consultation, return it to prevent duplicate payments
        existing_payment = (
            self.db.query(Payment)
            .filter(
                Payment.consultation_id == consultation.id,
                Payment.status.in_([PaymentStatus.CREATED, PaymentStatus.PENDING]),
            )
            .with_for_update()
            .first()
        )

        if existing_payment:
            if (
                isinstance(self.provider, StripePaymentProvider)
                and existing_payment.provider_payment_id
            ):
                try:
                    import stripe

                    stripe.api_key = settings.STRIPE_API_KEY
                    pi = stripe.PaymentIntent.retrieve(
                        existing_payment.provider_payment_id
                    )
                    client_secret = (
                        pi.client_secret or f"pi_mock_{existing_payment.id}_secret_test"
                    )
                except Exception as e:  # noqa: BLE001
                    logger.warning(
                        f"Failed to retrieve Stripe PaymentIntent {existing_payment.provider_payment_id}: {e}"
                    )
                    client_secret = f"pi_mock_{existing_payment.id}_secret_test"
            else:
                client_secret = f"pi_mock_{existing_payment.id}_secret_test"

            return PaymentIntentResponse(
                payment_id=existing_payment.id,
                client_secret=str(client_secret),
                amount=float(existing_payment.amount),
                currency=existing_payment.currency,
            )

        payment_id = generate_uuid7()
        client_secret, provider_payment_id = self.provider.create_payment_intent(
            amount, currency, payment_id
        )

        payment = Payment(
            id=payment_id,
            consultation_id=consultation.id,
            payer_user_id=user.id,
            amount=amount,
            currency=currency,
            status=PaymentStatus.CREATED,
            provider=(
                "stripe" if isinstance(self.provider, StripePaymentProvider) else "mock"
            ),
            provider_payment_id=provider_payment_id,
        )
        self.db.add(payment)
        self.db.commit()
        self.db.refresh(payment)

        self._log_audit(
            "PAYMENT_CREATED",
            user.id,
            {
                "payment_id": str(payment.id),
                "consultation_id": str(consultation.id),
                "amount": amount,
                "currency": currency,
            },
        )

        self.notification_service.create_notification(
            user_id=user.id,
            type=NotificationType.PAYMENT_CREATED,
            title="Payment Initiated",
            message=f"Payment of {payment.currency} {payment.amount:.2f} was initiated.",
            consultation_id=consultation.id,
            metadata={"payment_id": str(payment.id)},
        )

        return PaymentIntentResponse(
            payment_id=payment.id,
            client_secret=client_secret,
            amount=float(amount),
            currency=currency,
        )

    def get_payment(self, user: User, payment_id: uuid.UUID) -> Payment:
        payment = self.db.query(Payment).filter(Payment.id == payment_id).first()
        if not payment:
            raise ResourceNotFoundError("Payment not found")

        consultation = self.consultation_service._get_consultation(
            payment.consultation_id
        )
        self.consultation_service._authorize_consultation_access(user, consultation)

        return payment

    def get_consultation_payments(
        self, user: User, consultation_id: uuid.UUID
    ) -> list[Payment]:
        consultation = self.consultation_service._get_consultation(consultation_id)
        self.consultation_service._authorize_consultation_access(user, consultation)

        return (
            self.db.query(Payment)
            .filter(Payment.consultation_id == consultation_id)
            .order_by(Payment.created_at.desc(), Payment.id.desc())
            .all()
        )

    def handle_webhook(
        self, raw_body: bytes, signature_header: str | None = None
    ) -> dict:
        secret = settings.STRIPE_WEBHOOK_SECRET
        if not secret:
            raise HTTPException(
                status_code=500, detail="STRIPE_WEBHOOK_SECRET not configured"
            )

        payload = verify_stripe_webhook_signature(
            raw_payload=raw_body,
            signature_header=signature_header,
            secret=secret,
        )

        event_id = payload.get("id")
        event_type = payload.get("type")

        self._log_audit(
            "WEBHOOK_RECEIVED",
            None,
            {"event_id": event_id, "event_type": event_type},
        )

        if not event_type:
            raise ValidationError("Missing event type in webhook payload")

        # --- DB-LEVEL WEBHOOK DEDUPLICATION ---
        webhook_rec = None
        if event_id:
            existing_webhook = (
                self.db.query(ProcessedWebhookEvent)
                .filter(
                    ProcessedWebhookEvent.event_id == str(event_id),
                    ProcessedWebhookEvent.provider == "STRIPE",
                )
                .first()
            )
            if existing_webhook and existing_webhook.status in (
                WebhookProcessingStatus.PROCESSED,
                WebhookProcessingStatus.PROCESSING,
            ):
                return {"status": "already_processed"}

            if not existing_webhook:
                try:
                    webhook_rec = ProcessedWebhookEvent(
                        id=generate_uuid7(),
                        event_id=str(event_id),
                        provider="STRIPE",
                        event_type=str(event_type),
                        status=WebhookProcessingStatus.PROCESSING,
                        payload=payload,
                        created_at=datetime.now(UTC),
                    )
                    self.db.add(webhook_rec)
                    self.db.commit()
                except Exception:
                    self.db.rollback()
                    # Concurrent delivery caught by DB-level unique constraint on event_id
                    return {"status": "already_processed"}
            else:
                webhook_rec = existing_webhook

        if event_type == "payment_intent.succeeded":
            data_object = payload.get("data", {}).get("object", {})
            provider_payment_id = data_object.get("id")
            if not provider_payment_id:
                raise ValidationError("Invalid payload structure: missing payment id")

            payment = (
                self.db.query(Payment)
                .filter(Payment.provider_payment_id == provider_payment_id)
                .with_for_update()
                .first()
            )
            if not payment:
                if webhook_rec:
                    webhook_rec.status = WebhookProcessingStatus.FAILED
                    webhook_rec.error_message = f"Payment not found for provider ID {provider_payment_id}"
                    self.db.commit()
                raise ResourceNotFoundError("Payment not found")

            # Currency validation against gateway payload
            payload_currency = data_object.get("currency")
            if payload_currency and payload_currency.upper() != payment.currency.upper():
                if webhook_rec:
                    webhook_rec.status = WebhookProcessingStatus.FAILED
                    webhook_rec.error_message = f"Currency mismatch: expected {payment.currency}, got {payload_currency}"
                    self.db.commit()
                raise ValidationError(
                    f"Currency mismatch: expected {payment.currency}, got {payload_currency.upper()}"
                )

            # Idempotency: if already processed, finalize webhook record and return immediately
            if payment.status == PaymentStatus.SUCCEEDED:
                if webhook_rec:
                    webhook_rec.status = WebhookProcessingStatus.PROCESSED
                    webhook_rec.processed_at = datetime.now(UTC)
                    webhook_rec.resource_id = provider_payment_id
                    self.db.commit()
                return {"status": "already_processed"}

            payment.status = PaymentStatus.SUCCEEDED
            consultation = payment.consultation

            if consultation:
                if consultation.status in (
                    ConsultationStatus.REQUESTED,
                    ConsultationStatus.ACCEPTED,
                ):
                    consultation.status = ConsultationStatus.PAID
                elif consultation.status not in (
                    ConsultationStatus.PAID,
                    ConsultationStatus.SCHEDULED,
                    ConsultationStatus.IN_PROGRESS,
                    ConsultationStatus.COMPLETED,
                ):
                    logger.warning(
                        "Payment %s succeeded for consultation %s in non-standard state %s",
                        payment.id,
                        consultation.id,
                        consultation.status.value,
                    )

            # Synchronize authoritative CommercialTransaction & Entitlements
            from app.models.commercial import CommercialTransaction, TransactionStatus
            from app.services.commercial_service import CommercialService

            comm_service = CommercialService(self.db)
            if consultation:
                comm_txn = (
                    self.db.query(CommercialTransaction)
                    .filter(CommercialTransaction.consultation_id == consultation.id)
                    .first()
                )
                if not comm_txn:
                    payer = self.db.query(User).filter(User.id == payment.payer_user_id).first()
                    if payer:
                        try:
                            comm_txn = comm_service.create_consultation_transaction(
                                consultation=consultation,
                                payer=payer,
                                provider="STRIPE",
                                provider_transaction_id=provider_payment_id,
                            )
                            comm_service.capture_transaction(comm_txn.id, provider_payment_id=provider_payment_id)
                        except Exception as e:
                            logger.warning("Commercial transaction creation caught race condition: %s", e)
                            comm_txn = (
                                self.db.query(CommercialTransaction)
                                .filter(CommercialTransaction.consultation_id == consultation.id)
                                .first()
                            )
                            if comm_txn and comm_txn.status != TransactionStatus.CAPTURED:
                                comm_service.capture_transaction(comm_txn.id, provider_payment_id=provider_payment_id)
                elif comm_txn.status != TransactionStatus.CAPTURED:
                    comm_service.capture_transaction(comm_txn.id, provider_payment_id=provider_payment_id)

            if webhook_rec:
                webhook_rec.status = WebhookProcessingStatus.PROCESSED
                webhook_rec.processed_at = datetime.now(UTC)
                webhook_rec.resource_id = provider_payment_id

            self.db.commit()

            # Emit case timeline event if linked
            if consultation and consultation.case_id:
                self.case_service.record_case_activity(
                    consultation.case_id,
                    payment.payer_user_id,
                    "PAYMENT_CONFIRMED",
                    "Payment was successfully processed",
                    {
                        "consultation_id": str(consultation.id),
                        "payment_id": str(payment.id),
                    },
                )

            self._log_audit(
                "PAYMENT_SUCCEEDED",
                payment.payer_user_id,
                {
                    "payment_id": str(payment.id),
                    "consultation_id": str(consultation.id) if consultation else None,
                },
            )

            if consultation:
                self.notification_service.create_notification(
                    user_id=payment.payer_user_id,
                    type=NotificationType.PAYMENT_SUCCEEDED,
                    title="Payment Successful",
                    message=f"Your payment of {payment.currency} {payment.amount:.2f} was successful.",
                    consultation_id=consultation.id,
                    metadata={"payment_id": str(payment.id)},
                    event_id=f"payment_succeeded_{payment.id}",
                )
                self.notification_service.create_notification(
                    user_id=consultation.lawyer.user_id,
                    type=NotificationType.PAYMENT_SUCCEEDED,
                    title="Consultation Payment Received",
                    message=f"Payment received for consultation: {payment.currency} {payment.amount:.2f}.",
                    consultation_id=consultation.id,
                    metadata={"payment_id": str(payment.id)},
                    event_id=f"payment_received_{payment.id}",
                )

            self._log_audit(
                "WEBHOOK_PROCESSED",
                None,
                {"event_id": event_id, "status": "success"},
            )

            return {"status": "success"}

        elif event_type == "payment_intent.payment_failed":
            data_object = payload.get("data", {}).get("object", {})
            provider_payment_id = data_object.get("id")
            if not provider_payment_id:
                raise ValidationError("Invalid payload structure: missing payment id")

            payment = (
                self.db.query(Payment)
                .filter(Payment.provider_payment_id == provider_payment_id)
                .with_for_update()
                .first()
            )
            if not payment:
                if webhook_rec:
                    webhook_rec.status = WebhookProcessingStatus.FAILED
                    webhook_rec.error_message = f"Payment not found for provider ID {provider_payment_id}"
                    self.db.commit()
                raise ResourceNotFoundError("Payment not found")

            # Out-of-order protection: terminal success cannot be overridden by late failure
            if payment.status != PaymentStatus.SUCCEEDED:
                payment.status = PaymentStatus.FAILED
                consultation = payment.consultation
                if consultation and consultation.status in (
                    ConsultationStatus.REQUESTED,
                    ConsultationStatus.ACCEPTED,
                ):
                    consultation.status = ConsultationStatus.PAYMENT_FAILED

                if webhook_rec:
                    webhook_rec.status = WebhookProcessingStatus.PROCESSED
                    webhook_rec.processed_at = datetime.now(UTC)
                    webhook_rec.resource_id = provider_payment_id

                self.db.commit()

                self._log_audit(
                    "PAYMENT_FAILED",
                    payment.payer_user_id,
                    {
                        "payment_id": str(payment.id),
                        "consultation_id": str(payment.consultation_id),
                    },
                )

                self.notification_service.create_notification(
                    user_id=payment.payer_user_id,
                    type=NotificationType.PAYMENT_FAILED,
                    title="Payment Failed",
                    message=f"Your payment of {payment.currency} {payment.amount:.2f} failed to process.",
                    consultation_id=payment.consultation_id,
                    metadata={"payment_id": str(payment.id)},
                    event_id=f"payment_failed_{payment.id}",
                )
            else:
                if webhook_rec:
                    webhook_rec.status = WebhookProcessingStatus.PROCESSED
                    webhook_rec.processed_at = datetime.now(UTC)
                    webhook_rec.resource_id = provider_payment_id
                self.db.commit()

            self._log_audit(
                "WEBHOOK_PROCESSED",
                None,
                {"event_id": event_id, "status": "failed"},
            )

            return {"status": "failed_recorded"}

        if webhook_rec:
            webhook_rec.status = WebhookProcessingStatus.PROCESSED
            webhook_rec.processed_at = datetime.now(UTC)
            self.db.commit()

        return {"status": "ignored"}

    def reprocess_stale_or_failed_webhooks(
        self,
        stale_minutes: int = 10,
        limit: int = 25,
    ) -> dict[str, Any]:
        """
        Background maintenance job: safely reprocesses webhooks stuck in PROCESSING (past stale_minutes)
        or marked as FAILED due to transient errors.
        Ensures strict idempotency:
        - If payment is already succeeded and captured, updates webhook status to PROCESSED without double-mutating domain state.
        - If payment is still pending, executes capture and consultation update.
        """
        from datetime import timedelta
        from app.models.commercial import CommercialTransaction, TransactionStatus
        from app.services.commercial_service import CommercialService

        now = datetime.now(UTC)
        cutoff = now - timedelta(minutes=stale_minutes)

        stale_events = (
            self.db.query(ProcessedWebhookEvent)
            .filter(
                or_(
                    ProcessedWebhookEvent.status == WebhookProcessingStatus.FAILED,
                    and_(
                        ProcessedWebhookEvent.status == WebhookProcessingStatus.PROCESSING,
                        ProcessedWebhookEvent.created_at <= cutoff,
                    ),
                ),
            )
            .order_by(ProcessedWebhookEvent.created_at.asc())
            .limit(limit)
            .all()
        )

        reprocessed_count = 0
        failed_count = 0

        for event in stale_events:
            try:
                payload = event.payload or {}
                event_type = event.event_type

                if event_type == "payment_intent.succeeded":
                    data_object = payload.get("data", {}).get("object", {})
                    provider_payment_id = data_object.get("id") or event.resource_id
                    if not provider_payment_id:
                        event.status = WebhookProcessingStatus.FAILED
                        event.error_message = "Payload missing provider payment id"
                        failed_count += 1
                        continue

                    payment = (
                        self.db.query(Payment)
                        .filter(Payment.provider_payment_id == provider_payment_id)
                        .first()
                    )
                    if not payment:
                        event.status = WebhookProcessingStatus.FAILED
                        event.error_message = f"Payment record not found for {provider_payment_id}"
                        failed_count += 1
                        continue

                    # Safe synchronization
                    if payment.status != PaymentStatus.SUCCEEDED:
                        payment.status = PaymentStatus.SUCCEEDED

                    consultation = payment.consultation
                    if consultation and consultation.status in (
                        ConsultationStatus.REQUESTED,
                        ConsultationStatus.ACCEPTED,
                    ):
                        consultation.status = ConsultationStatus.PAID

                    comm_service = CommercialService(self.db)
                    if consultation:
                        comm_txn = (
                            self.db.query(CommercialTransaction)
                            .filter(CommercialTransaction.consultation_id == consultation.id)
                            .first()
                        )
                        if not comm_txn:
                            payer = self.db.query(User).filter(User.id == payment.payer_user_id).first()
                            if payer:
                                try:
                                    comm_txn = comm_service.create_consultation_transaction(
                                        consultation=consultation,
                                        payer=payer,
                                        provider="STRIPE",
                                        provider_transaction_id=provider_payment_id,
                                    )
                                    comm_service.capture_transaction(comm_txn.id, provider_payment_id=provider_payment_id)
                                except Exception as e:
                                    logger.warning("Reprocess caught commercial txn race: %s", e)
                        elif comm_txn.status != TransactionStatus.CAPTURED:
                            comm_service.capture_transaction(comm_txn.id, provider_payment_id=provider_payment_id)

                    event.status = WebhookProcessingStatus.PROCESSED
                    event.processed_at = now
                    event.resource_id = provider_payment_id
                    event.error_message = None
                    reprocessed_count += 1

                else:
                    # Non-payment webhook (e.g. informational)
                    event.status = WebhookProcessingStatus.PROCESSED
                    event.processed_at = now
                    reprocessed_count += 1

            except Exception as e:  # noqa: BLE001
                logger.error("Error reprocessing webhook %s: %s", event.event_id, e)
                event.error_message = str(e)
                failed_count += 1

        if reprocessed_count or failed_count:
            self.db.commit()

        return {
            "evaluated_count": len(stale_events),
            "reprocessed_count": reprocessed_count,
            "failed_count": failed_count,
        }
