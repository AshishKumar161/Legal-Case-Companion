import datetime
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.core.exceptions import ResourceNotFoundError
from app.models.case import Case, CaseParticipant, ParticipantStatus
from app.models.case_collaboration import CaseMessage, MatterRequest, MatterRequestStatus
from app.models.consultation import Consultation, ConsultationStatus
from app.models.court_case import CourtCase
from app.models.task import CaseTask, TaskStatus
from app.models.user import User, UserRole
from app.models.workflow import CaseDeadline, CaseHearing, DeadlineStatus, HearingStatus


def _ensure_utc(dt: datetime.datetime | None) -> datetime.datetime:
    if dt is None:
        return datetime.datetime.now(datetime.timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=datetime.timezone.utc)
    return dt.astimezone(datetime.timezone.utc)


class CaseAttentionService:
    """Computes deterministic operational attention across 6 dimensions:

    Hearing, Documents, Tasks, Court Sync, Communication, Payment.
    Strictly NO AI risk scores. Purely categorical and explainable.
    """

    def __init__(self, db: Session):
        self.db = db

    def evaluate_case_attention(self, case_id: uuid.UUID, user: User) -> dict[str, Any]:
        """Evaluates the 6 operational attention dimensions for a given matter."""
        case = (
            self.db.query(Case)
            .filter(Case.id == case_id, Case.deleted_at.is_(None))
            .first()
        )
        if not case:
            raise ResourceNotFoundError("Case not found.")

        # Ensure user is participant or admin
        if user.role != UserRole.ADMIN:
            is_participant = (
                self.db.query(CaseParticipant)
                .filter(
                    CaseParticipant.case_id == case_id,
                    CaseParticipant.user_id == user.id,
                    CaseParticipant.status == ParticipantStatus.ACTIVE,
                )
                .first()
            )
            if not is_participant:
                from app.core.exceptions import AuthorizationError
                raise AuthorizationError("Access denied to case attention evaluation.")

        now = datetime.datetime.now(datetime.UTC)

        # -------------------------------------------------------------
        # 1. HEARING DIMENSION
        # -------------------------------------------------------------
        upcoming_hearings = (
            self.db.query(CaseHearing)
            .filter(
                CaseHearing.case_id == case_id,
                CaseHearing.deleted_at.is_(None),
                CaseHearing.status == HearingStatus.SCHEDULED,
                CaseHearing.hearing_at >= now,
            )
            .order_by(CaseHearing.hearing_at.asc())
            .all()
        )

        hearing_state = "UP_TO_DATE"
        hearing_reason = "No hearings scheduled in the next 14 days."
        nearest_hearing = None

        if upcoming_hearings:
            nearest = upcoming_hearings[0]
            nearest_hearing = {
                "id": str(nearest.id),
                "court_name": nearest.court_name,
                "hearing_at": nearest.hearing_at.isoformat(),
                "purpose": nearest.purpose,
            }
            time_to_hearing = _ensure_utc(nearest.hearing_at) - now
            if time_to_hearing <= datetime.timedelta(hours=48):
                hearing_state = "URGENT"
                hearing_reason = f"Hearing scheduled in {int(time_to_hearing.total_seconds() // 3600)} hours at {nearest.court_name}."
            elif time_to_hearing <= datetime.timedelta(days=14):
                hearing_state = "UPCOMING"
                hearing_reason = f"Hearing scheduled on {nearest.hearing_at.strftime('%d %b %Y')} ({nearest.purpose})."

        # -------------------------------------------------------------
        # 2. DOCUMENTS DIMENSION
        # -------------------------------------------------------------
        pending_doc_requests = (
            self.db.query(MatterRequest)
            .filter(
                MatterRequest.case_id == case_id,
                MatterRequest.request_type == "DOCUMENT_UPLOAD",
                MatterRequest.status == MatterRequestStatus.PENDING,
            )
            .all()
        )

        if pending_doc_requests:
            doc_state = "PENDING"
            titles = [r.title for r in pending_doc_requests[:2]]
            doc_reason = f"{len(pending_doc_requests)} document(s) requested: {', '.join(titles)}"
        else:
            doc_state = "COMPLETE"
            doc_reason = "All requested documents uploaded and verified in evidence vault."

        # -------------------------------------------------------------
        # 3. TASKS / DEADLINES DIMENSION
        # -------------------------------------------------------------
        deadlines = (
            self.db.query(CaseDeadline)
            .filter(
                CaseDeadline.case_id == case_id,
                CaseDeadline.deleted_at.is_(None),
                CaseDeadline.status.in_([DeadlineStatus.UPCOMING, DeadlineStatus.DUE, DeadlineStatus.OVERDUE]),
            )
            .all()
        )

        overdue_deadlines = [
            d for d in deadlines if d.status == DeadlineStatus.OVERDUE or (d.deadline_at and _ensure_utc(d.deadline_at) < now)
        ]
        open_tasks = (
            self.db.query(CaseTask)
            .filter(
                CaseTask.case_id == case_id,
                CaseTask.deleted_at.is_(None),
                CaseTask.status.in_([TaskStatus.PENDING, TaskStatus.IN_PROGRESS]),
            )
            .count()
        )

        if overdue_deadlines:
            task_state = "OVERDUE"
            task_reason = f"{len(overdue_deadlines)} deadline(s) overdue: {overdue_deadlines[0].title}"
        elif deadlines or open_tasks > 0:
            task_state = "PENDING"
            task_reason = f"{len(deadlines)} active deadline(s) and {open_tasks} open task(s)."
        else:
            task_state = "COMPLETE"
            task_reason = "All case tasks and statutory deadlines completed."

        # -------------------------------------------------------------
        # 4. COURT SYNCHRONIZATION DIMENSION
        # -------------------------------------------------------------
        linked_court_case = (
            self.db.query(CourtCase)
            .filter(CourtCase.case_id == case_id, CourtCase.deleted_at.is_(None))
            .first()
        )

        if linked_court_case:
            sync_age = now - _ensure_utc(linked_court_case.last_synchronized_at)
            if linked_court_case.sync_status == "FAILED":
                court_sync_state = "FAILED"
                court_sync_reason = "Last court registry synchronization encountered an upstream provider error."
            elif sync_age > datetime.timedelta(hours=24):
                court_sync_state = "STALE"
                court_sync_reason = f"Docket last synced {int(sync_age.total_seconds() // 3600)} hours ago."
            else:
                court_sync_state = "CURRENT"
                court_sync_reason = f"eCourts record synced recently ({linked_court_case.court_name})."
        else:
            court_sync_state = "CURRENT"
            court_sync_reason = "Pre-litigation / direct workspace matter (not linked to external docket)."

        # -------------------------------------------------------------
        # 5. COMMUNICATION DIMENSION
        # -------------------------------------------------------------
        # Check for pending matter requests or recent messages
        pending_requests = (
            self.db.query(MatterRequest)
            .filter(
                MatterRequest.case_id == case_id,
                MatterRequest.status == MatterRequestStatus.PENDING,
                MatterRequest.requesting_user_id != user.id,
            )
            .count()
        )

        unread_messages = (
            self.db.query(CaseMessage)
            .filter(
                CaseMessage.case_id == case_id,
                CaseMessage.sender_id != user.id,
            )
            .order_by(CaseMessage.created_at.desc())
            .first()
        )

        if pending_requests > 0:
            comm_state = "REPLY_NEEDED"
            comm_reason = f"{pending_requests} formal request(s) awaiting your action."
        elif unread_messages:
            comm_state = "REPLY_NEEDED"
            comm_sender = unread_messages.sender.full_name if unread_messages.sender else "participant"
            comm_reason = f"Recent message from {comm_sender}."
        else:
            comm_state = "NO_ACTION"
            comm_reason = "Case communication is current. No pending responses required."

        # -------------------------------------------------------------
        # 6. PAYMENT DIMENSION
        # -------------------------------------------------------------
        pending_consultations = (
            self.db.query(Consultation)
            .filter(
                Consultation.case_id == case_id,
                Consultation.deleted_at.is_(None),
                Consultation.status.in_([ConsultationStatus.REQUESTED, ConsultationStatus.ACCEPTED]),
            )
            .all()
        )

        if any(c.status == ConsultationStatus.REQUESTED and (c.fee_amount or 0) > 0 for c in pending_consultations):
            payment_state = "PENDING"
            payment_reason = "Consultation booking fee pending checkout."
        else:
            payment_state = "PAID"
            payment_reason = "All matter fees and consultation disbursements up to date."

        # -------------------------------------------------------------
        # SYNTHESIZE PRIMARY NEXTSTEP (Section 4)
        # -------------------------------------------------------------
        if task_state == "OVERDUE":
            next_step = {
                "context": "CASE",
                "headline": f"Resolve Overdue Deadline: {overdue_deadlines[0].title}",
                "detail": f"This statutory deadline expired on {overdue_deadlines[0].deadline_at.strftime('%d %b %Y')}. File compliance promptly.",
                "provenance": "STATUTORY DEADLINE",
                "action": {"label": "Open Tasks →", "href": f"/cases/{case_id}?tab=tasks"},
                "urgency": "CRITICAL",
            }
        elif hearing_state == "URGENT" and nearest_hearing is not None:
            next_step = {
                "context": "HEARING",
                "headline": f"Prepare for Hearing: {nearest_hearing['court_name']}",
                "detail": f"Hearing scheduled in under 48 hours for purpose: {nearest_hearing['purpose']}.",
                "provenance": "OFFICIAL COURT DATA",
                "action": {"label": "View Hearing Details →", "href": f"/cases/{case_id}?tab=hearings"},
                "urgency": "HIGH",
            }
        elif doc_state == "PENDING":
            next_step = {
                "context": "DOCUMENT",
                "headline": "Upload Requested Evidence",
                "detail": doc_reason,
                "provenance": "LAWYER ENTERED",
                "action": {"label": "Upload Document →", "href": f"/cases/{case_id}?tab=documents"},
                "urgency": "HIGH",
            }
        elif payment_state == "PENDING":
            next_step = {
                "context": "PAYMENT",
                "headline": "Complete Pending Consultation Payment",
                "detail": payment_reason,
                "provenance": "SYSTEM",
                "action": {"label": "Pay Securely →", "href": f"/cases/{case_id}?tab=overview"},
                "urgency": "HIGH",
            }
        elif comm_state == "REPLY_NEEDED":
            next_step = {
                "context": "CASE",
                "headline": "Review Counsel Message / Request",
                "detail": comm_reason,
                "provenance": "LAWYER ENTERED",
                "action": {"label": "Open Workspace →", "href": f"/cases/{case_id}?tab=overview"},
                "urgency": "MEDIUM",
            }
        elif hearing_state == "UPCOMING":
            next_step = {
                "context": "HEARING",
                "headline": f"Upcoming Hearing on {upcoming_hearings[0].hearing_at.strftime('%d %b %Y')}",
                "detail": f"Court: {upcoming_hearings[0].court_name}. Verify necessary evidence is ready.",
                "provenance": "OFFICIAL COURT DATA",
                "action": {"label": "Review Hearing →", "href": f"/cases/{case_id}?tab=hearings"},
                "urgency": "MEDIUM",
            }
        else:
            next_step = {
                "context": "DASHBOARD",
                "headline": "Case Records Up to Date",
                "detail": "No urgent actions required. All documents, deadlines, and court syncs are current.",
                "provenance": "SYSTEM",
                "action": {"label": "View Case Evidence →", "href": f"/cases/{case_id}?tab=evidence"},
                "urgency": "LOW",
            }

        return {
            "case_id": str(case_id),
            "case_title": case.title,
            "evaluated_at": now.isoformat(),
            "dimensions": {
                "hearing": {
                    "state": hearing_state,
                    "reason": hearing_reason,
                    "data": nearest_hearing,
                },
                "documents": {
                    "state": doc_state,
                    "reason": doc_reason,
                    "pending_count": len(pending_doc_requests),
                },
                "tasks": {
                    "state": task_state,
                    "reason": task_reason,
                    "overdue_count": len(overdue_deadlines),
                    "open_tasks_count": open_tasks,
                },
                "court_sync": {
                    "state": court_sync_state,
                    "reason": court_sync_reason,
                    "is_tracked": linked_court_case is not None,
                },
                "communication": {
                    "state": comm_state,
                    "reason": comm_reason,
                },
                "payment": {
                    "state": payment_state,
                    "reason": payment_reason,
                },
            },
            "next_step": next_step,
        }
