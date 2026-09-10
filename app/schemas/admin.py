from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.case import CaseStatus
from app.models.consultation import ConsultationStatus
from app.models.document import DocumentSecurityStatus
from app.models.payment import PaymentStatus
from app.models.user import AccountStatus, UserRole


class AdminOverviewResponse(BaseModel):
    total_users: int
    active_users: int
    suspended_users: int
    total_lawyers: int
    pending_verifications: int
    verified_lawyers: int
    total_cases: int
    active_cases: int
    closed_cases: int
    total_consultations: int
    paid_consultations: int
    scheduled_consultations: int
    total_payments: int
    succeeded_payments: int
    total_revenue_inr: float
    total_documents: int
    quarantined_documents: int
    rejected_documents: int
    security_event_count: int


class AdminUserResponse(BaseModel):
    id: UUID
    email: str
    full_name: str
    role: UserRole
    account_status: AccountStatus
    created_at: datetime
    updated_at: datetime


class AdminCaseResponse(BaseModel):
    id: UUID
    title: str
    description: str
    status: CaseStatus
    created_at: datetime
    updated_at: datetime
    participant_count: int
    document_count: int
    owner_email: str | None = None


class AdminConsultationResponse(BaseModel):
    id: UUID
    client_id: UUID
    lawyer_id: UUID
    case_id: UUID | None = None
    status: ConsultationStatus
    fee_amount: float
    currency: str
    scheduled_at: datetime
    duration_minutes: int
    rejection_reason: str | None = None
    created_at: datetime


class AdminPaymentResponse(BaseModel):
    id: UUID
    consultation_id: UUID
    payer_user_id: UUID
    amount: float
    currency: str
    status: PaymentStatus
    provider: str
    provider_payment_id: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdminDocumentSecurityResponse(BaseModel):
    id: UUID
    case_id: UUID
    filename: str
    mime_type: str
    file_size: int
    security_status: DocumentSecurityStatus
    created_at: datetime


class AdminSecurityEventResponse(BaseModel):
    id: UUID
    actor_user_id: UUID | None = None
    event_type: str
    entity_type: str | None = None
    entity_id: UUID | None = None
    action: str
    timestamp: datetime
    metadata: dict

    model_config = ConfigDict(from_attributes=True)
