import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.localization import TranslationStatus


class TranslationCreateRequest(BaseModel):
    source_key: str = Field(..., min_length=2, max_length=255)
    source_text: str = Field(..., min_length=1)
    locale: str = Field(..., min_length=2, max_length=20)
    translation: str = Field(..., min_length=1)
    version: str = Field(default="1.0.0", max_length=50)
    metadata_: dict | None = None


class TranslationReviewRequest(BaseModel):
    approved: bool
    review_status: str = Field(default="HUMAN_REVIEWED", max_length=50)
    review_notes: str | None = None


class TranslationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_key: str
    source_text: str
    locale: str
    translation: str
    status: TranslationStatus
    review_status: str
    version: str
    reviewed_by: str | None
    reviewed_at: datetime | None
    created_at: datetime
