import datetime
import uuid
import pytest
from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.models.commercial import (
    AdvocatePayout,
    AdvocatePayoutStatus,
    CommercialBillingStrategy,
    CommercialTransaction,
    RefundReason,
    RefundRecord,
    RefundStatus,
    TransactionStatus,
    TransactionType,
)
from app.models.consultation import Consultation, ConsultationStatus
from app.models.support import (
    SupportCase,
    SupportCaseMessage,
    SupportCaseSeverity,
    SupportCaseStatus,
)
from app.models.user import (
    AccountStatus,
    ClientProfile,
    LawyerProfile,
    LawyerVerification,
    User,
    UserRole,
    VerificationStatus,
)
from app.domain.verification.cohort_governance_service import (
    Cohort2Stage,
    CohortGovernanceService,
    SourceOfTruthTag,
)
from app.domain.payments.commercial_service import CommercialService
from app.domain.users.support_service import SupportService
from app.domain.payments.unit_economics_service import UnitEconomicsService


@pytest.fixture
def test_client(db: Session) -> User:
    user = User(
        email=f"client_p10_{uuid.uuid4().hex[:6]}@example.com",
        role=UserRole.CLIENT,
        account_status=AccountStatus.ACTIVE,
    )
    db.add(user)
    db.flush()

    profile = ClientProfile(
        user_id=user.id,
        full_name="Priya Sharma",
        location="New Delhi",
    )
    db.add(profile)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def test_advocate(db: Session) -> User:
    user = User(
        email=f"advocate_p10_{uuid.uuid4().hex[:6]}@example.com",
        role=UserRole.LAWYER,
        account_status=AccountStatus.ACTIVE,
    )
    db.add(user)
    db.flush()

    profile = LawyerProfile(
        user_id=user.id,
        full_name="Adv. Sunita Narain",
        practice_areas=["Civil", "Consumer Protection"],
        languages=["English", "Hindi"],
        location="New Delhi",
        court_jurisdictions=["High Court of Delhi"],
        consultation_fee=1500.0,
        experience_years=8,
    )
    db.add(profile)
    db.flush()

    verification = LawyerVerification(
        lawyer_profile_id=profile.id,
        enrollment_number=f"D/{uuid.uuid4().hex[:4].upper()}/2018",
        state_bar_council="Bar Council of Delhi",
        status=VerificationStatus.APPROVED,
        reviewed_at=datetime.datetime.now(datetime.UTC),
    )
    db.add(verification)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def test_admin(db: Session) -> User:
    user = User(
        email=f"admin_p10_{uuid.uuid4().hex[:6]}@example.com",
        role=UserRole.ADMIN,
        account_status=AccountStatus.ACTIVE,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ==============================================================================
# RULE 1: SOURCE-OF-TRUTH RULE & DATA METADATA CLASSIFICATION
# ==============================================================================
def test_source_of_truth_classification_integrity(db: Session):
    """Rule 1: All analytical metrics must expose source, cohort size, and classification."""
    gov_service = CohortGovernanceService(db)
    cohort_status = gov_service.get_cohort_status()
    assert cohort_status["source_of_truth"] == SourceOfTruthTag.REAL_USER_DATA.value
    assert "current_stage_targets" in cohort_status
    assert cohort_status["current_stage_targets"]["max_advocates"] >= 10

    unit_econ_service = UnitEconomicsService(db)
    unit_econ = unit_econ_service.calculate_unit_economics()
    assert unit_econ["source_of_truth"] in [SourceOfTruthTag.REAL_USER_DATA.value, SourceOfTruthTag.ESTIMATED_DATA.value]
    assert "unit_economics_per_consultation" in unit_econ


# ==============================================================================
# RULE 2: COHORT 2 STAGED ROLLOUT GATING
# ==============================================================================
def test_cohort_2_staged_rollout_gates(db: Session):
    """Rule 2: Staged rollout gates (Phase A -> B -> C -> D) with deterministic verification."""
    gov_service = CohortGovernanceService(db)
    status = gov_service.get_cohort_status()
    assert status["current_stage"] in [s.value for s in Cohort2Stage]
    assert "gates" in status

    # Advance stage to Phase B
    res_b = gov_service.advance_stage(Cohort2Stage.PHASE_B_OPERATIONAL_REVIEW)
    assert res_b["current_stage"] == Cohort2Stage.PHASE_B_OPERATIONAL_REVIEW.value


# ==============================================================================
# RULE 3 & 4: ADVOCATE SUPPLY & DETERMINISTIC QUALITY
# ==============================================================================
def test_advocate_supply_deterministic_quality(db: Session, test_advocate: User):
    """Rule 3 & 4: Operational advocate supply tracking without opaque ML ranking."""
    gov_service = CohortGovernanceService(db)
    roster = gov_service.get_advocate_supply_roster()
    assert roster["source_of_truth"] == SourceOfTruthTag.REAL_USER_DATA.value
    assert roster["total_advocates"] >= 1

    adv_entry = next((a for a in roster["advocates"] if a["user_id"] == str(test_advocate.id)), None)
    assert adv_entry is not None
    assert adv_entry["operational_state"] in ["VERIFIED", "ACTIVE"]
    assert "quality_indicators" in adv_entry
    assert adv_entry["quality_indicators"]["verification"] in ["VERIFIED", "PENDING"]
    assert "ml_ranking" not in adv_entry


# ==============================================================================
# RULE 5: MARKETPLACE BALANCE
# ==============================================================================
def test_marketplace_category_balance(db: Session, test_advocate: User):
    """Rule 5: Measure demand vs advocate supply per category to identify undersupplied segments."""
    gov_service = CohortGovernanceService(db)
    balance = gov_service.get_marketplace_balance()
    assert balance["source_of_truth"] == SourceOfTruthTag.REAL_USER_DATA.value
    assert len(balance["categories"]) > 0

    civil_cat = next((c for c in balance["categories"] if "civil" in c["category"].lower()), None)
    assert civil_cat is not None
    assert civil_cat["advocate_supply_count"] >= 1
    assert civil_cat["market_health"] in ["BALANCED", "UNDER_SUPPLIED", "OVER_SUPPLIED", "HIGH_DEMAND"]


# ==============================================================================
# RULES 11, 12, 13: COMMERCIAL MODEL, SETTLEMENT & ADVOCATE PAYOUTS
# ==============================================================================
def test_commercial_settlement_reconciliation_and_double_payout_guard(
    db: Session, test_client: User, test_advocate: User
):
    """Rule 11, 12, 13: Financial reconciliation, double-payout guards, and idempotent payouts."""
    commercial_service = CommercialService(db)

    # 1. Create a consultation and completed commercial transaction
    consultation = Consultation(
        client_id=test_client.client_profile.id,
        lawyer_id=test_advocate.lawyer_profile.id,
        scheduled_at=datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=1),
        duration_minutes=45,
        fee_amount=2000.0,
        currency="INR",
        status=ConsultationStatus.SCHEDULED,
    )
    db.add(consultation)
    db.commit()
    db.refresh(consultation)

    tx = CommercialTransaction(
        transaction_id=f"TXN-{uuid.uuid4().hex[:12].upper()}",
        consultation_id=consultation.id,
        payer_user_id=test_client.id,
        payee_user_id=test_advocate.id,
        transaction_type=TransactionType.PAYMENT,
        status=TransactionStatus.CAPTURED,
        gross_amount=2000.0,
        platform_fee=400.0,
        tax_amount=360.0,
        net_advocate_amount=1600.0,
        currency="INR",
        provider="RAZORPAY",
        provider_transaction_id=f"pay_p10_{uuid.uuid4().hex[:8]}",
        invoice_number=f"INV-{uuid.uuid4().hex[:8].upper()}",
        reconciliation_status="SETTLED",
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)

    # 2. Verify Settlement Reconciliation
    reconciliation = commercial_service.get_settlement_reconciliation()
    assert reconciliation["source_of_truth"] == SourceOfTruthTag.REAL_USER_DATA.value
    assert reconciliation["transaction_count"] >= 1
    assert reconciliation["gross_consultation_inr"] >= 2000.0
    assert reconciliation["advocate_share_inr"] >= 1600.0
    assert reconciliation["tax_gst_inr"] >= 360.0

    # 3. Create advocate payout
    payout = commercial_service.create_advocate_payout(
        advocate_user_id=test_advocate.id,
        commercial_transaction_id=tx.id,
    )
    assert payout.status == AdvocatePayoutStatus.PENDING
    assert float(payout.amount) == 1600.0
    assert payout.advocate_user_id == test_advocate.id

    # 4. Attempt double payout creation -> Must raise AppException (400)
    with pytest.raises(AppException) as exc_info:
        commercial_service.create_advocate_payout(
            advocate_user_id=test_advocate.id,
            commercial_transaction_id=tx.id,
        )
    assert exc_info.value.status_code == 400
    assert "already exists" in exc_info.value.message.lower()

    # 5. Authoritatively settle the payout
    settled = commercial_service.settle_advocate_payout(
        payout_identifier=payout.id,
        provider_payout_id=f"UTR_P10_{uuid.uuid4().hex[:8]}",
    )
    assert settled.status == AdvocatePayoutStatus.PAID
    assert settled.settled_at is not None

    # 6. Settling again is idempotent
    settled_again = commercial_service.settle_advocate_payout(
        payout_identifier=payout.id,
        provider_payout_id="ANOTHER_REF",
    )
    assert settled_again.status == AdvocatePayoutStatus.PAID


