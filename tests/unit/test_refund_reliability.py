from datetime import UTC, datetime, timedelta
from decimal import Decimal
import uuid
import pytest
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import AppException
from app.core.identifiers import generate_uuid7
from app.models.commercial import (
    RefundReason,
    RefundRecord,
    RefundStatus,
    TransactionStatus,
)
from app.models.consultation import Consultation, ConsultationStatus
from app.models.user import (
    AccountStatus,
    ClientProfile,
    LawyerProfile,
    LawyerVerification,
    User,
    UserRole,
    VerificationStatus,
)
from app.domain.payments.cancellation_policy_service import CancellationPolicyService
from app.domain.payments.commercial_service import CommercialService


@pytest.fixture
def commercial_fixtures(db: Session):
    client = User(
        id=generate_uuid7(),
        email=f"client_rfd_{uuid.uuid4().hex[:6]}@example.com",
        role=UserRole.CLIENT,
        account_status=AccountStatus.ACTIVE,
    )
    db.add(client)
    db.flush()
    client_profile = ClientProfile(user_id=client.id, full_name="Refund Test Client")
    db.add(client_profile)

    lawyer = User(
        id=generate_uuid7(),
        email=f"lawyer_rfd_{uuid.uuid4().hex[:6]}@example.com",
        role=UserRole.LAWYER,
        account_status=AccountStatus.ACTIVE,
    )
    db.add(lawyer)
    db.flush()
    lawyer_profile = LawyerProfile(
        id=generate_uuid7(),
        user_id=lawyer.id,
        full_name="Refund Test Lawyer",
        consultation_fee=Decimal("3000.00"),
    )
    db.add(lawyer_profile)
    verification = LawyerVerification(
        lawyer_profile_id=lawyer_profile.id,
        enrollment_number=f"D/{uuid.uuid4().hex[:4].upper()}/2020",
        state_bar_council="DELHI",
        status=VerificationStatus.APPROVED,
    )
    db.add(verification)

    now = datetime.now(UTC)
    consultation = Consultation(
        id=generate_uuid7(),
        client_id=client_profile.id,
        lawyer_id=lawyer_profile.id,
        fee_amount=Decimal("3000.00"),
        currency="INR",
        status=ConsultationStatus.PAID,
        scheduled_at=now + timedelta(hours=24),
        duration_minutes=30,
    )
    db.add(consultation)
    db.commit()

    return {
        "client": client,
        "lawyer": lawyer,
        "consultation": consultation,
    }


def test_cumulative_partial_refunds_and_cap_enforcement(commercial_fixtures, db: Session):
    fixtures = commercial_fixtures
    service = CommercialService(db)

    txn = service.create_consultation_transaction(
        consultation=fixtures["consultation"],
        payer=fixtures["client"],
        provider="STRIPE",
        provider_transaction_id="pi_cumul_refund_test",
    )
    txn.status = TransactionStatus.CAPTURED
    db.commit()
    db.refresh(txn)

    # 1. First partial refund: ₹1000 of ₹3000
    r1 = service.execute_deterministic_refund(
        transaction_identifier=txn.id,
        reason=RefundReason.CLIENT_CANCELLATION,
        refund_amount=1000.0,
        audit_notes="1st partial refund",
    )
    assert r1.status == RefundStatus.SUCCEEDED
    assert Decimal(str(r1.amount)) == Decimal("1000.00")
    db.refresh(txn)
    assert txn.status == TransactionStatus.PARTIALLY_REFUNDED

    # 2. Second partial refund: ₹1200
    r2 = service.execute_deterministic_refund(
        transaction_identifier=txn.id,
        reason=RefundReason.CLIENT_CANCELLATION,
        refund_amount=1200.0,
        audit_notes="2nd partial refund",
    )
    assert r2.status == RefundStatus.SUCCEEDED
    assert Decimal(str(r2.amount)) == Decimal("1200.00")
    db.refresh(txn)
    assert txn.status == TransactionStatus.PARTIALLY_REFUNDED

    # 3. Attempt refund exceeding remaining balance:
    # Remaining is 3000 - 2200 = 800. Requesting 850 must be rejected!
    with pytest.raises(AppException) as exc_info:
        service.execute_deterministic_refund(
            transaction_identifier=txn.id,
            reason=RefundReason.CLIENT_CANCELLATION,
            refund_amount=850.0,
        )
    assert exc_info.value.code == "REFUND_EXCEEDS_CAPTURED_AMOUNT"

    # 4. Third refund of remaining ₹800 exactly
    r3 = service.execute_deterministic_refund(
        transaction_identifier=txn.id,
        reason=RefundReason.CLIENT_CANCELLATION,
        refund_amount=800.0,
        audit_notes="Final remaining partial refund",
    )
    assert r3.status == RefundStatus.SUCCEEDED
    db.refresh(txn)
    assert txn.status == TransactionStatus.REFUNDED

    # 5. Subsequent refund attempt on fully refunded txn must fail with TRANSACTION_ALREADY_REFUNDED
    with pytest.raises(AppException) as exc_info:
        service.execute_deterministic_refund(
            transaction_identifier=txn.id,
            reason=RefundReason.CLIENT_CANCELLATION,
            refund_amount=10.0,
        )
    assert exc_info.value.code == "TRANSACTION_ALREADY_REFUNDED"

    # 6. Total refunded records sum must equal exactly ₹3000.00
    total_refunded = (
        db.query(RefundRecord)
        .filter(RefundRecord.commercial_transaction_id == txn.id)
        .all()
    )
    assert len(total_refunded) == 3
    assert sum(Decimal(str(r.amount)) for r in total_refunded) == Decimal("3000.00")


