"""Real-time WebRTC WebSocket signaling layer for in-app video consultations.

Enforces HMAC-SHA256 token authentication, consultation-scoped room isolation,
bidirectional peer-to-peer signaling message relay (offer, answer, ICE candidates),
message size limits, and disconnect lifecycle handling.
"""

import json
import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session

from app.core.exceptions import ValidationError
from app.db.database import get_db
from app.models.consultation import Consultation
from app.models.video_meeting import VideoMeeting
from app.services.video_meeting_service import get_video_provider

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Video Signaling"])

# Maximum allowable signaling message size (64 KB) to protect against DoS/memory bloat
MAX_SIGNALING_PAYLOAD_BYTES = 64 * 1024


class VideoSignalingManager:
    """Manages active WebRTC WebSocket peer connections partitioned by meeting room."""

    def __init__(self):
        # room_id -> list of (websocket, user_id, role)
        self.rooms: dict[str, list[dict[str, Any]]] = {}

    async def connect(self, room_id: str, websocket: WebSocket, user_id: str, role: str):
        await websocket.accept()
        if room_id not in self.rooms:
            self.rooms[room_id] = []

        # Notify existing participants that a new peer has joined
        join_notification = {
            "type": "peer-joined",
            "user_id": user_id,
            "role": role,
            "peer_count": len(self.rooms[room_id]) + 1,
        }
        for client in self.rooms[room_id]:
            try:
                await client["ws"].send_text(json.dumps(join_notification))
            except Exception as e:
                logger.warning(f"Failed to notify peer {client['user_id']} of join: {e}")

        self.rooms[room_id].append({
            "ws": websocket,
            "user_id": user_id,
            "role": role,
        })
        logger.info(f"Peer {user_id} ({role}) connected to room {room_id}. Total: {len(self.rooms[room_id])}")

    async def disconnect(self, room_id: str, websocket: WebSocket):
        if room_id not in self.rooms:
            return

        disconnected_peer = None
        remaining = []
        for client in self.rooms[room_id]:
            if client["ws"] == websocket:
                disconnected_peer = client
            else:
                remaining.append(client)

        self.rooms[room_id] = remaining
        if not self.rooms[room_id]:
            del self.rooms[room_id]

        if disconnected_peer:
            logger.info(f"Peer {disconnected_peer['user_id']} disconnected from room {room_id}")
            # Notify remaining peers
            leave_notification = {
                "type": "peer-left",
                "user_id": disconnected_peer["user_id"],
                "role": disconnected_peer["role"],
                "peer_count": len(remaining),
            }
            for client in remaining:
                try:
                    await client["ws"].send_text(json.dumps(leave_notification))
                except Exception as e:
                    logger.warning(f"Failed to notify peer {client['user_id']} of leave: {e}")

    async def broadcast_to_room(self, room_id: str, sender_ws: WebSocket, message: dict[str, Any]):
        """Relays a validated WebRTC signaling message to all other peers in the room."""
        if room_id not in self.rooms:
            return

        payload_str = json.dumps(message)
        for client in self.rooms[room_id]:
            if client["ws"] != sender_ws:
                try:
                    await client["ws"].send_text(payload_str)
                except Exception as e:
                    logger.warning(f"Failed to relay signaling message to {client['user_id']}: {e}")


signaling_manager = VideoSignalingManager()


@router.websocket("/consultations/{consultation_id}/video/ws")
async def video_signaling_websocket(
    websocket: WebSocket,
    consultation_id: UUID,
    token: str = Query(..., description="Cryptographically signed HMAC-SHA256 video access token"),
):
    """
    Authenticated WebSocket signaling channel for in-app WebRTC consultation room.

    Validates cryptographic join token, enforces consultation and room context binding,
    and relays WebRTC peer negotiation messages (offer, answer, ICE candidate).
    """
    from fastapi import Depends
    from app.main import app

    # Respect dependency overrides (e.g. test fixtures)
    get_db_override = app.dependency_overrides.get(get_db, get_db)
    db_gen = get_db_override()
    db: Session = next(db_gen)
    try:
        # 1. Fetch meeting record
        meeting = (
            db.query(VideoMeeting)
            .filter(VideoMeeting.consultation_id == consultation_id)
            .first()
        )
        if not meeting:
            logger.warning(f"WebSocket rejected: no meeting record for consultation {consultation_id}")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

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
                ):
                    continue

                # Handle ping/pong heartbeat
                if msg_type == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
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
