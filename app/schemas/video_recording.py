from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.video_recording import VideoRecordingStatus


class RecordingConsentRequest(BaseModel):
    consented: bool = True


class RecordingConsentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    consultation_id: UUID
    user_id: UUID
    role: str
    consented: bool
    consented_at: datetime


class ConsentStatusResponse(BaseModel):
    consultation_id: UUID
    client_consented: bool
    lawyer_consented: bool
    can_record: bool


class RecordingStartResponse(BaseModel):
    recording_id: UUID
    consultation_id: UUID
    status: VideoRecordingStatus
    started_at: datetime


class RecordingStopResponse(BaseModel):
    recording_id: UUID
    consultation_id: UUID
    status: VideoRecordingStatus
    duration_seconds: int | None = None
    ended_at: datetime | None = None


class RecordingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    consultation_id: UUID
    case_id: UUID | None = None
    recording_type: str
    status: VideoRecordingStatus
    started_at: datetime | None = None
    ended_at: datetime | None = None
    duration_seconds: int | None = None
    file_size_bytes: int | None = None
    mime_type: str
    checksum_sha256: str | None = None
    playback_url: str | None = None
    created_at: datetime


class RecordingListResponse(BaseModel):
    items: list[RecordingResponse]
    total: int
