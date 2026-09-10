import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.identifiers import generate_uuid7
from app.models.case import Case, CaseParticipant, ParticipantRole, ParticipantStatus
from app.models.case_collaboration import CaseMessage, CaseMessageType
from app.models.consultation import Consultation
from app.models.court_case import CourtCase
from app.models.direct_message import DirectMessage
from app.models.user import ClientProfile, LawyerProfile, User, UserRole

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/messages", tags=["messages"])


class SendMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000, description="Message content")
    case_id: uuid.UUID | None = Field(default=None, description="Optional target case ID for message sync")


def _get_all_cases_between(
    db: Session, user1_id: uuid.UUID, user2_id: uuid.UUID
) -> list[dict[str, Any]]:
    """
    Finds all active cases shared or associated between user1 and user2.
    """
    p1 = (
        db.query(CaseParticipant.case_id)
        .filter(
            CaseParticipant.user_id == user1_id,
            CaseParticipant.status == ParticipantStatus.ACTIVE,
        )
    )
    cases = (
        db.query(Case)
        .join(CaseParticipant, CaseParticipant.case_id == Case.id)
        .filter(
            CaseParticipant.user_id == user2_id,
            CaseParticipant.status == ParticipantStatus.ACTIVE,
            Case.id.in_(p1),
            Case.deleted_at.is_(None),
        )
        .order_by(Case.updated_at.desc(), Case.created_at.desc())
        .all()
    )

    seen = {c.id for c in cases}

    # Check consultation linked cases
    cp1 = db.query(ClientProfile.id).filter(ClientProfile.user_id == user1_id).scalar()
    lp1 = db.query(LawyerProfile.id).filter(LawyerProfile.user_id == user1_id).scalar()
    cp2 = db.query(ClientProfile.id).filter(ClientProfile.user_id == user2_id).scalar()
    lp2 = db.query(LawyerProfile.id).filter(LawyerProfile.user_id == user2_id).scalar()

    conditions = []
    if cp1 and lp2:
        conditions.append((Consultation.client_id == cp1) & (Consultation.lawyer_id == lp2))
    if cp2 and lp1:
        conditions.append((Consultation.client_id == cp2) & (Consultation.lawyer_id == lp1))

    if conditions:
        cons_cases = (
            db.query(Case)
            .join(Consultation, Consultation.case_id == Case.id)
            .filter(
                Consultation.case_id.isnot(None),
                Consultation.deleted_at.is_(None),
                Case.deleted_at.is_(None),
                or_(*conditions),
            )
            .all()
        )
        for cc in cons_cases:
            if cc.id not in seen:
                cases.append(cc)
                seen.add(cc.id)

    # If demo lawyer and client, also ensure their created cases are listed
    for uid in [user1_id, user2_id]:
        owned = (
            db.query(Case)
            .join(CaseParticipant, CaseParticipant.case_id == Case.id)
            .filter(
                CaseParticipant.user_id == uid,
                Case.deleted_at.is_(None),
            )
            .all()
        )
        for oc in owned:
            if oc.id not in seen:
                cases.append(oc)
                seen.add(oc.id)

    result = []
    for sc in cases:
        court_case = (
            db.query(CourtCase)
            .filter(CourtCase.case_id == sc.id, CourtCase.deleted_at.is_(None))
            .first()
        )
        case_ref = court_case.case_number if (court_case and court_case.case_number) else f"REF #{str(sc.id)[:8].upper()}"
        result.append({
            "id": str(sc.id),
            "title": sc.title,
            "caseRef": case_ref,
        })
    return result


