from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import RequireRole, get_current_user, get_db
from app.api.v1.auth import limiter
from app.models.consultation import Consultation, ConsultationStatus
from app.models.notification import NotificationType
from app.models.payment import Payment, PaymentStatus
from app.models.user import LawyerProfile, User, UserRole
from app.services.notification_service import NotificationService
from app.schemas.case import CaseResponse
from app.schemas.consultation import (
    ConsultationCancelRequest,
    ConsultationCreate,
    ConsultationCreateCaseRequest,
    ConsultationLinkCaseRequest,
    ConsultationNoShowRequest,
    ConsultationRejectRequest,
    ConsultationRescheduleRequest,
    ConsultationResponse,
    ConsultationScheduleRequest,
)
from app.schemas.consultation_note import (
    ConsultationNoteCreate,
    ConsultationNoteResponse,
)
from app.schemas.message import MessageCreate, MessageResponse
from app.schemas.pagination import PaginatedResponse
from app.schemas.payment import PaymentIntentResponse, PaymentResponse
from app.schemas.video_meeting import (
    VideoJoinInfoResponse,
    VideoMeetingEndRequest,
    VideoMeetingResponse,
)
from app.schemas.video_recording import (
    ConsentStatusResponse,
    RecordingConsentRequest,
    RecordingConsentResponse,
    RecordingListResponse,
    RecordingResponse,
    RecordingStartResponse,
    RecordingStopResponse,
)
from app.services.consultation_service import ConsultationService
from app.services.message_service import MessageService
from app.services.payment_service import PaymentService
from app.services.video_meeting_service import VideoMeetingService
from app.services.video_recording_service import VideoRecordingService

router = APIRouter(prefix="/consultations", tags=["consultations"])


