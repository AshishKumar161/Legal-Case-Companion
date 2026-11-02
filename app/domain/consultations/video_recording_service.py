import hashlib
import hmac
import json
import logging
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, BinaryIO, ClassVar
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import (
    AuthorizationError,
    ConfigurationError,
    ResourceNotFoundError,
    ValidationError,
)
from app.core.identifiers import generate_uuid7
from app.models.consultation import Consultation, ConsultationStatus
from app.models.user import AccountStatus, User, UserRole
from app.models.video_recording import (
    VideoRecording,
    VideoRecordingConsent,
    VideoRecordingStatus,
)
from app.schemas.video_recording import ConsentStatusResponse
from app.domain.auth.auth_service import AuthService
from app.domain.consultations.recording_storage import (
    RecordingStorageProvider,
    get_recording_storage_provider,
)
from app.domain.users.user_service import UserService
from app.domain.consultations.video_telemetry_service import (
    VideoTelemetryEvent,
    VideoTelemetryService,
    metrics_registry,
)

logger = logging.getLogger(__name__)


class VideoRecordingService:
    ALLOWED_MIME_TYPES: ClassVar[set[str]] = {
        "video/webm",
        "video/mp4",
        "video/x-matroska",
        "application/octet-stream",
    }

    def __init__(
        self,
        db: Session,
        storage_provider: RecordingStorageProvider | None = None,
    ):
        self.db = db
        self.storage_provider = storage_provider or get_recording_storage_provider()
        self.auth_service = AuthService(db)

    def _log_audit(
        self,
        event_type: str,
        user_id: UUID,
        metadata: dict,
        entity_id: UUID | None = None,
    ):
        """Log secure audit events without sensitive payloads."""
        self.auth_service.log_audit_event(
            event_type=event_type,
            user_id=user_id,
            metadata=metadata,
            action="video_recording",
        )

    def _authorize_participant(self, user: User, consultation: Consultation) -> str:
        """Enforce strict BOLA authorization and return participant role.
        Unauthorized users receive ResourceNotFoundError to prevent existence enumeration.
        """
        if user.role == UserRole.ADMIN:
            return "ADMIN"

        if consultation.client and consultation.client.user_id == user.id:
            return "CLIENT"

        if consultation.lawyer and consultation.lawyer.user_id == user.id:
            return "LAWYER"

        raise ResourceNotFoundError("Consultation not found")

    def _authorize_playback(self, user: User, recording: VideoRecording) -> None:
        """Verify user is authorized to stream/play back this recording."""
        from app.core.authorization import authorize_recording_access

        authorize_recording_access(self.db, user, recording.id)

    def grant_consent(
        self,
        user: User,
        consultation_id: UUID,
        consented: bool = True,
    ) -> VideoRecordingConsent:
        consultation = (
            self.db.query(Consultation)
            .filter(Consultation.id == consultation_id)
            .first()
        )
        if not consultation:
            raise ResourceNotFoundError("Consultation not found")

        role = self._authorize_participant(user, consultation)
        if role == "ADMIN":
            raise AuthorizationError("Administrators cannot grant consent on behalf of call participants")

        # Upsert consent
        consent = (
            self.db.query(VideoRecordingConsent)
            .filter(
                VideoRecordingConsent.consultation_id == consultation_id,
                VideoRecordingConsent.user_id == user.id,
            )
            .first()
        )

        now_dt = datetime.now(UTC)
        if consent:
            consent.consented = consented
            consent.consented_at = now_dt
            consent.role = role
        else:
            consent = VideoRecordingConsent(
                id=generate_uuid7(),
                consultation_id=consultation_id,
                user_id=user.id,
                role=role,
                consented=consented,
                consented_at=now_dt,
            )
            self.db.add(consent)

        if not consented:
            # Stop any active recording for this consultation immediately upon consent revocation
            active_recs = (
                self.db.query(VideoRecording)
                .filter(
                    VideoRecording.consultation_id == consultation_id,
                    VideoRecording.status == VideoRecordingStatus.RECORDING,
                    VideoRecording.deleted_at.is_(None),
                )
                .all()
            )
            for rec in active_recs:
                rec.status = VideoRecordingStatus.FAILED
                rec.ended_at = now_dt
                rec.error_message = f"Recording halted: consent revoked by participant {user.id}"
                self._log_audit(
                    event_type="RECORDING_HALTED_CONSENT_REVOKED",
                    user_id=user.id,
                    metadata={"recording_id": str(rec.id), "consultation_id": str(consultation_id)},
                    entity_id=rec.id,
                )

        self.db.commit()
        self.db.refresh(consent)

        self._log_audit(
            event_type="RECORDING_CONSENT_GRANTED" if consented else "RECORDING_CONSENT_REVOKED",
            user_id=user.id,
            metadata={
                "consultation_id": str(consultation_id),
                "role": role,
                "consented": consented,
            },
            entity_id=consent.id,
        )
        return consent

    def get_consent_status(
        self,
        user: User,
        consultation_id: UUID,
    ) -> ConsentStatusResponse:
        consultation = (
            self.db.query(Consultation)
            .filter(Consultation.id == consultation_id)
            .first()
        )
        if not consultation:
            raise ResourceNotFoundError("Consultation not found")

        self._authorize_participant(user, consultation)

        consents = (
            self.db.query(VideoRecordingConsent)
            .filter(VideoRecordingConsent.consultation_id == consultation_id)
            .all()
        )

        client_user_id = consultation.client.user_id if consultation.client else None
        lawyer_user_id = consultation.lawyer.user_id if consultation.lawyer else None

        client_consented = False
        lawyer_consented = False

        for c in consents:
            if client_user_id and c.user_id == client_user_id and c.consented:
                client_consented = True
            if lawyer_user_id and c.user_id == lawyer_user_id and c.consented:
                lawyer_consented = True

        can_record = client_consented and lawyer_consented
        return ConsentStatusResponse(
            consultation_id=consultation_id,
            client_consented=client_consented,
            lawyer_consented=lawyer_consented,
            can_record=can_record,
        )

    def start_recording(
        self,
        user: User,
        consultation_id: UUID,
    ) -> VideoRecording:
        consultation = (
            self.db.query(Consultation)
            .filter(Consultation.id == consultation_id)
            .first()
        )
        if not consultation:
            raise ResourceNotFoundError("Consultation not found")

        self._authorize_participant(user, consultation)

        # 0. Production Feature Flag Check (Disabled by default in production)
        is_prod = settings.ENVIRONMENT in ("production", "staging")
        if is_prod and not getattr(settings, "ENABLE_CONSULTATION_RECORDING", False):
            raise ConfigurationError(
                "Consultation video recording is disabled by default in production. "
                "The workflow must be reviewed and certified by qualified Indian legal counsel before deployment."
            )

        # 1. State check
        allowed_statuses = {
            ConsultationStatus.ACCEPTED,
            ConsultationStatus.PAID,
            ConsultationStatus.SCHEDULED,
            ConsultationStatus.IN_PROGRESS,
        }
        if consultation.status not in allowed_statuses:
            raise ValidationError(
                f"Cannot record consultation in status '{consultation.status.value}'"
            )

        # 2. Check mutual consent
        consent_status = self.get_consent_status(user, consultation_id)
        if not consent_status.can_record:
            raise ValidationError(
                "Recording requires explicit mutual consent from both the client and lawyer"
            )

        # 3. Concurrency check: verify no active recording exists
        active_statuses = [
            VideoRecordingStatus.PENDING,
            VideoRecordingStatus.RECORDING,
            VideoRecordingStatus.UPLOADING,
            VideoRecordingStatus.PROCESSING,
        ]
        active_recording = (
            self.db.query(VideoRecording)
            .filter(
                VideoRecording.consultation_id == consultation_id,
                VideoRecording.status.in_(active_statuses),
                VideoRecording.deleted_at.is_(None),
            )
            .first()
        )
        if active_recording:
            raise ValidationError("An active recording session already exists for this consultation")

        # 4. Create new recording record
        rec_id = generate_uuid7()
        now_dt = datetime.now(UTC)
        rel_storage_path = f"consultations/{consultation_id}/{rec_id}.webm"

        recording = VideoRecording(
            id=rec_id,
            consultation_id=consultation_id,
            case_id=consultation.case_id,
            recording_type="BROWSER_MEDIA_RECORDER",
            status=VideoRecordingStatus.RECORDING,
            started_at=now_dt,
            storage_path=rel_storage_path,
            mime_type="video/webm",
        )
        self.db.add(recording)
        self.db.commit()
        self.db.refresh(recording)

        VideoTelemetryService.record_event(
            event=VideoTelemetryEvent.RECORDING_STARTED,
            consultation_id=consultation_id,
            recording_id=recording.id,
            user_id=user.id,
        )

        self._log_audit(
            event_type="RECORDING_STARTED",
            user_id=user.id,
            metadata={
                "recording_id": str(recording.id),
                "consultation_id": str(consultation_id),
                "started_at": now_dt.isoformat(),
            },
            entity_id=recording.id,
        )
        return recording

    def stop_recording(
        self,
        user: User,
        consultation_id: UUID,
        recording_id: UUID | None = None,
    ) -> VideoRecording:
        consultation = (
            self.db.query(Consultation)
            .filter(Consultation.id == consultation_id)
            .first()
        )
        if not consultation:
            raise ResourceNotFoundError("Consultation not found")

        self._authorize_participant(user, consultation)

        query = self.db.query(VideoRecording).filter(
            VideoRecording.consultation_id == consultation_id,
            VideoRecording.deleted_at.is_(None),
        )
        if recording_id:
            query = query.filter(VideoRecording.id == recording_id)
        else:
            query = query.filter(VideoRecording.status == VideoRecordingStatus.RECORDING)

        recording = query.first()
        if not recording:
            raise ResourceNotFoundError("No active recording session found to stop")

        if recording.status != VideoRecordingStatus.RECORDING:
            raise ValidationError(
                f"Recording cannot be stopped from status '{recording.status.value}'"
            )

        now_dt = datetime.now(UTC)
        recording.status = VideoRecordingStatus.UPLOADING
        recording.ended_at = now_dt

        if recording.started_at:
            s_at = recording.started_at.replace(tzinfo=UTC) if recording.started_at.tzinfo is None else recording.started_at
            recording.duration_seconds = max(1, int((now_dt - s_at).total_seconds()))

        self.db.commit()
        self.db.refresh(recording)

        VideoTelemetryService.record_event(
            event=VideoTelemetryEvent.RECORDING_STOPPED,
            consultation_id=consultation_id,
            recording_id=recording.id,
            user_id=user.id,
            duration_seconds=recording.duration_seconds,
        )

        self._log_audit(
            event_type="RECORDING_STOPPED",
            user_id=user.id,
            metadata={
                "recording_id": str(recording.id),
                "consultation_id": str(consultation_id),
                "duration_seconds": recording.duration_seconds,
            },
            entity_id=recording.id,
        )
        return recording

    def finalize_upload(
        self,
        user: User,
        consultation_id: UUID,
        recording_id: UUID,
        file_source: BinaryIO | bytes,
        filename: str,
        content_type: str | None = None,
    ) -> VideoRecording:
        consultation = (
            self.db.query(Consultation)
            .filter(Consultation.id == consultation_id)
            .first()
        )
        if not consultation:
            raise ResourceNotFoundError("Consultation not found")

        self._authorize_participant(user, consultation)

        recording = (
            self.db.query(VideoRecording)
            .filter(
                VideoRecording.id == recording_id,
                VideoRecording.consultation_id == consultation_id,
                VideoRecording.deleted_at.is_(None),
            )
            .first()
        )
        if not recording:
            raise ResourceNotFoundError("Recording not found")

        # Duplicate upload prevention: once AVAILABLE, re-upload is forbidden
        if recording.status == VideoRecordingStatus.AVAILABLE:
            raise ValidationError("Recording has already been uploaded and finalized")

        # Allow upload from RECORDING, UPLOADING, PROCESSING, or retry from FAILED
        if recording.status not in (
            VideoRecordingStatus.RECORDING,
            VideoRecordingStatus.UPLOADING,
            VideoRecordingStatus.PROCESSING,
            VideoRecordingStatus.FAILED,
        ):
            raise ValidationError(
                f"Cannot finalize recording in status '{recording.status.value}'"
            )

        VideoTelemetryService.record_event(
            event=VideoTelemetryEvent.RECORDING_UPLOAD_STARTED,
            consultation_id=consultation_id,
            recording_id=recording.id,
            user_id=user.id,
        )

        # Transition to PROCESSING
        recording.status = VideoRecordingStatus.PROCESSING
        self.db.commit()

        # Determine extension
        _, ext = os.path.splitext(filename)
        clean_ext = ext.lstrip(".").lower() or "webm"
        mime = content_type or f"video/{clean_ext}"

        try:
            storage_path, file_size, checksum = self.storage_provider.save_recording(
                consultation_id=consultation_id,
                recording_id=recording_id,
                file_source=file_source,
                extension=clean_ext,
            )

            if file_size <= 0:
                raise ValidationError("Uploaded recording file is empty")

            now_dt = datetime.now(UTC)
            recording.storage_path = storage_path
            recording.file_size_bytes = file_size
            recording.checksum_sha256 = checksum
            recording.mime_type = mime
            recording.status = VideoRecordingStatus.AVAILABLE

            if not recording.ended_at:
                recording.ended_at = now_dt
                if recording.started_at:
                    s_at = recording.started_at.replace(tzinfo=UTC) if recording.started_at.tzinfo is None else recording.started_at
                    recording.duration_seconds = max(1, int((now_dt - s_at).total_seconds()))

            if consultation.case_id:
                recording.case_id = consultation.case_id

            self.db.commit()
            self.db.refresh(recording)

            VideoTelemetryService.record_event(
                event=VideoTelemetryEvent.RECORDING_UPLOAD_COMPLETED,
                consultation_id=consultation_id,
                recording_id=recording.id,
                user_id=user.id,
                file_size_bytes=file_size,
                duration_seconds=recording.duration_seconds,
            )
            VideoTelemetryService.record_event(
                event=VideoTelemetryEvent.RECORDING_AVAILABLE,
                consultation_id=consultation_id,
                recording_id=recording.id,
                user_id=user.id,
                file_size_bytes=file_size,
            )

            self._log_audit(
                event_type="RECORDING_FINALIZED",
                user_id=user.id,
                metadata={
                    "recording_id": str(recording.id),
                    "consultation_id": str(consultation_id),
                    "file_size_bytes": file_size,
                    "checksum_sha256": checksum,
                    "duration_seconds": recording.duration_seconds,
                },
                entity_id=recording.id,
            )
            return recording
        except Exception as e:
            logger.error(f"Error finalizing recording {recording_id}: {e}")
            recording.status = VideoRecordingStatus.FAILED
            self.db.commit()

            VideoTelemetryService.record_event(
                event=VideoTelemetryEvent.RECORDING_UPLOAD_FAILED,
                consultation_id=consultation_id,
                recording_id=recording.id,
                user_id=user.id,
                result="FAILURE",
                failure_code=type(e).__name__,
            )

            self._log_audit(
                event_type="RECORDING_FAILED",
                user_id=user.id,
                metadata={
                    "recording_id": str(recording.id),
                    "consultation_id": str(consultation_id),
                    "error": str(e),
                },
                entity_id=recording.id,
            )
            raise

    async def finalize_upload_stream(
        self,
        user: User,
        consultation_id: UUID,
        recording_id: UUID,
        async_stream: Any,
        filename: str,
        content_type: str | None = None,
    ) -> VideoRecording:
        """Stream chunks from async request generator into finalize_upload."""
        chunks = []
        async for chunk in async_stream:
            if chunk:
                chunks.append(chunk)
        payload_bytes = b"".join(chunks)
        return self.finalize_upload(
            user=user,
            consultation_id=consultation_id,
            recording_id=recording_id,
            file_source=payload_bytes,
            filename=filename,
            content_type=content_type,
        )

    def list_recordings(
        self,
        user: User,
        consultation_id: UUID,
    ) -> list[VideoRecording]:
        consultation = (
            self.db.query(Consultation)
            .filter(Consultation.id == consultation_id)
            .first()
        )
        if not consultation:
            raise ResourceNotFoundError("Consultation not found")

        self._authorize_participant(user, consultation)

        return (
            self.db.query(VideoRecording)
            .filter(
                VideoRecording.consultation_id == consultation_id,
                VideoRecording.deleted_at.is_(None),
            )
            .order_by(VideoRecording.created_at.desc())
            .all()
        )

    _revoked_tickets: ClassVar[set[str]] = set()

    @classmethod
    def revoke_playback_ticket(cls, ticket_or_jti: str) -> None:
        """Revokes an active media playback ticket by ticket string or jti."""
        if ticket_or_jti:
            cls._revoked_tickets.add(ticket_or_jti)

    @classmethod
    def is_ticket_revoked(cls, ticket_or_jti: str) -> bool:
        """Checks if a playback ticket or its jti has been explicitly revoked."""
        return ticket_or_jti in cls._revoked_tickets

    @staticmethod
    def _get_signing_secret() -> str:
        secret = (
            getattr(settings, "CSRF_SECRET_KEY", None)
            or getattr(settings, "JWT_PRIVATE_KEY", None)
            or getattr(settings, "SECRET_KEY", None)
        )
        if not secret or secret == "mock-secret-for-dev":
            if settings.ENVIRONMENT in ("production", "staging"):
                raise ConfigurationError("Missing production cryptographic secret for playback ticket signing")
            secret = "lcc-dev-ephemeral-playback-secret"
        return secret

    def generate_playback_ticket(
        self,
        user: User,
        recording_id: UUID,
        expires_in_seconds: int = 60,
    ) -> str:
        """
        Generate an ephemeral, single-purpose media playback ticket.
        Prevents leaking primary bearer access tokens in URLs / browser history.
        Strictly valid for specified TTL (default 60s) and cryptographically bound
        to (user_id, consultation_id, recording_id) with unique jti.
        """
        recording = (
            self.db.query(VideoRecording)
            .filter(
                VideoRecording.id == recording_id,
                VideoRecording.deleted_at.is_(None),
            )
            .first()
        )
        if not recording:
            raise ResourceNotFoundError("Recording not found")

        self._authorize_playback(user, recording)

        if recording.status != VideoRecordingStatus.AVAILABLE:
            raise ValidationError("Recording is not available for playback")

        now_dt = datetime.now(UTC)
        exp_ts = int((now_dt + timedelta(seconds=expires_in_seconds)).timestamp())
        ticket_jti = generate_uuid7().hex
        payload = {
            "jti": ticket_jti,
            "sub": str(user.id),
            "consultation_id": str(recording.consultation_id),
            "rec_id": str(recording.id),
            "purpose": "media_playback",
            "iat": int(now_dt.timestamp()),
            "exp": exp_ts,
        }

        secret = self._get_signing_secret()
        encoded_payload = json.dumps(payload, sort_keys=True).encode("utf-8")
        signature = hmac.new(secret.encode("utf-8"), encoded_payload, hashlib.sha256).hexdigest()
        return f"mpt_{signature}.{encoded_payload.hex()}"

    def verify_playback_ticket(
        self,
        ticket: str,
        expected_recording_id: UUID,
        expected_consultation_id: UUID | None = None,
    ) -> User:
        """
        Verify an ephemeral media playback ticket.
        Validates HMAC signature, expiration window, purpose, revocation, and 
        independent binding to user, consultation, and recording.
        Returns the authenticated User.
        """
        if not ticket or not ticket.startswith("mpt_") or "." not in ticket:
            raise ValidationError("Invalid playback ticket format")

        if self.is_ticket_revoked(ticket):
            raise ValidationError("Playback ticket has been revoked")

        token_body = ticket[4:]
        parts = token_body.split(".", 1)
        if len(parts) != 2:
            raise ValidationError("Invalid playback ticket format")

        signature, payload_hex = parts[0], parts[1]
        secret = self._get_signing_secret()

        try:
            raw_payload = bytes.fromhex(payload_hex)
        except ValueError as e:
            raise ValidationError("Malformed playback ticket hex payload") from e

        expected_sig = hmac.new(secret.encode("utf-8"), raw_payload, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected_sig):
            raise ValidationError("Tampered or invalid playback ticket signature")

        try:
            payload = json.loads(raw_payload.decode("utf-8"))
        except Exception as e:
            raise ValidationError("Malformed JSON in playback ticket payload") from e

        # Check explicit jti revocation
        jti = payload.get("jti")
        if jti and self.is_ticket_revoked(jti):
            raise ValidationError("Playback ticket has been revoked")

        now_ts = int(datetime.now(UTC).timestamp())
        if payload.get("exp", 0) < now_ts:
            raise ValidationError("Playback ticket has expired")

        if payload.get("purpose") != "media_playback":
            raise ValidationError("Invalid ticket purpose")

        if payload.get("rec_id") != str(expected_recording_id):
            raise ValidationError("Playback ticket is not authorized for this recording")

        # Verify consultation binding
        ticket_consultation_id = payload.get("consultation_id")
        if not ticket_consultation_id:
            raise ValidationError("Playback ticket missing consultation binding")

        if expected_consultation_id and ticket_consultation_id != str(expected_consultation_id):
            raise ValidationError("Playback ticket is not authorized for this consultation")

        # Verify underlying recording is active and accessible
        recording = (
            self.db.query(VideoRecording)
            .filter(
                VideoRecording.id == expected_recording_id,
                VideoRecording.deleted_at.is_(None),
            )
            .first()
        )
        if not recording:
            raise ResourceNotFoundError("Recording not found or deleted")
        if str(recording.consultation_id) != ticket_consultation_id:
            raise ValidationError("Recording does not belong to the ticket consultation")
        if recording.status != VideoRecordingStatus.AVAILABLE:
            raise ValidationError(f"Recording is no longer available (status: {recording.status.value})")

        user_id_str = payload.get("sub")
        if not user_id_str:
            raise ValidationError("Playback ticket missing subject")

        try:
            user_id = UUID(user_id_str)
        except ValueError as e:
            raise ValidationError("Invalid user ID in playback ticket") from e

        user = UserService(self.db).get_user_by_id(user_id)
        if not user or user.account_status != AccountStatus.ACTIVE:
            raise ValidationError("User account is not active or found")

        return user

    def get_recording_for_playback(
        self,
        user: User,
        recording_id: UUID,
        verify_integrity: bool = True,
    ) -> tuple[VideoRecording, Path]:
        recording = (
            self.db.query(VideoRecording)
            .filter(
                VideoRecording.id == recording_id,
                VideoRecording.deleted_at.is_(None),
            )
            .first()
        )
        if not recording:
            raise ResourceNotFoundError("Recording not found")

        self._authorize_playback(user, recording)

        if recording.status != VideoRecordingStatus.AVAILABLE:
            raise ValidationError("Recording is not available for playback")

        file_path = self.storage_provider.get_recording_path(recording.storage_path)
        if not file_path.exists():
            raise ResourceNotFoundError("Recording physical file is missing from storage")

        # Cryptographic integrity verification (Phase 11)
        if verify_integrity and recording.checksum_sha256:
            hasher = hashlib.sha256()
            with open(file_path, "rb") as f:
                while chunk := f.read(65536):
                    hasher.update(chunk)
            actual_checksum = hasher.hexdigest()

            if actual_checksum != recording.checksum_sha256:
                logger.error(
                    f"Integrity mismatch for recording {recording_id}: "
                    f"expected {recording.checksum_sha256}, got {actual_checksum}"
                )
                raise ValidationError(
                    "Recording cryptographic integrity verification failed: physical file checksum mismatch"
                )

        self._log_audit(
            event_type="RECORDING_ACCESSED",
            user_id=user.id,
            metadata={
                "recording_id": str(recording.id),
                "consultation_id": str(recording.consultation_id),
            },
            entity_id=recording.id,
        )
        return recording, file_path

    def retry_pending_and_failed_recordings(
        self,
        max_age_minutes: int = 60,
        grace_period_minutes: int = 5,
    ) -> dict[str, Any]:
        """
        Background maintenance job: identifies recordings stuck in PROCESSING, UPLOADING,
        or FAILED states past the grace period, attempts safe integrity restoration if the
        underlying storage file exists, or marks permanently FAILED if missing past max_age.
        """
        now = datetime.now(UTC)
        grace_cutoff = now - timedelta(minutes=grace_period_minutes)
        max_age_cutoff = now - timedelta(minutes=max_age_minutes)

        candidates = (
            self.db.query(VideoRecording)
            .filter(
                VideoRecording.status.in_([
                    VideoRecordingStatus.PROCESSING,
                    VideoRecordingStatus.UPLOADING,
                    VideoRecordingStatus.FAILED,
                ]),
                VideoRecording.updated_at <= grace_cutoff,
                VideoRecording.deleted_at.is_(None),
            )
            .limit(25)
            .all()
        )

        recovered_count = 0
        exhausted_count = 0

        for rec in candidates:
            try:
                # Check if physical file exists at storage_path
                file_path = self.storage_provider.get_recording_path(rec.storage_path)
                if file_path.exists() and file_path.is_file():
                    size = file_path.stat().st_size
                    if size > 0:
                        # Recompute checksum and finalize
                        hasher = hashlib.sha256()
                        with open(file_path, "rb") as f:
                            while chunk := f.read(65536):
                                hasher.update(chunk)
                        checksum = hasher.hexdigest()

                        rec.file_size_bytes = size
                        rec.checksum_sha256 = checksum
                        rec.status = VideoRecordingStatus.AVAILABLE
                        rec.ended_at = rec.ended_at or now
                        recovered_count += 1
                        VideoTelemetryService.record_event(
                            event=VideoTelemetryEvent.RECORDING_AVAILABLE,
                            consultation_id=rec.consultation_id,
                            recording_id=rec.id,
                            file_size_bytes=size,
                            result="RECOVERED_BY_BACKGROUND_JOB",
                        )
                        continue
            except Exception as e:  # noqa: BLE001
                logger.warning("Error checking recording storage for %s: %s", rec.id, e)

            # If file does not exist and exceeds max age cutoff -> mark permanently FAILED
            rec_created_at = rec.created_at.replace(tzinfo=UTC) if rec.created_at.tzinfo is None else rec.created_at
            if rec_created_at <= max_age_cutoff:
                rec.status = VideoRecordingStatus.FAILED
                exhausted_count += 1
                VideoTelemetryService.record_event(
                    event=VideoTelemetryEvent.RECORDING_UPLOAD_FAILED,
                    consultation_id=rec.consultation_id,
                    recording_id=rec.id,
                    result="EXHAUSTED_BACKGROUND_RETRY",
                )

        if recovered_count or exhausted_count:
            self.db.commit()

        return {
            "evaluated_count": len(candidates),
            "recovered_count": recovered_count,
            "exhausted_count": exhausted_count,
        }

    def generate_download_url(
        self,
        user: User,
        recording_id: UUID,
        expires_in_seconds: int = 60,
    ) -> str:
        """Generates a short-lived signed download URL or playback ticket with strict access authorization."""
        recording = (
            self.db.query(VideoRecording)
            .filter(
                VideoRecording.id == recording_id,
                VideoRecording.deleted_at.is_(None),
            )
            .first()
        )
        if not recording:
            raise ResourceNotFoundError("Recording not found")

        self._authorize_playback(user, recording)

        if recording.status != VideoRecordingStatus.AVAILABLE:
            raise ValidationError("Recording is not available for download")

        # If S3 provider, generate short-lived signed S3 URL; otherwise generate signed playback ticket
        if hasattr(self.storage_provider, "generate_presigned_playback_url"):
            url = self.storage_provider.generate_presigned_playback_url(
                recording.storage_path, expires_in=expires_in_seconds
            )
        else:
            ticket = self.generate_playback_ticket(user, recording_id, expires_in_seconds=expires_in_seconds)
            url = f"/api/v1/consultations/{recording.consultation_id}/recordings/{recording.id}/stream?ticket={ticket}"

        self._log_audit(
            event_type="RECORDING_DOWNLOAD_URL_GENERATED",
            user_id=user.id,
            metadata={
                "recording_id": str(recording.id),
                "consultation_id": str(recording.consultation_id),
                "expires_in": expires_in_seconds,
            },
            entity_id=recording.id,
        )
        return url

    def delete_recording(
        self,
        user: User,
        recording_id: UUID,
    ) -> bool:
        """Deletes a recording with authorization, legal retention audit trail, and physical storage removal."""
        recording = (
            self.db.query(VideoRecording)
            .filter(
                VideoRecording.id == recording_id,
                VideoRecording.deleted_at.is_(None),
            )
            .first()
        )
        if not recording:
            raise ResourceNotFoundError("Recording not found")

        self._authorize_playback(user, recording)

        now_dt = datetime.now(UTC)
        recording.deleted_at = now_dt
        self.db.commit()

        # Remove physical file from private object storage
        try:
            self.storage_provider.delete_recording(recording.storage_path)
        except Exception as e:
            logger.warning(f"Error purging recording file from storage: {e}")

        self._log_audit(
            event_type="RECORDING_DELETED",
            user_id=user.id,
            metadata={
                "recording_id": str(recording.id),
                "consultation_id": str(recording.consultation_id),
                "deleted_at": now_dt.isoformat(),
            },
            entity_id=recording.id,
        )
        return True
