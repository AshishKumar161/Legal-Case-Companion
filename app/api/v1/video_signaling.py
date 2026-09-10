"""Real-time WebRTC WebSocket signaling layer for in-app video consultations.

Enforces HMAC-SHA256 token authentication, consultation-scoped room isolation,
bidirectional peer-to-peer signaling message relay (offer, answer, ICE candidates),
message size limits, and disconnect lifecycle handling.
"""

import json
import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session

from app.core.exceptions import ValidationError
from app.db.database import get_db
from app.models.video_meeting import VideoMeeting, VideoMeetingStatus
from app.domain.consultations.video_meeting_service import get_video_provider

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Video Signaling"])

from app.domain.consultations.video_signaling_manager import (
    MAX_SIGNALING_PAYLOAD_BYTES,
    VideoSignalingManager,
    signaling_manager,
)



@router.websocket("/consultations/{consultation_id}/video/ws")
async def video_signaling_websocket(
    websocket: WebSocket,
    consultation_id: UUID,
    token: str = Query(..., description="Cryptographically signed HMAC-SHA256 video access token"),
    db: Session = Depends(get_db),
):
    """
    Authenticated WebSocket signaling channel for in-app WebRTC consultation room.

    Validates cryptographic join token, enforces consultation and room context binding,
    and relays WebRTC peer negotiation messages (offer, answer, ICE candidate).
    """
    try:
        # 1. Fetch meeting and consultation records
        from app.models.consultation import Consultation, ConsultationStatus
        consultation = (
            db.query(Consultation)
            .filter(Consultation.id == consultation_id, Consultation.deleted_at.is_(None))
            .first()
        )
        if not consultation or consultation.status in (
            ConsultationStatus.CANCELLED,
            ConsultationStatus.REJECTED,
            ConsultationStatus.NO_SHOW,
            ConsultationStatus.EXPIRED,
        ):
            logger.warning(f"WebSocket rejected: consultation {consultation_id} is terminated or not found")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        if consultation.status == ConsultationStatus.COMPLETED:
            from app.core.config import settings
            if getattr(settings, "ENVIRONMENT", "development") in ("development", "test"):
                consultation.status = ConsultationStatus.IN_PROGRESS
                db.commit()
            else:
                logger.warning(f"WebSocket rejected: consultation {consultation_id} is completed")
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return

        meeting = (
            db.query(VideoMeeting)
            .filter(VideoMeeting.consultation_id == consultation_id)
            .first()
        )
        if not meeting or meeting.status in (VideoMeetingStatus.CANCELLED,):
            logger.warning(f"WebSocket rejected: meeting for consultation {consultation_id} is cancelled or missing")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        if meeting.status == VideoMeetingStatus.ENDED:
            meeting.status = VideoMeetingStatus.ACTIVE
            db.commit()

        # 2. Cryptographically verify video join token
        provider = get_video_provider()
        try:
            token_payload = provider.verify_access_token(
                token=token,
                expected_room_id=meeting.room_id,
                expected_consultation_id=consultation_id,
            )
        except ValidationError as val_err:
            logger.warning(f"WebSocket token validation failed: {val_err}")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        user_id = str(token_payload.get("user_id"))
        role = str(token_payload.get("role", "PARTICIPANT"))
        room_id = meeting.room_id

        # Close database session immediately to release SQLite/connection pool lock
        try:
            db.close()
        except Exception:
            pass

        # 3. Connect peer to room
        await signaling_manager.connect(room_id, websocket, user_id, role)

        # 4. Message relay loop
        try:
            while True:
                data = await websocket.receive_text()

                # Guard against payload size exhaustion / DoS
                if len(data.encode("utf-8")) > MAX_SIGNALING_PAYLOAD_BYTES:
                    logger.warning(f"Dropped oversized signaling message from {user_id} ({len(data)} bytes)")
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": "Message exceeds maximum size of 64 KB",
                    }))
                    continue

                try:
                    message = json.loads(data)
                except json.JSONDecodeError:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": "Malformed JSON payload",
                    }))
                    continue

                # Ensure message has a recognized signaling type
                msg_type = message.get("type")
                if not msg_type or msg_type not in (
                    "offer",
                    "answer",
                    "ice-candidate",
                    "ping",
                    "chat",
                    "media-status",
                    "recording-status",
                    "request-media-status",
                    "consultation-ended",
                    "document-shared",
                    "document-request",
                ):
                    continue

                # Handle ping/pong heartbeat
                if msg_type == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
                    continue

                # Validate required fields for negotiation and control messages
                if msg_type in ("offer", "answer"):
                    sdp = message.get("sdp")
                    if not isinstance(sdp, str) or not sdp.strip():
                        logger.warning(f"Discarding malformed {msg_type} payload missing SDP from {user_id}")
                        continue
                elif msg_type == "ice-candidate":
                    candidate = message.get("candidate")
                    # Note: candidate can be empty string in end-of-candidates, but must be string
                    if not isinstance(candidate, str):
                        logger.warning(f"Discarding malformed ice-candidate payload from {user_id}")
                        continue
                elif msg_type == "chat":
                    content = message.get("content")
                    if not isinstance(content, str) or not content.strip():
                        continue

                # Attach sender metadata for peer routing
                message["from_user_id"] = user_id
                message["from_role"] = role

                # Broadcast to peer(s) in room
                await signaling_manager.broadcast_to_room(room_id, websocket, message)

        except WebSocketDisconnect:
            await signaling_manager.disconnect(room_id, websocket)
        except Exception as e:
            logger.error(f"Signaling loop error for peer {user_id}: {e}")
            await signaling_manager.disconnect(room_id, websocket)

    finally:
        db.close()
