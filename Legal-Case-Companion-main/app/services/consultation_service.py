import uuid
from datetime import UTC, date, datetime, time, timedelta, timezone
from typing import ClassVar

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import (
    AuthorizationError,
    ResourceNotFoundError,
    ValidationError,
)
from app.core.identifiers import generate_uuid7
from app.models.availability import LawyerAvailability
from app.models.case import Case, CaseStatus
from app.models.consultation import Consultation, ConsultationStatus
from app.models.notification import NotificationType
from app.models.user import AccountStatus, ClientProfile, LawyerProfile, User, UserRole
from app.schemas.consultation import ConsultationCreate
from app.services.auth_service import AuthService
from app.services.case_service import CaseService
from app.services.notification_service import NotificationService


class ConsultationService:
    IST_TIMEZONE = timezone(timedelta(hours=5, minutes=30))
    BLOCKING_CONSULTATION_STATUSES: ClassVar[list[ConsultationStatus]] = [
        ConsultationStatus.REQUESTED,
        ConsultationStatus.ACCEPTED,
        ConsultationStatus.PAID,
        ConsultationStatus.SCHEDULED,
        ConsultationStatus.IN_PROGRESS,
    ]

    def __init__(self, db: Session):
        self.db = db
        self.case_service = CaseService(db)
        self.auth_service = AuthService(db)
        self.notification_service = NotificationService(db)

    def _log_audit(self, event_type: str, user_id: uuid.UUID, metadata: dict):
        self.auth_service.log_audit_event(
            event_type, user_id, metadata, action="consultation_mutation"
        )

    def _get_consultation(self, consultation_id: uuid.UUID) -> Consultation:
        consultation = (
            self.db.query(Consultation)
            .filter(
                Consultation.id == consultation_id, Consultation.deleted_at.is_(None)
            )
            .first()
        )
        if not consultation:
            raise ResourceNotFoundError("Consultation not found")
        return consultation

    def _authorize_consultation_access(self, user: User, consultation: Consultation):
        if user.role == UserRole.ADMIN:
            return

        # Verify user matches either the client or lawyer profile associated with the consultation
        is_client = (
            self.db.query(ClientProfile)
            .filter(
                ClientProfile.id == consultation.client_id,
                ClientProfile.user_id == user.id,
            )
            .first()
        )
        is_lawyer = (
            self.db.query(LawyerProfile)
            .filter(
                LawyerProfile.id == consultation.lawyer_id,
                LawyerProfile.user_id == user.id,
            )
            .first()
        )

        if not (is_client or is_lawyer):
            raise ResourceNotFoundError("Consultation not found")  # IDOR protection

    def _validate_slot_and_business_hours(
        self,
        scheduled_at: datetime,
        duration_minutes: int,
        lawyer_profile_id: uuid.UUID | None = None,
    ) -> tuple[datetime, datetime]:
        if duration_minutes <= 0 or duration_minutes > 240:
            raise ValidationError("Duration must be between 1 and 240 minutes")

        # Normalize timezone to UTC-aware
        if scheduled_at.tzinfo is None:
            req_start = scheduled_at.replace(tzinfo=UTC)
        else:
            req_start = scheduled_at.astimezone(UTC)

        now_utc = datetime.now(UTC)
        if req_start <= now_utc:
            raise ValidationError("Consultation must be scheduled for a future time")

        req_end = req_start + timedelta(minutes=duration_minutes)

        ist_start = req_start.astimezone(self.IST_TIMEZONE)
        ist_end = req_end.astimezone(self.IST_TIMEZONE)

        if ist_start.date() != ist_end.date():
            raise ValidationError(
                "Consultation cannot span across multiple calendar days"
            )

        # If lawyer has custom active availability windows configured for this day
        if lawyer_profile_id:
            custom_availabilities = (
                self.db.query(LawyerAvailability)
                .filter(
                    LawyerAvailability.lawyer_profile_id == lawyer_profile_id,
                    LawyerAvailability.day_of_week == ist_start.weekday(),
                    LawyerAvailability.is_active.is_(True),
                )
                .all()
            )
            if custom_availabilities:
                req_start_time = ist_start.time()
                req_end_time = ist_end.time()
                is_within_window = any(
                    win.start_time <= req_start_time and req_end_time <= win.end_time
                    for win in custom_availabilities
                )
                if not is_within_window:
                    raise ValidationError(
                        "Requested consultation time falls outside of the lawyer's configured availability"
                    )
                return req_start, req_end

        # Default business hours (08:00 to 22:00 IST)
        if ist_start.hour < 8:
            raise ValidationError(
                "Consultation must start within business hours (08:00 to 21:00 IST)"
            )

        if ist_end.hour > 22 or (
            ist_end.hour == 22 and (ist_end.minute > 0 or ist_end.second > 0)
        ):
            raise ValidationError(
                "Consultation must conclude within business hours (08:00 to 21:00 IST)"
            )

        return req_start, req_end

    def get_available_slots(
        self,
        lawyer_id: uuid.UUID,
        target_date: date | None = None,
        duration_minutes: int = 30,
    ) -> list[dict]:
        if duration_minutes < 15 or duration_minutes > 240:
            raise ValidationError("Slot duration must be between 15 and 240 minutes")

        lawyer_profile = (
            self.db.query(LawyerProfile)
            .join(User, LawyerProfile.user_id == User.id)
            .filter(
                or_(
                    LawyerProfile.user_id == lawyer_id,
                    LawyerProfile.id == lawyer_id,
                ),
                User.account_status == AccountStatus.ACTIVE,
                LawyerProfile.deleted_at.is_(None),
            )
            .first()
        )
        if not lawyer_profile:
            raise ResourceNotFoundError("Lawyer profile not found or inactive")

        if lawyer_profile.verification_status != "APPROVED":
            raise ValidationError("Lawyer is not verified for consultations")

        if target_date is None:
            target_date = datetime.now(self.IST_TIMEZONE).date()

        day_of_week = target_date.weekday()

        custom_availabilities = (
            self.db.query(LawyerAvailability)
            .filter(
                LawyerAvailability.lawyer_profile_id == lawyer_profile.id,
                LawyerAvailability.day_of_week == day_of_week,
                LawyerAvailability.is_active.is_(True),
            )
            .order_by(LawyerAvailability.start_time.asc())
            .all()
        )

        windows: list[tuple[time, time, int]] = []
        if custom_availabilities:
            for win in custom_availabilities:
                slot_dur = win.slot_duration_minutes or duration_minutes
                windows.append((win.start_time, win.end_time, slot_dur))
        else:
            # Standard business hours window for weekdays/Saturdays (08:00 to 20:00 IST)
            if day_of_week <= 5:  # Mon-Sat
                windows.append((time(8, 0), time(20, 0), duration_minutes))

        # Fetch existing active consultations for that lawyer on that target date
        day_start_ist = datetime.combine(target_date, time(0, 0), tzinfo=self.IST_TIMEZONE)
        day_end_ist = day_start_ist + timedelta(days=1)
        day_start_utc = day_start_ist.astimezone(UTC)
        day_end_utc = day_end_ist.astimezone(UTC)

        existing_consultations = (
            self.db.query(Consultation)
            .filter(
                Consultation.lawyer_id == lawyer_profile.id,
                Consultation.status.in_(self.BLOCKING_CONSULTATION_STATUSES),
                Consultation.deleted_at.is_(None),
                Consultation.scheduled_at >= day_start_utc - timedelta(hours=4),
                Consultation.scheduled_at <= day_end_utc + timedelta(hours=4),
            )
            .all()
        )

        booked_intervals = []
        for c in existing_consultations:
            c_start = c.scheduled_at if c.scheduled_at.tzinfo else c.scheduled_at.replace(tzinfo=UTC)
            c_end = c_start + timedelta(minutes=c.duration_minutes)
            booked_intervals.append((c_start, c_end))

        now_utc = datetime.now(UTC)
        slots = []

        for win_start, win_end, slot_dur in windows:
            curr_start = datetime.combine(target_date, win_start, tzinfo=self.IST_TIMEZONE).astimezone(UTC)
            win_end_utc = datetime.combine(target_date, win_end, tzinfo=self.IST_TIMEZONE).astimezone(UTC)

            while curr_start + timedelta(minutes=slot_dur) <= win_end_utc:
                curr_end = curr_start + timedelta(minutes=slot_dur)

                # Check if slot is in the past
                if curr_start <= now_utc:
                    is_avail = False
                else:
                    # Check overlap with booked consultations
                    is_avail = not any(
                        curr_start < b_end and b_start < curr_end
                        for b_start, b_end in booked_intervals
                    )

                slots.append(
                    {
                        "start_time": curr_start,
                        "end_time": curr_end,
                        "duration_minutes": slot_dur,
                        "is_available": is_avail,
                    }
                )
                curr_start = curr_end

        return slots

    def _assert_no_overlapping_consultation(
        self,
        lawyer_profile_id: uuid.UUID,
        req_start: datetime,
        req_end: datetime,
        exclude_consultation_id: uuid.UUID | None = None,
    ) -> None:
        query = self.db.query(Consultation).filter(
            Consultation.lawyer_id == lawyer_profile_id,
            Consultation.status.in_(self.BLOCKING_CONSULTATION_STATUSES),
            Consultation.deleted_at.is_(None),
            Consultation.scheduled_at < req_end,
        )
        if exclude_consultation_id:
            query = query.filter(Consultation.id != exclude_consultation_id)

        candidates = query.all()
        for existing in candidates:
            exist_start = existing.scheduled_at
            if exist_start.tzinfo is None:
                exist_start = exist_start.replace(tzinfo=UTC)
            else:
                exist_start = exist_start.astimezone(UTC)
            exist_end = exist_start + timedelta(minutes=existing.duration_minutes)

            # Strict interval intersection: [req_start, req_end) overlaps [exist_start, exist_end)
            if req_start < exist_end and exist_start < req_end:
                raise ValidationError(
                    "The requested time slot overlaps with an existing consultation for this lawyer"
                )

    def request_consultation(self, user: User, req: ConsultationCreate) -> Consultation:
        if user.role != UserRole.CLIENT:
            raise AuthorizationError("Only clients can request consultations")

        client_profile = (
            self.db.query(ClientProfile)
            .filter(ClientProfile.user_id == user.id)
            .first()
        )
        if not client_profile:
            raise ResourceNotFoundError("Client profile not found")

        # Acquire pessimistic row lock on lawyer profile for concurrency safety
        lawyer_profile = (
            self.db.query(LawyerProfile)
            .join(User, LawyerProfile.user_id == User.id)
            .filter(
                or_(
                    LawyerProfile.user_id == req.lawyer_id,
                    LawyerProfile.id == req.lawyer_id,
                ),
                User.account_status == AccountStatus.ACTIVE,
                LawyerProfile.deleted_at.is_(None),
            )
            .with_for_update()
            .first()
        )
        if not lawyer_profile:
            raise ResourceNotFoundError("Lawyer profile not found or inactive")

        if user.id == lawyer_profile.user_id:
            raise ValidationError("Clients cannot book consultations with themselves")

        if lawyer_profile.verification_status != "APPROVED":
            raise ValidationError(
                "Consultations can only be requested with verified lawyers"
            )

        req_start, req_end = self._validate_slot_and_business_hours(
            req.scheduled_at, req.duration_minutes, lawyer_profile_id=lawyer_profile.id
        )

        if req.case_id:
            # Case must exist and be OPEN/IN_PROGRESS
            case_ = (
                self.db.query(Case)
                .filter(Case.id == req.case_id, Case.deleted_at.is_(None))
                .first()
            )
            if not case_ or case_.status not in (
                CaseStatus.OPEN,
                CaseStatus.IN_PROGRESS,
            ):
                raise ValidationError(
                    "Consultations can only be linked to active cases"
                )
            # Authorize case access
            self.case_service.get_case_by_id(user, req.case_id)

        # Slot Overlap Protection
        self._assert_no_overlapping_consultation(lawyer_profile.id, req_start, req_end)

        consultation = Consultation(
            id=generate_uuid7(),
            client_id=client_profile.id,
            lawyer_id=lawyer_profile.id,
            case_id=req.case_id,
            scheduled_at=req_start,
            duration_minutes=req.duration_minutes,
            fee_amount=lawyer_profile.consultation_fee or 0.0,
            currency="INR",
            status=ConsultationStatus.REQUESTED,
        )
        try:
            self.db.add(consultation)
            self.db.commit()
            self.db.refresh(consultation)
        except IntegrityError:
            self.db.rollback()
            raise ValidationError(
                "The requested time slot overlaps with an existing consultation for this lawyer"
            ) from None

        self._log_audit(
            "CONSULTATION_REQUESTED",
            user.id,
            {
                "consultation_id": str(consultation.id),
                "case_id": str(req.case_id) if req.case_id else None,
                "lawyer_id": str(req.lawyer_id),
            },
        )

        if req.case_id:
            self.case_service.record_case_activity(
                req.case_id,
                user.id,
                "CONSULTATION_REQUESTED",
                "A consultation was requested",
                {"consultation_id": str(consultation.id)},
            )

        self.notification_service.create_notification(
            user_id=lawyer_profile.user_id,
            type=NotificationType.CONSULTATION_REQUESTED,
            title="Consultation Requested",
            message=f"New consultation requested for {consultation.scheduled_at.strftime('%Y-%m-%d %H:%M UTC')}.",
            consultation_id=consultation.id,
            case_id=req.case_id,
        )

        return consultation

    def get_consultation(self, user: User, consultation_id: uuid.UUID) -> Consultation:
        consultation = self._get_consultation(consultation_id)
        self._authorize_consultation_access(user, consultation)
        return consultation

    def get_consultations(
        self,
        user: User,
        case_id: uuid.UUID | None = None,
        status: ConsultationStatus | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> dict:
        limit = min(max(limit, 1), 100)
        query = self.db.query(Consultation).filter(Consultation.deleted_at.is_(None))

        if user.role != UserRole.ADMIN:
            if user.role == UserRole.CLIENT:
                client_profile = (
                    self.db.query(ClientProfile)
                    .filter(ClientProfile.user_id == user.id)
                    .first()
                )
                if not client_profile:
                    return {"items": [], "total": 0, "skip": skip, "limit": limit}
                query = query.filter(Consultation.client_id == client_profile.id)
            elif user.role == UserRole.LAWYER:
                lawyer_profile = (
                    self.db.query(LawyerProfile)
                    .filter(LawyerProfile.user_id == user.id)
                    .first()
                )
                if not lawyer_profile:
                    return {"items": [], "total": 0, "skip": skip, "limit": limit}
                query = query.filter(Consultation.lawyer_id == lawyer_profile.id)

        if case_id:
            if user.role != UserRole.ADMIN:
                self.case_service.get_case_by_id(user, case_id)
            query = query.filter(Consultation.case_id == case_id)

        if status is not None:
            query = query.filter(Consultation.status == status)

        total = query.count()
        query = query.order_by(Consultation.created_at.desc(), Consultation.id.desc())
        items = query.offset(skip).limit(limit).all()

        return {"items": items, "total": total, "skip": skip, "limit": limit}

    def accept_consultation(
        self, user: User, consultation_id: uuid.UUID
    ) -> Consultation:
        consultation = self._get_consultation(consultation_id)
        self._authorize_consultation_access(user, consultation)

        if user.role != UserRole.LAWYER and user.role != UserRole.ADMIN:
            raise AuthorizationError("Only lawyers can accept consultations")

        if consultation.status == ConsultationStatus.ACCEPTED:
            return consultation  # Idempotent

        if consultation.status != ConsultationStatus.REQUESTED:
            raise ValidationError(
                f"Cannot accept consultation in '{consultation.status.value}' state. Must be REQUESTED."
            )

        consultation.status = ConsultationStatus.ACCEPTED
        self.db.commit()
        self.db.refresh(consultation)

        self._log_audit(
            "CONSULTATION_ACCEPTED",
            user.id,
            {"consultation_id": str(consultation.id)},
        )

        if consultation.case_id:
            self.case_service.record_case_activity(
                consultation.case_id,
                user.id,
                "CONSULTATION_ACCEPTED",
                "Consultation was accepted by lawyer",
                {"consultation_id": str(consultation.id)},
            )

        self.notification_service.create_notification(
            user_id=consultation.client.user_id,
            type=NotificationType.CONSULTATION_ACCEPTED,
            title="Consultation Accepted",
            message="Your consultation request was accepted by the lawyer.",
            consultation_id=consultation.id,
            case_id=consultation.case_id,
            event_id=f"consultation_accepted_{consultation.id}",
        )

        return consultation

    def reject_consultation(
        self, user: User, consultation_id: uuid.UUID, reason: str | None = None
    ) -> Consultation:
        consultation = self._get_consultation(consultation_id)
        self._authorize_consultation_access(user, consultation)

        if user.role != UserRole.LAWYER and user.role != UserRole.ADMIN:
            raise AuthorizationError("Only lawyers can reject consultations")

        if consultation.status == ConsultationStatus.REJECTED:
            return consultation  # Idempotent

        if consultation.status != ConsultationStatus.REQUESTED:
            raise ValidationError(
                f"Cannot reject consultation in '{consultation.status.value}' state. Must be REQUESTED."
            )

        consultation.status = ConsultationStatus.REJECTED
        consultation.rejection_reason = reason
        self.db.commit()
        self.db.refresh(consultation)

        self._log_audit(
            "CONSULTATION_REJECTED",
            user.id,
            {"consultation_id": str(consultation.id), "reason": reason},
        )

        if consultation.case_id:
            self.case_service.record_case_activity(
                consultation.case_id,
                user.id,
                "CONSULTATION_REJECTED",
                "Consultation was rejected by lawyer",
                {"consultation_id": str(consultation.id), "reason": reason},
            )

        self.notification_service.create_notification(
            user_id=consultation.client.user_id,
            type=NotificationType.CONSULTATION_REJECTED,
            title="Consultation Rejected",
            message=f"Your consultation request was declined: {reason or 'No reason provided'}.",
            consultation_id=consultation.id,
            case_id=consultation.case_id,
            event_id=f"consultation_rejected_{consultation.id}",
        )

        return consultation

    def schedule_consultation(
        self,
        user: User,
        consultation_id: uuid.UUID,
        scheduled_at: datetime,
        duration_minutes: int | None = None,
    ) -> Consultation:
        consultation = self._get_consultation(consultation_id)
        self._authorize_consultation_access(user, consultation)

        if consultation.status in (
            ConsultationStatus.COMPLETED,
            ConsultationStatus.CANCELLED,
            ConsultationStatus.REJECTED,
            ConsultationStatus.NO_SHOW,
        ):
            raise ValidationError(
                f"Cannot schedule consultation in terminal '{consultation.status.value}' state"
            )

        dur = duration_minutes if (duration_minutes is not None and duration_minutes > 0) else consultation.duration_minutes
        req_start, req_end = self._validate_slot_and_business_hours(
            scheduled_at, dur, lawyer_profile_id=consultation.lawyer_id
        )

        # Overlap check excluding this consultation
        self._assert_no_overlapping_consultation(
            consultation.lawyer_id, req_start, req_end, exclude_consultation_id=consultation.id
        )

        # Fee status checks: Paid consultations must be ACCEPTED or PAID
        if consultation.fee_amount > 0 and consultation.status not in (
            ConsultationStatus.ACCEPTED,
            ConsultationStatus.PAID,
            ConsultationStatus.SCHEDULED,
        ):
            raise ValidationError(
                f"Cannot schedule paid consultation in '{consultation.status.value}' state. Must be ACCEPTED or PAID."
            )

        consultation.scheduled_at = req_start
        consultation.duration_minutes = dur
        consultation.status = ConsultationStatus.SCHEDULED
        self.db.commit()
        self.db.refresh(consultation)

        self._log_audit(
            "CONSULTATION_SCHEDULED",
            user.id,
            {
                "consultation_id": str(consultation.id),
                "scheduled_at": req_start.isoformat(),
            },
        )

        if consultation.case_id:
            self.case_service.record_case_activity(
                consultation.case_id,
                user.id,
                "CONSULTATION_SCHEDULED",
                "Consultation was scheduled",
                {"consultation_id": str(consultation.id)},
            )

        for uid in (consultation.client.user_id, consultation.lawyer.user_id):
            self.notification_service.create_notification(
                user_id=uid,
                type=NotificationType.CONSULTATION_SCHEDULED,
                title="Consultation Scheduled",
                message=f"Consultation is scheduled for {consultation.scheduled_at.strftime('%Y-%m-%d %H:%M UTC')}.",
                consultation_id=consultation.id,
                case_id=consultation.case_id,
                event_id=f"consultation_scheduled_{consultation.id}_{int(scheduled_at.timestamp())}_{uid}",
            )

        return consultation

    def reschedule_consultation(
        self,
        user: User,
        consultation_id: uuid.UUID,
        scheduled_at: datetime,
        duration_minutes: int | None = None,
        reason: str | None = None,
    ) -> Consultation:
        consultation = self._get_consultation(consultation_id)
        self._authorize_consultation_access(user, consultation)

        if consultation.status in (
            ConsultationStatus.COMPLETED,
            ConsultationStatus.CANCELLED,
            ConsultationStatus.REJECTED,
            ConsultationStatus.NO_SHOW,
        ):
            raise ValidationError(
                f"Cannot reschedule consultation in terminal '{consultation.status.value}' state"
            )

        dur = duration_minutes if (duration_minutes is not None and duration_minutes > 0) else consultation.duration_minutes
        req_start, req_end = self._validate_slot_and_business_hours(
            scheduled_at, dur, lawyer_profile_id=consultation.lawyer_id
        )

        # Pessimistic row lock to prevent race conditions during slot reassignment
        self.db.query(LawyerProfile).filter(LawyerProfile.id == consultation.lawyer_id).with_for_update().first()

        # Overlap check excluding this consultation
        self._assert_no_overlapping_consultation(
            consultation.lawyer_id, req_start, req_end, exclude_consultation_id=consultation.id
        )

        old_scheduled_at = consultation.scheduled_at
        consultation.scheduled_at = req_start
        consultation.duration_minutes = dur
        if consultation.status in (
            ConsultationStatus.ACCEPTED,
            ConsultationStatus.PAID,
            ConsultationStatus.SCHEDULED,
        ):
            consultation.status = ConsultationStatus.SCHEDULED

        self.db.commit()
        self.db.refresh(consultation)

        self._log_audit(
            "CONSULTATION_RESCHEDULED",
            user.id,
            {
                "consultation_id": str(consultation.id),
                "old_scheduled_at": old_scheduled_at.isoformat() if old_scheduled_at else None,
                "new_scheduled_at": req_start.isoformat(),
                "reason": reason or "",
            },
        )

        if consultation.case_id:
            self.case_service.record_case_activity(
                consultation.case_id,
                user.id,
                "CONSULTATION_RESCHEDULED",
                "Consultation was rescheduled",
                {"consultation_id": str(consultation.id), "new_scheduled_at": req_start.isoformat()},
            )

        for uid in (consultation.client.user_id, consultation.lawyer.user_id):
            self.notification_service.create_notification(
                user_id=uid,
                type=NotificationType.CONSULTATION_SCHEDULED,
                title="Consultation Rescheduled",
                message=f"Consultation was rescheduled to {consultation.scheduled_at.strftime('%Y-%m-%d %H:%M UTC')}.",
                consultation_id=consultation.id,
                case_id=consultation.case_id,
                event_id=f"consultation_rescheduled_{consultation.id}_{int(req_start.timestamp())}_{uid}",
            )

        return consultation

    def confirm_consultation(
        self, user: User, consultation_id: uuid.UUID
    ) -> Consultation:
        consultation = self._get_consultation(consultation_id)
        self._authorize_consultation_access(user, consultation)

        if user.role != UserRole.LAWYER and user.role != UserRole.ADMIN:
            raise AuthorizationError("Only lawyers can confirm consultations")

        # State machine enforcement
        if consultation.fee_amount > 0:
            if consultation.status not in (
                ConsultationStatus.PAID,
                ConsultationStatus.ACCEPTED,
            ):
                raise ValidationError(
                    f"Cannot confirm a non-free consultation in {consultation.status} state. It must be PAID or ACCEPTED."
                )
        else:
            if consultation.status not in (
                ConsultationStatus.REQUESTED,
                ConsultationStatus.ACCEPTED,
            ):
                raise ValidationError(
                    f"Cannot confirm free consultation in {consultation.status} state."
                )

        consultation.status = ConsultationStatus.SCHEDULED
        self.db.commit()
        self.db.refresh(consultation)

        self._log_audit(
            "CONSULTATION_ACCEPTED",
            user.id,
            {"consultation_id": str(consultation.id)},
        )

        if consultation.case_id:
            self.case_service.record_case_activity(
                consultation.case_id,
                user.id,
                "CONSULTATION_ACCEPTED",
                "Consultation was accepted",
                {"consultation_id": str(consultation.id)},
            )

        for uid in (consultation.client.user_id, consultation.lawyer.user_id):
            self.notification_service.create_notification(
                user_id=uid,
                type=NotificationType.CONSULTATION_SCHEDULED,
                title="Consultation Scheduled",
                message=f"Consultation is scheduled for {consultation.scheduled_at.strftime('%Y-%m-%d %H:%M UTC')}.",
                consultation_id=consultation.id,
                case_id=consultation.case_id,
            )

        return consultation

    def cancel_consultation(
        self, user: User, consultation_id: uuid.UUID, reason: str | None = None
    ) -> Consultation:
        consultation = self._get_consultation(consultation_id)
        self._authorize_consultation_access(user, consultation)

        if consultation.status == ConsultationStatus.CANCELLED:
            return consultation  # Idempotent

        if consultation.status in (
            ConsultationStatus.COMPLETED,
            ConsultationStatus.REJECTED,
            ConsultationStatus.NO_SHOW,
        ):
            raise ValidationError(
                f"Cannot cancel consultation in terminal '{consultation.status.value}' state"
            )

        consultation.status = ConsultationStatus.CANCELLED
        if reason:
            consultation.rejection_reason = reason
        self.db.commit()
        self.db.refresh(consultation)

        self._log_audit(
            "CONSULTATION_CANCELLED",
            user.id,
            {"consultation_id": str(consultation.id), "reason": reason},
        )

        if consultation.case_id:
            self.case_service.record_case_activity(
                consultation.case_id,
                user.id,
                "CONSULTATION_CANCELLED",
                "Consultation was cancelled",
                {"consultation_id": str(consultation.id)},
            )

        for uid in (consultation.client.user_id, consultation.lawyer.user_id):
            self.notification_service.create_notification(
                user_id=uid,
                type=NotificationType.CONSULTATION_CANCELLED,
                title="Consultation Cancelled",
                message=f"Consultation was cancelled: {reason or 'No reason provided'}.",
                consultation_id=consultation.id,
                case_id=consultation.case_id,
                event_id=f"consultation_cancelled_{consultation.id}_{uid}",
            )

        return consultation

    def mark_no_show(
        self, user: User, consultation_id: uuid.UUID, reason: str | None = None
    ) -> Consultation:
        consultation = self._get_consultation(consultation_id)
        self._authorize_consultation_access(user, consultation)

        if user.role not in (UserRole.LAWYER, UserRole.ADMIN):
            raise AuthorizationError(
                "Only the lawyer or administrator can mark a consultation as no-show"
            )

        if consultation.status == ConsultationStatus.NO_SHOW:
            return consultation  # Idempotent

        if consultation.status not in (
            ConsultationStatus.SCHEDULED,
            ConsultationStatus.IN_PROGRESS,
            ConsultationStatus.ACCEPTED,
            ConsultationStatus.PAID,
        ):
            raise ValidationError(
                f"Cannot mark consultation as no-show in '{consultation.status.value}' state"
            )

        consultation.status = ConsultationStatus.NO_SHOW
        consultation.rejection_reason = reason or "Participant did not attend"
        self.db.commit()
        self.db.refresh(consultation)

        self._log_audit(
            "CONSULTATION_NO_SHOW",
            user.id,
            {"consultation_id": str(consultation.id), "reason": reason or ""},
        )

        if consultation.case_id:
            self.case_service.record_case_activity(
                consultation.case_id,
                user.id,
                "CONSULTATION_NO_SHOW",
                "Consultation was marked as no-show",
                {"consultation_id": str(consultation.id)},
            )

        for uid in (consultation.client.user_id, consultation.lawyer.user_id):
            self.notification_service.create_notification(
                user_id=uid,
                type=NotificationType.CONSULTATION_CANCELLED,
                title="Consultation Marked No-Show",
                message=f"Consultation was marked as no-show: {reason or 'Participant did not attend'}.",
                consultation_id=consultation.id,
                case_id=consultation.case_id,
                event_id=f"consultation_noshow_{consultation.id}_{uid}",
            )

        return consultation

    def complete_consultation(
        self, user: User, consultation_id: uuid.UUID
    ) -> Consultation:
        consultation = self._get_consultation(consultation_id)
        self._authorize_consultation_access(user, consultation)

        if user.role not in (UserRole.ADMIN, UserRole.LAWYER):
            raise AuthorizationError(
                "Only the assigned lawyer or administrator can complete the consultation"
            )

        if consultation.status == ConsultationStatus.COMPLETED:
            return consultation  # Idempotent

        if consultation.status not in (
            ConsultationStatus.SCHEDULED,
            ConsultationStatus.IN_PROGRESS,
            ConsultationStatus.ACCEPTED,
            ConsultationStatus.PAID,
        ):
            raise ValidationError(
                f"Cannot complete consultation in '{consultation.status.value}' state. Must be SCHEDULED or IN_PROGRESS."
            )

        consultation.status = ConsultationStatus.COMPLETED
        consultation.completed_at = datetime.now(UTC)
        self.db.commit()
        self.db.refresh(consultation)

        self._log_audit(
            "CONSULTATION_COMPLETED",
            user.id,
            {"consultation_id": str(consultation.id)},
        )

        if consultation.case_id:
            self.case_service.record_case_activity(
                consultation.case_id,
                user.id,
                "CONSULTATION_COMPLETED",
                "Consultation was completed",
                {"consultation_id": str(consultation.id)},
            )

        self.notification_service.create_notification(
            user_id=consultation.client.user_id,
            type=NotificationType.CONSULTATION_COMPLETED,
            title="Consultation Completed",
            message="Your consultation has concluded.",
            consultation_id=consultation.id,
            case_id=consultation.case_id,
            event_id=f"consultation_completed_{consultation.id}",
        )

        return consultation