def test_cancellation_economics_advocate_cancellation(commercial_fixtures, db: Session):
    fixtures = commercial_fixtures
    policy_service = CancellationPolicyService(db)

    result = policy_service.evaluate_cancellation_economics(
        consultation=fixtures["consultation"],
        actor=fixtures["lawyer"],
        reason="Advocate had an emergency hearing in High Court",
    )

    assert result.refund_eligible is True
    assert result.refund_percentage == Decimal("100.00")
    assert result.refund_amount == Decimal("3000.00")
    assert result.advocate_payout_eligible is False
    assert result.advocate_payout_amount == Decimal("0.00")
    assert result.reason_classification == RefundReason.ADVOCATE_CANCELLATION.value


def test_cancellation_economics_technical_failure(commercial_fixtures, db: Session):
    fixtures = commercial_fixtures
    policy_service = CancellationPolicyService(db)

    result = policy_service.evaluate_cancellation_economics(
        consultation=fixtures["consultation"],
        reason="Platform network video infrastructure failure during call setup",
    )

    assert result.refund_eligible is True
    assert result.refund_percentage == Decimal("100.00")
    assert result.refund_amount == Decimal("3000.00")
    assert result.advocate_payout_eligible is False
    assert result.reason_classification == RefundReason.PLATFORM_TECHNICAL_FAILURE.value


def test_cancellation_economics_advance_client_cancellation(commercial_fixtures, db: Session):
    fixtures = commercial_fixtures
    policy_service = CancellationPolicyService(db)

    # Cancelled well in advance (> 2h before scheduled_at)
    result = policy_service.evaluate_cancellation_economics(
        consultation=fixtures["consultation"],
        actor=fixtures["client"],
        reason="Client requested reschedule due to personal conflict",
        evaluation_time=datetime.now(UTC),
    )

    assert result.refund_eligible is True
    assert result.refund_percentage == Decimal("100.00")
    assert result.refund_amount == Decimal("3000.00")
    assert result.advocate_payout_eligible is False
    assert result.is_late_cancellation is False


def test_cancellation_economics_late_client_cancellation(commercial_fixtures, db: Session, monkeypatch):
    fixtures = commercial_fixtures
    policy_service = CancellationPolicyService(db)

    consultation = fixtures["consultation"]
    # Evaluation 30 minutes before scheduled start (late cancellation)
    eval_time = consultation.scheduled_at - timedelta(minutes=30)

    # Mode 1: AUTOMATIC_TIERED
    monkeypatch.setattr(settings, "CANCELLATION_REFUND_POLICY_MODE", "AUTOMATIC_TIERED")
    monkeypatch.setattr(settings, "CLIENT_LATE_CANCELLATION_REFUND_PERCENT", 50.0)

    res_tiered = policy_service.evaluate_cancellation_economics(
        consultation=consultation,
        actor=fixtures["client"],
        reason="Late client cancellation",
        evaluation_time=eval_time,
    )

    assert res_tiered.is_late_cancellation is True
    assert res_tiered.refund_percentage == Decimal("50.0")
    assert res_tiered.refund_amount == Decimal("1500.00")
    assert res_tiered.advocate_payout_eligible is True
    assert res_tiered.advocate_payout_amount > Decimal("0.00")

    # Mode 2: PENDING_BUSINESS_DECISION (default) -> flags manual review
    monkeypatch.setattr(settings, "CANCELLATION_REFUND_POLICY_MODE", "PENDING_BUSINESS_DECISION")
    res_review = policy_service.evaluate_cancellation_economics(
        consultation=consultation,
        actor=fixtures["client"],
        reason="Late cancellation pending policy",
        evaluation_time=eval_time,
    )
    assert res_review.requires_manual_review is True


def test_no_show_economics(commercial_fixtures, db: Session):
    fixtures = commercial_fixtures
    policy_service = CancellationPolicyService(db)
    consultation = fixtures["consultation"]

    # Advocate No-Show -> 100% refund, zero advocate payout
    adv_ns = policy_service.evaluate_no_show_economics(consultation, no_show_party="ADVOCATE")
    assert adv_ns.refund_eligible is True
    assert adv_ns.refund_amount == Decimal("3000.00")
    assert adv_ns.advocate_payout_eligible is False

    # Client No-Show -> 0% refund, advocate retains compensation
    client_ns = policy_service.evaluate_no_show_economics(consultation, no_show_party="CLIENT")
    assert client_ns.refund_eligible is False
    assert client_ns.refund_amount == Decimal("0.00")
    assert client_ns.advocate_payout_eligible is True
    assert client_ns.advocate_payout_amount > Decimal("0.00")
