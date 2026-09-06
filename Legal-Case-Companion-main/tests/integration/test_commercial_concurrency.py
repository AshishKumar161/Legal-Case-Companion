import concurrent.futures
from datetime import UTC, datetime
from decimal import Decimal
import hashlib
import hmac
import json
import uuid
import pytest
from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.core.identifiers import generate_uuid7
from app.models.commercial import (
    AdvocatePayout,
    CommercialBillingStrategy,
    CommercialTransaction,
    RefundReason,
    RefundRecord,
    RefundStatus,
    TransactionStatus,
    TransactionType,
)
from app.models.consultation import Consultation, ConsultationStatus
from app.models.payment import Payment, PaymentStatus
from app.models.user import (
    AccountStatus,
    ClientProfile,
    LawyerProfile,
    LawyerVerification,
    User,
    UserRole,
    VerificationStatus,
)
from app.models.webhook import ProcessedWebhookEvent
from app.services.commercial_service import CommercialService
from app.services.payment_service import PaymentService
from tests.conftest import TestingSessionLocal


@pytest.fixture
def test_setup(db: Session):
    # Payer
    client_user = User(
        id=generate_uuid7(),
        email=f"client_conc_{uuid.uuid4().hex[:6]}@example.com",
        role=UserRole.CLIENT,
        account_status=AccountStatus.ACTIVE,
    )
    db.add(client_user)
    db.flush()
    client_profile = ClientProfile(user_id=client_user.id, full_name="Concurrent Client")
    db.add(client_profile)

    # Payee
    lawyer_user = User(
        id=generate_uuid7(),
        email=f"lawyer_conc_{uuid.uuid4().hex[:6]}@example.com",
        role=UserRole.LAWYER,
        account_status=AccountStatus.ACTIVE,
    )
    db.add(lawyer_user)
    db.flush()
    lawyer_profile = LawyerProfile(
        id=generate_uuid7(),
        user_id=lawyer_user.id,
        full_name="Concurrent Advocate",
        consultation_fee=Decimal("2500.00"),
    )
    db.add(lawyer_profile)
    verification = LawyerVerification(
        lawyer_profile_id=lawyer_profile.id,
        enrollment_number=f"D/{uuid.uuid4().hex[:4].upper()}/2020",
        state_bar_council="DELHI",
        status=VerificationStatus.APPROVED,
    )
    db.add(verification)

    # Consultation
    consultation = Consultation(
        id=generate_uuid7(),
        client_id=client_profile.id,
        lawyer_id=lawyer_profile.id,
        fee_amount=Decimal("2500.00"),
        currency="INR",
        status=ConsultationStatus.PAID,
        scheduled_at=datetime.now(UTC),
        duration_minutes=30,
    )
    db.add(consultation)
    db.commit()

    return {
        "client": client_user,
        "lawyer": lawyer_user,
        "lawyer_profile": lawyer_profile,
        "consultation": consultation,
    }


def test_concurrent_refund_double_spend_prevention(test_setup):
    setup = test_setup
    db = TestingSessionLocal()
    try:
        service = CommercialService(db)
        txn = service.create_consultation_transaction(
            consultation=setup["consultation"],
            payer=setup["client"],
            provider="STRIPE",
            provider_transaction_id="pi_conc_refund_123",
        )
        txn.status = TransactionStatus.CAPTURED
        db.commit()
        txn_id = txn.id
    finally:
        db.close()

    def attempt_refund():
        thread_db = TestingSessionLocal()
        try:
            thread_service = CommercialService(thread_db)
            record = thread_service.execute_deterministic_refund(
                transaction_identifier=txn_id,
                reason=RefundReason.CLIENT_CANCELLATION,
                refund_amount=2500.0,
                audit_notes="Concurrent refund test attempt",
            )
            return {"status": "SUCCESS", "refund_id": record.refund_id}
        except AppException as e:
            return {"status": "FAILED", "code": e.code, "message": e.message}
        except Exception as e:
            return {"status": "ERROR", "error": str(e)}
        finally:
            thread_db.close()

    # Execute 2 refunds concurrently against the same transaction
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(attempt_refund)
        f2 = executor.submit(attempt_refund)
        res1 = f1.result()
        res2 = f2.result()

    statuses = [res1["status"], res2["status"]]
    # Exactly one refund request must succeed
    assert statuses.count("SUCCESS") == 1, f"Expected 1 success, got {statuses}: {res1}, {res2}"
    failed_res = res2 if res1["status"] == "SUCCESS" else res1
    assert failed_res["status"] in ("FAILED", "ERROR")
    if failed_res["status"] == "FAILED":
        assert failed_res["code"] in ("TRANSACTION_ALREADY_REFUNDED", "REFUND_EXCEEDS_CAPTURED_AMOUNT")
    else:
        assert any(term in failed_res["error"].lower() for term in ("locked", "database", "operationalerror", "integrity", "conflict"))

    # Verify database state
    verify_db = TestingSessionLocal()
    try:
        refunds = (
            verify_db.query(RefundRecord)
            .filter(
                RefundRecord.commercial_transaction_id == txn_id,
                RefundRecord.status == RefundStatus.SUCCEEDED,
            )
            .all()
        )
        assert len(refunds) == 1
        assert Decimal(str(refunds[0].amount)) == Decimal("2500.00")
    finally:
        verify_db.close()