# ==============================================================================
# RULE 14: DETERMINISTIC REFUNDS
# ==============================================================================
def test_deterministic_refund_and_double_refund_guard(
    db: Session, test_client: User, test_advocate: User
):
    """Rule 14: Server-authoritative deterministic refund rules with double-refund protection."""
    commercial_service = CommercialService(db)

    consultation = Consultation(
        client_id=test_client.client_profile.id,
        lawyer_id=test_advocate.lawyer_profile.id,
        scheduled_at=datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=2),
        duration_minutes=30,
        fee_amount=1500.0,
        currency="INR",
        status=ConsultationStatus.SCHEDULED,
    )
    db.add(consultation)
    db.commit()
    db.refresh(consultation)

    tx = CommercialTransaction(
        transaction_id=f"TXN-{uuid.uuid4().hex[:12].upper()}",
        consultation_id=consultation.id,
        payer_user_id=test_client.id,
        payee_user_id=test_advocate.id,
        transaction_type=TransactionType.PAYMENT,
        status=TransactionStatus.CAPTURED,
        gross_amount=1500.0,
        platform_fee=300.0,
        tax_amount=270.0,
        net_advocate_amount=1200.0,
        currency="INR",
        provider="RAZORPAY",
        provider_transaction_id=f"pay_ref_{uuid.uuid4().hex[:8]}",
        invoice_number=f"INV-{uuid.uuid4().hex[:8].upper()}",
        reconciliation_status="SETTLED",
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)

    # Execute refund for advocate cancellation
    refund = commercial_service.execute_deterministic_refund(
        transaction_identifier=tx.id,
        reason=RefundReason.ADVOCATE_CANCELLATION,
        refund_amount=1500.0,
        audit_notes="Advocate had emergency court hearing conflict",
    )
    assert refund.status == RefundStatus.SUCCEEDED
    assert refund.reason == RefundReason.ADVOCATE_CANCELLATION
    assert float(refund.amount) == 1500.0

    # Verify transaction status changed to REFUNDED
    db.refresh(tx)
    assert tx.status == TransactionStatus.REFUNDED

    # Verify consultation was cancelled
    db.refresh(consultation)
    assert consultation.status == ConsultationStatus.CANCELLED

    # Attempt second refund on the same transaction -> Must raise AppException (400)
    with pytest.raises(AppException) as exc_info:
        commercial_service.execute_deterministic_refund(
            transaction_identifier=tx.id,
            reason=RefundReason.DUPLICATE_PAYMENT,
            audit_notes="Second attempt",
        )
    assert exc_info.value.status_code == 400
    assert "already been fully refunded" in exc_info.value.message.lower()


