from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.availability import LawyerAvailabilityResponse, SlotResponse
from app.schemas.pagination import PaginatedResponse
from app.schemas.profile import LawyerPublicResponse
from app.services.consultation_service import ConsultationService
from app.services.profile_service import ProfileService

from app.services.presence_service import presence_manager

router = APIRouter(prefix="/lawyers", tags=["lawyers"])


@router.post("/heartbeat")
def record_lawyer_heartbeat(
    current_user: User = Depends(get_current_user),
):
    """
    Heartbeat ping to mark lawyer/user as online in real-time.
    Called periodically by the client application while the lawyer tab is active.
    """
    presence_manager.record_heartbeat(current_user.id)
    return {"status": "ok", "user_id": str(current_user.id), "is_online": True}


@router.get("", response_model=PaginatedResponse[LawyerPublicResponse])
def search_lawyers(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    location: str | None = None,
    court_jurisdiction: str | None = None,
    practice_area: str | None = None,
    search: str | None = None,
    min_fee: float | None = None,
    max_fee: float | None = None,
    min_experience: int | None = None,
    max_experience: int | None = None,
    language: str | None = None,
    verified_only: bool = True,
    online_only: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Search and list lawyers.
    Requires authentication to prevent unauthenticated scraping.
    Defaults to verified_only=True for client safety.
    """
    # Also record activity for current user
    presence_manager.record_heartbeat(current_user.id)

    profile_service = ProfileService(db)
    return profile_service.search_lawyers(
        skip=skip,
        limit=limit,
        location=location,
        court_jurisdiction=court_jurisdiction,
        practice_area=practice_area,
        search=search,
        min_fee=min_fee,
        max_fee=max_fee,
        min_experience=min_experience,
        max_experience=max_experience,
        language=language,
        verified_only=verified_only,
        online_only=online_only,
    )


@router.get("/{user_id}", response_model=LawyerPublicResponse)
def get_lawyer_profile(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get a specific lawyer's public profile details.
    """
    profile_service = ProfileService(db)
    return profile_service.get_public_lawyer_profile(user_id)


@router.get("/{lawyer_id}/slots", response_model=list[SlotResponse])
def get_lawyer_slots(
    lawyer_id: UUID,
    date: date | None = Query(None, description="Target date in YYYY-MM-DD format"),
    duration_minutes: int = Query(30, ge=15, le=240),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get bookable consultation time slots for an eligible lawyer on a given date.
    """
    consultation_service = ConsultationService(db)
    return consultation_service.get_available_slots(
        lawyer_id=lawyer_id,
        target_date=date,
        duration_minutes=duration_minutes,
    )


@router.get("/{lawyer_id}/availability", response_model=list[LawyerAvailabilityResponse])
def get_public_lawyer_availability(
    lawyer_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get active availability rules configured by the lawyer.
    """
    profile_service = ProfileService(db)
    return profile_service.get_public_lawyer_availabilities(lawyer_id)

