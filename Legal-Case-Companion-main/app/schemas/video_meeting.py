import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.models.video_meeting import VideoMeetingStatus


class VideoMeetingResponse(BaseModel):
    id: uuid.UUID
    consultation_id: uuid.UUID
    room_id: str
    provider: str
    status: VideoMeetingStatus
    scheduled_start: datetime
    scheduled_end: datetime
    started_at: datetime | None = None
    ended_at: datetime | None = None
    recording_url: str | None = None

    model_config = ConfigDict(from_attributes=True)


class VideoJoinInfoResponse(BaseModel):
    consultation_id: uuid.UUID
    meeting_id: uuid.UUID
    room_id: str
    provider: str
    status: VideoMeetingStatus
    participant_user_id: uuid.UUID
    participant_name: str
    participant_role: str  # "CLIENT", "LAWYER", "ADMIN"
    scheduled_start: datetime
    scheduled_end: datetime
    started_at: datetime | None = None
    consultation_status: str | None = None
    token: str
    ice_servers: list[dict[str, Any]]
    is_live: bool

    model_config = ConfigDict(from_attributes=True)


class VideoMeetingEndRequest(BaseModel):
    notes: str | None = None
