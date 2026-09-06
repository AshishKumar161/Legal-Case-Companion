import uuid
import pytest
from datetime import UTC, datetime
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.models.analytics import ProductEvent, ProductEventType
from app.models.operator import OperationalPermission, UserOperatorPermission
from app.models.support import SupportCase, SupportCaseSeverity, SupportCaseStatus
from app.models.user import (
    AccountStatus,
    LawyerProfile,
    LawyerVerification,
    User,
    UserRole,
    VerificationStatus,
)


@pytest.fixture
def pilot_admin_user(db: Session) -> User:
    user = User(
        email=f"pilot_admin_{uuid.uuid4().hex[:6]}@example.com",
        role=UserRole.ADMIN,
        account_status=AccountStatus.ACTIVE,
    )
    db.add(user)
    db.flush()

    # Grant operator permissions for pilot governance and user support
    for perm in [OperationalPermission.PILOT_GOVERNANCE, OperationalPermission.USER_SUPPORT]:
        op_perm = UserOperatorPermission(
            user_id=user.id,
            permission=perm,
            granted_by_user_id=user.id,
        )
        db.add(op_perm)

    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def pilot_client_user(db: Session) -> User:
    user = User(
        email=f"pilot_litigant_{uuid.uuid4().hex[:6]}@example.com",
        role=UserRole.CLIENT,
        account_status=AccountStatus.ACTIVE,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def pilot_lawyer_user(db: Session) -> User:
    user = User(
        email=f"pilot_advocate_{uuid.uuid4().hex[:6]}@example.com",
        role=UserRole.LAWYER,
        account_status=AccountStatus.ACTIVE,
    )
    db.add(user)
    db.flush()

    profile = LawyerProfile(
        user_id=user.id,
        full_name="Adv. Vikram Malhotra",
        consultation_fee=1500,
        practice_areas=["Criminal Law & Bail", "Civil Disputes"],
        court_jurisdictions=["High Court of Delhi"],
    )
    db.add(profile)
    db.commit()
    db.refresh(user)
    return user


def test_pilot_cohort_capacity_and_geographic_scope(
    client: TestClient, pilot_admin_user: User
):
    token = create_access_token(str(pilot_admin_user.id), {"role": "ADMIN"})
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get("/api/v1/pilot/status", headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert "capacity" in data
    assert "clients" in data["capacity"]
    assert "lawyers" in data["capacity"]
    assert data["capacity"]["clients"]["max"] >= 30
    assert data["capacity"]["lawyers"]["max"] >= 10


def test_client_onboarding_intent_and_telemetry(
    client: TestClient, pilot_client_user: User, db: Session
):
    token = create_access_token(str(pilot_client_user.id), {"role": "CLIENT"})
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Log intent selected event
    intent_res = client.post(
        "/api/v1/pilot/telemetry/event",
        headers=headers,
        json={
            "event_type": "INTENT_SELECTED",
            "metadata": {"intent": "NEED_LAWYER", "jurisdiction": "delhi"},
        },
    )
    assert intent_res.status_code == 201
    assert intent_res.json()["status"] == "RECORDED"

    # 2. Log client onboarding completed event
    onboard_res = client.post(
        "/api/v1/pilot/telemetry/event",
        headers=headers,
        json={
            "event_type": "CLIENT_ONBOARDING_COMPLETED",
            "metadata": {
                "intent": "NEED_LAWYER",
                "location": "delhi",
                "language": "hi",
            },
        },
    )
    assert onboard_res.status_code == 201

    # Verify database persistence
    events = (
        db.query(ProductEvent)
        .filter(ProductEvent.user_id == pilot_client_user.id)
        .all()
    )
    assert len(events) >= 2
    types = [e.event_type for e in events]
    assert ProductEventType.INTENT_SELECTED in types
    assert ProductEventType.CLIENT_ONBOARDING_COMPLETED in types


def test_advocate_onboarding_verification_workflow(
    client: TestClient, pilot_lawyer_user: User, pilot_admin_user: User, db: Session
):
    lawyer_token = create_access_token(str(pilot_lawyer_user.id), {"role": "LAWYER"})
    lawyer_headers = {"Authorization": f"Bearer {lawyer_token}"}

    # 1. Advocate submits Bar Council verification
    submit_res = client.post(
        "/api/v1/verification/lawyer/submit",
        headers=lawyer_headers,
        json={
            "enrollment_number": "D/4321/2019",
            "state_bar_council": "Bar Council of Delhi",
        },
    )
    assert submit_res.status_code == 201
    verification_data = submit_res.json()
    verification_id = verification_data["id"]
    assert verification_data["status"] == "PENDING"

    # 2. Ensure advocate profile shows unverified initially
    db_profile = db.query(LawyerProfile).filter(LawyerProfile.user_id == pilot_lawyer_user.id).first()
    assert db_profile.verification_status in ["PENDING", "UNDER_REVIEW"]

    # 3. Admin reviews and approves verification
    admin_token = create_access_token(str(pilot_admin_user.id), {"role": "ADMIN"})
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    approve_res = client.post(
        f"/api/v1/admin/verifications/{verification_id}/approve",
        headers=admin_headers,
    )
    assert approve_res.status_code == 200
    approved_data = approve_res.json()
    assert approved_data["status"] == "APPROVED"

    # 4. Verify in DB
    verif = db.query(LawyerVerification).filter(LawyerVerification.id == uuid.UUID(verification_id)).first()
    assert verif.status == VerificationStatus.APPROVED
    assert verif.reviewed_by == pilot_admin_user.id


def test_support_ticket_submission_and_isolation(
    client: TestClient, pilot_client_user: User, pilot_lawyer_user: User, pilot_admin_user: User
):
    client_token = create_access_token(str(pilot_client_user.id), {"role": "CLIENT"})
    client_headers = {"Authorization": f"Bearer {client_token}"}

    # 1. Client creates support ticket
    create_res = client.post(
        "/api/v1/support/cases",
        headers=client_headers,
        json={
            "category": "PAYMENT_PROBLEM",
            "severity": "SEV1_CRITICAL",
            "subject": "Payment charged but consultation slot failed",
            "description": "UPI transaction deducted INR 1500 but consultation shows pending confirmation.",
            "workflow": "PILOT_SUPPORT",
        },
    )
    assert create_res.status_code == 201
    ticket = create_res.json()
    ticket_id = ticket["support_case_id"]
    assert ticket["status"] == "OPEN"
    assert ticket["severity"] == "SEV1_CRITICAL"

    # 2. Client retrieves their tickets
    list_res = client.get("/api/v1/support/cases", headers=client_headers)
    assert list_res.status_code == 200
    user_tickets = list_res.json()
    assert any(t["support_case_id"] == ticket_id for t in user_tickets)

    # 3. Unauthorized User (Lawyer) attempts to access Client's ticket by ID
    lawyer_token = create_access_token(str(pilot_lawyer_user.id), {"role": "LAWYER"})
    lawyer_headers = {"Authorization": f"Bearer {lawyer_token}"}
    unauth_res = client.get(f"/api/v1/support/cases/{ticket_id}", headers=lawyer_headers)
    assert unauth_res.status_code == 403

    # 4. Admin resolves ticket with formal resolution notes
    admin_token = create_access_token(str(pilot_admin_user.id), {"role": "ADMIN"})
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    resolve_res = client.post(
        f"/api/v1/support/cases/{ticket_id}/resolve",
        headers=admin_headers,
        json={
            "resolution_code": "PAYMENT_RECONCILED",
            "resolution_notes": "Stripe webhook verified and slot confirmed for 11:30 AM IST.",
        },
    )
    assert resolve_res.status_code == 200
    resolved_ticket = resolve_res.json()
    assert resolved_ticket["status"] == "RESOLVED"
    assert resolved_ticket["resolution_code"] == "PAYMENT_RECONCILED"


def test_privacy_preserving_telemetry_scrubber(
    client: TestClient, pilot_client_user: User, db: Session
):
    token = create_access_token(str(pilot_client_user.id), {"role": "CLIENT"})
    headers = {"Authorization": f"Bearer {token}"}

    # Attempt to pass sensitive litigation narrative and personal identity in telemetry metadata
    res = client.post(
        "/api/v1/pilot/telemetry/event",
        headers=headers,
        json={
            "event_type": "SEARCH_COMPLETED",
            "metadata": {
                "results_count": 5,
                "password": "SuperSecretPassword123!",
                "aadhaar": "1234 5678 9012",
                "pan": "ABCDE1234F",
                "narrative": "Confidential divorce and property partition details",
                "cnr": "DLHC010041202025",
                "safe_filter": "commercial_civil",
            },
        },
    )
    assert res.status_code == 201
    event_id = uuid.UUID(res.json()["event_id"])

    # Query the stored event and assert sensitive keys were scrubbed
    event = db.query(ProductEvent).filter(ProductEvent.id == event_id).first()
    assert event is not None
    meta = event.metadata_

    # Verify sensitive keys were removed
    assert "password" not in meta
    assert "aadhaar" not in meta
    assert "pan" not in meta
    assert "narrative" not in meta
    assert "cnr" not in meta

    # Safe keys are preserved
    assert meta["safe_filter"] == "commercial_civil"
    assert meta["results_count"] == 5


def test_commercial_conversion_funnel_computation(
    client: TestClient, pilot_admin_user: User, db: Session
):
    admin_token = create_access_token(str(pilot_admin_user.id), {"role": "ADMIN"})
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Seed simulated funnel progression events
    now = datetime.now(UTC)
    events = [
        # 10 Discovery events
        *[ProductEvent(event_type=ProductEventType.DISCOVERY_STARTED, timestamp=now) for _ in range(10)],
        # 8 Profile views
        *[ProductEvent(event_type=ProductEventType.PROFILE_VIEWED, timestamp=now) for _ in range(8)],
        # 5 Slot selections
        *[ProductEvent(event_type=ProductEventType.SLOT_SELECTED, timestamp=now) for _ in range(5)],
        # 4 Checkout starts
        *[ProductEvent(event_type=ProductEventType.CHECKOUT_STARTED, timestamp=now) for _ in range(4)],
        # 3 Successful payments
        *[ProductEvent(event_type=ProductEventType.PAYMENT_SUCCESS, timestamp=now) for _ in range(3)],
        # 3 Bookings
        *[ProductEvent(event_type=ProductEventType.CONSULTATION_BOOKED, timestamp=now) for _ in range(3)],
    ]
    db.add_all(events)
    db.commit()

    res = client.get("/api/v1/pilot/conversion-funnel", headers=admin_headers)
    assert res.status_code == 200
    funnel = res.json()

    assert "funnel_steps" in funnel
    assert len(funnel["funnel_steps"]) == 6
    assert funnel["overall_conversion_pct"] > 0
    assert funnel["total_discovery_events"] >= 10
    assert funnel["total_bookings"] >= 3
