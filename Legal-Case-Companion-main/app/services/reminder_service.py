import datetime
import logging
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.core.identifiers import generate_uuid7
from app.models.case import Case, CaseParticipant, ParticipantStatus
from app.models.case_collaboration import MatterRequest, MatterRequestStatus
from app.models.consultation import Consultation, ConsultationStatus
from app.models.notification import Notification, NotificationType
from app.models.workflow import CaseDeadline, CaseHearing, DeadlineStatus, HearingStatus
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)


class ReminderService:
    """Processes deterministic operational reminders for:

    Hearings, Deadlines, Consultations, Document Requests, and Payments.
    Enforces user preferences and deterministic deduplication via event_id.
    Each notification answers: What happened? Why does it matter? What should I do?
    """

    def __init__(self, db: Session):
        self.db = db
        self.notification_service = NotificationService(db)

    def process_hearing_reminders(self, hours_ahead: int = 24) -> list[dict[str, Any]]:
        """Schedules deterministic reminders for hearings occurring within the specified window."""
        now = datetime.datetime.now(datetime.UTC)
        window_end = now + datetime.timedelta(hours=hours_ahead)

        hearings = (
            self.db.query(CaseHearing, Case.title)
            .join(Case, CaseHearing.case_id == Case.id)
            .filter(
                CaseHearing.deleted_at.is_(None),
                CaseHearing.status == HearingStatus.SCHEDULED,
                CaseHearing.hearing_at >= now,
                CaseHearing.hearing_at <= window_end,
            )
            .all()
        )

        created_notifications = []
        for h, case_title in hearings:
            # Notify all active participants of this case
            participants = (
                self.db.query(CaseParticipant.user_id)
                .filter(
                    CaseParticipant.case_id == h.case_id,
                    CaseParticipant.status == ParticipantStatus.ACTIVE,
                )
                .all()
            )

            time_str = h.hearing_at.strftime("%d %b %Y at %I:%M %p")
            event_dedup_id = f"reminder-hearing-{h.id}-{hours_ahead}h"

            what_happened = f"Court hearing listed on {time_str}."
            why_it_matters = f"Your matter '{case_title}' is listed before {h.court_name} for purpose: {h.purpose}. Failure to appear may result in adverse procedural orders."
            what_to_do = "Review hearing schedule and verify all case documents are ready."

            for (uid,) in participants:
                notif = self.notification_service.create_notification(
                    user_id=uid,
                    type=NotificationType.HEARING_REMINDER,
                    title=f"Hearing in {hours_ahead}h: {case_title}",
                    message=f"{what_happened} {why_it_matters}",
                    case_id=h.case_id,
                    hearing_id=h.id,
                    event_id=event_dedup_id,
                    metadata={
                        "what_happened": what_happened,
                        "why_it_matters": why_it_matters,
                        "what_to_do": what_to_do,
                        "action_url": f"/cases/{h.case_id}?tab=hearings",
                        "action_label": "View Hearing Details",
                        "hours_ahead": hours_ahead,
                        "hearing_at": h.hearing_at.isoformat(),
                    },
                )
                if notif:
                    created_notifications.append({
                        "notification_id": str(notif.id),
                        "user_id": str(uid),
                        "type": "HEARING_REMINDER",
                        "event_id": event_dedup_id,
                    })

        return created_notifications

    def process_deadline_reminders(self, hours_ahead: int = 48) -> list[dict[str, Any]]:
        """Schedules reminders for approaching statutory deadlines and compliance dates."""
        now = datetime.datetime.now(datetime.UTC)
        window_end = now + datetime.timedelta(hours=hours_ahead)

        deadlines = (
            self.db.query(CaseDeadline, Case.title)
            .join(Case, CaseDeadline.case_id == Case.id)
            .filter(
                CaseDeadline.deleted_at.is_(None),
                CaseDeadline.status.in_([DeadlineStatus.UPCOMING, DeadlineStatus.DUE]),
                CaseDeadline.deadline_at >= now,
                CaseDeadline.deadline_at <= window_end,
            )
            .all()
        )

        created_notifications = []
        for d, case_title in deadlines:
            participants = (
                self.db.query(CaseParticipant.user_id)
                .filter(
                    CaseParticipant.case_id == d.case_id,
                    CaseParticipant.status == ParticipantStatus.ACTIVE,
                )
                .all()
            )

            due_str = d.deadline_at.strftime("%d %b %Y")
            event_dedup_id = f"reminder-deadline-{d.id}-{hours_ahead}h"

            what_happened = f"Deadline '{d.title}' due on {due_str}."
            why_it_matters = f"Statutory limitation or court compliance date for '{case_title}' is approaching. Lapsed filings risk dismissal or cost penalties."
            what_to_do = "Complete required filing or submit compliance proof."

            for (uid,) in participants:
                notif = self.notification_service.create_notification(
                    user_id=uid,
                    type=NotificationType.DEADLINE_APPROACHING,
                    title=f"Deadline Approaching: {d.title}",
                    message=f"{what_happened} {why_it_matters}",
                    case_id=d.case_id,
                    deadline_id=d.id,
                    event_id=event_dedup_id,
                    metadata={
                        "what_happened": what_happened,
                        "why_it_matters": why_it_matters,
                        "what_to_do": what_to_do,
                        "action_url": f"/cases/{d.case_id}?tab=tasks",
                        "action_label": "Review Deadline",
                        "deadline_at": d.deadline_at.isoformat(),
                    },
                )
                if notif:
                    created_notifications.append({
                        "notification_id": str(notif.id),
                        "user_id": str(uid),
                        "type": "DEADLINE_APPROACHING",
                        "event_id": event_dedup_id,
                    })

        return created_notifications

    def process_consultation_reminders(self, hours_ahead: int = 2) -> list[dict[str, Any]]:
        """Schedules reminders for upcoming scheduled consultations."""
        now = datetime.datetime.now(datetime.UTC)
        window_end = now + datetime.timedelta(hours=hours_ahead)

        consultations = (
            self.db.query(Consultation)
            .filter(
                Consultation.deleted_at.is_(None),
                Consultation.status.in_([ConsultationStatus.PAID, ConsultationStatus.SCHEDULED]),
                Consultation.scheduled_at >= now,
                Consultation.scheduled_at <= window_end,
            )
            .all()
        )

        created_notifications = []
        for c in consultations:
            time_str = c.scheduled_at.strftime("%I:%M %p") if c.scheduled_at else "Upcoming"
            event_dedup_id = f"reminder-consultation-{c.id}-{hours_ahead}h"

            what_happened = f"Legal consultation scheduled for {time_str} today."
            why_it_matters = f"Your 30-minute confidential consultation session starts soon. Please test your camera and microphone."
            what_to_do = "Join the video consultation room when active."

            # Notify Client
            if c.client_user_id:
                notif_client = self.notification_service.create_notification(
                    user_id=c.client_user_id,
                    type=NotificationType.CONSULTATION_REMINDER,
                    title=f"Consultation in {hours_ahead}h: Adv. {c.lawyer_name or 'Counsel'}",
                    message=f"{what_happened} {why_it_matters}",
                    consultation_id=c.id,
                    case_id=c.case_id,
                    event_id=f"{event_dedup_id}-client",
                    metadata={
                        "what_happened": what_happened,
                        "why_it_matters": why_it_matters,
                        "what_to_do": what_to_do,
                        "action_url": f"/consultations/{c.id}/room",
                        "action_label": "Open Consultation Room",
                    },
                )
                if notif_client:
                    created_notifications.append({"notification_id": str(notif_client.id), "user_id": str(c.client_user_id)})

            # Notify Lawyer
            if c.lawyer and c.lawyer.user_id:
                notif_lawyer = self.notification_service.create_notification(
                    user_id=c.lawyer.user_id,
                    type=NotificationType.CONSULTATION_REMINDER,
                    title=f"Consultation in {hours_ahead}h: Client {c.client_name or 'Litigant'}",
                    message=f"{what_happened} Client consultation will begin on schedule.",
                    consultation_id=c.id,
                    case_id=c.case_id,
                    event_id=f"{event_dedup_id}-lawyer",
                    metadata={
                        "what_happened": what_happened,
                        "why_it_matters": "Client has paid and reserved this consultation slot.",
                        "what_to_do": "Review client matter intake brief and join room.",
                        "action_url": f"/consultations/{c.id}/room",
                        "action_label": "Join Room as Counsel",
                    },
                )
                if notif_lawyer:
                    created_notifications.append({"notification_id": str(notif_lawyer.id), "user_id": str(c.lawyer.user_id)})

        return created_notifications

    def process_all_due_reminders(self) -> dict[str, Any]:
        """Runs the deterministic reminder batch across all categories."""
        hearing_notifs = self.process_hearing_reminders(hours_ahead=24)
        deadline_notifs = self.process_deadline_reminders(hours_ahead=48)
        consultation_notifs = self.process_consultation_reminders(hours_ahead=2)

        total_emitted = len(hearing_notifs) + len(deadline_notifs) + len(consultation_notifs)
        return {
            "processed_at": datetime.datetime.now(datetime.UTC).isoformat(),
            "total_emitted": total_emitted,
            "hearings_processed": len(hearing_notifs),
            "deadlines_processed": len(deadline_notifs),
            "consultations_processed": len(consultation_notifs),
        }
