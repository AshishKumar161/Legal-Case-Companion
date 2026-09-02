import hashlib
import hmac
import json
import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import (
    AuthorizationError,
    ResourceNotFoundError,
    ValidationError,
)
from app.core.identifiers import generate_uuid7
from app.models.consultation import Consultation, ConsultationStatus
from app.models.notification import NotificationType
from app.models.user import User, UserRole
from app.models.video_meeting import VideoMeeting, VideoMeetingStatus
from app.schemas.video_meeting import VideoJoinInfoResponse
from app.services.auth_service import AuthService
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)


class VideoMeetingProvider(Protocol):
    def create_meeting_room(self, consultation: Consultation) -> dict[str, Any]: ...
    def generate_access_token(
        self, user: User, meeting: VideoMeeting, role: str, expires_in_seconds: int = 7200
    ) -> str: ...
    def verify_access_token(
        self,
        token: str,
        expected_room_id: str | None = None,
        expected_user_id: uuid.UUID | str | None = None,
        expected_consultation_id: uuid.UUID | str | None = None,
    ) -> dict[str, Any]: ...


class InternalWebRTCMeetingProvider:
    """Production-grade WebRTC meeting provider with cryptographic HMAC-SHA256 join tokens."""

    def create_meeting_room(self, consultation: Consultation) -> dict[str, Any]:
        room_id = f"lcc-room-{consultation.id.hex[:12]}-{generate_uuid7().hex[:6]}"
        ice_servers: list[dict[str, Any]] = [
            {"urls": "stun:stun.l.google.com:19302"},
            {"urls": "stun:stun1.l.google.com:19302"},
        ]
        if getattr(settings, "TURN_SERVER_URL", None):
            turn_entry: dict[str, Any] = {"urls": settings.TURN_SERVER_URL}
            if getattr(settings, "TURN_USERNAME", None):
                turn_entry["username"] = settings.TURN_USERNAME
            if getattr(settings, "TURN_CREDENTIAL", None):
                turn_entry["credential"] = settings.TURN_CREDENTIAL
            ice_servers.append(turn_entry)

        return {
            "room_id": room_id,
            "provider": "internal_webrtc",
            "ice_servers": ice_servers,
        }

    def generate_access_token(
        self, user: User, meeting: VideoMeeting, role: str, expires_in_seconds: int = 7200
    ) -> str:
        now_dt = datetime.now(UTC)
        exp = int((now_dt + timedelta(seconds=expires_in_seconds)).timestamp())
        payload = {
            "jti": uuid.uuid4().hex,
            "iat": int(now_dt.timestamp()),
            "room_id": meeting.room_id,
            "meeting_id": str(meeting.id),
            "consultation_id": str(meeting.consultation_id),
            "user_id": str(user.id),
            "role": role,
            "exp": exp,
        }
        secret = getattr(settings, "SECRET_KEY", None) or getattr(settings, "JWT_PRIVATE_KEY", None) or "lcc-secure-video-secret-key"
        encoded_payload = json.dumps(payload, sort_keys=True).encode("utf-8")
        signature = hmac.new(secret.encode("utf-8"), encoded_payload, hashlib.sha256).hexdigest()
        token = f"{signature}.{encoded_payload.hex()}"
        return token

    def verify_access_token(
        self,
        token: str,
        expected_room_id: str | None = None,
        expected_user_id: uuid.UUID | str | None = None,
        expected_consultation_id: uuid.UUID | str | None = None,
    ) -> dict[str, Any]:
        """Cryptographically verifies HMAC-SHA256 signature, expiry, and context binding of video join token."""
        if not token or "." not in token:
            raise ValidationError("Invalid video token format")

        parts = token.split(".", 1)
        if len(parts) != 2:
            raise ValidationError("Invalid video token format")

        signature, payload_hex = parts[0], parts[1]
        secret = getattr(settings, "SECRET_KEY", None) or getattr(settings, "JWT_PRIVATE_KEY", None) or "lcc-secure-video-secret-key"

        try:
            raw_payload = bytes.fromhex(payload_hex)
        except ValueError:
            raise ValidationError("Malformed video token hex payload")

        expected_sig = hmac.new(secret.encode("utf-8"), raw_payload, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected_sig):
            raise ValidationError("Tampered or invalid video token signature")

        try:
            payload: dict[str, Any] = json.loads(raw_payload.decode("utf-8"))
        except Exception as e:
            raise ValidationError("Malformed JSON in video token payload") from e

        # Check expiry
        now_ts = int(datetime.now(UTC).timestamp())
        if payload.get("exp", 0) < now_ts:
            raise ValidationError("Video access token has expired")

        # Contextual bindings
        if expected_room_id and payload.get("room_id") != expected_room_id:
            raise ValidationError("Video token is not authorized for this meeting room")

        if expected_user_id and str(payload.get("user_id")) != str(expected_user_id):
            raise ValidationError("Video token does not belong to this participant")

        if expected_consultation_id and str(payload.get("consultation_id")) != str(expected_consultation_id):
            raise ValidationError("Video token does not match this consultation")

        return payload


