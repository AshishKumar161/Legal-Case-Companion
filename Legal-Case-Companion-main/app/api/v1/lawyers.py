from datetime import UTC, date, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_optional_current_user
from app.models.user import LawyerProfile, User
from app.schemas.availability import LawyerAvailabilityResponse, SlotResponse
from app.schemas.pagination import PaginatedResponse
from app.schemas.presence import (
    HeartbeatRequest,
    LawyerPresenceStatusResponse,
    PresenceStatus,
)
from app.schemas.profile import LawyerPublicResponse
from app.services.consultation_service import ConsultationService
from app.services.presence_service import presence_service
from app.services.profile_service import ProfileService

router = APIRouter(prefix="/lawyers", tags=["lawyers"])


@router.post("/heartbeat")
def record_lawyer_heartbeat(
    req: HeartbeatRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Heartbeat ping to mark lawyer/user as online in real-time.
    Authoritatively calculates whether the lawyer is available for instant calls.
    """
    avail_pref = req.available_for_instant if req is not None else True

    lawyer_profile = (
        db.query(LawyerProfile)
        .filter(LawyerProfile.user_id == current_user.id, LawyerProfile.deleted_at.is_(None))
        .first()
    )
    lawyer_id = lawyer_profile.id if lawyer_profile else None

    presence_service.record_heartbeat(
        user_id=current_user.id,
        lawyer_id=lawyer_id,
        available_preference=avail_pref,
    )

    is_avail = False
    p_status = PresenceStatus.ONLINE
    if lawyer_profile:
        consultation_service = ConsultationService(db)
        is_avail, _, p_status = consultation_service.is_lawyer_available(lawyer_profile.id)

    now_utc = datetime.now(UTC)
    return {
        "status": "ok",
        "user_id": str(current_user.id),
        "lawyer_id": str(lawyer_id) if lawyer_id else None,
        "is_online": True,
        "is_available": is_avail,
        "presence_status": p_status.value if hasattr(p_status, "value") else str(p_status),
        "last_heartbeat": now_utc.isoformat(),
    }


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
    current_user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    """
    Search and list verified lawyers.
    Supports public unauthenticated discovery (verified-only) and authenticated user discovery.
    """
    if current_user:
        presence_service.record_heartbeat(current_user.id)
    else:
        # Enforce verified_only for unauthenticated public browsing
        verified_only = True

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
    current_user: User | None = Depends(get_optional_current_user),
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
    current_user: User | None = Depends(get_optional_current_user),
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
    current_user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    """
    Get active availability rules configured by the lawyer.
    """
    profile_service = ProfileService(db)
    return profile_service.get_public_lawyer_availabilities(lawyer_id)


@router.get("/{lawyer_id}/presence", response_model=LawyerPresenceStatusResponse)
def get_lawyer_presence(
    lawyer_id: UUID,
    current_user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    """
    Authoritatively get the current real-time presence and instant-call availability status for a lawyer.
    """
    lawyer_profile = (
        db.query(LawyerProfile)
        .filter(
            (LawyerProfile.id == lawyer_id) | (LawyerProfile.user_id == lawyer_id),
            LawyerProfile.deleted_at.is_(None),
        )
        .first()
    )
    user_id = lawyer_profile.user_id if lawyer_profile else lawyer_id
    actual_lawyer_id = lawyer_profile.id if lawyer_profile else lawyer_id

    consultation_service = ConsultationService(db)
    is_avail, reason, p_status = consultation_service.is_lawyer_available(actual_lawyer_id)
    rec = presence_service.get_presence(user_id=user_id, lawyer_id=actual_lawyer_id)
    is_online = rec is not None
    last_hb_str = rec.get("last_heartbeat") if rec else None
    last_hb = datetime.fromisoformat(last_hb_str) if last_hb_str else None

    return LawyerPresenceStatusResponse(
        user_id=user_id,
        lawyer_id=actual_lawyer_id,
        is_online=is_online,
        is_available=is_avail,
        presence_status=p_status,
        last_heartbeat=last_hb,
    )


