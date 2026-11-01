import json
import logging
import secrets
from datetime import UTC, datetime, timedelta
from decimal import Decimal, ROUND_HALF_EVEN
from typing import Any
from uuid import UUID

TWOPLACES = Decimal("0.01")


def _to_decimal(val: Any) -> Decimal:
    if isinstance(val, Decimal):
        return val
    if val is None:
        return Decimal("0.00")
    return Decimal(str(val))


def _quantize(val: Decimal) -> Decimal:
    return val.quantize(TWOPLACES, rounding=ROUND_HALF_EVEN)

import io
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.responses import StreamingResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import RequireRole, get_current_user, get_db
from app.api.v1.auth import limiter
from app.core.config import settings
from app.core.exceptions import AuthorizationError, ResourceNotFoundError, ValidationError
from app.core.redis import get_redis_client
from app.core.security import verify_access_token
from app.core.storage import get_storage_provider
from app.core.identifiers import generate_uuid7
from app.models.case import Case, CaseParticipant, ParticipantRole, ParticipantStatus
from app.models.case_collaboration import CaseMessage, CaseMessageType
from app.models.direct_message import DirectMessage
from app.models.consultation_document import ConsultationDocument
from app.models.consultation import Consultation, ConsultationStatus
from app.models.notification import NotificationType
from app.models.payment import Payment, PaymentStatus
from app.models.user import AccountStatus, ClientProfile, LawyerProfile, User, UserRole
from app.schemas.auth import WSTicketResponse
from app.schemas.presence import PresenceStatus
from app.domain.consultations.lawyer_call_channel import incoming_call_channel_manager
from app.domain.notifications.notification_service import NotificationService
from app.domain.consultations.presence_service import presence_service

