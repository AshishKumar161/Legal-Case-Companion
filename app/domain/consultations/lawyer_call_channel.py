"""Real-time incoming call WebSocket channel manager for lawyers.

Maintains authenticated, per-lawyer WebSocket connections with multi-tab
support and zero cross-lawyer event leakage.
"""

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import WebSocket

from app.core.identifiers import generate_uuid7

logger = logging.getLogger(__name__)


class IncomingCallChannelManager:
    """Manages real-time WebSocket connections for incoming legal consultations."""

    def __init__(self) -> None:
        # lawyer_profile_id -> set of active WebSockets (multi-tab support)
        self._connections: dict[UUID, set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, lawyer_id: UUID, websocket: WebSocket) -> None:
        """Register a new active WebSocket connection for a lawyer."""
        await websocket.accept()
        async with self._lock:
            if lawyer_id not in self._connections:
                self._connections[lawyer_id] = set()
            self._connections[lawyer_id].add(websocket)
        logger.info(
            "Lawyer %s connected to incoming call channel (total tabs: %d)",
            lawyer_id,
            len(self._connections[lawyer_id]),
        )

    async def disconnect(self, lawyer_id: UUID, websocket: WebSocket) -> None:
        """Remove a closed or disconnected WebSocket for a lawyer."""
        async with self._lock:
            if lawyer_id in self._connections:
                self._connections[lawyer_id].discard(websocket)
                if not self._connections[lawyer_id]:
                    del self._connections[lawyer_id]
        logger.info(
            "Lawyer %s tab disconnected from incoming call channel",
            lawyer_id,
        )

    def get_connection_count(self, lawyer_id: UUID) -> int:
        """Return the number of open connections (tabs) for a lawyer."""
        return len(self._connections.get(lawyer_id, set()))

    async def broadcast_to_lawyer(
        self, lawyer_id: UUID, message: dict[str, Any]
    ) -> int:
        """Safely broadcast a message to all open tabs of a specific lawyer.

        Automatically cleans up any broken or abruptly disconnected connections.
        Returns the count of successfully notified client tabs.
        """
        async with self._lock:
            sockets = list(self._connections.get(lawyer_id, set()))

        if not sockets:
            logger.debug(
                "No active WebSocket connections for lawyer %s to receive event %s",
                lawyer_id,
                message.get("type"),
            )
            return 0

        stale_sockets = []
        sent_count = 0

        for ws in sockets:
            try:
                await ws.send_json(message)
                sent_count += 1
            except Exception as e:
                logger.warning(
                    "Failed to deliver event to socket for lawyer %s: %s",
                    lawyer_id,
                    e,
                )
                stale_sockets.append(ws)

        if stale_sockets:
            async with self._lock:
                if lawyer_id in self._connections:
                    for ws in stale_sockets:
                        self._connections[lawyer_id].discard(ws)
                    if not self._connections[lawyer_id]:
                        del self._connections[lawyer_id]

        return sent_count

    async def notify_incoming_call(
        self, lawyer_id: UUID, consultation_data: dict[str, Any]
    ) -> int:
        """Dispatch real-time incoming consultation alert to all active tabs of the lawyer."""
        now = datetime.now(UTC)
        payload = {
            "type": "incoming_consultation",
            "event_type": "incoming_consultation",
            "event_id": str(generate_uuid7()),
            "lawyer_id": str(lawyer_id),
            "server_timestamp": now.isoformat(),
            "consultation_id": str(consultation_data.get("id")),
            "client_name": consultation_data.get("client_name", "Prospective Client"),
            "fee": consultation_data.get("fee", 0.0),
            "case_id": str(consultation_data.get("case_id"))
            if consultation_data.get("case_id")
            else None,
            "scheduled_at": consultation_data.get("scheduled_at"),
            "created_at": consultation_data.get("created_at"),
            "ring_timeout_seconds": consultation_data.get("ring_timeout_seconds", 60),
        }
        count = await self.broadcast_to_lawyer(lawyer_id, payload)
        logger.info(
            "Dispatched incoming_consultation %s to lawyer %s on %d tabs",
            payload["consultation_id"],
            lawyer_id,
            count,
        )
        return count

    async def notify_call_accepted(
        self, lawyer_id: UUID, consultation_id: UUID | str
    ) -> int:
        """Notify other tabs of the lawyer that the consultation was accepted."""
        now = datetime.now(UTC)
        payload = {
            "type": "consultation_accepted",
            "event_type": "consultation_accepted",
            "event_id": str(generate_uuid7()),
            "lawyer_id": str(lawyer_id),
            "server_timestamp": now.isoformat(),
            "consultation_id": str(consultation_id),
        }
        return await self.broadcast_to_lawyer(lawyer_id, payload)

    async def notify_call_cancelled(
        self, lawyer_id: UUID, consultation_id: UUID | str, reason: str = ""
    ) -> int:
        """Notify lawyer that the incoming call was cancelled by client."""
        now = datetime.now(UTC)
        payload = {
            "type": "consultation_cancelled",
            "event_type": "consultation_cancelled",
            "event_id": str(generate_uuid7()),
            "lawyer_id": str(lawyer_id),
            "server_timestamp": now.isoformat(),
            "consultation_id": str(consultation_id),
            "reason": reason,
        }
        return await self.broadcast_to_lawyer(lawyer_id, payload)

    async def notify_call_expired(
        self, lawyer_id: UUID, consultation_id: UUID | str
    ) -> int:
        """Notify lawyer that the call timed out without response."""
        now = datetime.now(UTC)
        payload = {
            "type": "consultation_expired",
            "event_type": "consultation_expired",
            "event_id": str(generate_uuid7()),
            "lawyer_id": str(lawyer_id),
            "server_timestamp": now.isoformat(),
            "consultation_id": str(consultation_id),
            "reason": "Call timed out with no response",
        }
        return await self.broadcast_to_lawyer(lawyer_id, payload)


# Singleton channel manager instance
incoming_call_channel_manager = IncomingCallChannelManager()
