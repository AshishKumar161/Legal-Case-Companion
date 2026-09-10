import datetime
import uuid
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.identifiers import generate_uuid7
from app.models.case import Case, CaseParticipant, ParticipantStatus
from app.models.case_collaboration import CaseMessage, MatterRequest, MatterRequestStatus
from app.models.consultation import Consultation
from app.models.court_case import CourtCase, UserFollowedCase
from app.models.document import Document
from app.models.task import CaseTask
from app.models.user import ClientProfile, LawyerProfile, User, UserRole
from app.models.user_feed import UserFeedAcknowledgment
from app.models.workflow import CaseDeadline, CaseHearing


class ChangeFeedService:
    """Provides a deterministic 'What changed since your last visit?' experience.

    Aggregates delta events across hearings, court status updates, orders,
    documents, document requests, counsel messages, tasks, and payments since
    the user's last acknowledged checkpoint. Zero AI used.
    """

    def __init__(self, db: Session):
        self.db = db

    def get_or_create_acknowledgment(self, user_id: uuid.UUID) -> UserFeedAcknowledgment:
        ack = (
            self.db.query(UserFeedAcknowledgment)
            .filter(UserFeedAcknowledgment.user_id == user_id)
            .first()
        )
        if not ack:
            # Default checkpoint to 7 days ago if first visit
            seven_days_ago = datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=7)
            ack = UserFeedAcknowledgment(
                id=generate_uuid7(),
                user_id=user_id,
                last_acknowledged_at=seven_days_ago,
                preferences={},
            )
            self.db.add(ack)
            self.db.commit()
            self.db.refresh(ack)
        return ack

    def acknowledge_changes(self, user: User) -> dict[str, Any]:
        """Marks all changes up to now as acknowledged by the user."""
        now = datetime.datetime.now(datetime.UTC)
        ack = self.get_or_create_acknowledgment(user.id)
        ack.last_acknowledged_at = now
        self.db.commit()
        return {
            "status": "ACKNOWLEDGED",
            "user_id": str(user.id),
            "acknowledged_at": now.isoformat(),
        }

    def get_what_changed(self, user: User, limit: int = 30) -> dict[str, Any]:
        """Calculates delta events that occurred strictly after the user's last_acknowledged_at."""
        ack = self.get_or_create_acknowledgment(user.id)
        since = ack.last_acknowledged_at

        # Get list of case IDs the user participates in
        participant_cases = (
            self.db.query(CaseParticipant.case_id)
            .filter(
                CaseParticipant.user_id == user.id,
                CaseParticipant.status == ParticipantStatus.ACTIVE,
            )
            .all()
        )
        case_ids = [c[0] for c in participant_cases]

        # Get list of court case IDs the user follows
        followed_court_cases = (
            self.db.query(UserFollowedCase.court_case_id)
            .filter(UserFollowedCase.user_id == user.id)
            .all()
        )
        court_case_ids = [fc[0] for fc in followed_court_cases]

        events: list[dict[str, Any]] = []

        # 1. Hearing Changes
        if case_ids:
            recent_hearings = (
                self.db.query(CaseHearing, Case.title)
                .join(Case, CaseHearing.case_id == Case.id)
                .filter(
                    CaseHearing.case_id.in_(case_ids),
                    CaseHearing.deleted_at.is_(None),
                    or_(
                        CaseHearing.created_at > since,
                        CaseHearing.updated_at > since,
                    ),
                )
                .order_by(CaseHearing.updated_at.desc())
                .limit(10)
                .all()
            )
            for h, case_title in recent_hearings:
                is_update = h.updated_at > h.created_at and h.updated_at > since
                events.append({
                    "id": f"hearing-{h.id}",
                    "event_type": "HEARING_DATE_CHANGED" if is_update else "HEARING_SCHEDULED",
                    "category": "HEARING",
                    "title": f"Hearing Scheduled: {case_title}",
                    "description": f"Hearing listed on {h.hearing_at.strftime('%d %b %Y')} before {h.court_name} for purpose: {h.purpose}",
                    "source_url": f"/cases/{h.case_id}?tab=hearings",
                    "provenance": "COURT SCHEDULE",
                    "timestamp": (h.updated_at or h.created_at).isoformat(),
                    "entity_id": str(h.id),
                    "case_id": str(h.case_id),
                })

        # 2. Court Tracking Dockets (eCourts)
        if court_case_ids:
            recent_court_cases = (
                self.db.query(CourtCase)
                .filter(
                    CourtCase.id.in_(court_case_ids),
                    CourtCase.deleted_at.is_(None),
                    or_(
                        CourtCase.updated_at > since,
                        CourtCase.last_synchronized_at > since,
                    ),
                )
                .order_by(CourtCase.last_synchronized_at.desc())
                .limit(10)
                .all()
            )
            for cc in recent_court_cases:
                events.append({
                    "id": f"court-case-{cc.id}",
                    "event_type": "COURT_STATUS_CHANGED",
                    "category": "COURT_TRACKING",
                    "title": f"Court Update: {cc.case_number}",
                    "description": f"{cc.court_name} docket status: {cc.human_status}. Next listing: {cc.next_hearing_date.strftime('%d %b %Y') if cc.next_hearing_date else 'Pending assignment'}.",
                    "source_url": "/court-tracking",
                    "provenance": cc.source_provenance,
                    "timestamp": (cc.last_synchronized_at or cc.updated_at).isoformat(),
                    "entity_id": str(cc.id),
                })

        # 3. Documents
        if case_ids:
            recent_docs = (
                self.db.query(Document, Case.title)
                .join(Case, Document.case_id == Case.id)
                .filter(
                    Document.case_id.in_(case_ids),
                    Document.deleted_at.is_(None),
                    Document.uploaded_by != user.id,  # uploaded by other party/lawyer
                    Document.created_at > since,
                )
                .order_by(Document.created_at.desc())
                .limit(10)
                .all()
            )
            for d, case_title in recent_docs:
                events.append({
                    "id": f"doc-{d.id}",
                    "event_type": "NEW_DOCUMENT",
                    "category": "DOCUMENT",
                    "title": f"New Document Added: {case_title}",
                    "description": f"Document '{d.filename}' was uploaded to your case evidence locker.",
                    "source_url": f"/cases/{d.case_id}?tab=evidence",
                    "provenance": "EVIDENCE LOCKER",
                    "timestamp": d.created_at.isoformat(),
                    "entity_id": str(d.id),
                    "case_id": str(d.case_id),
                })

        # 4. Document Requests
        if case_ids:
            recent_requests = (
                self.db.query(MatterRequest, Case.title)
                .join(Case, MatterRequest.case_id == Case.id)
                .filter(
                    MatterRequest.case_id.in_(case_ids),
                    MatterRequest.request_type == "DOCUMENT_UPLOAD",
                    MatterRequest.status == MatterRequestStatus.PENDING,
                    MatterRequest.requesting_user_id != user.id,
                    MatterRequest.created_at > since,
                )
                .order_by(MatterRequest.created_at.desc())
                .limit(5)
                .all()
            )
            for r, case_title in recent_requests:
                events.append({
                    "id": f"req-{r.id}",
                    "event_type": "DOCUMENT_REQUESTED",
                    "category": "DOCUMENT_REQUEST",
                    "title": f"Counsel Document Request: {case_title}",
                    "description": f"Your advocate requested: '{r.title}'. Please provide the requested filing.",
                    "source_url": f"/cases/{r.case_id}?tab=documents",
                    "provenance": "COUNSEL REQUEST",
                    "timestamp": r.created_at.isoformat(),
                    "entity_id": str(r.id),
                    "case_id": str(r.case_id),
                })

        # 5. Messages / Formal Notes
        if case_ids:
            recent_messages = (
                self.db.query(CaseMessage, Case.title)
                .join(Case, CaseMessage.case_id == Case.id)
                .filter(
                    CaseMessage.case_id.in_(case_ids),
                    CaseMessage.sender_id != user.id,
                    CaseMessage.created_at > since,
                )
                .order_by(CaseMessage.created_at.desc())
                .limit(5)
                .all()
            )
            for m, case_title in recent_messages:
                sender_name = m.sender.full_name if m.sender else "Counsel"
                events.append({
                    "id": f"msg-{m.id}",
                    "event_type": "LAWYER_MESSAGE_RECEIVED",
                    "category": "COMMUNICATION",
                    "title": f"New Message: {case_title}",
                    "description": f"{sender_name} sent: '{m.content[:100]}...'",
                    "source_url": f"/cases/{m.case_id}?tab=overview",
                    "provenance": "CASE MESSAGING",
                    "timestamp": m.created_at.isoformat(),
                    "entity_id": str(m.id),
                    "case_id": str(m.case_id),
                })

        # 6. Tasks / Deadlines
        if case_ids:
            recent_deadlines = (
                self.db.query(CaseDeadline, Case.title)
                .join(Case, CaseDeadline.case_id == Case.id)
                .filter(
                    CaseDeadline.case_id.in_(case_ids),
                    CaseDeadline.deleted_at.is_(None),
                    or_(
                        CaseDeadline.created_at > since,
                        CaseDeadline.updated_at > since,
                    ),
                )
                .order_by(CaseDeadline.updated_at.desc())
                .limit(5)
                .all()
            )
            for dl, case_title in recent_deadlines:
                events.append({
                    "id": f"deadline-{dl.id}",
                    "event_type": "TASK_UPDATE",
                    "category": "DEADLINE",
                    "title": f"Deadline Notice: {case_title}",
                    "description": f"Task/Deadline '{dl.title}' due on {dl.deadline_at.strftime('%d %b %Y')}.",
                    "source_url": f"/cases/{dl.case_id}?tab=tasks",
                    "provenance": "STATUTORY DEADLINE",
                    "timestamp": (dl.updated_at or dl.created_at).isoformat(),
                    "entity_id": str(dl.id),
                    "case_id": str(dl.case_id),
                })

        # 7. Consultations & Payments
        consult_filter = None
        if user.role == UserRole.CLIENT:
            client_prof = (
                self.db.query(ClientProfile)
                .filter(ClientProfile.user_id == user.id)
                .first()
            )
            if client_prof:
                consult_filter = Consultation.client_id == client_prof.id
        elif user.role == UserRole.LAWYER:
            lawyer_prof = (
                self.db.query(LawyerProfile)
                .filter(LawyerProfile.user_id == user.id)
                .first()
            )
            if lawyer_prof:
                consult_filter = Consultation.lawyer_id == lawyer_prof.id

        if consult_filter is not None:
            recent_consultations = (
                self.db.query(Consultation)
                .filter(
                    consult_filter,
                    Consultation.deleted_at.is_(None),
                    or_(
                        Consultation.created_at > since,
                        Consultation.updated_at > since,
                    ),
                )
                .order_by(Consultation.updated_at.desc())
                .limit(5)
                .all()
            )
            for c in recent_consultations:
                lawyer_label = (c.lawyer.full_name if c.lawyer and hasattr(c.lawyer, "full_name") else "Advocate")
                client_label = (c.client.full_name if c.client and hasattr(c.client, "full_name") else "Client")
                target_person = lawyer_label if user.role == UserRole.CLIENT else client_label
                events.append({
                    "id": f"consult-{c.id}",
                    "event_type": "CONSULTATION_UPDATE",
                    "category": "CONSULTATION",
                    "title": f"Consultation Update: Status {c.status.value}",
                    "description": f"Consultation session with {target_person} on {c.scheduled_at.strftime('%d %b %Y, %I:%M %p') if c.scheduled_at else 'pending schedule'}.",
                    "source_url": "/calendar",
                    "provenance": "CONSULTATION DESK",
                    "timestamp": (c.updated_at or c.created_at).isoformat(),
                    "entity_id": str(c.id),
                })

        # Sort chronologically descending
        events.sort(key=lambda x: x["timestamp"], reverse=True)
        paginated_events = events[:limit]

        return {
            "since": since.isoformat(),
            "total_new_changes": len(events),
            "events": paginated_events,
            "has_unacknowledged_changes": len(events) > 0,
        }
