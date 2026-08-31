from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import RequireRole, get_current_user, get_db
from app.core.exceptions import ResourceNotFoundError
from app.models.user import User, UserRole
from app.schemas.availability import (
    LawyerAvailabilityCreate,
    LawyerAvailabilityResponse,
    LawyerAvailabilityUpdate,
)
from app.schemas.profile import (
    ClientProfileResponse,
    ClientProfileUpdate,
    LawyerProfileResponse,
    LawyerProfileUpdate,
    LawyerVerificationCreate,
    LawyerVerificationResponse,
)
from app.services.profile_service import ProfileService

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.get("/me", response_model=ClientProfileResponse | LawyerProfileResponse)
def get_my_profile(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    profile_service = ProfileService(db)
    if current_user.role == UserRole.CLIENT:
        return profile_service.get_client_profile(current_user.id)
    elif current_user.role == UserRole.LAWYER:
        return profile_service.get_lawyer_profile(current_user.id)
    else:
        raise ResourceNotFoundError("Profile not found for this user role")


@router.patch("/client", response_model=ClientProfileResponse)
def update_client_profile(
    update_data: ClientProfileUpdate,
    current_user: User = Depends(RequireRole([UserRole.CLIENT])),
    db: Session = Depends(get_db),
):
    profile_service = ProfileService(db)
    return profile_service.update_client_profile(current_user, update_data)


@router.patch("/lawyer", response_model=LawyerProfileResponse)
def update_lawyer_profile(
    update_data: LawyerProfileUpdate,
    current_user: User = Depends(RequireRole([UserRole.LAWYER])),
    db: Session = Depends(get_db),
):
    profile_service = ProfileService(db)
    return profile_service.update_lawyer_profile(current_user, update_data)


@router.post("/lawyer/verification", response_model=LawyerVerificationResponse)
def submit_lawyer_verification(
    req: LawyerVerificationCreate,
    current_user: User = Depends(RequireRole([UserRole.LAWYER])),
    db: Session = Depends(get_db),
):
    profile_service = ProfileService(db)
    return profile_service.submit_verification(current_user, req)


@router.get(
    "/lawyer/availability",
    response_model=list[LawyerAvailabilityResponse],
)
def get_lawyer_availabilities(
    current_user: User = Depends(RequireRole([UserRole.LAWYER])),
    db: Session = Depends(get_db),
):
    """
    Get all availability schedule rules configured for the authenticated lawyer.
    """
    profile_service = ProfileService(db)
    return profile_service.get_lawyer_availabilities(current_user)


@router.post(
    "/lawyer/availability",
    response_model=LawyerAvailabilityResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_lawyer_availability(
    req: LawyerAvailabilityCreate,
    current_user: User = Depends(RequireRole([UserRole.LAWYER])),
    db: Session = Depends(get_db),
):
    """
    Create a new availability schedule rule for the authenticated lawyer.
    """
    profile_service = ProfileService(db)
    return profile_service.create_lawyer_availability(current_user, req)


@router.patch(
    "/lawyer/availability/{availability_id}",
    response_model=LawyerAvailabilityResponse,
)
def update_lawyer_availability(
    availability_id: UUID,
    req: LawyerAvailabilityUpdate,
    current_user: User = Depends(RequireRole([UserRole.LAWYER])),
    db: Session = Depends(get_db),
):
    """
    Update an existing availability schedule rule for the authenticated lawyer.
    """
    profile_service = ProfileService(db)
    return profile_service.update_lawyer_availability(
        current_user, availability_id, req
    )


@router.delete(
    "/lawyer/availability/{availability_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_lawyer_availability(
    availability_id: UUID,
    current_user: User = Depends(RequireRole([UserRole.LAWYER])),
    db: Session = Depends(get_db),
):
    """
    Delete an availability schedule rule for the authenticated lawyer.
    """
    profile_service = ProfileService(db)
    profile_service.delete_lawyer_availability(current_user, availability_id)