# ==============================================================================
# RULES 16 & 17: SUPPORT WORKFLOW & ZERO-TRUST INTERNAL NOTE ISOLATION
# ==============================================================================
def test_support_messages_and_zero_trust_privacy_isolation(
    db: Session, test_client: User, test_admin: User
):
    """Rule 16 & 23: Two-way support messages with strict privacy isolation for internal notes."""
    support_service = SupportService(db)

    case = support_service.create_case(
        category="BILLING_PAYMENTS",
        subject="GST invoice breakdown query",
        description="I have a question regarding my GST invoice breakdown.",
        user=test_client,
        severity=SupportCaseSeverity.SEV3_MEDIUM,
    )

    # Client sends a message
    msg1 = support_service.add_case_message(
        identifier=case.id,
        message_text="Can you provide the SAC 9982 tax breakdown on my receipt?",
        sender=test_client,
        is_internal_note=False,
    )
    assert msg1.id is not None
    assert not msg1.is_internal_note

    # Admin adds an internal note (for support operators only)
    note = support_service.add_case_message(
        identifier=case.id,
        message_text="Internal Note: Verified payment gateway invoice #9921.",
        sender=test_admin,
        is_internal_note=True,
    )
    assert note.is_internal_note

    # Admin sends customer communication
    msg2 = support_service.add_case_message(
        identifier=case.id,
        message_text="Your official tax receipt has been generated with 18% GST.",
        sender=test_admin,
        is_internal_note=False,
    )
    assert not msg2.is_internal_note

    # Query messages as client -> Internal note MUST BE FILTERED OUT (Zero-trust)
    client_view = support_service.get_case_messages(identifier=case.id, current_user=test_client)
    assert len(client_view) == 2
    assert all(not m.is_internal_note for m in client_view)
    assert "Internal Note" not in [m.message_text for m in client_view]

    # Query messages as admin -> Internal note MUST BE VISIBLE
    admin_view = support_service.get_case_messages(identifier=case.id, current_user=test_admin)
    assert len(admin_view) == 3
    assert any(m.is_internal_note for m in admin_view)

    # Test enhanced analytics
    analytics = support_service.get_enhanced_support_analytics()
    assert analytics["source_of_truth"] == SourceOfTruthTag.REAL_USER_DATA.value
    assert analytics["total_tickets"] >= 1


# ==============================================================================
# RULE 25: UNIT ECONOMICS CALCULATION
# ==============================================================================
def test_unit_economics_direct_contribution_margins(db: Session):
    """Rule 25: Deterministic unit economics per consultation with direct costs and gross margin."""
    unit_econ_service = UnitEconomicsService(db)
    econ = unit_econ_service.calculate_unit_economics()
    assert econ["source_of_truth"] in [SourceOfTruthTag.REAL_USER_DATA.value, SourceOfTruthTag.ESTIMATED_DATA.value]

    unit_metrics = econ["unit_economics_per_consultation"]
    assert unit_metrics["average_gross_fee"] > 0

    costs = unit_metrics["cost_breakdown"]
    assert "payment_gateway_processing_2_pct" in costs
    assert "infrastructure_and_video_webrtc" in costs
    assert "customer_support_allocation" in costs
    assert "refund_and_chargeback_reserve_3_pct" in costs

    assert unit_metrics["gross_contribution_margin_pct"] >= 0
    assert "channel_acquisition_cost" in econ
