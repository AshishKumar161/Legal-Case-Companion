from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import RequireRole, get_current_user, get_db
from app.models.consultation import ConsultationStatus
from app.models.user import User, UserRole
from app.schemas.consultation import (
    ConsultationCancelRequest,
    ConsultationCreate,
    ConsultationNoShowRequest,
    ConsultationRejectRequest,
    ConsultationRescheduleRequest,
    ConsultationResponse,
    ConsultationScheduleRequest,
)
from app.schemas.message import MessageCreate, MessageResponse
from app.schemas.pagination import PaginatedResponse
from app.schemas.payment import PaymentIntentResponse, PaymentResponse
from app.services.consultation_service import ConsultationService
from app.services.message_service import MessageService
from app.services.payment_service import PaymentService

router = APIRouter(prefix="/consultations", tags=["consultations"])


@router.post(
    "", response_model=ConsultationResponse, status_code=status.HTTP_201_CREATED
)
def request_consultation(
    req: ConsultationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    consultation_service = ConsultationService(db)
    return consultation_service.request_consultation(current_user, req)


@router.get("", response_model=PaginatedResponse[ConsultationResponse])
def get_consultations(
    case_id: UUID | None = None,
    consultation_status: ConsultationStatus | None = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    consultation_service = ConsultationService(db)
    return consultation_service.get_consultations(
        current_user, case_id=case_id, status=consultation_status, skip=skip, limit=limit
    )


@router.get("/{consultation_id}", response_model=ConsultationResponse)
def get_consultation(
    consultation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    consultation_service = ConsultationService(db)
    return consultation_service.get_consultation(current_user, consultation_id)


@router.post("/{consultation_id}/accept", response_model=ConsultationResponse)
def accept_consultation(
    consultation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    consultation_service = ConsultationService(db)
    return consultation_service.accept_consultation(current_user, consultation_id)


@router.post("/{consultation_id}/reject", response_model=ConsultationResponse)
def reject_consultation(
    consultation_id: UUID,
    req: ConsultationRejectRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    consultation_service = ConsultationService(db)
    reason = req.reason if req else None
    return consultation_service.reject_consultation(
        current_user, consultation_id, reason=reason
    )


@router.post("/{consultation_id}/schedule", response_model=ConsultationResponse)
def schedule_consultation(
    consultation_id: UUID,
    req: ConsultationScheduleRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    consultation_service = ConsultationService(db)
    return consultation_service.schedule_consultation(
        current_user,
        consultation_id,
        scheduled_at=req.scheduled_at,
        duration_minutes=req.duration_minutes,
    )


@router.post("/{consultation_id}/reschedule", response_model=ConsultationResponse)
def reschedule_consultation(
    consultation_id: UUID,
    req: ConsultationRescheduleRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    consultation_service = ConsultationService(db)
    return consultation_service.reschedule_consultation(
        current_user,
        consultation_id,
        scheduled_at=req.scheduled_at,
        duration_minutes=req.duration_minutes,
        reason=req.reason,
    )


@router.post("/{consultation_id}/confirm", response_model=ConsultationResponse)
def confirm_consultation(
    consultation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    consultation_service = ConsultationService(db)
    return consultation_service.confirm_consultation(current_user, consultation_id)


@router.post("/{consultation_id}/cancel", response_model=ConsultationResponse)
def cancel_consultation(
    consultation_id: UUID,
    req: ConsultationCancelRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    consultation_service = ConsultationService(db)
    reason = req.reason if req else None
    return consultation_service.cancel_consultation(
        current_user, consultation_id, reason=reason
    )


@router.post("/{consultation_id}/no-show", response_model=ConsultationResponse)
def mark_no_show(
    consultation_id: UUID,
    req: ConsultationNoShowRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    consultation_service = ConsultationService(db)
    reason = req.reason if req else None
    return consultation_service.mark_no_show(
        current_user, consultation_id, reason=reason
    )


@router.post("/{consultation_id}/complete", response_model=ConsultationResponse)
def complete_consultation(
    consultation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    consultation_service = ConsultationService(db)
    return consultation_service.complete_consultation(current_user, consultation_id)


@router.post(
    "/{consultation_id}/payments", response_model=PaymentIntentResponse, status_code=201
)
def create_payment(
    consultation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequireRole([UserRole.CLIENT])),
):
    service = PaymentService(db)
    return service.create_payment_intent(current_user, consultation_id)


@router.get("/{consultation_id}/payments", response_model=list[PaymentResponse])
def get_consultation_payments(
    consultation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = PaymentService(db)
    return service.get_consultation_payments(current_user, consultation_id)


@router.post(
    "/{consultation_id}/messages", response_model=MessageResponse, status_code=201
)
def send_message(
    consultation_id: UUID,
    req: MessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = MessageService(db)
    return service.send_message(current_user, consultation_id, req)


@router.get("/{consultation_id}/messages", response_model=list[MessageResponse])
def get_messages(
    consultation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = MessageService(db)
    return service.get_messages(current_user, consultation_id)
