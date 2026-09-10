import datetime
import uuid

import pytest
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.models.analytics import ProductEvent, ProductEventType
from app.models.case import Case, CaseParticipant, CaseStatus, ParticipantRole, ParticipantStatus
from app.models.case_collaboration import MatterRequest, MatterRequestStatus
from app.models.court_case import CourtCase, UserFollowedCase
from app.models.document import Document
from app.models.notification import Notification, NotificationType
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
from app.models.workflow import CaseDeadline, CaseHearing, DeadlineStatus, HearingStatus
from app.domain.cases.case_attention_service import CaseAttentionService
from app.domain.jobs.change_feed_service import ChangeFeedService
from app.domain.users.profile_service import ProfileService
from app.domain.notifications.reminder_service import ReminderService
from app.domain.users.support_service import SupportService
from app.domain.governance.workflow_telemetry_service import WorkflowTelemetryService


@pytest.fixture
def test_client_user(db: Session) -> User:
    user = User(
        email=f"client_{uuid.uuid4().hex[:6]}@example.com",
        role=UserRole.CLIENT,
        account_status=AccountStatus.ACTIVE,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def test_lawyer_user(db: Session) -> User:
    user = User(
        email=f"advocate_{uuid.uuid4().hex[:6]}@example.com",
        role=UserRole.LAWYER,
        account_status=AccountStatus.ACTIVE,
    )
    db.add(user)
    db.flush()

    profile = LawyerProfile(
        user_id=user.id,
        full_name="Adv. Vikramaditya Sharma",
        location="New Delhi",
        court_jurisdictions=["High Court of Delhi", "Tis Hazari District Court"],
        practice_areas=["Criminal Law", "Constitutional Law"],
        languages=["English", "Hindi"],
        consultation_fee=1500.0,
        experience_years=12,
    )
    db.add(profile)
    db.flush()

    verif = LawyerVerification(
        lawyer_profile_id=profile.id,
        enrollment_number="D/1992/2012",
        state_bar_council="Bar Council of Delhi",
        status=VerificationStatus.APPROVED,
    )
    db.add(verif)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def test_case(db: Session, test_client_user: User, test_lawyer_user: User) -> Case:
    case = Case(
        title="State of NCT of Delhi vs. Arvind & Ors.",
        description="Criminal revision matter before Delhi High Court.",
        status=CaseStatus.IN_PROGRESS,
    )
    db.add(case)
    db.flush()

    # Client participant
    client_part = CaseParticipant(
        case_id=case.id,
        user_id=test_client_user.id,
        participant_role=ParticipantRole.OWNER,
        status=ParticipantStatus.ACTIVE,
    )
    db.add(client_part)

    # Lawyer participant
    lawyer_part = CaseParticipant(
        case_id=case.id,
        user_id=test_lawyer_user.id,
        participant_role=ParticipantRole.LAWYER,
        status=ParticipantStatus.ACTIVE,
    )
    db.add(lawyer_part)

    db.commit()
    db.refresh(case)
    return case


def test_what_changed_feed_and_acknowledgment(
    db: Session, test_client_user: User, test_lawyer_user: User, test_case: Case
):
    """Verifies that ChangeFeedService detects new hearings and requests since last visit,

    and that acknowledging the changes resets the delta feed cleanly.
    """
    service = ChangeFeedService(db)

    # Initially acknowledged checkpoint set to 7 days ago
    ack = service.get_or_create_acknowledgment(test_client_user.id)
    assert ack is not None

    # 1. Create a hearing and a document request occurring after checkpoint
    now = datetime.datetime.now(datetime.UTC)
    hearing = CaseHearing(
        case_id=test_case.id,
        court_name="High Court of Delhi (Court No. 14)",
        hearing_at=now + datetime.timedelta(days=3),
        purpose="Arguments on Admission",
        status=HearingStatus.SCHEDULED,
        created_at=now,
        updated_at=now,
    )
    db.add(hearing)

    doc_request = MatterRequest(
        case_id=test_case.id,
        requesting_user_id=test_lawyer_user.id,
        request_type="DOCUMENT_UPLOAD",
        status=MatterRequestStatus.PENDING,
        title="Certified Copy of Trial Court Charge Sheet",
        description="Please provide the certified trial court charge sheet for drafting review.",
        created_at=now,
        updated_at=now,
    )
    db.add(doc_request)
    db.commit()

    # Query 'What Changed'
    feed = service.get_what_changed(test_client_user)
    assert feed["has_unacknowledged_changes"] is True
    assert feed["total_new_changes"] >= 2

    event_types = [e["event_type"] for e in feed["events"]]
    assert "HEARING_SCHEDULED" in event_types or "HEARING_DATE_CHANGED" in event_types
    assert "DOCUMENT_REQUESTED" in event_types

    # Every item links directly to its source
    for ev in feed["events"]:
        assert "source_url" in ev
        assert ev["source_url"].startswith("/")
        assert "provenance" in ev

    # 2. Acknowledge changes
    ack_res = service.acknowledge_changes(test_client_user)
    assert ack_res["status"] == "ACKNOWLEDGED"

    # Subsequent query returns zero unacknowledged changes
    subsequent_feed = service.get_what_changed(test_client_user)
    assert subsequent_feed["has_unacknowledged_changes"] is False
    assert subsequent_feed["total_new_changes"] == 0


def test_case_attention_six_dimensions_and_next_step(
    db: Session, test_client_user: User, test_case: Case
):
    """Verifies that CaseAttentionService evaluates all 6 dimensions deterministically

    and provides a NextStep recommendation with ZERO AI risk scores.
    """
    service = CaseAttentionService(db)

    # 1. Add an urgent hearing (< 48 hours)
    now = datetime.datetime.now(datetime.UTC)
    urgent_hearing = CaseHearing(
        case_id=test_case.id,
        court_name="High Court of Delhi",
        hearing_at=now + datetime.timedelta(hours=24),
        purpose="Bail Arguments",
        status=HearingStatus.SCHEDULED,
    )
    db.add(urgent_hearing)

    # 2. Add an open document request
    doc_request = MatterRequest(
        case_id=test_case.id,
        requesting_user_id=test_case.participants[1].user_id,
        request_type="DOCUMENT_UPLOAD",
        status=MatterRequestStatus.PENDING,
        title="Surety Verification Certificate",
        description="Please upload the surety verification certificate from the local tehsildar.",
    )
    db.add(doc_request)
    db.commit()

    attention = service.evaluate_case_attention(test_case.id, test_client_user)

    assert attention["case_id"] == str(test_case.id)
    dims = attention["dimensions"]

    # Verify all 6 dimensions exist
    assert "hearing" in dims
    assert "documents" in dims
    assert "tasks" in dims
    assert "court_sync" in dims
    assert "communication" in dims
    assert "payment" in dims

    # Verify deterministic states
    assert dims["hearing"]["state"] == "URGENT"
    assert dims["documents"]["state"] == "PENDING"
    assert dims["tasks"]["state"] in ("COMPLETE", "PENDING")

    # Strictly NO numerical AI risk score
    assert "risk_score" not in attention
    assert "ai_score" not in attention

    # Verify synthesized NextStep
    next_step = attention["next_step"]
    assert next_step is not None
    assert next_step["context"] in ("HEARING", "DOCUMENT", "CASE")
    assert next_step["urgency"] in ("CRITICAL", "HIGH", "MEDIUM")
    assert "action" in next_step
    assert next_step["action"]["href"].startswith("/")


def test_reminder_service_processing_and_deduplication(
    db: Session, test_client_user: User, test_case: Case
):
    """Verifies that ReminderService creates deterministic 3-part notifications

    and enforces strict deduplication.
    """
    service = ReminderService(db)

    now = datetime.datetime.now(datetime.UTC)
    hearing = CaseHearing(
        case_id=test_case.id,
        court_name="High Court of Delhi",
        hearing_at=now + datetime.timedelta(hours=12),
        purpose="Final Disposal",
        status=HearingStatus.SCHEDULED,
    )
    db.add(hearing)
    db.commit()

    # Process hearing reminders
    emitted = service.process_hearing_reminders(hours_ahead=24)
    assert len(emitted) >= 1

    # Verify the generated notification has the 3-part quality format
    notif = db.query(Notification).filter(Notification.hearing_id == hearing.id).first()
    assert notif is not None
    assert notif.type == NotificationType.HEARING_REMINDER
    assert notif.metadata_ is not None
    assert "what_happened" in notif.metadata_
    assert "why_it_matters" in notif.metadata_
    assert "what_to_do" in notif.metadata_
    assert notif.metadata_["action_url"].startswith("/")

    # Run again: deduplication must ensure 0 new notifications created
    repeat_emitted = service.process_hearing_reminders(hours_ahead=24)
    # The existing notification is returned or skipped, no duplicate created
    notif_count = (
        db.query(Notification)
        .filter(
            Notification.hearing_id == hearing.id,
            Notification.user_id == test_client_user.id,
        )
        .count()
    )
    assert notif_count == 1


def test_explainable_lawyer_discovery_match_reasons(
    db: Session, test_lawyer_user: User
):
    """Verifies that ProfileService.search_lawyers returns explainable match reasons

    without opaque AI ranking.
    """
    service = ProfileService(db)

    results = service.search_lawyers(
        court_jurisdiction="High Court of Delhi",
        practice_area="Criminal Law",
        language="Hindi",
        verified_only=True,
    )

    assert results["total"] >= 1
    lawyer = results["items"][0]

    # Verify explainable match reasons
    reasons = getattr(lawyer, "match_reasons", [])
    assert len(reasons) >= 2
    reasons_str = " ".join(reasons)
    assert "Jurisdiction" in reasons_str
    assert "Practice Area" in reasons_str
    assert "Verified Bar Council Advocate" in reasons_str


def test_client_and_advocate_retention_metrics(db: Session, test_client_user: User):
    """Verifies that WorkflowTelemetryService calculates empirical client & advocate retention metrics

    with strict privacy preservation.
    """
    telemetry = WorkflowTelemetryService(db)

    # Record privacy-preserving onboarding & viewing events
    telemetry.record_product_event(
        event_type=ProductEventType.CLIENT_ONBOARDING_COMPLETED,
        user_id=test_client_user.id,
        metadata={"client_role": "LITIGANT", "narrative": "STRIP_THIS_CONFIDENTIAL_TEXT"},
    )
    telemetry.record_product_event(
        event_type=ProductEventType.HEARING_VIEWED,
        user_id=test_client_user.id,
    )

    client_metrics = telemetry.calculate_client_retention_metrics()
    assert "day1_activation_rate_pct" in client_metrics
    assert "day7_retention_rate_pct" in client_metrics
    assert "return_after_hearing_update_pct" in client_metrics
    assert client_metrics["day1_activation_rate_pct"] > 0.0

    advocate_metrics = telemetry.calculate_advocate_retention_metrics()
    assert "total_advocates" in advocate_metrics
    assert "consultation_completion_rate_pct" in advocate_metrics
    assert "average_response_time_hours" in advocate_metrics


def test_support_analytics_and_error_to_product_loop(db: Session, test_client_user: User):
    """Verifies that SupportService calculates SLA metrics and detects recurring issues."""
    service = SupportService(db)

    # Create two payment tickets to simulate recurring friction
    for i in range(2):
        service.create_case(
            category="PAYMENT_PROBLEM",
            subject=f"UPI Payment Status Inquiry #{i}",
            description="Transaction debited but session not marked confirmed immediately.",
            user=test_client_user,
        )

    analytics = service.get_support_analytics()
    assert analytics["total_cases"] >= 2
    assert "PAYMENT_PROBLEM" in analytics["category_distribution"]
    assert analytics["first_response_hours"] <= 4.0  # within published 4-hr SLA

    # Error-to-product loop: recurring issues detected
    recurring = analytics.get("recurring_issues", [])
    assert any(r["category"] == "PAYMENT_PROBLEM" for r in recurring)
