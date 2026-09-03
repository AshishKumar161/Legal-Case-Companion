from uuid import UUID

from pydantic import BaseModel


class ClientProfileUpdate(BaseModel):
    full_name: str | None = None
    location: str | None = None
    phone: str | None = None

    model_config = {"extra": "forbid"}


class LawyerProfileUpdate(BaseModel):
    full_name: str | None = None
    bio: str | None = None
    location: str | None = None
    phone: str | None = None
    consultation_fee: float | None = None
    practice_areas: list[str] | None = None
    experience_years: int | None = None
    court_jurisdictions: list[str] | None = None
    languages: list[str] | None = None

    model_config = {"extra": "forbid"}


class ClientProfileResponse(BaseModel):
    id: UUID
    user_id: UUID
    full_name: str
    location: str | None = None
    email: str | None = None
    phone: str | None = None

    model_config = {"from_attributes": True}


class LawyerPublicResponse(BaseModel):
    id: UUID
    user_id: UUID
    full_name: str
    bio: str | None = None
    location: str | None = None
    consultation_fee: float | None = None
    practice_areas: list[str] | None = None
    experience_years: int | None = None
    court_jurisdictions: list[str] | None = None
    languages: list[str] | None = None
    verification_status: str
    is_online: bool = False

    model_config = {"from_attributes": True}


class LawyerProfileResponse(BaseModel):
    id: UUID
    user_id: UUID
    full_name: str
    bio: str | None = None
    location: str | None = None
    email: str | None = None
    phone: str | None = None
    consultation_fee: float | None = None
    practice_areas: list[str] | None = None
    experience_years: int | None = None
    court_jurisdictions: list[str] | None = None
    languages: list[str] | None = None
    verification_status: str
    is_online: bool = False

    model_config = {"from_attributes": True}


class LawyerVerificationCreate(BaseModel):
    enrollment_number: str
    state_bar_council: str


class LawyerVerificationResponse(BaseModel):
    id: UUID
    lawyer_profile_id: UUID
    enrollment_number: str
    state_bar_council: str
    status: str

    model_config = {"from_attributes": True}
