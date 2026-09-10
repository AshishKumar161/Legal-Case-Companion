import asyncio
import logging
import uuid
from datetime import UTC, date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Any, ClassVar

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import (
    AuthorizationError,
    ResourceNotFoundError,
    ValidationError,
)
from app.core.identifiers import generate_uuid7
from app.models.availability import LawyerAvailability
from app.models.case import (
    Case,
    CaseParticipant,
    CaseStatus,
    ParticipantRole,
    ParticipantStatus,
)
from app.models.consultation import Consultation, ConsultationStatus
from app.models.notification import NotificationType
from app.models.user import AccountStatus, ClientProfile, LawyerProfile, User, UserRole
from app.models.video_meeting import VideoMeeting, VideoMeetingStatus
from app.schemas.consultation import ConsultationCreate
from app.schemas.presence import PresenceStatus
from app.domain.auth.auth_service import AuthService
from app.domain.cases.case_service import CaseService
from app.domain.consultations.lawyer_call_channel import incoming_call_channel_manager
from app.domain.notifications.notification_service import NotificationService
from app.domain.consultations.presence_service import presence_service

logger = logging.getLogger(__name__)


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

    def _get_consultation(
        self, consultation_id: uuid.UUID, for_update: bool = False
    ) -> Consultation:
        query = self.db.query(Consultation).filter(
            Consultation.id == consultation_id, Consultation.deleted_at.is_(None)
        )
        if for_update:
            query = query.with_for_update()
        consultation = query.first()
        if not consultation:
            raise ResourceNotFoundError("Consultation not found")
        return consultation

    @staticmethod
    def _dispatch_async(coro: Any) -> None:
        """Safely schedule an asyncio coroutine from either async or sync contexts."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(coro)
        except RuntimeError:
            try:
                new_loop = asyncio.new_event_loop()
                new_loop.run_until_complete(coro)
                new_loop.close()
            except Exception as e:
                logger.warning("Failed to dispatch async notification: %s", e)

    def expire_stale_incoming_calls(
        self, lawyer_profile_id: uuid.UUID | None = None
    ) -> list[Consultation]:
        """Automatically expire instant consultations waiting past the ring timeout."""
        cutoff = datetime.now(UTC) - timedelta(
            seconds=settings.INSTANT_CALL_RING_TIMEOUT_SECONDS
        )
        query = self.db.query(Consultation).filter(
            Consultation.status.in_([ConsultationStatus.REQUESTED, ConsultationStatus.PAID]),
            Consultation.deleted_at.is_(None),
            Consultation.created_at < cutoff,
        )
        if lawyer_profile_id:
            query = query.filter(Consultation.lawyer_id == lawyer_profile_id)

        expired_list = []
        for con in query.all():
            is_instant_call = (
                getattr(con, "is_instant", False)
                or con.status == ConsultationStatus.PAID
                or (con.scheduled_at and con.created_at and abs((con.scheduled_at - con.created_at).total_seconds()) <= 900)
            )
            if is_instant_call:
                con.status = ConsultationStatus.CANCELLED
                con.rejection_reason = "Instant call timed out with no response from lawyer"
                expired_list.append(con)
                self._dispatch_async(
                    incoming_call_channel_manager.notify_call_expired(con.lawyer_id, con.id)
                )

        if expired_list:
            try:
                self.db.commit()
            except Exception as e:
                logger.warning("Failed committing expired calls: %s", e)
                self.db.rollback()

        return expired_list

    def is_lawyer_available(
        self,
        lawyer_profile_id: uuid.UUID,
    ) -> tuple[bool, str, PresenceStatus]:
        """Authoritatively evaluate whether a lawyer is available for instant consultations.

        Returns (is_available, reason, presence_status).
        """
        self.expire_stale_incoming_calls(lawyer_profile_id)

        lawyer_profile = (
            self.db.query(LawyerProfile)
            .join(User, LawyerProfile.user_id == User.id)
            .filter(
                or_(
                    LawyerProfile.id == lawyer_profile_id,
                    LawyerProfile.user_id == lawyer_profile_id,
                ),
                User.account_status == AccountStatus.ACTIVE,
                LawyerProfile.deleted_at.is_(None),
            )
            .first()
        )
        if not lawyer_profile:
            return False, "Lawyer account is inactive or not found", PresenceStatus.OFFLINE

        if lawyer_profile.verification_status != "APPROVED":
            return False, "Lawyer is not verified", PresenceStatus.ONLINE

        has_presence = presence_service.is_online(lawyer_profile.user_id)
        if has_presence:
            if not presence_service.is_available_preference(lawyer_profile.user_id):
                return False, "Lawyer is not accepting instant calls", PresenceStatus.ONLINE
        else:
            if getattr(settings, "ENVIRONMENT", "").lower() != "development":
                return False, "Lawyer is currently offline", PresenceStatus.OFFLINE

        # Check for active in-progress consultation
        active_consultation = (
            self.db.query(Consultation)
            .filter(
                Consultation.lawyer_id == lawyer_profile.id,
                Consultation.status == ConsultationStatus.IN_PROGRESS,
                Consultation.deleted_at.is_(None),
            )
            .first()
        )
        if active_consultation:
            return False, "Lawyer is currently active in another consultation", PresenceStatus.BUSY

        # Check for active video meeting
        now_utc = datetime.now(UTC)
        active_meeting = (
            self.db.query(VideoMeeting)
            .join(Consultation, VideoMeeting.consultation_id == Consultation.id)
            .filter(
                Consultation.lawyer_id == lawyer_profile.id,
                VideoMeeting.status == VideoMeetingStatus.ACTIVE,
                VideoMeeting.ended_at.is_(None),
                VideoMeeting.scheduled_end >= now_utc - timedelta(minutes=120),
                Consultation.status.in_([
                    ConsultationStatus.IN_PROGRESS,
                    ConsultationStatus.SCHEDULED,
                    ConsultationStatus.PAID,
                ]),
                Consultation.deleted_at.is_(None),
            )
            .first()
        )
        if active_meeting:
            return False, "Lawyer is currently in an active video meeting", PresenceStatus.BUSY

        # Check for pending ringing instant calls within timeout window
        ring_cutoff = datetime.now(UTC) - timedelta(
            seconds=settings.INSTANT_CALL_RING_TIMEOUT_SECONDS
        )
        pending_call = (
            self.db.query(Consultation)
            .filter(
                Consultation.lawyer_id == lawyer_profile.id,
                Consultation.status.in_([ConsultationStatus.REQUESTED, ConsultationStatus.PAID]),
                Consultation.created_at >= ring_cutoff,
                Consultation.deleted_at.is_(None),
            )
            .first()
        )
        if pending_call:
            is_instant_call = (
                getattr(pending_call, "is_instant", False)
                or pending_call.status == ConsultationStatus.PAID
                or (pending_call.scheduled_at and pending_call.created_at and abs((pending_call.scheduled_at - pending_call.created_at).total_seconds()) <= 900)
            )
            if is_instant_call:
                return False, "Lawyer is currently receiving another incoming call", PresenceStatus.BUSY

        return True, "Available", PresenceStatus.AVAILABLE

    def _authorize_consultation_access(self, user: User, consultation: Consultation):
        from app.core.authorization import authorize_consultation_access

        authorize_consultation_access(self.db, user, consultation.id)

    def _validate_slot_and_business_hours(
        self,
        scheduled_at: datetime,
        duration_minutes: int,
        lawyer_profile_id: uuid.UUID | None = None,
        is_instant: bool = False,
    ) -> tuple[datetime, datetime]:
        if duration_minutes <= 0 or duration_minutes > 240:
            raise ValidationError("Duration must be between 1 and 240 minutes")

        # Normalize timezone to UTC-aware
        if scheduled_at.tzinfo is None:
            req_start = scheduled_at.replace(tzinfo=UTC)
        else:
            req_start = scheduled_at.astimezone(UTC)

        now_utc = datetime.now(UTC)

        # If instant consultation, clamp to now or allow within 5-minute past buffer for clock drift
        if is_instant:
            if req_start < now_utc - timedelta(minutes=10):
                req_start = now_utc
        else:
            # Allow 5-minute grace period for network latency / client clock slight drift
            if req_start < now_utc - timedelta(minutes=5):
                now_ist_str = now_utc.astimezone(self.IST_TIMEZONE).strftime("%I:%M %p IST")
                raise ValidationError(
                    f"Consultation must be scheduled for a future time (Current Indian Time: {now_ist_str})"
                )

        req_end = req_start + timedelta(minutes=duration_minutes)

        ist_start = req_start.astimezone(self.IST_TIMEZONE)
        ist_end = req_end.astimezone(self.IST_TIMEZONE)

        if not is_instant and ist_start.date() != ist_end.date():
            raise ValidationError(
                "Consultation cannot span across multiple calendar days"
            )

        # For instant consultations, bypass static availability windows if both parties are present
        if is_instant:
            return req_start, req_end

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

        # Default business hours (08:00 to 21:00 IST)
        if ist_start.hour < 8:
            raise ValidationError(
                "Consultation must start within standard business hours (08:00 to 21:00 IST)"
            )

        if ist_end.hour > 21 or (
            ist_end.hour == 21 and (ist_end.minute > 0 or ist_end.second > 0)
        ):
            raise ValidationError(
                "Consultation must conclude within standard business hours (08:00 to 21:00 IST)"
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
        is_instant: bool = False,
    ) -> None:
        blocking_statuses = (
            [ConsultationStatus.IN_PROGRESS]
            if is_instant
            else self.BLOCKING_CONSULTATION_STATUSES
        )
        query = self.db.query(Consultation).filter(
            Consultation.lawyer_id == lawyer_profile_id,
            Consultation.status.in_(blocking_statuses),
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
                conflict_msg = (
                    "Lawyer is currently active in another video consultation"
                    if is_instant
                    else "The requested time slot overlaps with an existing consultation for this lawyer"
                )
                raise ValidationError(conflict_msg)

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

        # Enforce consultation velocity protection against request flooding
        from app.domain.governance.abuse_defense_service import AbuseDefenseService

        abuse_svc = AbuseDefenseService(self.db)
        velocity_check = abuse_svc.check_consultation_velocity(client_profile.id)
        if not velocity_check["allowed"]:
            raise ValidationError(velocity_check["reason"])

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

        if req.is_instant:
            is_avail, reason, p_status = self.is_lawyer_available(lawyer_profile.id)
            if not is_avail:
                raise ValidationError(
                    f"Lawyer is currently unavailable for instant consultation: {reason}"
                )

        if req.is_instant:
            scheduled_at_to_use = datetime.now(UTC)
        elif req.scheduled_at is None:
            # Default to tomorrow at 10:00 AM IST (or Monday if weekend)
            now_ist = datetime.now(self.IST_TIMEZONE)
            sched_date = (now_ist + timedelta(days=1)).date()
            if sched_date.weekday() == 6:  # Sunday
                sched_date += timedelta(days=1)
            scheduled_at_to_use = datetime.combine(
                sched_date, time(10, 0), tzinfo=self.IST_TIMEZONE
            ).astimezone(UTC)
        else:
            scheduled_at_to_use = req.scheduled_at

        req_start, req_end = self._validate_slot_and_business_hours(
            scheduled_at_to_use,
            req.duration_minutes,
            lawyer_profile_id=lawyer_profile.id,
            is_instant=req.is_instant,
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
        self._assert_no_overlapping_consultation(
            lawyer_profile.id, req_start, req_end, is_instant=req.is_instant
        )

        consultation = Consultation(
            id=generate_uuid7(),
            client_id=client_profile.id,
            lawyer_id=lawyer_profile.id,
            case_id=req.case_id,
            scheduled_at=req_start,
            duration_minutes=req.duration_minutes,
            is_instant=req.is_instant,
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

        # Automatically provision video meeting room
        try:
            from app.domain.consultations.video_meeting_service import VideoMeetingService
            vms = VideoMeetingService(self.db)
            vms.ensure_meeting_provisioned(consultation)
        except Exception as e:
            logger.warning("Could not auto-provision meeting: %s", e)

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

        # Dispatch real-time incoming call alert via WebSocket for instant consultations
        if req.is_instant:
            client_name = client_profile.full_name if client_profile else "Prospective Client"
            call_data = {
                "id": str(consultation.id),
                "client_name": client_name,
                "fee": float(consultation.fee_amount),
                "case_id": str(consultation.case_id) if consultation.case_id else None,
                "scheduled_at": consultation.scheduled_at.isoformat() if consultation.scheduled_at else None,
                "created_at": consultation.created_at.isoformat() if consultation.created_at else None,
                "ring_timeout_seconds": settings.INSTANT_CALL_RING_TIMEOUT_SECONDS,
            }
            self._dispatch_async(
                incoming_call_channel_manager.notify_incoming_call(
                    lawyer_profile.id, call_data
                )
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
        consultation = self._get_consultation(consultation_id, for_update=True)
        self._authorize_consultation_access(user, consultation)

        if user.role != UserRole.LAWYER and user.role != UserRole.ADMIN:
            raise AuthorizationError("Only lawyers can accept consultations")

        if consultation.status in (
            ConsultationStatus.ACCEPTED,
            ConsultationStatus.PAID,
            ConsultationStatus.SCHEDULED,
            ConsultationStatus.IN_PROGRESS,
        ):
            return consultation  # Idempotent - already authorized

        if consultation.status != ConsultationStatus.REQUESTED:
            raise ValidationError(
                f"Cannot accept consultation in '{consultation.status.value}' state. Must be REQUESTED."
            )

        consultation.status = ConsultationStatus.ACCEPTED
        self.db.commit()
        self.db.refresh(consultation)

        # Mark lawyer presence as busy and notify all tabs of lawyer
        lawyer_user_id = consultation.lawyer.user_id if consultation.lawyer else user.id
        presence_service.mark_busy(lawyer_user_id, consultation.lawyer_id, reason="In consultation")
        self._dispatch_async(
            incoming_call_channel_manager.notify_call_accepted(
                consultation.lawyer_id, consultation.id
            )
        )

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
        consultation = self._get_consultation(consultation_id, for_update=True)
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

        # Notify lawyer tabs that this call was rejected/cleared
        self._dispatch_async(
            incoming_call_channel_manager.notify_call_cancelled(
                consultation.lawyer_id, consultation.id, reason=reason or "Rejected by lawyer"
            )
        )

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
        consultation = self._get_consultation(consultation_id, for_update=True)
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

        from app.domain.consultations.video_meeting_service import VideoMeetingService
        VideoMeetingService(self.db).ensure_meeting_provisioned(consultation)

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
        consultation = self._get_consultation(consultation_id, for_update=True)
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
        consultation = self._get_consultation(consultation_id, for_update=True)
        self._authorize_consultation_access(user, consultation)

        if user.role != UserRole.LAWYER and user.role != UserRole.ADMIN:
            raise AuthorizationError("Only lawyers can confirm consultations")

        if consultation.status == ConsultationStatus.SCHEDULED:
            return consultation  # Idempotent

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

        from app.domain.consultations.video_meeting_service import VideoMeetingService
        VideoMeetingService(self.db).ensure_meeting_provisioned(consultation)

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
                event_id=f"consultation_confirmed_{consultation.id}_{uid}",
            )

        return consultation

    def cancel_consultation(
        self, user: User, consultation_id: uuid.UUID, reason: str | None = None
    ) -> Consultation:
        consultation = self._get_consultation(consultation_id, for_update=True)
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
        if consultation.video_meeting and consultation.video_meeting.status != VideoMeetingStatus.ENDED:
            consultation.video_meeting.status = VideoMeetingStatus.CANCELLED
            if not consultation.video_meeting.ended_at:
                consultation.video_meeting.ended_at = datetime.now(UTC)
        self.db.commit()
        self.db.refresh(consultation)

        # Notify lawyer tabs that incoming call was cancelled
        self._dispatch_async(
            incoming_call_channel_manager.notify_call_cancelled(
                consultation.lawyer_id, consultation.id, reason=reason or "Cancelled"
            )
        )

        # Authoritative cancellation economics & refund calculation
        from app.models.commercial import CommercialTransaction, TransactionStatus
        from app.domain.payments.cancellation_policy_service import CancellationPolicyService
        from app.domain.payments.commercial_service import CommercialService

        policy_svc = CancellationPolicyService(self.db)
        economics = policy_svc.evaluate_cancellation_economics(
            consultation=consultation,
            actor=user,
            reason=reason,
        )

        if economics.refund_eligible and economics.refund_amount > Decimal("0.00"):
            txn = (
                self.db.query(CommercialTransaction)
                .filter(CommercialTransaction.consultation_id == consultation.id)
                .first()
            )
            if txn and txn.status in (TransactionStatus.CAPTURED, TransactionStatus.AUTHORIZED):
                try:
                    commercial_svc = CommercialService(self.db)
                    commercial_svc.process_refund(
                        transaction_identifier=txn.id,
                        refund_amount=float(economics.refund_amount),
                        reason=economics.reason_classification,
                        actor=user,
                    )
                except Exception as e:
                    logger.warning(
                        "Automatic cancellation refund failed for consultation %s: %s",
                        consultation.id,
                        e,
                    )

        self._log_audit(
            "CONSULTATION_CANCELLED",
            user.id,
            {
                "consultation_id": str(consultation.id),
                "reason": reason,
                "refund_eligible": economics.refund_eligible,
                "refund_amount": str(economics.refund_amount),
                "is_late_cancellation": economics.is_late_cancellation,
                "policy_mode": economics.policy_mode,
            },
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
        consultation = self._get_consultation(consultation_id, for_update=True)
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

        now_utc = datetime.now(UTC)
        consultation.status = ConsultationStatus.NO_SHOW
        consultation.rejection_reason = reason or "Participant did not attend"

        if consultation.video_meeting and consultation.video_meeting.status != VideoMeetingStatus.ENDED:
            consultation.video_meeting.status = VideoMeetingStatus.CANCELLED
            if not consultation.video_meeting.ended_at:
                consultation.video_meeting.ended_at = now_utc

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
        consultation = self._get_consultation(consultation_id, for_update=True)
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

        now_utc = datetime.now(UTC)
        consultation.status = ConsultationStatus.COMPLETED
        consultation.completed_at = now_utc

        if consultation.video_meeting and consultation.video_meeting.status != VideoMeetingStatus.ENDED:
            consultation.video_meeting.status = VideoMeetingStatus.ENDED
            consultation.video_meeting.ended_at = now_utc

        # Automatically finalize or stop any active recordings belonging to this consultation
        from app.models.video_recording import VideoRecording, VideoRecordingStatus
        active_recordings = (
            self.db.query(VideoRecording)
            .filter(
                VideoRecording.consultation_id == consultation.id,
                VideoRecording.status.in_([
                    VideoRecordingStatus.RECORDING,
                    VideoRecordingStatus.PENDING,
                ]),
                VideoRecording.deleted_at.is_(None),
            )
            .all()
        )
        for rec in active_recordings:
            rec.status = VideoRecordingStatus.UPLOADING
            rec.ended_at = now_utc
            if rec.started_at:
                s_at = rec.started_at.replace(tzinfo=UTC) if rec.started_at.tzinfo is None else rec.started_at
                rec.duration_seconds = max(1, int((now_utc - s_at).total_seconds()))

        self.db.commit()
        self.db.refresh(consultation)

        # Broadcast consultation-ended signaling event to all active peers in room
        if consultation.video_meeting:
            try:
                from app.domain.consultations.video_signaling_manager import signaling_manager
                payload = {
                    "type": "consultation-ended",
                    "consultation_id": str(consultation.id),
                    "meeting_id": str(consultation.video_meeting.id),
                    "ended_by": str(user.id),
                    "ended_at": now_utc.isoformat(),
                }
                self._dispatch_async(signaling_manager.broadcast_to_room(consultation.video_meeting.room_id, None, payload))
            except Exception as e:
                logger.warning("Could not broadcast consultation-ended event: %s", e)

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

    def link_case(
        self,
        user: User,
        consultation_id: uuid.UUID,
        case_id: uuid.UUID,
        assign_lawyer: bool = True,
    ) -> Consultation:
        """Link a consultation to an active legal case and assign lawyer if requested."""
        consultation = self._get_consultation(consultation_id)
        self._authorize_consultation_access(user, consultation)

        if user.role != UserRole.CLIENT and user.role != UserRole.ADMIN:
            raise AuthorizationError("Only clients or admins can link consultations to cases")

        if user.role == UserRole.CLIENT and consultation.client.user_id != user.id:
            raise AuthorizationError("Only the consultation client can link this consultation to a case")

        if assign_lawyer:
            from app.core.authorization import authorize_participant_management

            target_case = authorize_participant_management(self.db, user, case_id)
        else:
            from app.core.authorization import authorize_case_modification

            target_case = authorize_case_modification(self.db, user, case_id)

        if not target_case or target_case.status in (CaseStatus.CLOSED, CaseStatus.CANCELLED):
            raise ValidationError("Cannot link consultation to an inactive or closed case")

        if consultation.case_id and consultation.case_id != case_id:
            raise ValidationError("Consultation is already linked to another legal case matter")

        consultation.case_id = case_id

        # If assign_lawyer, assign the lawyer as a LAWYER participant to the case
        if assign_lawyer and consultation.lawyer:
            lawyer_user_id = consultation.lawyer.user_id
            existing_participant = (
                self.db.query(CaseParticipant)
                .filter(
                    CaseParticipant.case_id == case_id,
                    CaseParticipant.user_id == lawyer_user_id,
                )
                .first()
            )
            if not existing_participant:
                lawyer_part = CaseParticipant(
                    id=generate_uuid7(),
                    case_id=case_id,
                    user_id=lawyer_user_id,
                    participant_role=ParticipantRole.LAWYER,
                    status=ParticipantStatus.ACTIVE,
                    joined_at=datetime.now(UTC),
                )
                self.db.add(lawyer_part)
            elif existing_participant.status != ParticipantStatus.ACTIVE:
                existing_participant.status = ParticipantStatus.ACTIVE

        self.db.commit()
        self.db.refresh(consultation)

        self._log_audit(
            "CONSULTATION_LINKED_TO_CASE",
            user.id,
            {"consultation_id": str(consultation.id), "case_id": str(case_id)},
        )

        self.case_service.record_case_activity(
            case_id,
            user.id,
            "CONSULTATION_LINKED",
            "A consultation was linked to this case matter",
            {"consultation_id": str(consultation.id)},
        )
        return consultation

    def create_case_from_consultation(
        self,
        user: User,
        consultation_id: uuid.UUID,
        title: str,
        description: str | None = None,
        practice_area: str | None = None,
        court_jurisdiction: str | None = None,
    ) -> Case:
        """Create a new legal case from a consultation and assign client and lawyer."""
        consultation = self._get_consultation(consultation_id)
        self._authorize_consultation_access(user, consultation)

        if user.role != UserRole.CLIENT and user.role != UserRole.ADMIN:
            raise AuthorizationError("Only clients or admins can create cases from consultations")

        if user.role == UserRole.CLIENT and consultation.client.user_id != user.id:
            raise AuthorizationError("Only the consultation client can create a case from this consultation")

        if consultation.case_id:
            raise ValidationError("Consultation is already linked to an existing legal case matter")

        desc = description or f"Matter established following consultation with Advocate {consultation.lawyer.full_name if consultation.lawyer else 'Counsel'}."
        meta_items = []
        if practice_area:
            meta_items.append(f"Practice Area: {practice_area}")
        if court_jurisdiction:
            meta_items.append(f"Jurisdiction: {court_jurisdiction}")
        if meta_items:
            desc += f"\n[{', '.join(meta_items)}]"

        from app.schemas.case import CaseCreate
        case_in = CaseCreate(
            title=title,
            description=desc,
        )

        new_case = self.case_service.create_case(user, case_in)
        consultation.case_id = new_case.id

        # Assign lawyer as LAWYER participant
        if consultation.lawyer:
            lawyer_user_id = consultation.lawyer.user_id
            existing_participant = (
                self.db.query(CaseParticipant)
                .filter(
                    CaseParticipant.case_id == new_case.id,
                    CaseParticipant.user_id == lawyer_user_id,
                )
                .first()
            )
            if not existing_participant:
                lawyer_part = CaseParticipant(
                    id=generate_uuid7(),
                    case_id=new_case.id,
                    user_id=lawyer_user_id,
                    participant_role=ParticipantRole.LAWYER,
                    status=ParticipantStatus.ACTIVE,
                    joined_at=datetime.now(UTC),
                )
                self.db.add(lawyer_part)

        self.db.commit()
        self.db.refresh(consultation)
        self.db.refresh(new_case)

        self._log_audit(
            "CASE_CREATED_FROM_CONSULTATION",
            user.id,
            {"consultation_id": str(consultation.id), "case_id": str(new_case.id)},
        )

        self.case_service.record_case_activity(
            new_case.id,
            user.id,
            "CASE_ESTABLISHED_FROM_CONSULTATION",
            f"Case matter was formally established following consultation with Advocate {consultation.lawyer.full_name if consultation.lawyer else 'counsel'}",
            {"consultation_id": str(consultation.id)},
        )

        return new_case

    def add_consultation_note(
        self,
        user: User,
        consultation_id: uuid.UUID,
        summary: str,
        action_items: list[str] | None = None,
        client_shared: bool = True,
    ):
        consultation = self._get_consultation(consultation_id)
        self._authorize_consultation_access(user, consultation)

        if not summary or not summary.strip():
            raise ValidationError("Consultation note summary cannot be empty")
        if len(summary) > 10000:
            raise ValidationError("Consultation note summary cannot exceed 10000 characters")

        # Clients cannot create lawyer-private notes
        effective_shared = client_shared
        if user.role == UserRole.CLIENT:
            effective_shared = True

        from app.models.consultation_note import ConsultationNote
        note = ConsultationNote(
            id=generate_uuid7(),
            consultation_id=consultation.id,
            author_user_id=user.id,
            summary=summary.strip(),
            action_items=action_items or [],
            client_shared=effective_shared,
        )
        self.db.add(note)
        self.db.commit()
        self.db.refresh(note)

        self._log_audit(
            "CONSULTATION_NOTE_ADDED",
            user.id,
            {"consultation_id": str(consultation.id), "note_id": str(note.id)},
        )
        return note

    def get_consultation_notes(
        self, user: User, consultation_id: uuid.UUID
    ) -> list:
        consultation = self._get_consultation(consultation_id)
        self._authorize_consultation_access(user, consultation)

        from app.models.consultation_note import ConsultationNote
        query = self.db.query(ConsultationNote).filter(
            ConsultationNote.consultation_id == consultation.id
        )
        if user.role == UserRole.CLIENT:
            query = query.filter(ConsultationNote.client_shared.is_(True))

        return query.order_by(ConsultationNote.created_at.desc()).all()