logger = logging.getLogger(__name__)
from app.schemas.case import CaseResponse
from app.schemas.consultation import (
    ConsultationCancelRequest,
    ConsultationCreate,
    ConsultationCreateCaseRequest,
    ConsultationDocumentResponse,
    ConsultationLinkCaseRequest,
    ConsultationNoShowRequest,
    ConsultationPricingBreakdown,
    ConsultationPricingResponse,
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
    VideoRoomAccessStatusResponse,
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
from app.domain.consultations.consultation_service import ConsultationService
from app.domain.consultations.message_service import MessageService
from app.domain.payments.payment_service import PaymentService
from app.domain.consultations.video_meeting_service import VideoMeetingService
from app.domain.consultations.video_recording_service import VideoRecordingService

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


@router.get("/pricing-preview", response_model=ConsultationPricingResponse)
def get_consultation_pricing_preview(
    lawyer_id: UUID = Query(..., description="ID of the advocate"),
    duration_minutes: int = Query(30, ge=15, le=240),
    db: Session = Depends(get_db),
):
    """
    Authoritative pricing preview calculating advocate consultation fee,
    statutory 18% GST (9% CGST + 9% SGST), and total payable amount.
    """
    lawyer = (
        db.query(LawyerProfile)
        .filter(
            (LawyerProfile.id == lawyer_id) | (LawyerProfile.user_id == lawyer_id),
            LawyerProfile.deleted_at.is_(None),
        )
        .first()
    )
    if not lawyer:
        raise ResourceNotFoundError("Lawyer profile not found")

    base_fee = _to_decimal(lawyer.consultation_fee) if lawyer.consultation_fee is not None else Decimal("2500.00")
    ratio = Decimal(str(max(1, duration_minutes // 30)))
    fee_amount = _quantize(base_fee * ratio)
    gst_percent = _to_decimal(getattr(settings, "COMMERCIAL_GST_PERCENT", 18.0))
    gst_rate = _quantize(gst_percent / Decimal("100.0"))
    gst_amount = _quantize(fee_amount * gst_rate)
    platform_fee = Decimal("0.00")
    total_amount = _quantize(fee_amount + gst_amount + platform_fee)

    cgst = _quantize(gst_amount / Decimal("2.0"))
    sgst = _quantize(gst_amount - cgst)

    return ConsultationPricingResponse(
        lawyer_id=lawyer.id,
        duration_minutes=duration_minutes,
        fee_amount=float(fee_amount),
        gst_rate=float(gst_rate),
        gst_amount=float(gst_amount),
        platform_fee=float(platform_fee),
        total_amount=float(total_amount),
        currency="INR",
        breakdown=ConsultationPricingBreakdown(
            cgst=float(cgst),
            sgst=float(sgst),
            description=f"{int(gst_percent)}% GST ({int(gst_percent / 2)}% Central GST + {int(gst_percent / 2)}% State GST)",
        ),
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

    consultation_service = ConsultationService(db)
    # Expire stale calls waiting past the ring timeout
    consultation_service.expire_stale_incoming_calls(lawyer_profile.id)

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


@router.post("/ws-ticket", response_model=WSTicketResponse)
def create_websocket_ticket(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Generate a short-lived (60s), single-use ticket for authenticating the incoming-calls WebSocket.
    Restricted to verified lawyers and platform administrators.
    """
    if current_user.role not in (UserRole.LAWYER, UserRole.ADMIN):
        raise AuthorizationError("Only lawyers and admins can acquire an incoming call WebSocket ticket")

    lawyer_profile = (
        db.query(LawyerProfile)
        .filter(LawyerProfile.user_id == current_user.id, LawyerProfile.deleted_at.is_(None))
        .first()
    )
    if not lawyer_profile and current_user.role != UserRole.ADMIN:
        raise AuthorizationError("No active lawyer profile found for this account")

    ticket = secrets.token_urlsafe(32)
    ticket_payload = {
        "user_id": str(current_user.id),
        "lawyer_id": str(lawyer_profile.id) if lawyer_profile else None,
        "role": current_user.role.value,
        "created_at": datetime.now(UTC).isoformat(),
    }

    redis_client = get_redis_client()
    key = f"{settings.REDIS_KEY_PREFIX}:{settings.ENVIRONMENT}:ws_ticket:{ticket}"
    redis_client.set(key, json.dumps(ticket_payload).encode("utf-8"), ex=60)

    return WSTicketResponse(ticket=ticket, expires_in=60)


@router.websocket("/ws/incoming-calls")
async def websocket_incoming_calls(
    websocket: WebSocket,
    ticket: str | None = Query(None, description="Short-lived single-use WebSocket ticket"),
    token: str | None = Query(None, description="Legacy JWT bearer access token fallback"),
    db: Session = Depends(get_db),
):
    """
    Real-time WebSocket connection for lawyers to receive instantaneous incoming call alerts.
    Authenticates via single-use ticket (or legacy bearer token fallback).
    Supports multi-tab broadcasting and automatic presence heartbeat.
    """
    user_id: UUID | None = None
    if ticket:
        redis_client = get_redis_client()
        key = f"{settings.REDIS_KEY_PREFIX}:{settings.ENVIRONMENT}:ws_ticket:{ticket}"
        raw = redis_client.get(key)
        if not raw:
            logger.warning("Incoming call WebSocket auth rejected: ticket invalid or expired")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        # Single-use: delete immediately upon consumption
        redis_client.delete(key)
        try:
            t_data = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
            user_id = UUID(t_data["user_id"])
        except Exception as e:
            logger.warning("Incoming call WebSocket auth rejected: corrupted ticket payload: %s", e)
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
    elif token:
        try:
            payload = verify_access_token(token)
            user_id = UUID(payload["sub"])
        except Exception as e:
            logger.warning("Incoming call WebSocket auth rejected: %s", e)
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
    else:
        logger.warning("Incoming call WebSocket auth rejected: neither ticket nor token provided")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    user = (
        db.query(User)
        .filter(User.id == user_id, User.deleted_at.is_(None))
        .first()
    )
    if not user or user.account_status != AccountStatus.ACTIVE or user.role not in (UserRole.LAWYER, UserRole.ADMIN):
        logger.warning("Incoming call WebSocket unauthorized for user %s", user_id)
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    lawyer_profile = (
        db.query(LawyerProfile)
        .filter(LawyerProfile.user_id == user.id, LawyerProfile.deleted_at.is_(None))
        .first()
    )
    if not lawyer_profile:
        logger.warning("Incoming call WebSocket: no lawyer profile for user %s", user_id)
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    lawyer_id = lawyer_profile.id
    await incoming_call_channel_manager.connect(lawyer_id, websocket)

    # Immediately register lawyer presence
    presence_service.record_heartbeat(user.id, lawyer_id, available_preference=True)

    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
                presence_service.record_heartbeat(user.id, lawyer_id, available_preference=True)
            elif data == "heartbeat":
                presence_service.record_heartbeat(user.id, lawyer_id, available_preference=True)
                await websocket.send_json({"type": "heartbeat_ack", "status": "AVAILABLE"})
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.debug("Incoming call WebSocket disconnected: %s", e)
    finally:
        await incoming_call_channel_manager.disconnect(lawyer_id, websocket)


from pydantic import BaseModel


class InstantCallRequest(BaseModel):
    lawyer_id: UUID
    case_id: UUID | None = None
    duration_minutes: int = 30


@router.get("/lawyer-call-status")
def get_lawyer_call_status(
    lawyer_id: UUID = Query(..., description="ID of the lawyer profile or user"),
    case_id: UUID | None = Query(None, description="Optional case ID to check existing consultations"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Check if a lawyer is currently online, in another meeting, or available for video consultation.
    """
    consultation_service = ConsultationService(db)
    is_avail, reason, p_status = consultation_service.is_lawyer_available(lawyer_id)

    # Check if there is an active consultation for this client and lawyer
    client_profile = db.query(ClientProfile).filter(ClientProfile.user_id == current_user.id).first()
    active_con_id = None
    is_meeting_with_me = False

    lawyer_profile = (
        db.query(LawyerProfile)
        .filter(or_(LawyerProfile.id == lawyer_id, LawyerProfile.user_id == lawyer_id))
        .first()
    )

    if client_profile and lawyer_profile:
        # Check if currently in an active meeting with THIS client
        in_progress_con = (
            db.query(Consultation)
            .filter(
                Consultation.client_id == client_profile.id,
                Consultation.lawyer_id == lawyer_profile.id,
                Consultation.status == ConsultationStatus.IN_PROGRESS,
                Consultation.deleted_at.is_(None),
            )
            .first()
        )
        if in_progress_con:
            is_meeting_with_me = True
            active_con_id = str(in_progress_con.id)

        if not active_con_id:
            query = db.query(Consultation).filter(
                Consultation.client_id == client_profile.id,
                Consultation.lawyer_id == lawyer_profile.id,
                Consultation.deleted_at.is_(None),
                Consultation.status.in_([
                    ConsultationStatus.REQUESTED,
                    ConsultationStatus.ACCEPTED,
                    ConsultationStatus.SCHEDULED,
                    ConsultationStatus.PAID,
                ]),
            )
            if case_id:
                query = query.filter(Consultation.case_id == case_id)
            active_con = query.order_by(Consultation.created_at.desc()).first()
            if active_con:
                active_con_id = str(active_con.id)
                is_meeting_with_me = True

    is_online = p_status in (PresenceStatus.ONLINE, PresenceStatus.AVAILABLE, PresenceStatus.BUSY)
    is_in_meeting = p_status == PresenceStatus.BUSY and not is_meeting_with_me

    if is_meeting_with_me:
        status_label = "Meeting Ready with You"
        can_call = True
    elif is_in_meeting:
        status_label = "In Another Meeting"
        can_call = False
    elif is_avail:
        status_label = "Available for Video Call"
        can_call = True
    else:
        status_label = "Offline"
        can_call = False

    return {
        "lawyer_id": str(lawyer_id),
        "is_online": is_online,
        "is_available": is_avail or is_meeting_with_me,
        "is_in_meeting": is_in_meeting,
        "is_meeting_with_me": is_meeting_with_me,
        "presence_status": p_status.value,
        "status_label": status_label,
        "reason": reason,
        "can_call_now": can_call,
        "active_consultation_id": active_con_id,
    }


def _notify_lawyer_meeting_live(
    db: Session,
    consultation: Consultation,
    client_user: User,
    consultation_service: ConsultationService,
):
    try:
        lawyer_prof = (
            db.query(LawyerProfile)
            .filter(LawyerProfile.id == consultation.lawyer_id)
            .first()
        )
        if not lawyer_prof or not lawyer_prof.user_id:
            return

        client_name = client_user.full_name or (client_user.email.split("@")[0] if client_user.email else "Client")
        case_title = "Direct Consultation"
        if consultation.case_id:
            c_obj = db.query(Case).filter(Case.id == consultation.case_id).first()
            if c_obj and c_obj.title:
                case_title = c_obj.title

            # Ensure both client and lawyer are enrolled as active participants in this case
            for uid, role in [(client_user.id, ParticipantRole.OWNER), (lawyer_prof.user_id, ParticipantRole.LAWYER)]:
                p_existing = (
                    db.query(CaseParticipant)
                    .filter(
                        CaseParticipant.case_id == consultation.case_id,
                        CaseParticipant.user_id == uid,
                    )
                    .first()
                )
                if not p_existing:
                    new_p = CaseParticipant(
                        id=generate_uuid7(),
                        case_id=consultation.case_id,
                        user_id=uid,
                        participant_role=role,
                        status=ParticipantStatus.ACTIVE,
                        joined_at=datetime.now(UTC),
                    )
                    db.add(new_p)

        # 1. Direct message in chat thread
        chat_msg_content = f"📹 Video Call Started: I have joined the video room for case '{case_title}'. Click to join: /consultations/{consultation.id}/room"
        dm = DirectMessage(
            id=generate_uuid7(),
            sender_id=client_user.id,
            recipient_id=lawyer_prof.user_id,
            content=chat_msg_content,
            is_read=False,
        )
        db.add(dm)

        # 2. CaseMessage if linked to case
        if consultation.case_id:
            cm = CaseMessage(
                id=generate_uuid7(),
                case_id=consultation.case_id,
                sender_id=client_user.id,
                content=chat_msg_content,
                message_type=CaseMessageType.GENERAL,
            )
            db.add(cm)

        # 3. In-app notification
        notification_service = NotificationService(db)
        notification_service.create_notification(
            user_id=lawyer_prof.user_id,
            type=NotificationType.CONSULTATION_REQUESTED,
            title="Client Joined Video Meeting",
            message=f"{client_name} has joined the video meeting for case '{case_title}'. Click to join now.",
            case_id=consultation.case_id,
            consultation_id=consultation.id,
            metadata={
                "consultation_id": str(consultation.id),
                "action": "incoming_video_call",
                "client_name": client_name,
                "case_id": str(consultation.case_id) if consultation.case_id else None,
                "case_title": case_title,
                "room_url": f"/consultations/{consultation.id}/room",
            },
            event_id=f"incoming_call_{consultation.id}_{int(datetime.now(UTC).timestamp())}",
        )

        db.commit()

        # 4. Real-time WebSocket ringing alert
        call_data = {
            "id": str(consultation.id),
            "client_name": client_name,
            "fee": float(consultation.fee_amount) if consultation.fee_amount else 0.0,
            "case_id": str(consultation.case_id) if consultation.case_id else None,
            "case_title": case_title,
            "room_url": f"/consultations/{consultation.id}/room",
            "scheduled_at": consultation.scheduled_at.isoformat() if consultation.scheduled_at else None,
            "created_at": consultation.created_at.isoformat() if consultation.created_at else None,
            "ring_timeout_seconds": settings.INSTANT_CALL_RING_TIMEOUT_SECONDS,
        }
        consultation_service._dispatch_async(
            incoming_call_channel_manager.notify_incoming_call(
                consultation.lawyer_id, call_data
            )
        )
    except Exception as exc:
        logger.warning("Error notifying lawyer of client meeting join: %s", exc)


@router.post("/instant-call")
def request_instant_video_call(
    req: InstantCallRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Initiate or join an immediate video call with a lawyer.
    If an active consultation already exists, reuses it.
    Otherwise creates an instant consultation and provisions the room immediately.
    """
    consultation_service = ConsultationService(db)
    client_profile = db.query(ClientProfile).filter(ClientProfile.user_id == current_user.id).first()
    if not client_profile and current_user.role == UserRole.CLIENT:
        raise ResourceNotFoundError("Client profile not found")

    vms = VideoMeetingService(db)

    # If an active consultation already exists, reuse it directly
    if client_profile:
        existing = (
            db.query(Consultation)
            .filter(
                Consultation.client_id == client_profile.id,
                Consultation.deleted_at.is_(None),
                Consultation.status.in_([
                    ConsultationStatus.IN_PROGRESS,
                    ConsultationStatus.ACCEPTED,
                    ConsultationStatus.SCHEDULED,
                    ConsultationStatus.PAID,
                    ConsultationStatus.REQUESTED,
                ]),
            )
        )
        if req.case_id:
            existing = existing.filter(Consultation.case_id == req.case_id)
        con = existing.order_by(Consultation.created_at.desc()).first()
        if con:
            m = vms.ensure_meeting_provisioned(con)
            if con.status != ConsultationStatus.IN_PROGRESS:
                con.status = ConsultationStatus.IN_PROGRESS
                db.commit()
            _notify_lawyer_meeting_live(db, con, current_user, consultation_service)
            return {
                "consultation_id": str(con.id),
                "room_id": m.room_id,
                "room_url": f"/consultations/{con.id}/room",
                "status": con.status.value,
                "is_new": False,
            }

    # Create new instant consultation
    create_req = ConsultationCreate(
        lawyer_id=req.lawyer_id,
        case_id=req.case_id,
        duration_minutes=req.duration_minutes,
        is_instant=True,
    )
    new_con = consultation_service.request_consultation(current_user, create_req)
    m = vms.ensure_meeting_provisioned(new_con)
    new_con.status = ConsultationStatus.IN_PROGRESS
    db.commit()
    _notify_lawyer_meeting_live(db, new_con, current_user, consultation_service)

    return {
        "consultation_id": str(new_con.id),
        "room_id": m.room_id,
        "room_url": f"/consultations/{new_con.id}/room",
        "status": new_con.status.value,
        "is_new": True,
    }



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
    if not settings.ENABLE_TEST_PAYMENTS or settings.ENVIRONMENT in ("production", "staging"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Simulated test payments are strictly disabled in this environment.",
        )

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

        call_data = {
            "id": str(consultation.id),
            "client_name": client_name,
            "fee": float(consultation.fee_amount),
            "case_id": str(consultation.case_id) if consultation.case_id else None,
            "scheduled_at": consultation.scheduled_at.isoformat() if consultation.scheduled_at else None,
            "created_at": consultation.created_at.isoformat() if consultation.created_at else None,
            "ring_timeout_seconds": settings.INSTANT_CALL_RING_TIMEOUT_SECONDS,
        }
        consultation_service._dispatch_async(
            incoming_call_channel_manager.notify_incoming_call(
                consultation.lawyer_id, call_data
            )
        )
    except Exception as e:
        logger.warning("Error notifying lawyer of paid consultation: %s", e)

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
    "/{consultation_id}/video/access-status",
    response_model=VideoRoomAccessStatusResponse,
)
@limiter.limit("60/minute")
def get_video_meeting_access_status(
    request: Request,
    consultation_id: UUID,
    bypass_time: bool = Query(default=False, description="Bypass scheduled time window check for instant testing or when advocate is online"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Evaluates server-authoritative eligibility to join the video consultation room.
    Provides precise UTC and IST join-window timing, countdown, and blocking reason without throwing 422.
    """
    service = VideoMeetingService(db)
    return service.get_room_access_status(current_user, consultation_id, bypass_time_window=bypass_time)


@router.get(
    "/{consultation_id}/video/join",
    response_model=VideoJoinInfoResponse,
)
@limiter.limit("60/minute")
def join_video_meeting(
    request: Request,
    consultation_id: UUID,
    bypass_time: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieve cryptographically signed join credentials for the in-app video consultation room.
    Enforces strict participant authorization (Client, assigned Lawyer, or Admin).
    """
    service = VideoMeetingService(db)
    return service.get_join_information(current_user, consultation_id, bypass_time_window=bypass_time)


@router.post(
    "/{consultation_id}/video/reconnect",
    response_model=VideoJoinInfoResponse,
)
@limiter.limit("60/minute")
def reconnect_video_meeting(
    request: Request,
    consultation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Idempotent reconnect and session restoration endpoint for active video consultations.
    Reissues fresh room credentials without creating duplicate meetings or drifting business status.
    """
    service = VideoMeetingService(db)
    return service.restore_or_reconnect_session(current_user, consultation_id)


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
    res = service.start_meeting(current_user, consultation_id)
    if current_user.role != UserRole.LAWYER:
        con = db.query(Consultation).filter(Consultation.id == consultation_id).first()
        if con:
            consultation_service = ConsultationService(db)
            _notify_lawyer_meeting_live(db, con, current_user, consultation_service)
    return res


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
    Recording is disabled.
    """
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Video call recording is disabled.",
    )


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
    return ConsentStatusResponse(
        consultation_id=consultation_id,
        client_consented=False,
        lawyer_consented=False,
        can_record=False,
    )


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
    Video call recording is disabled.
    """
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Video call recording is disabled.",
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
    Video call recording is disabled.
    """
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Video call recording is disabled.",
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
    Video call recording upload is disabled.
    """
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Video call recording upload is disabled.",
    )


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
    return RecordingListResponse(items=[], total=0)


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


# --------------------------------------------------------------------------
# IN-CONSULTATION SHARED DOCUMENTS ENDPOINTS
# --------------------------------------------------------------------------


@router.post(
    "/{consultation_id}/documents",
    response_model=ConsultationDocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("30/minute")
async def upload_consultation_document(
    request: Request,
    consultation_id: UUID,
    file: UploadFile = File(...),
    description: str | None = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Upload and share a document directly within a consultation session.
    """
    consultation = db.query(Consultation).filter(Consultation.id == consultation_id).first()
    if not consultation:
        raise ResourceNotFoundError("Consultation not found")

    is_client = current_user.client_profile and consultation.client_id == current_user.client_profile.id
    is_lawyer = current_user.lawyer_profile and consultation.lawyer_id == current_user.lawyer_profile.id
    is_admin = current_user.role == UserRole.ADMIN
    if not (is_client or is_lawyer or is_admin):
        raise AuthorizationError("You do not have access to this consultation.")

    file_bytes = await file.read()
    if len(file_bytes) > 25 * 1024 * 1024:  # 25 MB limit
        raise ValidationError("File size exceeds 25 MB limit.")

    from app.core.file_validation import validate_filename_security
    file_name = validate_filename_security(file.filename or "shared_document.pdf")
    mime_type = file.content_type or "application/octet-stream"
    storage_key = f"consultations/{consultation_id}/{secrets.token_hex(8)}_{file_name}"

    storage = get_storage_provider()
    storage.put_object_bytes(storage_key, file_bytes, mime_type)

    doc = ConsultationDocument(
        consultation_id=consultation_id,
        uploader_id=current_user.id,
        file_name=file_name,
        file_size=len(file_bytes),
        mime_type=mime_type,
        storage_key=storage_key,
        description=description,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    uploader_name = current_user.full_name or "Participant"
    uploader_role = "LAWYER" if is_lawyer else ("CLIENT" if is_client else "ADMIN")

    return ConsultationDocumentResponse(
        id=doc.id,
        consultation_id=doc.consultation_id,
        uploader_id=doc.uploader_id,
        uploader_name=uploader_name,
        uploader_role=uploader_role,
        file_name=doc.file_name,
        file_size=doc.file_size,
        mime_type=doc.mime_type,
        description=doc.description,
        download_url=f"/api/v1/consultations/{consultation_id}/documents/{doc.id}/download",
        created_at=doc.created_at,
    )


@router.get(
    "/{consultation_id}/documents",
    response_model=list[ConsultationDocumentResponse],
)
def get_consultation_documents(
    consultation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List all documents shared during or for this consultation.
    """
    consultation = db.query(Consultation).filter(Consultation.id == consultation_id).first()
    if not consultation:
        raise ResourceNotFoundError("Consultation not found")

    is_client = current_user.client_profile and consultation.client_id == current_user.client_profile.id
    is_lawyer = current_user.lawyer_profile and consultation.lawyer_id == current_user.lawyer_profile.id
    is_admin = current_user.role == UserRole.ADMIN
    if not (is_client or is_lawyer or is_admin):
        raise AuthorizationError("You do not have access to this consultation.")

    docs = (
        db.query(ConsultationDocument)
        .filter(ConsultationDocument.consultation_id == consultation_id)
        .order_by(ConsultationDocument.created_at.asc())
        .all()
    )

    results = []
    for d in docs:
        uploader = db.query(User).filter(User.id == d.uploader_id).first()
        u_name = uploader.full_name if uploader and uploader.full_name else "Participant"
        u_role = "LAWYER" if (uploader and uploader.role == UserRole.LAWYER) else "CLIENT"

        results.append(
            ConsultationDocumentResponse(
                id=d.id,
                consultation_id=d.consultation_id,
                uploader_id=d.uploader_id,
                uploader_name=u_name,
                uploader_role=u_role,
                file_name=d.file_name,
                file_size=d.file_size,
                mime_type=d.mime_type,
                description=d.description,
                download_url=f"/api/v1/consultations/{consultation_id}/documents/{d.id}/download",
                created_at=d.created_at,
            )
        )
    return results


@router.get(
    "/{consultation_id}/documents/{document_id}/download",
)
def download_consultation_document(
    consultation_id: UUID,
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Download a shared consultation document.
    """
    doc = (
        db.query(ConsultationDocument)
        .filter(
            ConsultationDocument.id == document_id,
            ConsultationDocument.consultation_id == consultation_id,
        )
        .first()
    )
    if not doc:
        raise ResourceNotFoundError("Consultation document not found")

    consultation = db.query(Consultation).filter(Consultation.id == consultation_id).first()
    if not consultation:
        raise ResourceNotFoundError("Consultation not found")

    is_client = current_user.client_profile and consultation.client_id == current_user.client_profile.id
    is_lawyer = current_user.lawyer_profile and consultation.lawyer_id == current_user.lawyer_profile.id
    is_admin = current_user.role == UserRole.ADMIN
    if not (is_client or is_lawyer or is_admin):
        raise AuthorizationError("You do not have access to this document.")

    storage = get_storage_provider()
    file_bytes = storage.get_object_bytes(doc.storage_key)
    if not file_bytes:
        raise ResourceNotFoundError("Document file bytes not found")

    from urllib.parse import quote
    safe_filename = quote(doc.file_name)

    return StreamingResponse(
        io.BytesIO(file_bytes),
        media_type=doc.mime_type,
        headers={
            "Content-Disposition": f'attachment; filename="{doc.file_name}"; filename*=UTF-8\'\'{safe_filename}',
            "Content-Length": str(len(file_bytes)),
        },
    )

