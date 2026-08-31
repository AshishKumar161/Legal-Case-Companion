from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AuditEventResponse(BaseModel):
    id: UUID
    actor_user_id: UUID | None = None
    event_type: str
    entity_type: str
    entity_id: UUID | None = None
    action: str
    timestamp: datetime
    metadata: dict | None = Field(default=None, alias="metadata_")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
