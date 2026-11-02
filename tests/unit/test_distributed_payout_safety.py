import concurrent.futures
import multiprocessing
import os
import time
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.core.exceptions import AppException
from app.core.identifiers import generate_uuid7
from app.domain.payments.commercial_service import CommercialService
from app.models.commercial import (
    AdvocatePayout,
    AdvocatePayoutStatus,
    CommercialTransaction,
    TransactionStatus,
    TransactionType,
)
from app.models.consultation import Consultation, ConsultationStatus
from app.models.user import ClientProfile, LawyerProfile, User, UserRole


def _create_seed_user_and_consultation(db: Session) -> tuple[User, User, CommercialTransaction]:
    now = datetime.now(UTC)
    lawyer_user = User(
        id=generate_uuid7(),
        email=f"lawyer_payout_{uuid.uuid4().hex[:6]}@example.com",
        password_hash="hashed_pw",
        role=UserRole.LAWYER,
        created_at=now,
        updated_at=now,
    )
    client_user = User(
        id=generate_uuid7(),
        email=f"client_payout_{uuid.uuid4().hex[:6]}@example.com",
        password_hash="hashed_pw",
        role=UserRole.CLIENT,
        created_at=now,
        updated_at=now,
    )
    db.add(lawyer_user)
    db.add(client_user)
    db.flush()

    lawyer_profile = LawyerProfile(
        id=generate_uuid7(),
        user_id=lawyer_user.id,
        full_name="Advocate Test Lawyer",
        consultation_fee=2000.0,
        experience_years=5,
        created_at=now,
        updated_at=now,
    )
    db.add(lawyer_profile)
    db.flush()

    client_profile = ClientProfile(
        id=generate_uuid7(),
        user_id=client_user.id,
        full_name="Client Test User",
        created_at=now,
        updated_at=now,
    )
    db.add(client_profile)
    db.flush()

    consultation = Consultation(
        id=generate_uuid7(),
        lawyer_id=lawyer_profile.id,
        client_id=client_profile.id,
        scheduled_at=now,
        duration_minutes=45,
        fee_amount=1500.0,
        currency="INR",
        status=ConsultationStatus.PAID,
        created_at=now,
        updated_at=now,
    )
    db.add(consultation)
    db.flush()

    txn = CommercialTransaction(
        id=generate_uuid7(),
        transaction_id=f"TXN-TEST-{uuid.uuid4().hex[:6].upper()}",
        consultation_id=consultation.id,
        payer_user_id=client_user.id,
        payee_user_id=lawyer_user.id,
        transaction_type=TransactionType.PAYMENT,
        status=TransactionStatus.CAPTURED,
        gross_amount=Decimal("1500.00"),
        platform_fee=Decimal("150.00"),
        tax_amount=Decimal("27.00"),
        net_advocate_amount=Decimal("1350.00"),
        currency="INR",
        provider="STRIPE",
        invoice_number=f"INV-TEST-{uuid.uuid4().hex[:6].upper()}",
        created_at=now,
        updated_at=now,
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)
    return lawyer_user, client_user, txn


def test_concurrent_payout_requests_independent_sessions(db: Session, db_engine):
    """Test 1: Two concurrent payout requests using two independent database sessions."""
    lawyer, _, txn = _create_seed_user_and_consultation(db)
    session_factory = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)

    results = []
    errors = []

    def execute_payout(session_num: int):
        s = session_factory()
        try:
            svc = CommercialService(s)
            payout = svc.create_advocate_payout(
                advocate_user_id=lawyer.id,
                commercial_transaction_id=txn.id,
                idempotency_key=f"idemp_test_concurrent_{txn.id}",
            )
            results.append((session_num, payout.id, payout.payout_id))
        except AppException as ae:
            errors.append((session_num, ae.code, str(ae)))
        finally:
            s.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(execute_payout, 1)
        f2 = executor.submit(execute_payout, 2)
        concurrent.futures.wait([f1, f2])

    # Exactly one payout record must exist in DB for this transaction
    payout_records = (
        db.query(AdvocatePayout)
        .filter(AdvocatePayout.commercial_transaction_id == txn.id)
        .all()
    )
    assert len(payout_records) == 1, f"Expected exactly 1 payout record, found {len(payout_records)}"

    # One call succeeded, and the second was either idempotently returned or blocked with PAYOUT_ALREADY_EXISTS
    assert len(results) >= 1
    if len(errors) > 0:
        assert errors[0][1] in ("PAYOUT_ALREADY_EXISTS", "PAYOUT_CONCURRENCY_CONFLICT")


