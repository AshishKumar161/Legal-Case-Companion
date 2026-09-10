"""Domain signaling manager for active WebRTC WebSocket peer connections partitioned by meeting room."""

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Maximum allowable signaling message size (64 KB) to protect against DoS/memory bloat
MAX_SIGNALING_PAYLOAD_BYTES = 64 * 1024


class VideoSignalingManager:
    """Manages active WebRTC WebSocket peer connections partitioned by meeting room."""

    def __init__(self) -> None:
        # room_id -> list of dict with keys "ws", "user_id", "role"
        self.rooms: dict[str, list[dict[str, Any]]] = {}

    async def connect(self, room_id: str, websocket: Any, user_id: str, role: str) -> None:
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

        # Notify the newly connected peer about all existing peers already in the room
        for client in self.rooms[room_id]:
            try:
                await websocket.send_text(json.dumps({
                    "type": "existing-peer",
                    "user_id": client["user_id"],
                    "role": client["role"],
                    "peer_count": len(self.rooms[room_id]) + 1,
                }))
            except Exception as e:
                logger.warning(f"Failed to notify new peer of existing peer: {e}")

        self.rooms[room_id].append({
            "ws": websocket,
            "user_id": user_id,
            "role": role,
        })
        logger.info(f"Peer {user_id} ({role}) connected to room {room_id}. Total: {len(self.rooms[room_id])}")

    async def disconnect(self, room_id: str, websocket: Any) -> None:
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

    async def broadcast_to_room(self, room_id: str, sender_ws: Any | None, message: dict[str, Any]) -> None:
        """Relays a validated WebRTC signaling message to all other peers in the room."""
        if room_id not in self.rooms:
            return

        payload_str = json.dumps(message)
        dead_clients = []
        for client in self.rooms[room_id]:
            if client["ws"] != sender_ws:
                try:
                    await client["ws"].send_text(payload_str)
                except Exception as e:
                    logger.warning(f"Failed to relay signaling message to {client['user_id']}: {e}")
                    dead_clients.append(client)

        if dead_clients:
            for dead in dead_clients:
                if dead in self.rooms.get(room_id, []):
                    self.rooms[room_id].remove(dead)
            if not self.rooms.get(room_id):
                self.rooms.pop(room_id, None)


signaling_manager = VideoSignalingManager()
