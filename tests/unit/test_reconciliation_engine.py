from datetime import UTC, datetime, timedelta
from decimal import Decimal
import uuid
import pytest
from sqlalchemy.orm import Session

from app.core.identifiers import generate_uuid7
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
from app.models.user import (
    AccountStatus,
    ClientProfile,
    LawyerProfile,
    LawyerVerification,
    User,
    UserRole,
    VerificationStatus,
)
from app.domain.payments.commercial_service import CommercialService


@pytest.fixture
def recon_fixtures(db: Session):
    client = User(
        id=generate_uuid7(),
        email=f"client_rec_{uuid.uuid4().hex[:6]}@example.com",
        role=UserRole.CLIENT,
        account_status=AccountStatus.ACTIVE,
    )
    db.add(client)
    db.flush()
    client_profile = ClientProfile(user_id=client.id, full_name="Recon Test Client")
    db.add(client_profile)

    lawyer = User(
        id=generate_uuid7(),
        email=f"lawyer_rec_{uuid.uuid4().hex[:6]}@example.com",
        role=UserRole.LAWYER,
        account_status=AccountStatus.ACTIVE,
    )
    db.add(lawyer)
    db.flush()
    lawyer_profile = LawyerProfile(
        id=generate_uuid7(),
        user_id=lawyer.id,
        full_name="Recon Test Lawyer",
        consultation_fee=Decimal("2000.00"),
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
        fee_amount=Decimal("2000.00"),
        currency="INR",
        status=ConsultationStatus.PAID,
        scheduled_at=now + timedelta(hours=2),
        duration_minutes=30,
    )
    db.add(consultation)
    db.commit()

    return {
        "client": client,
        "lawyer": lawyer,
        "consultation": consultation,
    }


def test_reconciliation_balanced_settlement(recon_fixtures, db: Session):
    fixtures = recon_fixtures
    service = CommercialService(db)

    txn = service.create_consultation_transaction(
        consultation=fixtures["consultation"],
        payer=fixtures["client"],
        provider="STRIPE",
        provider_transaction_id="pi_rec_bal_123",
    )
    txn.status = TransactionStatus.CAPTURED
    db.commit()

    payout = service.create_advocate_payout(
        advocate_user_id=fixtures["lawyer"].id,
        commercial_transaction_id=txn.id,
    )
    service.settle_advocate_payout(payout.payout_id)
    db.commit()

    recon = service.get_settlement_reconciliation()
    assert recon["discrepancy_count"] == 0
    assert len(recon["discrepancies"]) == 0
    assert recon["total_collected"] == float(txn.gross_amount)
    assert recon["total_payouts_settled"] == float(payout.amount)


def test_reconciliation_detects_payout_on_refunded_transaction(recon_fixtures, db: Session):
    fixtures = recon_fixtures
    service = CommercialService(db)

    txn = service.create_consultation_transaction(
        consultation=fixtures["consultation"],
        payer=fixtures["client"],
        provider="STRIPE",
        provider_transaction_id="pi_rec_disc_123",
    )
    txn.status = TransactionStatus.CAPTURED
    db.commit()

    # Create & settle payout
    payout = service.create_advocate_payout(
        advocate_user_id=fixtures["lawyer"].id,
        commercial_transaction_id=txn.id,
    )
    service.settle_advocate_payout(payout.payout_id)
    db.commit()

    # Now execute refund on transaction
    service.execute_deterministic_refund(
        transaction_identifier=txn.id,
        reason=RefundReason.CLIENT_CANCELLATION,
        refund_amount=2000.0,
        audit_notes="Refund processed after payout settled",
    )
    db.commit()

    # Run reconciliation
    recon = service.get_settlement_reconciliation()
    assert recon["discrepancy_count"] >= 1
    types = [d["type"] for d in recon["discrepancies"]]
    assert "PAYOUT_ON_REFUNDED_TRANSACTION" in types
    disc = next(d for d in recon["discrepancies"] if d["type"] == "PAYOUT_ON_REFUNDED_TRANSACTION")
    assert disc["transaction_id"] == txn.transaction_id
    assert disc["severity"] == "CRITICAL"