def test_concurrent_payout_creation_prevention(test_setup):
    setup = test_setup
    db = TestingSessionLocal()
    try:
        service = CommercialService(db)
        txn = service.create_consultation_transaction(
            consultation=setup["consultation"],
            payer=setup["client"],
            provider="STRIPE",
            provider_transaction_id="pi_conc_payout_123",
        )
        txn.status = TransactionStatus.CAPTURED
        db.commit()
        txn_id = txn.id
        advocate_user_id = setup["lawyer"].id
    finally:
        db.close()

    def attempt_payout():
        thread_db = TestingSessionLocal()
        try:
            thread_service = CommercialService(thread_db)
            payout = thread_service.create_advocate_payout(
                advocate_user_id=advocate_user_id,
                commercial_transaction_id=txn_id,
            )
            return {"status": "SUCCESS", "payout_id": payout.payout_id}
        except AppException as e:
            return {"status": "FAILED", "code": e.code, "message": e.message}
        except Exception as e:
            return {"status": "ERROR", "error": str(e)}
        finally:
            thread_db.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(attempt_payout)
        f2 = executor.submit(attempt_payout)
        res1 = f1.result()
        res2 = f2.result()

    statuses = [res1["status"], res2["status"]]
    assert statuses.count("SUCCESS") == 1, f"Expected 1 payout success, got {statuses}: {res1}, {res2}"
    failed_res = res2 if res1["status"] == "SUCCESS" else res1
    assert failed_res["status"] in ("FAILED", "ERROR")
    if failed_res["status"] == "FAILED":
        assert failed_res["code"] == "PAYOUT_ALREADY_EXISTS"
    else:
        assert any(term in failed_res["error"].lower() for term in ("locked", "database", "operationalerror", "integrity", "conflict"))

    verify_db = TestingSessionLocal()
    try:
        payouts = (
            verify_db.query(AdvocatePayout)
            .filter(AdvocatePayout.commercial_transaction_id == txn_id)
            .all()
        )
        assert len(payouts) == 1
    finally:
        verify_db.close()


def test_concurrent_webhook_deduplication(test_setup):
    setup = test_setup
    db = TestingSessionLocal()
    try:
        # Reset consultation to REQUESTED so payment intent can be created
        consultation = db.query(Consultation).filter(Consultation.id == setup["consultation"].id).first()
        consultation.status = ConsultationStatus.REQUESTED
        db.commit()

        # Create payment intent
        payment_service = PaymentService(db)
        pay_res = payment_service.create_payment_intent(
            user=setup["client"],
            consultation_id=consultation.id,
        )
        payment = db.query(Payment).filter(Payment.id == pay_res.payment_id).first()
        payment_intent_id = payment.provider_payment_id
    finally:
        db.close()

    shared_event_id = f"evt_conc_{uuid.uuid4().hex[:10]}"
    webhook_event = {
        "id": shared_event_id,
        "type": "payment_intent.succeeded",
        "data": {
            "object": {
                "id": payment_intent_id,
                "amount": 250000,
                "currency": "inr",
                "status": "succeeded",
            }
        },
    }

    raw_body_bytes = json.dumps(webhook_event).encode("utf-8")
    ts = int(datetime.now(UTC).timestamp())
    signed_payload = f"{ts}.".encode() + raw_body_bytes
    sig = hmac.new("whsec_test_secret_123".encode(), signed_payload, hashlib.sha256).hexdigest()
    sig_header = f"t={ts},v1={sig}"

    def deliver_webhook():
        thread_db = TestingSessionLocal()
        try:
            thread_ps = PaymentService(thread_db)
            res = thread_ps.handle_webhook(raw_body=raw_body_bytes, signature_header=sig_header)
            return {"status": "SUCCESS", "res": res}
        except Exception as e:
            return {"status": "ERROR", "error": str(e)}
        finally:
            thread_db.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(deliver_webhook)
        f2 = executor.submit(deliver_webhook)
        res1 = f1.result()
        res2 = f2.result()

    assert res1["status"] == "SUCCESS", f"res1 error: {res1.get('error')}"
    assert res2["status"] == "SUCCESS", f"res2 error: {res2.get('error')}"

    # Exactly one must have already_processed or status == already_processed
    statuses = [res1["res"].get("status"), res2["res"].get("status")]
    assert "already_processed" in statuses, f"Expected already_processed in {statuses}"

    # Verify DB state
    verify_db = TestingSessionLocal()
    try:
        events = verify_db.query(ProcessedWebhookEvent).filter(ProcessedWebhookEvent.event_id == shared_event_id).all()
        assert len(events) == 1

        payment = verify_db.query(Payment).filter(Payment.provider_payment_id == payment_intent_id).first()
        assert payment.status == PaymentStatus.SUCCEEDED

        consultation = verify_db.query(Consultation).filter(Consultation.id == setup["consultation"].id).first()
        assert consultation.status == ConsultationStatus.PAID
    finally:
        verify_db.close()
