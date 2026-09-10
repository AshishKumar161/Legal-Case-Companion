from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class CourtHearingHistoryItem(BaseModel):
    date: str
    judge: str
    business: str
    next_date: str | None = None
    hearing_id: str | None = None


class CourtCauseListItem(BaseModel):
    court_room: str
    item_number: str
    cause_list_date: str
    bench: str
    board_status: str


class CourtOrderItem(BaseModel):
    title: str
    order_date: str
    pages: int
    sha256: str
    document_id: str | None = None


class CourtCaseSummary(BaseModel):
    id: UUID
    cnr: str
    case_number: str
    case_type: str
    court_name: str
    bench: str | None = None
    petitioner: str
    respondent: str
    petitioner_advocate: str | None = None
    respondent_advocate: str | None = None
    technical_status: str
    human_status: str
    next_hearing_date: datetime | None = None
    next_hearing_purpose: str | None = None
    source_provenance: str = "OFFICIAL COURT DATA"
    last_synchronized_at: datetime
    sync_status: str = "SYNCED"
    case_id: UUID | None = None
    is_followed: bool = False

    model_config = ConfigDict(from_attributes=True)


class CourtCaseDetail(CourtCaseSummary):
    filing_number: str | None = None
    filing_date: str | None = None
    registration_date: str | None = None
    court_room: str | None = None
    item_number: str | None = None
    acts_and_sections: str | None = None
    history: list[CourtHearingHistoryItem] = Field(default_factory=list)
    cause_list: CourtCauseListItem | None = None
    orders: list[CourtOrderItem] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class CourtCaseFollowResponse(BaseModel):
    court_case_id: UUID
    is_followed: bool
    message: str


class CourtCaseSyncResponse(BaseModel):
    court_case_id: UUID
    last_synchronized_at: datetime
    sync_status: str
    message: str


class CourtCaseLinkMatterRequest(BaseModel):
    case_id: UUID | None = None


class CourtCaseLinkMatterResponse(BaseModel):
    court_case_id: UUID
    case_id: UUID
    message: str