def test_reconciliation_detects_multiple_currencies(recon_fixtures, db: Session):
    fixtures = recon_fixtures
    service = CommercialService(db)

    # 1. INR transaction
    txn1 = service.create_consultation_transaction(
        consultation=fixtures["consultation"],
        payer=fixtures["client"],
        provider="STRIPE",
        provider_transaction_id="pi_rec_curr_inr",
    )
    txn1.status = TransactionStatus.CAPTURED
    txn1.currency = "INR"

    # 2. USD transaction
    txn2 = CommercialTransaction(
        id=generate_uuid7(),
        transaction_id=service._generate_transaction_id(),
        consultation_id=fixtures["consultation"].id,
        payer_user_id=fixtures["client"].id,
        payee_user_id=fixtures["lawyer"].id,
        transaction_type=TransactionType.PAYMENT,
        status=TransactionStatus.CAPTURED,
        currency="USD",
        gross_amount=Decimal("100.00"),
        platform_fee=Decimal("10.00"),
        tax_amount=Decimal("1.80"),
        net_advocate_amount=Decimal("90.00"),
        provider="STRIPE",
        provider_transaction_id="pi_rec_curr_usd",
        invoice_number=service._generate_invoice_number(),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db.add(txn2)
    db.commit()

    recon = service.get_settlement_reconciliation()
    assert recon["discrepancy_count"] >= 1
    types = [d["type"] for d in recon["discrepancies"]]
    assert "MULTIPLE_CURRENCIES_DETECTED" in types


def test_reconciliation_uses_stored_tax_not_recalculated_18(recon_fixtures, db: Session, monkeypatch):
    """
    Verify historical reconciliation uses the stored applied tax from the transaction/snapshot,
    NOT recalculating dynamically from current configuration or a hardcoded 18%.
    """
    fixtures = recon_fixtures
    service = CommercialService(db)

    # 1. Historical transaction created under a 12% GST regime
    # Gross: 1000.00, Platform Fee: 100.00, 12% GST on platform fee = 12.00, Net Advocate: 900.00
    txn = CommercialTransaction(
        id=generate_uuid7(),
        transaction_id=service._generate_transaction_id(),
        consultation_id=fixtures["consultation"].id,
        payer_user_id=fixtures["client"].id,
        payee_user_id=fixtures["lawyer"].id,
        transaction_type=TransactionType.PAYMENT,
        status=TransactionStatus.CAPTURED,
        currency="INR",
        gross_amount=Decimal("1000.00"),
        platform_fee=Decimal("100.00"),
        tax_amount=Decimal("12.00"),  # 12% rate stored!
        net_advocate_amount=Decimal("900.00"),
        provider="STRIPE",
        provider_transaction_id="pi_rec_hist_12pct",
        invoice_number=service._generate_invoice_number(),
        metadata_={
            "financial_snapshot": {
                "gross_amount": 1000.0,
                "platform_fee": 100.0,
                "gst_rate_percent": 12.0,
                "tax_amount": 12.0,
                "net_advocate_amount": 900.0,
                "currency": "INR",
            }
        },
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db.add(txn)
    db.commit()

    # Create and settle payout to advocate
    payout = service.create_advocate_payout(
        advocate_user_id=fixtures["lawyer"].id,
        commercial_transaction_id=txn.id,
    )
    service.settle_advocate_payout(payout.payout_id)
    db.commit()

    # Now simulate future config change to 28% GST
    from app.core.config import settings
    monkeypatch.setattr(settings, "COMMERCIAL_GST_PERCENT", 28.0)

    # Historical reconciliation MUST still report exactly 12.00 tax, not 18.00 or 28.00!
    recon = service.get_settlement_reconciliation()
    assert recon["total_tax_collected"] == 12.00
    assert recon["tax_gst_inr"] == 12.00
    assert recon["total_gst_tax_collected_18"] == 12.00  # Legacy alias uses stored tax
    assert recon["platform_net_revenue_inr"] == 88.00  # 100.00 fee - 12.00 tax
    assert recon["reconciliation_variance"] == 0.00
    assert recon["reconciliation_status"] == "BALANCED"


def test_reconciliation_zero_tax_scenario(recon_fixtures, db: Session):
    """
    Verify zero-tax transactions (e.g. tax-exempt or SEZ consultations) reconcile deterministically.
    """
    fixtures = recon_fixtures
    service = CommercialService(db)

    # Gross: 1500.00, Platform Fee: 150.00, Tax: 0.00, Net Advocate: 1350.00
    txn = CommercialTransaction(
        id=generate_uuid7(),
        transaction_id=service._generate_transaction_id(),
        consultation_id=fixtures["consultation"].id,
        payer_user_id=fixtures["client"].id,
        payee_user_id=fixtures["lawyer"].id,
        transaction_type=TransactionType.PAYMENT,
        status=TransactionStatus.CAPTURED,
        currency="INR",
        gross_amount=Decimal("1500.00"),
        platform_fee=Decimal("150.00"),
        tax_amount=Decimal("0.00"),  # 0% tax
        net_advocate_amount=Decimal("1350.00"),
        provider="STRIPE",
        provider_transaction_id="pi_rec_zero_tax",
        invoice_number=service._generate_invoice_number(),
        metadata_={
            "financial_snapshot": {
                "gross_amount": 1500.0,
                "platform_fee": 150.0,
                "gst_rate_percent": 0.0,
                "tax_amount": 0.0,
                "net_advocate_amount": 1350.0,
                "currency": "INR",
            }
        },
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db.add(txn)
    db.commit()

    payout = service.create_advocate_payout(
        advocate_user_id=fixtures["lawyer"].id,
        commercial_transaction_id=txn.id,
    )
    service.settle_advocate_payout(payout.payout_id)
    db.commit()

    recon = service.get_settlement_reconciliation()
    assert recon["total_tax_collected"] == 0.00
    assert recon["platform_net_revenue_inr"] == 150.00
    assert recon["reconciliation_variance"] == 0.00
    assert recon["reconciliation_status"] == "BALANCED"


def test_reconciliation_refund_and_tax_interaction(recon_fixtures, db: Session):
    """
    Verify that when transactions are refunded, net cash retained and reconciliation balance cleanly.
    """
    fixtures = recon_fixtures
    service = CommercialService(db)

    # 1. Create transaction with standard 18% tax
    txn = service.create_consultation_transaction(
        consultation=fixtures["consultation"],
        payer=fixtures["client"],
        provider="STRIPE",
        provider_transaction_id="pi_rec_rfd_tax_123",
    )
    txn.status = TransactionStatus.CAPTURED
    db.commit()

    # 2. Execute full refund (e.g. advocate cancelled)
    service.execute_deterministic_refund(
        transaction_identifier=txn.id,
        reason=RefundReason.ADVOCATE_CANCELLATION,
        refund_amount=2000.0,
        audit_notes="Advocate cancelled consultation; 100% refunded",
    )
    db.commit()

    recon = service.get_settlement_reconciliation()
    # Fully refunded: net cash retained is 0, active platform fee is 0, variance is 0.00
    assert recon["total_refunds_processed"] == 2000.00
    assert recon["net_cash_retained"] == 0.00
    assert recon["reconciliation_variance"] == 0.00
    assert recon["reconciliation_status"] == "BALANCED"


def test_reconciliation_rounding_precision(recon_fixtures, db: Session):
    """
    Verify multi-transaction bankers rounding does not produce fractional paise drift.
    """
    fixtures = recon_fixtures
    service = CommercialService(db)

    # Create 3 transactions with fractional amounts that test bankers rounding
    amounts = [Decimal("100.125"), Decimal("100.135"), Decimal("100.145")]
    for idx, amt in enumerate(amounts):
        gross = amt.quantize(Decimal("0.01"))
        fee = (gross * Decimal("0.10")).quantize(Decimal("0.01"))
        tax = (fee * Decimal("0.18")).quantize(Decimal("0.01"))
        adv = gross - fee

        tx = CommercialTransaction(
            id=generate_uuid7(),
            transaction_id=f"TXN-RND-{idx}-{uuid.uuid4().hex[:4]}",
            consultation_id=fixtures["consultation"].id,
            payer_user_id=fixtures["client"].id,
            payee_user_id=fixtures["lawyer"].id,
            transaction_type=TransactionType.PAYMENT,
            status=TransactionStatus.CAPTURED,
            currency="INR",
            gross_amount=gross,
            platform_fee=fee,
            tax_amount=tax,
            net_advocate_amount=adv,
            provider="STRIPE",
            provider_transaction_id=f"pi_rec_rnd_{idx}",
            invoice_number=f"INV-RND-{idx}",
            metadata_={
                "financial_snapshot": {
                    "gross_amount": float(gross),
                    "platform_fee": float(fee),
                    "gst_rate_percent": 18.0,
                    "tax_amount": float(tax),
                    "net_advocate_amount": float(adv),
                    "currency": "INR",
                }
            },
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        db.add(tx)
    db.commit()

    recon = service.get_settlement_reconciliation()
    assert recon["reconciliation_variance"] == 0.00
    assert recon["reconciliation_status"] == "BALANCED"

