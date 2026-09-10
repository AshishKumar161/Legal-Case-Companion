import re
import uuid
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, selectinload

from app.core.authorization import _get_case_participant, authorize_case_access
from app.core.identifiers import generate_uuid7
from app.models.case import (
    CaseParticipant,
    CaseTimelineEvent,
    ParticipantRole,
    ParticipantStatus,
)
from app.models.case_collaboration import CaseMessage, MatterRequest
from app.models.consultation import Consultation
from app.models.document import Document
from app.models.note import CaseNote, CaseNoteVisibility
from app.models.task import CaseTask
from app.models.user import ClientProfile, LawyerProfile, User, UserRole
from app.models.workflow import CaseDeadline, CaseHearing
from app.schemas.report import (
    CaseOverviewReportItem,
    CaseSummaryReportResponse,
    CommunicationsSummaryReportItem,
    ConsultationReportItem,
    DeadlineReportItem,
    DocumentReportItem,
    HearingReportItem,
    NoteReportItem,
    ParticipantReportItem,
    ReportMetadataItem,
    TaskReportItem,
    TimelineReportItem,
)
from app.domain.auth.auth_service import AuthService


class CaseReportService:
    def __init__(self, db: Session):
        self.db = db
        self.auth_service = AuthService(db)

    def _get_user_display_name(self, user_id: uuid.UUID) -> str:
        client_prof = (
            self.db.query(ClientProfile).filter(ClientProfile.user_id == user_id).first()
        )
        if client_prof and client_prof.full_name:
            return client_prof.full_name

        lawyer_prof = (
            self.db.query(LawyerProfile).filter(LawyerProfile.user_id == user_id).first()
        )
        if lawyer_prof and lawyer_prof.full_name:
            return lawyer_prof.full_name

        usr = self.db.query(User).filter(User.id == user_id).first()
        if usr:
            return usr.email.split("@")[0]
        return f"User #{str(user_id)[:8]}"

    def generate_report_data(
        self, user: User, case_id: uuid.UUID
    ) -> CaseSummaryReportResponse:
        # 1. BOLA authorization check
        case_ = authorize_case_access(self.db, user, case_id)

        # Determine requester participant role
        participant = None
        if user.role != UserRole.ADMIN:
            participant = _get_case_participant(self.db, case_id, user.id)

        requester_name = self._get_user_display_name(user.id)
        requester_role = (
            user.role.value
            if user.role == UserRole.ADMIN
            else (participant.participant_role.value if participant else "VIEWER")
        )

        report_id = generate_uuid7()
        now = datetime.now(UTC)

        # 2. Case Overview
        case_overview = CaseOverviewReportItem(
            case_id=case_.id,
            case_number=getattr(case_, "case_number", None),
            title=case_.title,
            description=case_.description or "",
            status=case_.status.value if hasattr(case_.status, "value") else str(case_.status),
            created_at=case_.created_at,
            updated_at=case_.updated_at,
        )

        # 3. Participants
        raw_participants = (
            self.db.query(CaseParticipant)
            .options(selectinload(CaseParticipant.user))
            .filter(
                CaseParticipant.case_id == case_id,
                CaseParticipant.status == ParticipantStatus.ACTIVE,
            )
            .order_by(CaseParticipant.created_at.asc())
            .all()
        )
        participants = [
            ParticipantReportItem(
                id=p.id,
                user_id=p.user_id,
                full_name=self._get_user_display_name(p.user_id),
                email=p.user.email if p.user else None,
                participant_role=p.participant_role.value if hasattr(p.participant_role, "value") else str(p.participant_role),
                status=p.status.value if hasattr(p.status, "value") else str(p.status),
                joined_at=p.joined_at,
            )
            for p in raw_participants
        ]

        # 4. Hearings (Court Diary)
        raw_hearings = (
            self.db.query(CaseHearing)
            .filter(CaseHearing.case_id == case_id, CaseHearing.deleted_at.is_(None))
            .order_by(CaseHearing.hearing_at.asc())
            .all()
        )
        hearings = [
            HearingReportItem(
                id=h.id,
                court_name=h.court_name,
                bench_judge=h.bench_or_coram,
                hearing_date=h.hearing_at,
                purpose=h.purpose,
                outcome=h.notes,
                status=h.status.value if hasattr(h.status, "value") else str(h.status),
            )
            for h in raw_hearings
        ]

        # 5. Statutory Limitation Deadlines
        raw_deadlines = (
            self.db.query(CaseDeadline)
            .filter(CaseDeadline.case_id == case_id, CaseDeadline.deleted_at.is_(None))
            .order_by(CaseDeadline.deadline_at.asc())
            .all()
        )
        deadlines = [
            DeadlineReportItem(
                id=d.id,
                title=d.title,
                deadline_type=d.deadline_type.value if hasattr(d.deadline_type, "value") else str(d.deadline_type),
                deadline_at=d.deadline_at,
                status=d.status.value if hasattr(d.status, "value") else str(d.status),
                description=d.description,
            )
            for d in raw_deadlines
        ]

        # 6. Case Tasks
        raw_tasks = (
            self.db.query(CaseTask)
            .filter(CaseTask.case_id == case_id, CaseTask.deleted_at.is_(None))
            .order_by(CaseTask.created_at.desc())
            .all()
        )
        tasks = [
            TaskReportItem(
                id=t.id,
                title=t.title,
                description=t.description,
                priority=t.priority.value if hasattr(t.priority, "value") else str(t.priority),
                status=t.status.value if hasattr(t.status, "value") else str(t.status),
                due_date=t.due_date,
                completed_at=t.completed_at,
                assignee_name=self._get_user_display_name(t.owner_user_id) if t.owner_user_id else None,
            )
            for t in raw_tasks
        ]

        # 7. Documents (Safe metadata only - NO S3 URLs/keys)
        raw_docs = (
            self.db.query(Document)
            .filter(Document.case_id == case_id, Document.deleted_at.is_(None))
            .order_by(Document.created_at.desc())
            .all()
        )
        documents = [
            DocumentReportItem(
                id=doc.id,
                name=doc.filename,
                category=doc.document_type.value if hasattr(doc.document_type, "value") else str(doc.document_type),
                security_status=doc.security_status.value if hasattr(doc.security_status, "value") else str(doc.security_status),
                mime_type=doc.mime_type,
                file_size_bytes=doc.file_size,
                created_at=doc.created_at,
            )
            for doc in raw_docs
        ]

        # 8. Timeline Events
        raw_timeline = (
            self.db.query(CaseTimelineEvent)
            .filter(CaseTimelineEvent.case_id == case_id)
            .order_by(CaseTimelineEvent.created_at.asc())
            .all()
        )
        timeline = [
            TimelineReportItem(
                id=ev.id,
                event_type=ev.event_type,
                description=ev.description,
                created_at=ev.created_at,
                actor_user_id=ev.actor_user_id,
            )
            for ev in raw_timeline
        ]

        # 9. Consultations
        raw_consultations = (
            self.db.query(Consultation)
            .filter(Consultation.case_id == case_id, Consultation.deleted_at.is_(None))
            .order_by(Consultation.scheduled_at.asc())
            .all()
        )
        consultations = []
        for c in raw_consultations:
            lawyer_prof = (
                self.db.query(LawyerProfile)
                .filter(LawyerProfile.id == c.lawyer_id)
                .first()
            )
            l_name = lawyer_prof.full_name if lawyer_prof else "Authorized Counsel"
            consultations.append(
                ConsultationReportItem(
                    id=c.id,
                    lawyer_name=l_name,
                    scheduled_at=c.scheduled_at,
                    status=c.status.value if hasattr(c.status, "value") else str(c.status),
                    duration_minutes=c.duration_minutes,
                    fee_amount=float(c.fee_amount) if c.fee_amount is not None else None,
                    currency=c.currency,
                )
            )

        # 10. Communications Summary (Message bodies excluded for privacy)
        msg_count = self.db.query(func.count(CaseMessage.id)).filter(
            CaseMessage.case_id == case_id, CaseMessage.deleted_at.is_(None)
        ).scalar() or 0

        req_count = self.db.query(func.count(MatterRequest.id)).filter(
            MatterRequest.case_id == case_id, MatterRequest.deleted_at.is_(None)
        ).scalar() or 0

        latest_msg = (
            self.db.query(CaseMessage.created_at)
            .filter(CaseMessage.case_id == case_id, CaseMessage.deleted_at.is_(None))
            .order_by(CaseMessage.created_at.desc())
            .first()
        )
        communications_summary = CommunicationsSummaryReportItem(
            total_messages=msg_count,
            total_requests=req_count,
            latest_activity_at=latest_msg[0] if latest_msg else None,
        )

        # 11. Case Notes (Strict 3-tier privacy filter)
        note_query = self.db.query(CaseNote).filter(
            CaseNote.case_id == case_id, CaseNote.deleted_at.is_(None)
        )
        if user.role == UserRole.ADMIN:
            # Admin can see SHARED notes (or all if authorized)
            note_query = note_query.filter(CaseNote.visibility == CaseNoteVisibility.SHARED)
        elif participant:
            if participant.participant_role == ParticipantRole.OWNER:
                # Owner sees SHARED + CLIENT_PRIVATE + notes authored by themselves
                note_query = note_query.filter(
                    or_(
                        CaseNote.visibility == CaseNoteVisibility.SHARED,
                        CaseNote.visibility == CaseNoteVisibility.CLIENT_PRIVATE,
                        CaseNote.author_user_id == user.id,
                    )
                )
            elif participant.participant_role == ParticipantRole.LAWYER:
                # Lawyer sees SHARED + LAWYER_PRIVATE authored by themselves
                note_query = note_query.filter(
                    or_(
                        CaseNote.visibility == CaseNoteVisibility.SHARED,
                        CaseNote.author_user_id == user.id,
                    )
                )
            elif participant.participant_role == ParticipantRole.VIEWER:
                # Viewer sees SHARED notes only
                note_query = note_query.filter(CaseNote.visibility == CaseNoteVisibility.SHARED)
            else:
                note_query = note_query.filter(CaseNote.visibility == CaseNoteVisibility.SHARED)
        else:
            note_query = note_query.filter(CaseNote.visibility == CaseNoteVisibility.SHARED)

        raw_notes = note_query.order_by(CaseNote.created_at.desc()).all()
        notes = [
            NoteReportItem(
                id=n.id,
                title=n.title,
                content=n.content,
                visibility=n.visibility.value if hasattr(n.visibility, "value") else str(n.visibility),
                author_name=self._get_user_display_name(n.author_user_id),
                created_at=n.created_at,
            )
            for n in raw_notes
        ]

        # Audit event
        self.auth_service.log_audit_event(
            "CASE_REPORT_GENERATED",
            user.id,
            {"case_id": str(case_id), "report_id": str(report_id)},
            action="report_generation",
        )
        self.db.commit()

        return CaseSummaryReportResponse(
            metadata=ReportMetadataItem(
                report_id=report_id,
                generated_at=now,
                generated_by_user_id=user.id,
                generated_by_name=requester_name,
                generated_by_role=requester_role,
            ),
            case_overview=case_overview,
            participants=participants,
            hearings=hearings,
            deadlines=deadlines,
            tasks=tasks,
            documents=documents,
            timeline=timeline,
            consultations=consultations,
            communications_summary=communications_summary,
            notes=notes,
        )

    def generate_markdown_report(self, report: CaseSummaryReportResponse) -> str:
        lines: list[str] = []
        gen_time = report.metadata.generated_at.strftime("%Y-%m-%d %H:%M:%S UTC")

        # Header
        lines.append("# LEGAL CASE COMPANION — CASE SUMMARY REPORT")
        lines.append("")
        lines.append(f"**Report Reference**: `#{report.metadata.report_id!s}`  ")
        lines.append(f"**Generated On**: {gen_time}  ")
        lines.append(f"**Generated By**: {report.metadata.generated_by_name} ({report.metadata.generated_by_role})  ")
        lines.append("")
        lines.append("---")
        lines.append("")

        # Section 1: Case Overview
        lines.append("## 1. Case Overview")
        lines.append("")
        lines.append(f"- **Matter Title**: {report.case_overview.title}")
        lines.append(f"- **Case Identifier**: `{report.case_overview.case_id!s}`")
        if report.case_overview.case_number:
            lines.append(f"- **Court Case Number**: {report.case_overview.case_number}")
        lines.append(f"- **Current Status**: `{report.case_overview.status}`")
        lines.append(f"- **Opened At**: {report.case_overview.created_at.strftime('%Y-%m-%d %H:%M UTC')}")
        lines.append(f"- **Last Updated**: {report.case_overview.updated_at.strftime('%Y-%m-%d %H:%M UTC')}")
        lines.append("")
        lines.append("### Summary Statement / Dispute Description")
        lines.append(f"> {report.case_overview.description.replace(chr(10), ' ')}")
        lines.append("")

        # Section 2: Participants
        lines.append("## 2. Case Participants & Representation Registry")
        lines.append("")
        if not report.participants:
            lines.append("_No additional active participants registered._")
        else:
            lines.append("| Name / Caption | Role | Account Status | Joined At |")
            lines.append("|---|---|---|---|")
            for p in report.participants:
                joined = p.joined_at.strftime("%Y-%m-%d")
                lines.append(f"| {p.full_name} | `{p.participant_role}` | {p.status} | {joined} |")
        lines.append("")

        # Section 3: Court Hearings
        lines.append("## 3. Court Diary & Hearing Records")
        lines.append("")
        if not report.hearings:
            lines.append("_No court hearing dates recorded for this matter._")
        else:
            lines.append("| Hearing Date & Time | Forum / Court | Bench / Judge | Purpose / Stage | Status | Outcome / Next Steps |")
            lines.append("|---|---|---|---|---|---|")
            for h in report.hearings:
                h_date = h.hearing_date.strftime("%Y-%m-%d %H:%M")
                court = h.court_name
                bench = h.bench_judge or "—"
                purpose = h.purpose or "General Proceedings"
                outcome = h.outcome or "Pending"
                lines.append(f"| {h_date} | {court} | {bench} | {purpose} | `{h.status}` | {outcome} |")
        lines.append("")

        # Section 4: Statutory Limitation Deadlines
        lines.append("## 4. Statutory Limitation & Compliance Deadlines")
        lines.append("")
        if not report.deadlines:
            lines.append("_No statutory limitation deadlines recorded._")
        else:
            lines.append("| Deadline Due Date | Title | Type | Status | Description |")
            lines.append("|---|---|---|---|---|")
            for d in report.deadlines:
                due = d.deadline_at.strftime("%Y-%m-%d %H:%M")
                desc = d.description or "—"
                lines.append(f"| {due} | {d.title} | `{d.deadline_type}` | `{d.status}` | {desc} |")
        lines.append("")

        # Section 5: Tasks & Workflow
        lines.append("## 5. Case Tasks & Action Schedule")
        lines.append("")
        if not report.tasks:
            lines.append("_No tasks scheduled._")
        else:
            lines.append("| Task Title | Priority | Status | Due Date | Assignee | Completed At |")
            lines.append("|---|---|---|---|---|---|")
            for t in report.tasks:
                due = t.due_date.strftime("%Y-%m-%d") if t.due_date else "—"
                comp = t.completed_at.strftime("%Y-%m-%d") if t.completed_at else "—"
                assignee = t.assignee_name or "Unassigned"
                lines.append(f"| {t.title} | `{t.priority}` | `{t.status}` | {due} | {assignee} | {comp} |")
        lines.append("")

        # Section 6: Documents
        lines.append("## 6. Document Repository (Safe Metadata)")
        lines.append("")
        if not report.documents:
            lines.append("_No documents uploaded to this workspace._")
        else:
            lines.append("| Document Name | Category | Security Status | Size | Uploaded Date |")
            lines.append("|---|---|---|---|---|")
            for doc in report.documents:
                size_kb = f"{(doc.file_size_bytes or 0) / 1024:.1f} KB" if doc.file_size_bytes else "—"
                up_date = doc.created_at.strftime("%Y-%m-%d %H:%M")
                lines.append(f"| {doc.name} | `{doc.category}` | `{doc.security_status}` | {size_kb} | {up_date} |")
        lines.append("")

        # Section 7: Consultations
        lines.append("## 7. Legal Counsel Consultations")
        lines.append("")
        if not report.consultations:
            lines.append("_No formal consultations logged for this case._")
        else:
            lines.append("| Scheduled Time | Counsel | Duration | Status | Fee |")
            lines.append("|---|---|---|---|---|")
            for c in report.consultations:
                c_time = c.scheduled_at.strftime("%Y-%m-%d %H:%M")
                dur = f"{c.duration_minutes}m" if c.duration_minutes else "—"
                fee = f"{c.currency or 'INR'} {c.fee_amount:.2f}" if c.fee_amount is not None else "—"
                lines.append(f"| {c_time} | {c.lawyer_name or 'Counsel'} | {dur} | `{c.status}` | {fee} |")
        lines.append("")

        # Section 8: Timeline
        lines.append("## 8. Matter Chronology & Timeline Audit")
        lines.append("")
        if not report.timeline:
            lines.append("_No timeline events recorded._")
        else:
            for ev in report.timeline:
                t_date = ev.created_at.strftime("%Y-%m-%d %H:%M UTC")
                lines.append(f"- **{t_date}** — `[{ev.event_type}]` {ev.description}")
        lines.append("")

        # Section 9: Case Notes
        lines.append("## 9. Authorized Case Strategy Notes")
        lines.append("")
        if not report.notes:
            lines.append("_No authorized case strategy notes recorded._")
        else:
            for n in report.notes:
                n_date = n.created_at.strftime("%Y-%m-%d %H:%M UTC")
                title = n.title or "Untitled Note"
                lines.append(f"### {title} (`{n.visibility}`)")
                lines.append(f"_Authored by {n.author_name or 'Authorized Counsel'} on {n_date}_")
                lines.append("")
                lines.append(f"> {n.content.replace(chr(10), ' ')}")
                lines.append("")

        # Footer
        lines.append("---")
        lines.append(f"_Generated securely by Legal Case Companion at {gen_time}. Document confidentiality applies._")
        return "\n".join(lines)

    @staticmethod
    def generate_safe_filename(
        case_id: uuid.UUID,
        case_title: str | None = None,
        ext: Literal["json", "markdown"] = "json",
    ) -> str:
        safe_ext = "json" if ext == "json" else "md"
        prefix = f"case_{str(case_id)[:8]}"
        if case_title:
            cleaned_title = re.sub(r"[^a-zA-Z0-9_\-]", "_", case_title).strip("_")
            cleaned_title = re.sub(r"_+", "_", cleaned_title)[:30]
            if cleaned_title:
                prefix = f"{prefix}_{cleaned_title}"
        return f"{prefix}_summary_report.{safe_ext}"
