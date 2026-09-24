from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ClientProfileUpdate(BaseModel):
    full_name: str | None = None
    location: str | None = None
    phone: str | None = None
    date_of_birth: str | None = None
    gender: str | None = None
    id_type: str | None = None
    id_number: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    pincode: str | None = None

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
    date_of_birth: str | None = None
    gender: str | None = None
    id_type: str | None = None
    id_number: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    pincode: str | None = None
    kyc_status: str = "PENDING"
    is_kyc_completed: bool = False
    kyc_document_filename: str | None = None
    kyc_submitted_at: datetime | None = None
    kyc_verified_at: datetime | None = None

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
    is_available: bool = False
    presence_status: str = "OFFLINE"
    match_reasons: list[str] = []

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
    match_reasons: list[str] = []

    model_config = {"from_attributes": True}


class LawyerVerificationCreate(BaseModel):
    enrollment_number: str
    state_bar_council: str
    evidence_document_id: UUID | None = None
    is_reverification: bool = False


class LawyerVerificationReviewRequest(BaseModel):
    approved: bool
    rejection_category: str | None = None
    validity_days: int = 365


class LawyerVerificationResponse(BaseModel):
    id: UUID
    lawyer_profile_id: UUID
    enrollment_number: str
    state_bar_council: str
    status: str
    evidence_document_id: UUID | None = None
    expires_at: datetime | None = None
    rejection_reason_category: str | None = None
    is_reverification: bool = False

    model_config = {"from_attributes": True}