class MockVideoMeetingProvider:
    """Deterministic video provider for development and testing."""

    def create_meeting_room(self, consultation: Consultation) -> dict[str, Any]:
        return {
            "room_id": f"mock-room-{consultation.id}",
            "provider": "mock",
            "ice_servers": [{"urls": "stun:mock-stun.local"}],
        }

    def generate_access_token(
        self, user: User, meeting: VideoMeeting, role: str, expires_in_seconds: int = 7200
    ) -> str:
        return f"mock_token_{user.id}_{meeting.id}_{role}"

    def verify_access_token(
        self,
        token: str,
        expected_room_id: str | None = None,
        expected_user_id: uuid.UUID | str | None = None,
        expected_consultation_id: uuid.UUID | str | None = None,
    ) -> dict[str, Any]:
        if not token.startswith("mock_token_"):
            raise ValidationError("Invalid mock token")
        return {"provider": "mock", "valid": True}


def get_video_provider() -> VideoMeetingProvider:
    if settings.ENVIRONMENT == "production":
        return InternalWebRTCMeetingProvider()
    return InternalWebRTCMeetingProvider()


class VideoMeetingService:
    EARLY_JOIN_WINDOW_MINUTES = 15
    POST_END_GRACE_PERIOD_MINUTES = 120

    def __init__(self, db: Session):
        self.db = db
        self.auth_service = AuthService(db)
        self.notification_service = NotificationService(db)
        self.provider = get_video_provider()

    def _log_audit(self, event_type: str, user_id: uuid.UUID, metadata: dict[str, Any]):
        self.auth_service.log_audit_event(
            event_type, user_id, metadata, action="video_meeting_mutation"
        )

    def _authorize_participant(self, user: User, consultation: Consultation) -> str:
        """Enforce strict BOLA authorization and return role in the meeting."""
        if user.role == UserRole.ADMIN:
            return "ADMIN"

        if consultation.client and consultation.client.user_id == user.id:
            return "CLIENT"

        if consultation.lawyer and consultation.lawyer.user_id == user.id:
            return "LAWYER"

        # Protection against unauthorized access (IDOR / BOLA)
        raise ResourceNotFoundError("Consultation not found")

    def ensure_meeting_provisioned(self, consultation: Consultation) -> VideoMeeting:
        """Create or retrieve the VideoMeeting record for a scheduled consultation."""
        meeting = (
            self.db.query(VideoMeeting)
            .filter(VideoMeeting.consultation_id == consultation.id)
            .first()
        )

        scheduled_start = consultation.scheduled_at
        if scheduled_start.tzinfo is None:
            scheduled_start = scheduled_start.replace(tzinfo=UTC)
        else:
            scheduled_start = scheduled_start.astimezone(UTC)
        scheduled_end = scheduled_start + timedelta(minutes=consultation.duration_minutes)

        if meeting:
            # Sync schedule if consultation was rescheduled or updated
            sched_changed = False
            m_start = meeting.scheduled_start.replace(tzinfo=UTC) if meeting.scheduled_start.tzinfo is None else meeting.scheduled_start
            m_end = meeting.scheduled_end.replace(tzinfo=UTC) if meeting.scheduled_end.tzinfo is None else meeting.scheduled_end
            if m_start != scheduled_start or m_end != scheduled_end:
                meeting.scheduled_start = scheduled_start
                meeting.scheduled_end = scheduled_end
                sched_changed = True
            if sched_changed:
                self.db.commit()
                self.db.refresh(meeting)
            return meeting

        room_data = self.provider.create_meeting_room(consultation)
        meeting = VideoMeeting(
            id=generate_uuid7(),
            consultation_id=consultation.id,
            room_id=room_data["room_id"],
            provider=room_data["provider"],
            status=VideoMeetingStatus.SCHEDULED,
            scheduled_start=scheduled_start,
            scheduled_end=scheduled_end,
            meeting_metadata={"ice_servers": room_data.get("ice_servers", [])},
        )
        self.db.add(meeting)
        self.db.commit()
        self.db.refresh(meeting)

        self._log_audit(
            "VIDEO_MEETING_PROVISIONED",
            consultation.client.user_id,
            {
                "meeting_id": str(meeting.id),
                "consultation_id": str(consultation.id),
                "room_id": meeting.room_id,
            },
        )
        return meeting

    def get_join_information(
        self, user: User, consultation_id: uuid.UUID
    ) -> VideoJoinInfoResponse:
        consultation = (
            self.db.query(Consultation)
            .filter(
                Consultation.id == consultation_id,
                Consultation.deleted_at.is_(None),
            )
            .first()
        )
        if not consultation:
            raise ResourceNotFoundError("Consultation not found")

        role = self._authorize_participant(user, consultation)

        # Validate consultation status: must be active/scheduled
        if consultation.status in (
            ConsultationStatus.CANCELLED,
            ConsultationStatus.REJECTED,
            ConsultationStatus.NO_SHOW,
        ):
            raise ValidationError(
                f"Cannot join video call for a {consultation.status.value.lower()} consultation"
            )

        if consultation.status == ConsultationStatus.COMPLETED:
            raise ValidationError(
                "This consultation has already concluded and is no longer joinable"
            )

        meeting = self.ensure_meeting_provisioned(consultation)

        # Time window check
        now_utc = datetime.now(UTC)
        sched_start = meeting.scheduled_start
        if sched_start.tzinfo is None:
            sched_start = sched_start.replace(tzinfo=UTC)
        sched_end = meeting.scheduled_end
        if sched_end.tzinfo is None:
            sched_end = sched_end.replace(tzinfo=UTC)

        earliest_join = sched_start - timedelta(minutes=self.EARLY_JOIN_WINDOW_MINUTES)
        latest_join = sched_end + timedelta(minutes=self.POST_END_GRACE_PERIOD_MINUTES)

        if now_utc < earliest_join and user.role != UserRole.ADMIN:
            start_str = sched_start.strftime("%H:%M UTC")
            raise ValidationError(
                f"Meeting room opens {self.EARLY_JOIN_WINDOW_MINUTES} minutes before scheduled time ({start_str})"
            )

        if now_utc > latest_join and user.role != UserRole.ADMIN:
            raise ValidationError("Meeting session time window has expired")

        participant_name = user.email
        if role == "CLIENT" and consultation.client:
            participant_name = consultation.client.full_name
        elif role == "LAWYER" and consultation.lawyer:
            participant_name = consultation.lawyer.full_name

        token = self.provider.generate_access_token(user, meeting, role)
        ice_servers = (meeting.meeting_metadata or {}).get("ice_servers", [
            {"urls": "stun:stun.l.google.com:19302"}
        ])

        self._log_audit(
            "VIDEO_JOIN_INFO_REQUESTED",
            user.id,
            {
                "meeting_id": str(meeting.id),
                "consultation_id": str(consultation.id),
                "role": role,
            },
        )

        return VideoJoinInfoResponse(
            consultation_id=consultation.id,
            meeting_id=meeting.id,
            room_id=meeting.room_id,
            provider=meeting.provider,
            status=meeting.status,
            participant_user_id=user.id,
            participant_name=participant_name,
            participant_role=role,
            scheduled_start=meeting.scheduled_start,
            scheduled_end=meeting.scheduled_end,
            token=token,
            ice_servers=ice_servers,
            is_live=meeting.status == VideoMeetingStatus.ACTIVE,
        )

    def start_meeting(self, user: User, consultation_id: uuid.UUID) -> VideoMeeting:
        consultation = (
            self.db.query(Consultation)
            .filter(
                Consultation.id == consultation_id,
                Consultation.deleted_at.is_(None),
            )
            .first()
        )
        if not consultation:
            raise ResourceNotFoundError("Consultation not found")

        self._authorize_participant(user, consultation)
        meeting = self.ensure_meeting_provisioned(consultation)

        if meeting.status == VideoMeetingStatus.ACTIVE:
            return meeting  # Idempotent

        if meeting.status in (VideoMeetingStatus.ENDED, VideoMeetingStatus.CANCELLED):
            raise ValidationError(
                f"Cannot start meeting in '{meeting.status.value}' state"
            )

        now_utc = datetime.now(UTC)
        meeting.status = VideoMeetingStatus.ACTIVE
        if not meeting.started_at:
            meeting.started_at = now_utc

        if consultation.status == ConsultationStatus.SCHEDULED:
            consultation.status = ConsultationStatus.IN_PROGRESS

        self.db.commit()
        self.db.refresh(meeting)

        self._log_audit(
            "VIDEO_MEETING_STARTED",
            user.id,
            {
                "meeting_id": str(meeting.id),
                "consultation_id": str(consultation.id),
                "started_at": now_utc.isoformat(),
            },
        )
        return meeting

    def end_meeting(
        self, user: User, consultation_id: uuid.UUID, notes: str | None = None
    ) -> VideoMeeting:
        consultation = (
            self.db.query(Consultation)
            .filter(
                Consultation.id == consultation_id,
                Consultation.deleted_at.is_(None),
            )
            .first()
        )
        if not consultation:
            raise ResourceNotFoundError("Consultation not found")

        role = self._authorize_participant(user, consultation)
        meeting = self.ensure_meeting_provisioned(consultation)

        if meeting.status == VideoMeetingStatus.ENDED:
            return meeting  # Idempotent

        now_utc = datetime.now(UTC)
        meeting.status = VideoMeetingStatus.ENDED
        meeting.ended_at = now_utc

        consultation.status = ConsultationStatus.COMPLETED
        consultation.completed_at = now_utc

        self.db.commit()
        self.db.refresh(meeting)

        self._log_audit(
            "VIDEO_MEETING_ENDED",
            user.id,
            {
                "meeting_id": str(meeting.id),
                "consultation_id": str(consultation.id),
                "ended_at": now_utc.isoformat(),
                "notes_provided": bool(notes),
            },
        )

        for uid in (consultation.client.user_id, consultation.lawyer.user_id):
            self.notification_service.create_notification(
                user_id=uid,
                type=NotificationType.CONSULTATION_COMPLETED,
                title="Consultation Concluded",
                message="The video consultation session has ended.",
                consultation_id=consultation.id,
                case_id=consultation.case_id,
                event_id=f"video_ended_{meeting.id}_{uid}",
            )

        return meeting
