from datetime import datetime, time
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class LawyerAvailabilityCreate(BaseModel):
    day_of_week: int = Field(..., ge=0, le=6, description="0=Monday, 6=Sunday")
    start_time: time
    end_time: time
    slot_duration_minutes: int = Field(default=30, ge=15, le=240)
    is_active: bool = True

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_time_range(self) -> "LawyerAvailabilityCreate":
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be strictly after start_time")
        return self


class LawyerAvailabilityUpdate(BaseModel):
    start_time: time | None = None
    end_time: time | None = None
    slot_duration_minutes: int | None = Field(default=None, ge=15, le=240)
    is_active: bool | None = None

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_time_range(self) -> "LawyerAvailabilityUpdate":
        if (
            self.start_time is not None
            and self.end_time is not None
            and self.end_time <= self.start_time
        ):
            raise ValueError("end_time must be strictly after start_time")
        return self


class LawyerAvailabilityResponse(BaseModel):
    id: UUID
    lawyer_profile_id: UUID
    day_of_week: int
    start_time: time
    end_time: time
    slot_duration_minutes: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SlotResponse(BaseModel):
    start_time: datetime
    end_time: datetime
    duration_minutes: int
    is_available: bool

    model_config = ConfigDict(from_attributes=True)
