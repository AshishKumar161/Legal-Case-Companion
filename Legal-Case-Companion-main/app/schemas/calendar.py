from datetime import datetime
from typing import Literal
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
    source_type: str | None = None
    source_id: str | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    status: str | None = None
    priority: str | None = None
    category: str | None = None
    lawyer_details: dict | None = None

    model_config = ConfigDict(from_attributes=True)


class CalendarEventsResponse(BaseModel):
    events: list[CalendarEventItem] = Field(default_factory=list)
    total: int = 0
    next_attention_event: CalendarEventItem | None = None
    timeframe: str | None = None
    range_start: datetime | None = None
    range_end: datetime | None = None