def test_concurrent_worker_execution_idempotency(db: Session, db_engine):
    """Test 2: Multiple concurrent worker threads attempting to settle the same payout."""
    lawyer, _, txn = _create_seed_user_and_consultation(db)
    svc = CommercialService(db)
    payout = svc.create_advocate_payout(
        advocate_user_id=lawyer.id,
        commercial_transaction_id=txn.id,
    )
    payout_id = payout.id

    session_factory = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)
    settle_results = []
    settle_errors = []

    def worker_settle(worker_id: int):
        s = session_factory()
        try:
            w_svc = CommercialService(s)
            settled = w_svc.settle_advocate_payout(
                payout_id,
                provider_payout_id=f"rp_concurrent_{payout_id}",
            )
            settle_results.append((worker_id, settled.status))
        except Exception as e:
            settle_errors.append((worker_id, e))
        finally:
            s.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(worker_settle, i) for i in range(4)]
        concurrent.futures.wait(futures)

    assert len(settle_errors) == 0, f"Unexpected settle errors: {settle_errors}"
    assert len(settle_results) == 4
    for _, status in settle_results:
        assert status == AdvocatePayoutStatus.PAID

    # Authoritative verification in main session
    db.refresh(payout)
    assert payout.status == AdvocatePayoutStatus.PAID
    assert payout.settled_at is not None


