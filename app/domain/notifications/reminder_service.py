import datetime
import logging
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.core.identifiers import generate_uuid7
from app.core.locking import job_lock
from app.models.case import Case, CaseParticipant, ParticipantStatus
from app.models.case_collaboration import MatterRequest, MatterRequestStatus
from app.models.consultation import Consultation, ConsultationStatus
from app.models.notification import Notification, NotificationType
from app.models.task import CaseTask, TaskStatus
from app.models.workflow import CaseDeadline, CaseHearing, DeadlineStatus, HearingStatus
from app.domain.notifications.notification_service import NotificationService

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

            client_user_id = c.client.user_id if c.client else None
            lawyer_user_id = c.lawyer.user_id if c.lawyer else None
            lawyer_name = c.lawyer.full_name if c.lawyer and c.lawyer.full_name else "Counsel"
            client_name = c.client.full_name if c.client and c.client.full_name else "Litigant"

            # Notify Client
            if client_user_id:
                notif_client = self.notification_service.create_notification(
                    user_id=client_user_id,
                    type=NotificationType.CONSULTATION_REMINDER,
                    title=f"Consultation in {hours_ahead}h: Adv. {lawyer_name}",
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
                    created_notifications.append({"notification_id": str(notif_client.id), "user_id": str(client_user_id)})

            # Notify Lawyer
            if lawyer_user_id:
                notif_lawyer = self.notification_service.create_notification(
                    user_id=lawyer_user_id,
                    type=NotificationType.CONSULTATION_REMINDER,
                    title=f"Consultation in {hours_ahead}h: Client {client_name}",
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
                    created_notifications.append({"notification_id": str(notif_lawyer.id), "user_id": str(lawyer_user_id)})

        return created_notifications

    def process_task_reminders(self, hours_ahead: int = 24) -> list[dict[str, Any]]:
        """Schedules reminders for approaching case tasks."""
        now = datetime.datetime.now(datetime.UTC)
        window_end = now + datetime.timedelta(hours=hours_ahead)

        tasks = (
            self.db.query(CaseTask, Case.title)
            .join(Case, CaseTask.case_id == Case.id)
            .filter(
                CaseTask.deleted_at.is_(None),
                CaseTask.status.in_([TaskStatus.PENDING, TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED]),
                CaseTask.due_date.isnot(None),
                CaseTask.due_date >= now,
                CaseTask.due_date <= window_end,
            )
            .all()
        )

        created_notifications = []
        for t, case_title in tasks:
            recipients = []
            if t.owner_user_id:
                recipients.append(t.owner_user_id)
            else:
                # If unassigned, notify active case participants
                participants = (
                    self.db.query(CaseParticipant.user_id)
                    .filter(
                        CaseParticipant.case_id == t.case_id,
                        CaseParticipant.status == ParticipantStatus.ACTIVE,
                    )
                    .all()
                )
                recipients = [p[0] for p in participants]

            due_str = t.due_date.strftime("%d %b %Y") if t.due_date else "soon"
            what_happened = f"Task '{t.title}' is due on {due_str}."
            why_it_matters = f"Operational case action required for matter '{case_title}'."
            what_to_do = "Review and progress task deliverables."

            for uid in recipients:
                event_dedup_id = f"reminder-task-{t.id}-{hours_ahead}h-{uid}"
                notif = self.notification_service.create_notification(
                    user_id=uid,
                    type=NotificationType.TASK_DUE_SOON,
                    title=f"Task Due in {hours_ahead}h: {t.title}",
                    message=f"{what_happened} {why_it_matters}",
                    case_id=t.case_id,
                    task_id=t.id,
                    event_id=event_dedup_id,
                    metadata={
                        "what_happened": what_happened,
                        "why_it_matters": why_it_matters,
                        "what_to_do": what_to_do,
                        "action_url": f"/cases/{t.case_id}?tab=tasks",
                        "action_label": "Review Task",
                        "due_date": t.due_date.isoformat() if t.due_date else None,
                    },
                )
                if notif:
                    created_notifications.append({
                        "notification_id": str(notif.id),
                        "user_id": str(uid),
                        "type": "TASK_DUE_SOON",
                        "event_id": event_dedup_id,
                    })

        return created_notifications

    def process_overdue_deadlines_and_tasks(self) -> dict[str, Any]:
        """Detects and transitions overdue deadlines and emits overdue notifications deterministically."""
        with job_lock("process_overdue_deadlines_and_tasks", ttl_seconds=120, db=self.db) as acquired:
            if not acquired:
                logger.info("Overdue processing lock already held by another worker. Skipping.")
                return {
                    "deadlines_marked_overdue": 0,
                    "deadline_overdue_notifications": 0,
                    "task_overdue_notifications": 0,
                    "skipped_due_to_lock": True,
                }

            now = datetime.datetime.now(datetime.UTC)

            # 1. Update upcoming/due deadlines that have passed
            overdue_deadlines = (
                self.db.query(CaseDeadline, Case.title)
                .join(Case, CaseDeadline.case_id == Case.id)
                .filter(
                    CaseDeadline.deleted_at.is_(None),
                    CaseDeadline.status.in_([DeadlineStatus.UPCOMING, DeadlineStatus.DUE]),
                    CaseDeadline.deadline_at < now,
                )
                .all()
            )

            deadlines_updated = 0
            deadline_notifications = 0
            for d, case_title in overdue_deadlines:
                d.status = DeadlineStatus.OVERDUE
                deadlines_updated += 1

                participants = (
                    self.db.query(CaseParticipant.user_id)
                    .filter(
                        CaseParticipant.case_id == d.case_id,
                        CaseParticipant.status == ParticipantStatus.ACTIVE,
                    )
                    .all()
                )
                for (uid,) in participants:
                    event_dedup_id = f"overdue-deadline-{d.id}-{uid}"
                    notif = self.notification_service.create_notification(
                        user_id=uid,
                        type=NotificationType.DEADLINE_OVERDUE,
                        title=f"OVERDUE: Deadline '{d.title}' in {case_title}",
                        message=f"Compliance deadline '{d.title}' was due on {d.deadline_at.strftime('%d %b %Y')}. Immediate review required.",
                        case_id=d.case_id,
                        deadline_id=d.id,
                        event_id=event_dedup_id,
                        metadata={
                            "action_url": f"/cases/{d.case_id}?tab=tasks",
                            "deadline_at": d.deadline_at.isoformat(),
                        },
                    )
                    if notif:
                        deadline_notifications += 1

            # 2. Emit overdue notifications for active tasks past due date
            overdue_tasks = (
                self.db.query(CaseTask, Case.title)
                .join(Case, CaseTask.case_id == Case.id)
                .filter(
                    CaseTask.deleted_at.is_(None),
                    CaseTask.status.in_([TaskStatus.PENDING, TaskStatus.IN_PROGRESS]),
                    CaseTask.due_date.isnot(None),
                    CaseTask.due_date < now,
                )
                .all()
            )

            task_notifications = 0
            for t, case_title in overdue_tasks:
                recipients = [t.owner_user_id] if t.owner_user_id else []
                if not recipients:
                    participants = (
                        self.db.query(CaseParticipant.user_id)
                        .filter(
                            CaseParticipant.case_id == t.case_id,
                            CaseParticipant.status == ParticipantStatus.ACTIVE,
                        )
                        .all()
                    )
                    recipients = [p[0] for p in participants]

                due_fmt = t.due_date.strftime("%d %b %Y") if t.due_date else "previously"
                for uid in recipients:
                    event_dedup_id = f"overdue-task-{t.id}-{uid}"
                    notif = self.notification_service.create_notification(
                        user_id=uid,
                        type=NotificationType.TASK_OVERDUE,
                        title=f"OVERDUE: Task '{t.title}' in {case_title}",
                        message=f"Task '{t.title}' was due on {due_fmt}. Action required.",
                        case_id=t.case_id,
                        task_id=t.id,
                        event_id=event_dedup_id,
                        metadata={
                            "action_url": f"/cases/{t.case_id}?tab=tasks",
                            "due_date": t.due_date.isoformat() if t.due_date else None,
                        },
                    )
                    if notif:
                        task_notifications += 1

            self.db.commit()
            return {
                "deadlines_marked_overdue": deadlines_updated,
                "deadline_overdue_notifications": deadline_notifications,
                "task_overdue_notifications": task_notifications,
                "skipped_due_to_lock": False,
            }

    def process_all_due_reminders(self) -> dict[str, Any]:
        """Runs the deterministic reminder batch across all categories."""
        with job_lock("process_all_due_reminders", ttl_seconds=180, db=self.db) as acquired:
            if not acquired:
                logger.info("Reminders batch processing lock already held by another worker. Skipping.")
                return {
                    "processed_at": datetime.datetime.now(datetime.UTC).isoformat(),
                    "total_emitted": 0,
                    "skipped_due_to_lock": True,
                }

            hearing_notifs = self.process_hearing_reminders(hours_ahead=24)
            deadline_notifs = self.process_deadline_reminders(hours_ahead=48)
            consultation_notifs = self.process_consultation_reminders(hours_ahead=2)
            task_notifs = self.process_task_reminders(hours_ahead=24)
            overdue_summary = self.process_overdue_deadlines_and_tasks()

            total_emitted = (
                len(hearing_notifs)
                + len(deadline_notifs)
                + len(consultation_notifs)
                + len(task_notifs)
                + overdue_summary["deadline_overdue_notifications"]
                + overdue_summary["task_overdue_notifications"]
            )
            return {
                "processed_at": datetime.datetime.now(datetime.UTC).isoformat(),
                "total_emitted": total_emitted,
                "hearings_processed": len(hearing_notifs),
                "deadlines_processed": len(deadline_notifs),
                "consultations_processed": len(consultation_notifs),
                "tasks_processed": len(task_notifs),
                "overdue_summary": overdue_summary,
                "skipped_due_to_lock": False,
            }