@router.post(
    "", response_model=ConsultationResponse, status_code=status.HTTP_201_CREATED
)
@limiter.limit("30/minute")
def request_consultation(
    request: Request,
    req: ConsultationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    consultation_service = ConsultationService(db)
    return consultation_service.request_consultation(current_user, req)


@router.get("", response_model=PaginatedResponse[ConsultationResponse])
def get_consultations(
    case_id: UUID | None = None,
    consultation_status: ConsultationStatus | None = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    consultation_service = ConsultationService(db)
    return consultation_service.get_consultations(
        current_user, case_id=case_id, status=consultation_status, skip=skip, limit=limit
    )


@router.get("/incoming-calls")
def get_incoming_calls_for_lawyer(
    db: Session = Depends(get_db),
    current_user: User = Depends(RequireRole([UserRole.LAWYER, UserRole.ADMIN])),
):
    """
    Returns active incoming calls/consultations that need the lawyer's immediate attention.
    """
    lawyer_profile = (
        db.query(LawyerProfile)
        .filter(LawyerProfile.user_id == current_user.id)
        .first()
    )
    if not lawyer_profile:
        return []

    now_utc = datetime.now(UTC)
    recent_cutoff = now_utc - timedelta(hours=4)
    consultations = (
        db.query(Consultation)
        .filter(
            Consultation.lawyer_id == lawyer_profile.id,
            Consultation.status.in_([ConsultationStatus.PAID, ConsultationStatus.REQUESTED]),
            Consultation.deleted_at.is_(None),
            Consultation.created_at >= recent_cutoff,
        )
        .order_by(Consultation.created_at.desc())
        .limit(5)
        .all()
    )

    items = []
    for c in consultations:
        client_name = c.client.full_name if c.client else "Client"
        items.append({
            "id": str(c.id),
            "client_name": client_name,
            "scheduled_at": c.scheduled_at.isoformat() if c.scheduled_at else None,
            "status": c.status.value,
            "fee_amount": float(c.fee_amount),
            "currency": c.currency,
            "created_at": c.created_at.isoformat(),
        })
    return items


@router.get("/{consultation_id}", response_model=ConsultationResponse)
def get_consultation(
    consultation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    consultation_service = ConsultationService(db)
    return consultation_service.get_consultation(current_user, consultation_id)


@router.post("/{consultation_id}/accept", response_model=ConsultationResponse)
def accept_consultation(
    consultation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    consultation_service = ConsultationService(db)
    return consultation_service.accept_consultation(current_user, consultation_id)


@router.post("/{consultation_id}/reject", response_model=ConsultationResponse)
def reject_consultation(
    consultation_id: UUID,
    req: ConsultationRejectRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    consultation_service = ConsultationService(db)
    reason = req.reason if req else None
    return consultation_service.reject_consultation(
        current_user, consultation_id, reason=reason
    )


@router.post("/{consultation_id}/schedule", response_model=ConsultationResponse)
def schedule_consultation(
    consultation_id: UUID,
    req: ConsultationScheduleRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    consultation_service = ConsultationService(db)
    return consultation_service.schedule_consultation(
        current_user,
        consultation_id,
        scheduled_at=req.scheduled_at,
        duration_minutes=req.duration_minutes,
    )


@router.post("/{consultation_id}/reschedule", response_model=ConsultationResponse)
def reschedule_consultation(
    consultation_id: UUID,
    req: ConsultationRescheduleRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    consultation_service = ConsultationService(db)
    return consultation_service.reschedule_consultation(
        current_user,
        consultation_id,
        scheduled_at=req.scheduled_at,
        duration_minutes=req.duration_minutes,
        reason=req.reason,
    )


@router.post("/{consultation_id}/confirm", response_model=ConsultationResponse)
def confirm_consultation(
    consultation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    consultation_service = ConsultationService(db)
    return consultation_service.confirm_consultation(current_user, consultation_id)


@router.post("/{consultation_id}/cancel", response_model=ConsultationResponse)
def cancel_consultation(
    consultation_id: UUID,
    req: ConsultationCancelRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    consultation_service = ConsultationService(db)
    reason = req.reason if req else None
    return consultation_service.cancel_consultation(
        current_user, consultation_id, reason=reason
    )


@router.post("/{consultation_id}/no-show", response_model=ConsultationResponse)
def mark_no_show(
    consultation_id: UUID,
    req: ConsultationNoShowRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    consultation_service = ConsultationService(db)
    reason = req.reason if req else None
    return consultation_service.mark_no_show(
        current_user, consultation_id, reason=reason
    )


@router.post("/{consultation_id}/complete", response_model=ConsultationResponse)
def complete_consultation(
    consultation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    consultation_service = ConsultationService(db)
    return consultation_service.complete_consultation(current_user, consultation_id)


@router.post(
    "/{consultation_id}/payments", response_model=PaymentIntentResponse, status_code=201
)
@limiter.limit("20/minute")
def create_payment(
    request: Request,
    consultation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequireRole([UserRole.CLIENT])),
):
    service = PaymentService(db)
    return service.create_payment_intent(current_user, consultation_id)


@router.post(
    "/{consultation_id}/pay-test", response_model=ConsultationResponse, status_code=200
)
def process_test_payment(
    consultation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequireRole([UserRole.CLIENT, UserRole.ADMIN])),
):
    """
    Authoritative one-click simulated test payment.
    Instantly marks consultation as PAID, provisions the video meeting room,
    and alerts the lawyer that the consultation call is ready.
    """
    consultation_service = ConsultationService(db)
    payment_service = PaymentService(db)
    video_service = VideoMeetingService(db)

    consultation = consultation_service._get_consultation(consultation_id)
    consultation_service._authorize_consultation_access(current_user, consultation)

    # 1. Create or retrieve active payment intent
    intent = payment_service.create_payment_intent(current_user, consultation_id)

    # 2. Mark payment as SUCCEEDED
    payment = (
        db.query(Payment)
        .filter(Payment.id == intent.payment_id)
        .first()
    )
    if payment:
        payment.status = PaymentStatus.SUCCEEDED

    # 3. Mark consultation status as PAID
    consultation.status = ConsultationStatus.PAID
    db.commit()
    db.refresh(consultation)

    # 4. Provision VideoMeeting record
    video_service.ensure_meeting_provisioned(consultation)

    # 5. Send notification to lawyer
    try:
        notification_service = NotificationService(db)
        client_name = consultation.client.full_name if consultation.client else "Client"
        notification_service.create_notification(
            user_id=consultation.lawyer.user_id,
            type=NotificationType.PAYMENT_SUCCEEDED,
            title="Instant Consultation Call Received",
            message=f"{client_name} has authorized consultation #{str(consultation.id)[:8].upper()} (₹{consultation.fee_amount:.2f} Paid). Ready to join video call.",
            consultation_id=consultation.id,
            metadata={
                "consultation_id": str(consultation.id),
                "action": "incoming_video_call",
                "client_name": client_name,
            },
            event_id=f"incoming_call_{consultation.id}",
        )
    except Exception:
        pass

    return consultation


@router.get("/{consultation_id}/payments", response_model=list[PaymentResponse])
def get_consultation_payments(
    consultation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = PaymentService(db)
    return service.get_consultation_payments(current_user, consultation_id)


@router.post(
    "/{consultation_id}/messages", response_model=MessageResponse, status_code=201
)
def send_message(
    consultation_id: UUID,
    req: MessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = MessageService(db)
    return service.send_message(current_user, consultation_id, req)


@router.get("/{consultation_id}/messages", response_model=list[MessageResponse])
def get_messages(
    consultation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = MessageService(db)
    return service.get_messages(current_user, consultation_id)


# --- Video Meeting Endpoints ---


@router.get(
    "/{consultation_id}/video/join",
    response_model=VideoJoinInfoResponse,
)
@limiter.limit("60/minute")
def join_video_meeting(
    request: Request,
    consultation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieve cryptographically signed join credentials for the in-app video consultation room.
    Enforces strict participant authorization (Client, assigned Lawyer, or Admin).
    """
    service = VideoMeetingService(db)
    return service.get_join_information(current_user, consultation_id)


@router.post(
    "/{consultation_id}/video/start",
    response_model=VideoMeetingResponse,
)
def start_video_meeting(
    consultation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Mark the video consultation meeting as ACTIVE and consultation as IN_PROGRESS.
    """
    service = VideoMeetingService(db)
    return service.start_meeting(current_user, consultation_id)


@router.post(
    "/{consultation_id}/video/end",
    response_model=VideoMeetingResponse,
)
def end_video_meeting(
    consultation_id: UUID,
    req: VideoMeetingEndRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Conclude the video consultation meeting and mark consultation as COMPLETED.
    """
    service = VideoMeetingService(db)
    notes = req.notes if req else None
    return service.end_meeting(current_user, consultation_id, notes=notes)


# --- Consultation Video Recording Endpoints ---


def _format_recording_response(rec: Any) -> RecordingResponse:
    return RecordingResponse(
        id=rec.id,
        consultation_id=rec.consultation_id,
        case_id=rec.case_id,
        recording_type=rec.recording_type,
        status=rec.status,
        started_at=rec.started_at,
        ended_at=rec.ended_at,
        duration_seconds=rec.duration_seconds,
        file_size_bytes=rec.file_size_bytes,
        mime_type=rec.mime_type,
        checksum_sha256=rec.checksum_sha256,
        playback_url=f"/api/v1/recordings/{rec.id}/play" if rec.status.value == "AVAILABLE" or rec.status == "AVAILABLE" else None,
        created_at=rec.created_at,
    )


@router.post(
    "/{consultation_id}/video/recording/consent",
    response_model=RecordingConsentResponse,
)
def grant_recording_consent(
    consultation_id: UUID,
    req: RecordingConsentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Explicitly grant or revoke recording consent for a consultation.
    Both Client and assigned Lawyer must consent before a recording can be started.
    """
    service = VideoRecordingService(db)
    consent = service.grant_consent(current_user, consultation_id, consented=req.consented)
    return RecordingConsentResponse.model_validate(consent)


@router.get(
    "/{consultation_id}/video/recording/consent-status",
    response_model=ConsentStatusResponse,
)
def get_recording_consent_status(
    consultation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieve current recording consent status for both participants.
    """
    service = VideoRecordingService(db)
    return service.get_consent_status(current_user, consultation_id)


@router.post(
    "/{consultation_id}/video/recording/start",
    response_model=RecordingStartResponse,
)
@limiter.limit("20/minute")
def start_recording(
    request: Request,
    consultation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Authoritatively begin a video recording session for an active consultation.
    Requires mutual consent from both client and lawyer.
    """
    service = VideoRecordingService(db)
    rec = service.start_recording(current_user, consultation_id)
    return RecordingStartResponse(
        recording_id=rec.id,
        consultation_id=rec.consultation_id,
        status=rec.status,
        started_at=rec.started_at,
    )


@router.post(
    "/{consultation_id}/video/recording/stop",
    response_model=RecordingStopResponse,
)
@limiter.limit("20/minute")
def stop_recording(
    request: Request,
    consultation_id: UUID,
    recording_id: UUID | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Stop the currently active recording session and prepare for binary finalization.
    """
    service = VideoRecordingService(db)
    rec = service.stop_recording(current_user, consultation_id, recording_id=recording_id)
    return RecordingStopResponse(
        recording_id=rec.id,
        consultation_id=rec.consultation_id,
        status=rec.status,
        duration_seconds=rec.duration_seconds,
        ended_at=rec.ended_at,
    )


@router.post(
    "/{consultation_id}/video/recording/upload",
    response_model=RecordingResponse,
)
@limiter.limit("10/minute")
async def upload_recording_file(
    request: Request,
    consultation_id: UUID,
    recording_id: UUID = Query(...),
    filename: str = Query("recording.webm"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Stream and finalize recorded video binary into local storage.
    Calculates SHA-256 checksum and marks the recording AVAILABLE.
    """
    service = VideoRecordingService(db)
    content_type = request.headers.get("content-type", "video/webm")
    rec = await service.finalize_upload_stream(
        user=current_user,
        consultation_id=consultation_id,
        recording_id=recording_id,
        async_stream=request.stream(),
        filename=filename,
        content_type=content_type,
    )
    return _format_recording_response(rec)


@router.get(
    "/{consultation_id}/recordings",
    response_model=RecordingListResponse,
)
def list_consultation_recordings(
    consultation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieve all authorized video recordings for a consultation.
    """
    service = VideoRecordingService(db)
    recordings = service.list_recordings(current_user, consultation_id)
    formatted = [_format_recording_response(r) for r in recordings]
    return RecordingListResponse(items=formatted, total=len(formatted))


# --- Consultation -> Case Linking Endpoints ---


@router.post(
    "/{consultation_id}/link-case",
    response_model=ConsultationResponse,
)
def link_consultation_to_case(
    consultation_id: UUID,
    req: ConsultationLinkCaseRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Link this consultation to an existing active legal case matter in LCC.
    Optionally assigns the lawyer as a LAWYER participant to the case.
    """
    service = ConsultationService(db)
    return service.link_case(
        current_user,
        consultation_id,
        case_id=req.case_id,
        assign_lawyer=req.assign_lawyer,
    )


@router.post(
    "/{consultation_id}/create-case",
    response_model=CaseResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_case_from_consultation(
    consultation_id: UUID,
    req: ConsultationCreateCaseRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a new legal case matter from this consultation, assigning the client as OWNER
    and the consultation lawyer as LAWYER participant.
    """
    service = ConsultationService(db)
    return service.create_case_from_consultation(
        current_user,
        consultation_id,
        title=req.title,
        description=req.description,
        practice_area=req.practice_area,
        court_jurisdiction=req.court_jurisdiction,
    )


# --- Consultation Notes Endpoints ---


@router.post(
    "/{consultation_id}/notes",
    response_model=ConsultationNoteResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_consultation_note(
    consultation_id: UUID,
    req: ConsultationNoteCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Record consultation advice, summary, or recommended action items.
    """
    service = ConsultationService(db)
    return service.add_consultation_note(
        current_user,
        consultation_id,
        summary=req.summary,
        action_items=req.action_items,
        client_shared=req.client_shared,
    )


@router.get(
    "/{consultation_id}/notes",
    response_model=list[ConsultationNoteResponse],
)
def get_consultation_notes(
    consultation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List consultation advice and notes. Clients see shared notes; lawyers and admins see all.
    """
    service = ConsultationService(db)
    return service.get_consultation_notes(current_user, consultation_id)
