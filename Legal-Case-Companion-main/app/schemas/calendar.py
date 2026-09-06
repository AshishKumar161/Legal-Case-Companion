from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class CalendarEventItem(BaseModel):
    id: str
    type: str  # "hearing" | "limitation" | "consultation" | "task"
    type_label: str
    scheduled_at: datetime
    month: str
    day: str
    time_display: str
    title: str
    case_id: UUID | None = None
    case_name: str
    case_ref: str
    forum: str
    action_tip: str
    technical_term: str | None = None
    source: str
    action_label: str
    action_href: str
    is_urgent: bool = False
    lawyer_details: dict | None = None

    model_config = ConfigDict(from_attributes=True)


class CalendarEventsResponse(BaseModel):
    events: list[CalendarEventItem] = Field(default_factory=list)
    total: int = 0
    next_attention_event: CalendarEventItem | None = None
