"""Presence schemas and presence state enums."""

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PresenceStatus(str, Enum):
    """Authoritative platform presence states."""

    OFFLINE = "OFFLINE"
    ONLINE = "ONLINE"
    AVAILABLE = "AVAILABLE"
    BUSY = "BUSY"


class HeartbeatRequest(BaseModel):
    """Optional heartbeat payload allowing lawyers to toggle instant availability preference."""

    available_for_instant: bool = Field(
        default=True,
        description="Whether the lawyer prefers to accept instant consultations.",
    )


class HeartbeatResponse(BaseModel):
    """Authoritative heartbeat response returned to lawyer client."""

    is_online: bool = Field(..., description="True if a valid heartbeat is registered.")
    is_available: bool = Field(
        ...,
        description="True if online, verified, account active, and not in conflicting consultation.",
    )
    presence_status: PresenceStatus = Field(
        ..., description="Current authoritative presence state."
    )
    last_heartbeat: datetime = Field(
        ..., description="UTC timestamp when heartbeat was recorded."
    )

    model_config = ConfigDict(from_attributes=True)


class LawyerPresenceStatusResponse(BaseModel):
    """Detailed presence status for lawyer discovery and profile views."""

    user_id: UUID
    lawyer_id: UUID | None = None
    is_online: bool = False
    is_available: bool = False
    presence_status: PresenceStatus = PresenceStatus.OFFLINE
    last_heartbeat: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
