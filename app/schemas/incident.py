from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.incident import (
    IncidentCategory,
    IncidentDetector,
    IncidentSeverity,
    IncidentStatus,
)


class IncidentCreateRequest(BaseModel):
    summary: str = Field(..., min_length=5, max_length=500)
    severity: IncidentSeverity
    category: IncidentCategory
    affected_scope: str | None = Field(None, max_length=500)
    assigned_to_user_id: UUID | None = None
    metadata_: dict | None = None


class IncidentTransitionRequest(BaseModel):
    new_status: IncidentStatus
    notes: str = Field(..., min_length=3)
    root_cause: str | None = None
    mitigation: str | None = None
    resolution: str | None = None


class IncidentTimelineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_type: str
    message: str
    metadata_: dict | None = Field(None, alias="metadata_")
    timestamp: datetime
    actor_user_id: UUID | None


class IncidentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    incident_id: str
    severity: IncidentSeverity
    category: IncidentCategory
    status: IncidentStatus
    detected_at: datetime
    acknowledged_at: datetime | None
    mitigated_at: datetime | None
    resolved_at: datetime | None
    closed_at: datetime | None
    summary: str
    affected_scope: str | None
    detected_by: IncidentDetector
    assigned_to_user_id: UUID | None
    root_cause: str | None
    mitigation: str | None
    resolution: str | None
    postmortem_required: bool
    postmortem_url: str | None
    metadata_: dict | None = Field(None, alias="metadata_")
    timeline_events: list[IncidentTimelineResponse] = []