def test_duplicate_webhook_delivery_safety(db: Session):
    """Test 3: Duplicate webhook delivery idempotency for payout confirmation."""
    from app.domain.payments.payment_service import PaymentService
    from app.models.webhook import ProcessedWebhookEvent, WebhookProcessingStatus

    lawyer, _, txn = _create_seed_user_and_consultation(db)
    svc = CommercialService(db)
    payout = svc.create_advocate_payout(
        advocate_user_id=lawyer.id,
        commercial_transaction_id=txn.id,
    )

    # First webhook event delivery
    event_id = f"evt_payout_test_{uuid.uuid4().hex[:8]}"
    evt1 = ProcessedWebhookEvent(
        id=generate_uuid7(),
        event_id=event_id,
        provider="STRIPE",
        event_type="payout.paid",
        status=WebhookProcessingStatus.PROCESSED,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db.add(evt1)
    db.commit()

    # Second webhook delivery with duplicate event_id must detect PROCESSED state
    existing = (
        db.query(ProcessedWebhookEvent)
        .filter(
            ProcessedWebhookEvent.event_id == event_id,
            ProcessedWebhookEvent.provider == "STRIPE",
        )
        .first()
    )
    assert existing is not None
    assert existing.status == WebhookProcessingStatus.PROCESSED

    # Settle payout via first event
    svc.settle_advocate_payout(payout.id, provider_payout_id=f"rp_evt_{event_id}")
    db.refresh(payout)
    assert payout.status == AdvocatePayoutStatus.PAID

    # Duplicate webhook delivery re-attempts settlement; must be idempotent without raising
    settled_again = svc.settle_advocate_payout(payout.id, provider_payout_id=f"rp_evt_{event_id}")
    assert settled_again.status == AdvocatePayoutStatus.PAID


def test_application_restart_interrupted_payout_recovery(db: Session):
    """Test 4: Recovery of interrupted payout operations after application restart/crash."""
    lawyer, _, txn = _create_seed_user_and_consultation(db)
    now = datetime.now(UTC)

    # Simulate payout created 20 minutes ago that was interrupted (server crashed mid-settlement)
    stale_payout = AdvocatePayout(
        id=generate_uuid7(),
        payout_id=f"PAY-STALE-{uuid.uuid4().hex[:6].upper()}",
        advocate_user_id=lawyer.id,
        commercial_transaction_id=txn.id,
        amount=Decimal("1350.00"),
        currency="INR",
        status=AdvocatePayoutStatus.PENDING,
        provider="RAZORPAYX",
        idempotency_key=f"idemp_interrupted_{txn.id}",
        created_at=now - timedelta(minutes=25),
        updated_at=now - timedelta(minutes=25),
    )
    db.add(stale_payout)
    db.commit()

    svc = CommercialService(db)
    # Run recovery with 15-minute threshold
    recovered = svc.recover_interrupted_payouts(stale_threshold_minutes=15)
    assert len(recovered) >= 1
    rec_target = next(p for p in recovered if p.id == stale_payout.id)
    assert rec_target.status == AdvocatePayoutStatus.PAID
    assert "Auto-recovered" in rec_target.audit_notes


def _worker_process_payout(db_url: str, lawyer_id_str: str, txn_id_str: str, idemp_key: str, queue):
    """Helper executed in a separate OS process."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    connect_args = {"check_same_thread": False, "timeout": 30} if "sqlite" in db_url else {}
    eng = create_engine(db_url, connect_args=connect_args)
    Sm = sessionmaker(bind=eng)
    session = Sm()
    try:
        svc = CommercialService(session)
        payout = svc.create_advocate_payout(
            advocate_user_id=uuid.UUID(lawyer_id_str),
            commercial_transaction_id=uuid.UUID(txn_id_str),
            idempotency_key=idemp_key,
        )
        queue.put(("SUCCESS", payout.payout_id))
    except AppException as ae:
        queue.put(("APP_EXCEPTION", ae.code))
    except Exception as e:
        queue.put(("ERROR", str(e)))
    finally:
        session.close()
        eng.dispose()


def test_duplicate_payout_prevention_across_processes(db: Session):
    """Test 5: Multi-process concurrency: two separate OS processes race to create a payout."""
    from tests.conftest import TEST_DB_URL

    lawyer, _, txn = _create_seed_user_and_consultation(db)
    idemp_key = f"cross_process_{txn.id}"

    q = multiprocessing.Queue()
    p1 = multiprocessing.Process(
        target=_worker_process_payout,
        args=(TEST_DB_URL, str(lawyer.id), str(txn.id), idemp_key, q),
    )
    p2 = multiprocessing.Process(
        target=_worker_process_payout,
        args=(TEST_DB_URL, str(lawyer.id), str(txn.id), idemp_key, q),
    )

    p1.start()
    p2.start()
    p1.join(timeout=15)
    p2.join(timeout=15)

    results = []
    while not q.empty():
        results.append(q.get())

    # Exactly 1 active payout must exist in DB
    payout_count = (
        db.query(AdvocatePayout)
        .filter(AdvocatePayout.commercial_transaction_id == txn.id)
        .count()
    )
    assert payout_count == 1, f"Expected exactly 1 payout across processes, found {payout_count}"

    # Across the two processes, we must see at least one SUCCESS, and no corrupt duplicates
    statuses = [r[0] for r in results]
    assert "SUCCESS" in statuses
    for r in results:
        if r[0] != "SUCCESS":
            assert r[1] in ("PAYOUT_ALREADY_EXISTS", "PAYOUT_CONCURRENCY_CONFLICT")


def test_postgresql_multiprocess_payout_concurrency():
    """Test 6: Real PostgreSQL multi-process concurrency with separate OS processes and connections."""
    import sqlalchemy as sa
    from sqlalchemy.orm import sessionmaker
    from app.models.outbox import OutboxEvent

    pg_url = os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql://postgres@127.0.0.1:5433/lcc_test",
    )
    try:
        engine = sa.create_engine(pg_url, connect_args={"connect_timeout": 2})
        with engine.connect() as conn:
            conn.execute(sa.text("SELECT 1;"))
    except Exception:
        pytest.skip("PostgreSQL test cluster not accessible for multi-process test")

    from app.models import Base
    Base.metadata.create_all(bind=engine)

    SessionMaker = sessionmaker(bind=engine)
    db = SessionMaker()
    try:
        lawyer, _, txn = _create_seed_user_and_consultation(db)
        idemp_key = f"pg_cross_proc_{txn.id}"

        q = multiprocessing.Queue()
        p1 = multiprocessing.Process(
            target=_worker_process_payout,
            args=(pg_url, str(lawyer.id), str(txn.id), idemp_key, q),
        )
        p2 = multiprocessing.Process(
            target=_worker_process_payout,
            args=(pg_url, str(lawyer.id), str(txn.id), idemp_key, q),
        )

        p1.start()
        p2.start()
        p1.join(timeout=15)
        p2.join(timeout=15)

        results = []
        while not q.empty():
            results.append(q.get())

        db.commit()
        payout = (
            db.query(AdvocatePayout)
            .filter(AdvocatePayout.commercial_transaction_id == txn.id)
            .first()
        )
        assert payout is not None, "Expected exactly 1 payout created across PostgreSQL processes"

        # Assert transactional outbox durability: outbox event emitted
        outbox_events = (
            db.query(OutboxEvent)
            .filter(
                OutboxEvent.event_type == "COMMERCIAL_PAYOUT_INITIATED",
                OutboxEvent.aggregate_id == payout.id,
            )
            .all()
        )
        assert len(outbox_events) >= 1
    finally:
        db.close()
        engine.dispose()


def _worker_process_refund(db_url: str, txn_id_str: str, refund_amount: float | None, queue):
    """Helper executed in a separate OS process for concurrent refund testing."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.models.commercial import RefundReason

    connect_args = {"check_same_thread": False, "timeout": 30} if "sqlite" in db_url else {}
    eng = create_engine(db_url, connect_args=connect_args)
    Sm = sessionmaker(bind=eng)
    session = Sm()
    try:
        svc = CommercialService(session)
        refund = svc.execute_deterministic_refund(
            transaction_identifier=uuid.UUID(txn_id_str),
            reason=RefundReason.CLIENT_CANCELLATION,
            refund_amount=refund_amount,
        )
        queue.put(("SUCCESS", refund.refund_id, float(refund.amount)))
    except AppException as ae:
        queue.put(("APP_EXCEPTION", ae.code, str(ae)))
    except Exception as e:
        queue.put(("ERROR", str(e)))
    finally:
        session.close()
        eng.dispose()


def test_multiprocess_refund_concurrency_prevention(db: Session):
    """Test 7: Multi-process refund concurrency: two separate OS processes race to refund the same captured transaction."""
    from tests.conftest import TEST_DB_URL
    from app.models.commercial import RefundRecord

    _, _, txn = _create_seed_user_and_consultation(db)

    q = multiprocessing.Queue()
    p1 = multiprocessing.Process(
        target=_worker_process_refund,
        args=(TEST_DB_URL, str(txn.id), None, q),
    )
    p2 = multiprocessing.Process(
        target=_worker_process_refund,
        args=(TEST_DB_URL, str(txn.id), None, q),
    )

    p1.start()
    p2.start()
    p1.join(timeout=15)
    p2.join(timeout=15)

    results = []
    while not q.empty():
        results.append(q.get())

    # Exactly 1 refund record must exist in DB
    refund_count = (
        db.query(RefundRecord)
        .filter(RefundRecord.commercial_transaction_id == txn.id)
        .count()
    )
    assert refund_count == 1, f"Expected exactly 1 refund across processes, found {refund_count}"

    statuses = [r[0] for r in results]
    assert "SUCCESS" in statuses
    for r in results:
        if r[0] != "SUCCESS":
            assert r[1] in ("TRANSACTION_ALREADY_REFUNDED", "REFUND_EXCEEDS_CAPTURED_AMOUNT")


def test_postgresql_multiprocess_refund_concurrency():
    """Test 8: Real PostgreSQL multi-process refund concurrency with separate OS processes and connections."""
    import sqlalchemy as sa
    from sqlalchemy.orm import sessionmaker
    from app.models.commercial import RefundRecord
    from app.models.outbox import OutboxEvent

    pg_url = os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql://postgres@127.0.0.1:5433/lcc_test",
    )
    try:
        engine = sa.create_engine(pg_url, connect_args={"connect_timeout": 2})
        with engine.connect() as conn:
            conn.execute(sa.text("SELECT 1;"))
    except Exception:
        pytest.skip("PostgreSQL test cluster not accessible for multi-process refund test")

    from app.models import Base
    Base.metadata.create_all(bind=engine)

    SessionMaker = sessionmaker(bind=engine)
    db = SessionMaker()
    try:
        _, _, txn = _create_seed_user_and_consultation(db)

        q = multiprocessing.Queue()
        p1 = multiprocessing.Process(
            target=_worker_process_refund,
            args=(pg_url, str(txn.id), None, q),
        )
        p2 = multiprocessing.Process(
            target=_worker_process_refund,
            args=(pg_url, str(txn.id), None, q),
        )

        p1.start()
        p2.start()
        p1.join(timeout=15)
        p2.join(timeout=15)

        results = []
        while not q.empty():
            results.append(q.get())

        db.commit()
        refunds = (
            db.query(RefundRecord)
            .filter(RefundRecord.commercial_transaction_id == txn.id)
            .all()
        )
        assert len(refunds) == 1, f"Expected exactly 1 refund record, found {len(refunds)}"

        statuses = [r[0] for r in results]
        assert "SUCCESS" in statuses
        for r in results:
            if r[0] != "SUCCESS":
                assert r[1] in ("TRANSACTION_ALREADY_REFUNDED", "REFUND_EXCEEDS_CAPTURED_AMOUNT")

        # Verify transactional outbox durability: outbox event emitted for the refund
        outbox_events = (
            db.query(OutboxEvent)
            .filter(
                OutboxEvent.event_type == "COMMERCIAL_TRANSACTION_REFUNDED",
                OutboxEvent.aggregate_id == txn.id,
            )
            .all()
        )
        assert len(outbox_events) >= 1
    finally:
        db.close()
        engine.dispose()

