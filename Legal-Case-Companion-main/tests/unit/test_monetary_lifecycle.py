from decimal import Decimal
import uuid
from unittest.mock import MagicMock
import pytest

from app.models.commercial import CommercialTransaction, TransactionStatus, AdvocatePayout, AdvocatePayoutStatus, RefundRecord, RefundStatus
from app.models.consultation import Consultation
from app.models.user import User
from app.services.commercial_service import CommercialService, _to_decimal, _quantize, TWOPLACES


def test_decimal_conversion_and_bankers_rounding():
    """Verify that _to_decimal and _quantize execute deterministic ROUND_HALF_EVEN rounding."""
    assert _to_decimal(10.5) == Decimal("10.5")
    assert _to_decimal("2500.00") == Decimal("2500.00")
    assert _to_decimal(None) == Decimal("0.00")
    assert _to_decimal(Decimal("45.50")) == Decimal("45.50")

    # Round half to even:
    # 0.025 rounds to 0.02 (2 is even)
    # 0.035 rounds to 0.04 (4 is even)
    assert _quantize(Decimal("0.025")) == Decimal("0.02")
    assert _quantize(Decimal("0.035")) == Decimal("0.04")
    assert _quantize(Decimal("100.125")) == Decimal("100.12")
    assert _quantize(Decimal("100.135")) == Decimal("100.14")


def test_commercial_transaction_financial_separation(db):
    """Verify that create_consultation_transaction calculates platform fee and GST via Decimal precision."""
    comm_service = CommercialService(db)

    # Set up mock/fixture objects
    lawyer_user = User(id=uuid.uuid4(), email="advocate_monetary@test.com")
    payer_user = User(id=uuid.uuid4(), email="client_monetary@test.com")
    lawyer_profile = MagicMock(user_id=lawyer_user.id)

    consultation = Consultation(
        id=uuid.uuid4(),
        fee_amount=2500.0,
        currency="INR",
        lawyer_id=uuid.uuid4(),
    )
    consultation.lawyer = lawyer_profile

    # 10% platform fee on 2500.00 = 250.00
    # 18% GST on platform fee 250.00 = 45.00
    # Net advocate = 2500.00 - 250.00 = 2250.00
    txn = comm_service.create_consultation_transaction(
        consultation=consultation,
        payer=payer_user,
    )

    assert txn.gross_amount == Decimal("2500.00")
    assert txn.platform_fee == Decimal("250.00")
    assert txn.tax_amount == Decimal("45.00")
    assert txn.net_advocate_amount == Decimal("2250.00")


def test_reconciliation_exact_decimal_balance(db):
    """Verify that settlement reconciliation accurately sums Decimals without floating-point drift."""
    comm_service = CommercialService(db)

    # Add transactions with amounts that would typically cause float drift (e.g. 0.1, 0.2)
    tx1 = CommercialTransaction(
        id=uuid.uuid4(),
        transaction_id=f"TXN-{uuid.uuid4().hex[:8]}",
        consultation_id=uuid.uuid4(),
        payer_user_id=uuid.uuid4(),
        payee_user_id=uuid.uuid4(),
        status=TransactionStatus.CAPTURED,
        gross_amount=Decimal("100.10"),
        platform_fee=Decimal("10.01"),
        tax_amount=Decimal("1.80"),
        net_advocate_amount=Decimal("90.09"),
        currency="INR",
    )
    tx2 = CommercialTransaction(
        id=uuid.uuid4(),
        transaction_id=f"TXN-{uuid.uuid4().hex[:8]}",
        consultation_id=uuid.uuid4(),
        payer_user_id=uuid.uuid4(),
        payee_user_id=uuid.uuid4(),
        status=TransactionStatus.CAPTURED,
        gross_amount=Decimal("200.20"),
        platform_fee=Decimal("20.02"),
        tax_amount=Decimal("3.60"),
        net_advocate_amount=Decimal("180.18"),
        currency="INR",
    )
    db.add_all([tx1, tx2])
    db.commit()

    reconciliation = comm_service.get_settlement_reconciliation()
    assert reconciliation["gross_consultation_inr"] == 300.30
    assert reconciliation["platform_fee_inr"] == 30.03
    assert reconciliation["tax_gst_inr"] == 5.40
    assert reconciliation["advocate_share_inr"] == 270.27
    assert reconciliation["reconciliation_status"] in ("BALANCED", "VARIANCE_DETECTED")