def _resolve_active_case_between(
    db: Session, user1_id: uuid.UUID, user2_id: uuid.UUID
) -> tuple[str | None, str | None, str]:
    """
    Dynamically finds the active case shared between user1 and user2.
    Returns (case_id, case_title, case_ref).
    """
    # 1. Check if both users are active participants in the same case
    p1 = (
        db.query(CaseParticipant.case_id)
        .filter(
            CaseParticipant.user_id == user1_id,
            CaseParticipant.status == ParticipantStatus.ACTIVE,
        )
    )
    shared_case = (
        db.query(Case)
        .join(CaseParticipant, CaseParticipant.case_id == Case.id)
        .filter(
            CaseParticipant.user_id == user2_id,
            CaseParticipant.status == ParticipantStatus.ACTIVE,
            Case.id.in_(p1),
            Case.deleted_at.is_(None),
        )
        .order_by(Case.updated_at.desc(), Case.created_at.desc())
        .first()
    )

    # 2. Check if linked via a consultation between lawyer and client
    if not shared_case:
        cp1 = db.query(ClientProfile.id).filter(ClientProfile.user_id == user1_id).scalar()
        lp1 = db.query(LawyerProfile.id).filter(LawyerProfile.user_id == user1_id).scalar()
        cp2 = db.query(ClientProfile.id).filter(ClientProfile.user_id == user2_id).scalar()
        lp2 = db.query(LawyerProfile.id).filter(LawyerProfile.user_id == user2_id).scalar()

        conditions = []
        if cp1 and lp2:
            conditions.append((Consultation.client_id == cp1) & (Consultation.lawyer_id == lp2))
        if cp2 and lp1:
            conditions.append((Consultation.client_id == cp2) & (Consultation.lawyer_id == lp1))

        if conditions:
            consultation = (
                db.query(Consultation)
                .filter(
                    Consultation.case_id.isnot(None),
                    Consultation.deleted_at.is_(None),
                    or_(*conditions),
                )
                .order_by(Consultation.created_at.desc())
                .first()
            )
            if consultation and consultation.case:
                shared_case = consultation.case
                # Ensure lawyer is enrolled as a participant
                lawyer_user_id = user1_id if lp1 else user2_id
                existing_p = (
                    db.query(CaseParticipant)
                    .filter(
                        CaseParticipant.case_id == shared_case.id,
                        CaseParticipant.user_id == lawyer_user_id,
                    )
                    .first()
                )
                if not existing_p:
                    lawyer_part = CaseParticipant(
                        id=generate_uuid7(),
                        case_id=shared_case.id,
                        user_id=lawyer_user_id,
                        participant_role=ParticipantRole.LAWYER,
                        status=ParticipantStatus.ACTIVE,
                        joined_at=datetime.now(UTC),
                    )
                    db.add(lawyer_part)
                    db.commit()

    # 3. Fallback to any active case owned by client if they are collaborating
    if not shared_case:
        for uid in [user1_id, user2_id]:
            client_case = (
                db.query(Case)
                .join(CaseParticipant, CaseParticipant.case_id == Case.id)
                .filter(
                    CaseParticipant.user_id == uid,
                    CaseParticipant.participant_role == ParticipantRole.OWNER,
                    CaseParticipant.status == ParticipantStatus.ACTIVE,
                    Case.deleted_at.is_(None),
                )
                .order_by(Case.created_at.desc())
                .first()
            )
            if client_case:
                shared_case = client_case
                break

    if shared_case:
        court_case = (
            db.query(CourtCase)
            .filter(CourtCase.case_id == shared_case.id, CourtCase.deleted_at.is_(None))
            .first()
        )
        case_ref = court_case.case_number if (court_case and court_case.case_number) else shared_case.title
        return str(shared_case.id), shared_case.title, case_ref

    return None, None, "Direct Consultation"


def _format_timestamp(dt: datetime | None) -> str:
    if not dt:
        return ""
    now = datetime.now(UTC)
    # Ensure dt has tzinfo if naive
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    diff = now - dt
    if diff.total_seconds() < 86400 and dt.date() == now.date():
        return dt.strftime("%I:%M %p").lstrip("0")
    elif diff.total_seconds() < 172800 and (now.date() - dt.date()).days == 1:
        return "Yesterday"
    elif diff.total_seconds() < 86400 * 7:
        return dt.strftime("%a %I:%M %p")
    else:
        return dt.strftime("%b %d, %Y")


def _get_user_display(user: User, db: Session) -> dict[str, str]:
    name = user.full_name or user.email.split("@")[0]
    role = "client"
    if user.role == UserRole.LAWYER:
        role = "lawyer"
        lp = db.query(LawyerProfile).filter(LawyerProfile.user_id == user.id).first()
        if lp and lp.full_name:
            name = lp.full_name
    elif user.role == UserRole.CLIENT:
        cp = db.query(ClientProfile).filter(ClientProfile.user_id == user.id).first()
        if cp and cp.full_name:
            name = cp.full_name
    elif user.role == UserRole.ADMIN:
        role = "admin"
    return {"name": name, "role": role}


@router.get("/threads")
def list_message_threads(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """
    List all messaging threads for the current user.
    If current user is client: returns threads with their retained lawyers.
    If current user is lawyer: returns threads with their clients.
    """
    partner_ids: set[uuid.UUID] = set()

    # 1. Partners from existing direct messages
    existing_msgs = (
        db.query(DirectMessage)
        .filter(
            or_(
                DirectMessage.sender_id == current_user.id,
                DirectMessage.recipient_id == current_user.id,
            )
        )
        .all()
    )
    for m in existing_msgs:
        if m.sender_id != current_user.id:
            partner_ids.add(m.sender_id)
        if m.recipient_id != current_user.id:
            partner_ids.add(m.recipient_id)

    # 2. Partners from consultations
    if current_user.role == UserRole.CLIENT:
        cp = db.query(ClientProfile).filter(ClientProfile.user_id == current_user.id).first()
        if cp:
            consultations = db.query(Consultation).filter(Consultation.client_id == cp.id).all()
            for c in consultations:
                lp = db.query(LawyerProfile).filter(LawyerProfile.id == c.lawyer_id).first()
                if lp and lp.user_id:
                    partner_ids.add(lp.user_id)

        # Ensure default advocate Ananya Roy is available if no partners found
        if not partner_ids:
            advocate_user = db.query(User).filter(User.email == "advocate@lcc.test").first()
            if advocate_user and advocate_user.id != current_user.id:
                partner_ids.add(advocate_user.id)

    elif current_user.role == UserRole.LAWYER:
        lp = db.query(LawyerProfile).filter(LawyerProfile.user_id == current_user.id).first()
        if lp:
            consultations = db.query(Consultation).filter(Consultation.lawyer_id == lp.id).all()
            for c in consultations:
                cp = db.query(ClientProfile).filter(ClientProfile.id == c.client_id).first()
                if cp and cp.user_id:
                    partner_ids.add(cp.user_id)

        # Ensure default client Vikram Sharma is available if no partners found
        if not partner_ids:
            client_user = db.query(User).filter(User.email == "client@lcc.test").first()
            if client_user and client_user.id != current_user.id:
                partner_ids.add(client_user.id)

    # 3. Build thread items
    threads = []
    for pid in partner_ids:
        partner_user = db.query(User).filter(User.id == pid).first()
        if not partner_user:
            continue

        partner_info = _get_user_display(partner_user, db)

        # Find latest message
        latest_msg = (
            db.query(DirectMessage)
            .filter(
                or_(
                    (DirectMessage.sender_id == current_user.id)
                    & (DirectMessage.recipient_id == pid),
                    (DirectMessage.sender_id == pid)
                    & (DirectMessage.recipient_id == current_user.id),
                )
            )
            .order_by(DirectMessage.created_at.desc())
            .first()
        )

        # If no message exists yet between default client and advocate, seed initial message
        if not latest_msg:
            # Check if this is the demo client/advocate pair
            advocate_user = db.query(User).filter(User.email == "advocate@lcc.test").first()
            client_user = db.query(User).filter(User.email == "client@lcc.test").first()
            if advocate_user and client_user and (
                (current_user.id == client_user.id and pid == advocate_user.id)
                or (current_user.id == advocate_user.id and pid == client_user.id)
            ):
                seeded = DirectMessage(
                    id=generate_uuid7(),
                    sender_id=advocate_user.id,
                    recipient_id=client_user.id,
                    content="I have uploaded the certified copy of the sale deed. Please review before filing.",
                    is_read=False,
                )
                db.add(seeded)
                db.commit()
                db.refresh(seeded)
                latest_msg = seeded

        # Count unread messages received from partner
        unread_count = (
            db.query(DirectMessage)
            .filter(
                DirectMessage.sender_id == pid,
                DirectMessage.recipient_id == current_user.id,
                DirectMessage.is_read == False,  # noqa: E712
            )
            .count()
        )

        # Dynamic case reference determination
        case_id, case_title, case_ref = _resolve_active_case_between(db, current_user.id, pid)

        last_content = latest_msg.content if latest_msg else "Start a conversation..."
        timestamp = _format_timestamp(latest_msg.created_at) if latest_msg else "New"
        sort_key = latest_msg.created_at.isoformat() if latest_msg else "1970-01-01T00:00:00"

        threads.append(
            {
                "id": str(pid),
                "partnerId": str(pid),
                "senderName": partner_info["name"],
                "senderRole": partner_info["role"],
                "lastMessage": last_content,
                "timestamp": timestamp,
                "unreadCount": unread_count,
                "caseId": case_id,
                "caseTitle": case_title,
                "caseRef": case_ref,
                "_sortKey": sort_key,
            }
        )

    # Sort threads by most recent message
    threads.sort(key=lambda t: str(t["_sortKey"]), reverse=True)
    return threads


@router.get("/threads/{partner_id}")
def get_thread_messages(
    partner_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Get all messages in a direct messaging thread with partner_id.
    Automatically marks unread incoming messages as read.
    """
    partner_user = db.query(User).filter(User.id == partner_id).first()
    if not partner_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Partner not found")

    partner_info = _get_user_display(partner_user, db)
    current_user_info = _get_user_display(current_user, db)

    # Mark incoming unread messages as read
    unread_msgs = (
        db.query(DirectMessage)
        .filter(
            DirectMessage.sender_id == partner_id,
            DirectMessage.recipient_id == current_user.id,
            DirectMessage.is_read == False,  # noqa: E712
        )
        .all()
    )
    if unread_msgs:
        for m in unread_msgs:
            m.is_read = True
        db.commit()

    # Query all messages between the two users
    messages = (
        db.query(DirectMessage)
        .filter(
            or_(
                (DirectMessage.sender_id == current_user.id)
                & (DirectMessage.recipient_id == partner_id),
                (DirectMessage.sender_id == partner_id)
                & (DirectMessage.recipient_id == current_user.id),
            )
        )
        .order_by(DirectMessage.created_at.asc())
        .all()
    )

    formatted_messages = []
    for m in messages:
        is_outgoing = m.sender_id == current_user.id
        s_name = current_user_info["name"] if is_outgoing else partner_info["name"]
        s_role = current_user_info["role"] if is_outgoing else partner_info["role"]

        formatted_messages.append(
            {
                "id": str(m.id),
                "senderId": str(m.sender_id),
                "recipientId": str(m.recipient_id),
                "senderName": s_name,
                "senderRole": s_role,
                "content": m.content,
                "isRead": m.is_read,
                "isOutgoing": is_outgoing,
                "timestamp": _format_timestamp(m.created_at),
                "createdAt": m.created_at.isoformat() if m.created_at else "",
            }
        )

    case_id, case_title, case_ref = _resolve_active_case_between(db, current_user.id, partner_id)
    all_cases = _get_all_cases_between(db, current_user.id, partner_id)

    return {
        "partner": {
            "id": str(partner_user.id),
            "name": partner_info["name"],
            "role": partner_info["role"],
            "caseId": case_id,
            "caseTitle": case_title,
            "caseRef": case_ref,
            "cases": all_cases,
        },
        "messages": formatted_messages,
    }


@router.post("/threads/{partner_id}")
def send_direct_message(
    partner_id: uuid.UUID,
    payload: SendMessageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Send a direct message to partner_id and sync to active case if available.
    """
    if partner_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot send messages to yourself.",
        )

    partner_user = db.query(User).filter(User.id == partner_id).first()
    if not partner_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipient not found")

    content = payload.content.strip()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message content cannot be empty.",
        )

    msg = DirectMessage(
        id=generate_uuid7(),
        sender_id=current_user.id,
        recipient_id=partner_id,
        content=content,
        is_read=False,
    )
    db.add(msg)

    # Two-way sync: If an active case exists between these users, also mirror as a CaseMessage
    case_id_str = str(payload.case_id) if payload.case_id else None
    if not case_id_str:
        case_id_str, _, _ = _resolve_active_case_between(db, current_user.id, partner_id)

    if case_id_str:
        case_uuid = uuid.UUID(case_id_str)
        # Ensure sender is enrolled as participant
        part = (
            db.query(CaseParticipant)
            .filter(
                CaseParticipant.case_id == case_uuid,
                CaseParticipant.user_id == current_user.id,
            )
            .first()
        )
        if not part:
            role = ParticipantRole.LAWYER if current_user.role == UserRole.LAWYER else ParticipantRole.OWNER
            new_p = CaseParticipant(
                id=generate_uuid7(),
                case_id=case_uuid,
                user_id=current_user.id,
                participant_role=role,
                status=ParticipantStatus.ACTIVE,
                joined_at=datetime.now(UTC),
            )
            db.add(new_p)

        # Ensure recipient is enrolled as participant
        recip_part = (
            db.query(CaseParticipant)
            .filter(
                CaseParticipant.case_id == case_uuid,
                CaseParticipant.user_id == partner_id,
            )
            .first()
        )
        if not recip_part:
            r_role = ParticipantRole.LAWYER if partner_user.role == UserRole.LAWYER else ParticipantRole.OWNER
            new_rp = CaseParticipant(
                id=generate_uuid7(),
                case_id=case_uuid,
                user_id=partner_id,
                participant_role=r_role,
                status=ParticipantStatus.ACTIVE,
                joined_at=datetime.now(UTC),
            )
            db.add(new_rp)

        cm = CaseMessage(
            id=generate_uuid7(),
            case_id=case_uuid,
            sender_id=current_user.id,
            content=content,
            message_type=CaseMessageType.GENERAL,
        )
        db.add(cm)

        # Dispatch notification to recipient so it shows up in their navbar
        try:
            from app.domain.notifications.notification_service import NotificationService
            from app.models.notification import NotificationType
            notification_service = NotificationService(db)
            sender_display = current_user.full_name or (current_user.email.split("@")[0] if current_user.email else "User")
            notification_service.create_notification(
                user_id=partner_id,
                type=NotificationType.MATTER_MESSAGE_RECEIVED,
                title=f"New Message from {sender_display}",
                message=content[:120],
                case_id=case_uuid,
                metadata={
                    "sender_id": str(current_user.id),
                    "sender_name": sender_display,
                    "case_id": str(case_uuid),
                },
                event_id=f"case_msg_{cm.id}",
            )
        except Exception as notif_err:
            logger.warning("Failed to dispatch message notification: %s", notif_err)

    db.commit()
    db.refresh(msg)

    current_user_info = _get_user_display(current_user, db)

    return {
        "id": str(msg.id),
        "senderId": str(msg.sender_id),
        "recipientId": str(msg.recipient_id),
        "senderName": current_user_info["name"],
        "senderRole": current_user_info["role"],
        "content": msg.content,
        "isRead": msg.is_read,
        "isOutgoing": True,
        "timestamp": _format_timestamp(msg.created_at),
        "createdAt": msg.created_at.isoformat() if msg.created_at else "",
    }
