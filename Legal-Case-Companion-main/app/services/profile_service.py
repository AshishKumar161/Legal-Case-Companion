import uuid

from sqlalchemy import String, cast, exists, or_
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import (
    AuthorizationError,
    ResourceNotFoundError,
    ValidationError,
)
from app.models.availability import LawyerAvailability
from app.models.user import (
    AccountStatus,
    ClientProfile,
    LawyerProfile,
    LawyerVerification,
    User,
    UserRole,
    VerificationStatus,
)
from app.schemas.availability import (
    LawyerAvailabilityCreate,
    LawyerAvailabilityUpdate,
)
from app.schemas.profile import (
    ClientProfileUpdate,
    LawyerProfileUpdate,
    LawyerVerificationCreate,
)
from app.services.auth_service import AuthService
from app.services.presence_service import presence_service


class ProfileService:
    def __init__(self, db: Session):
        self.db = db
        self.auth_service = AuthService(db)

    def _log_audit(self, event_type: str, user_id: uuid.UUID, metadata: dict):
        self.auth_service.log_audit_event(
            event_type, user_id, metadata, action="profile_mutation"
        )

    def get_client_profile(self, user_id: uuid.UUID) -> ClientProfile:
        profile = (
            self.db.query(ClientProfile)
            .filter(ClientProfile.user_id == user_id)
            .first()
        )
        if not profile:
            raise ResourceNotFoundError("Client profile not found")
        return profile

    def update_client_profile(
        self, user: User, update_data: ClientProfileUpdate
    ) -> ClientProfile:
        if user.role != UserRole.CLIENT:
            raise AuthorizationError("Only clients can update client profiles")

        profile = self.get_client_profile(user.id)

        updated_fields = {}
        for field, value in update_data.model_dump(exclude_unset=True).items():
            if field == "phone":
                user.phone = value
                updated_fields["phone"] = value
            else:
                setattr(profile, field, value)
                updated_fields[field] = value

        self.db.commit()
        self.db.refresh(profile)

        if updated_fields:
            self._log_audit(
                "PROFILE_UPDATED",
                user.id,
                {"updated_fields": list(updated_fields.keys())},
            )

        return profile

    def get_lawyer_profile(self, user_id: uuid.UUID) -> LawyerProfile:
        profile = (
            self.db.query(LawyerProfile)
            .options(selectinload(LawyerProfile.verifications))
            .filter(LawyerProfile.user_id == user_id)
            .first()
        )
        if not profile:
            raise ResourceNotFoundError("Lawyer profile not found")
        return profile

    def get_public_lawyer_profile(self, identifier: uuid.UUID) -> LawyerProfile:
        profile = (
            self.db.query(LawyerProfile)
            .options(selectinload(LawyerProfile.verifications))
            .join(User, LawyerProfile.user_id == User.id)
            .filter(
                or_(
                    LawyerProfile.user_id == identifier,
                    LawyerProfile.id == identifier,
                ),
                User.account_status == AccountStatus.ACTIVE,
                LawyerProfile.deleted_at.is_(None),
            )
            .first()
        )
        if not profile:
            raise ResourceNotFoundError("Lawyer profile not found or inactive")
        profile.is_online = presence_service.is_online(profile.user_id)
        if profile.is_online:
            from app.services.consultation_service import ConsultationService
            consultation_service = ConsultationService(self.db)
            is_avail, _, p_status = consultation_service.is_lawyer_available(profile.id)
            profile.is_available = is_avail
            profile.presence_status = p_status.value if hasattr(p_status, "value") else str(p_status)
        else:
            profile.is_available = False
            profile.presence_status = "OFFLINE"
        return profile

    def search_lawyers(
        self,
        skip: int = 0,
        limit: int = 20,
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
    ) -> dict:
        limit = min(max(limit, 1), 100)
        query = (
            self.db.query(LawyerProfile)
            .options(selectinload(LawyerProfile.verifications))
            .join(User, LawyerProfile.user_id == User.id)
            .filter(
                User.account_status == AccountStatus.ACTIVE,
                LawyerProfile.deleted_at.is_(None),
            )
        )

        online_uids = presence_service.get_online_user_ids()
        if online_only:
            if not online_uids:
                return {"items": [], "total": 0, "skip": skip, "limit": limit}
            query = query.filter(
                LawyerProfile.user_id.in_([uuid.UUID(uid) for uid in online_uids])
            )

        if search and search.strip():
            term = f"%{search.strip()}%"
            query = query.filter(
                or_(
                    LawyerProfile.full_name.ilike(term),
                    LawyerProfile.bio.ilike(term),
                )
            )

        if location and location.strip():
            loc_term = f"%{location.strip()}%"
            query = query.filter(LawyerProfile.location.ilike(loc_term))

        if court_jurisdiction and court_jurisdiction.strip():
            juris_term = f"%{court_jurisdiction.strip()}%"
            query = query.filter(
                cast(LawyerProfile.court_jurisdictions, String).ilike(juris_term)
            )

        if practice_area and practice_area.strip():
            pa_term = f"%{practice_area.strip()}%"
            query = query.filter(
                cast(LawyerProfile.practice_areas, String).ilike(pa_term)
            )

        if language and language.strip():
            lang_term = f"%{language.strip()}%"
            query = query.filter(cast(LawyerProfile.languages, String).ilike(lang_term))

        if min_fee is not None:
            query = query.filter(LawyerProfile.consultation_fee >= min_fee)

        if max_fee is not None:
            query = query.filter(LawyerProfile.consultation_fee <= max_fee)

        if min_experience is not None:
            query = query.filter(LawyerProfile.experience_years >= min_experience)

        if max_experience is not None:
            query = query.filter(LawyerProfile.experience_years <= max_experience)

        if verified_only:
            # Use exists() subquery to avoid duplicate rows from 1:N verifications join
            has_approved_verif = exists().where(
                LawyerVerification.lawyer_profile_id == LawyerProfile.id,
                LawyerVerification.status == VerificationStatus.APPROVED,
            )
            query = query.filter(has_approved_verif)

        all_matches = query.order_by(LawyerProfile.created_at.desc()).all()
        from app.services.consultation_service import ConsultationService
        consultation_service = ConsultationService(self.db)

        for lp in all_matches:
            lp.is_online = presence_service.is_online(lp.user_id)
            if lp.is_online:
                is_avail, _, p_status = consultation_service.is_lawyer_available(lp.id)
                lp.is_available = is_avail
                lp.presence_status = p_status.value if hasattr(p_status, "value") else str(p_status)
            else:
                lp.is_available = False
                lp.presence_status = "OFFLINE"

            # Phase 9: Explainable Discovery Match Criteria
            reasons: list[str] = []
            if court_jurisdiction and lp.court_jurisdictions:
                if any(court_jurisdiction.lower() in str(cj).lower() for cj in lp.court_jurisdictions):
                    reasons.append(f"Jurisdiction: {court_jurisdiction}")
            if practice_area and lp.practice_areas:
                if any(practice_area.lower() in str(pa).lower() for pa in lp.practice_areas):
                    reasons.append(f"Practice Area: {practice_area}")
            if language and lp.languages:
                if any(language.lower() in str(lang).lower() for lang in lp.languages):
                    reasons.append(f"Language: {language}")
            if getattr(lp, "is_available", False):
                reasons.append("Available for Consultation")
            elif getattr(lp, "is_online", False):
                reasons.append("Currently Online")
            if lp.verification_status == "APPROVED":
                reasons.append("Verified Bar Council Advocate")
            if lp.consultation_fee is not None:
                reasons.append(f"Transparent Fee: ₹{int(lp.consultation_fee)}")

            lp.match_reasons = reasons

        # Deterministic explainable sort: highest match count first, then availability, then recency
        all_matches.sort(
            key=lambda x: (
                -len(getattr(x, "match_reasons", [])),
                not getattr(x, "is_available", False),
                not getattr(x, "is_online", False),
                -(x.created_at.timestamp() if x.created_at else 0),
            )
        )

        total = len(all_matches)
        paginated = all_matches[skip : skip + limit]
        return {"items": paginated, "total": total, "skip": skip, "limit": limit}

    def update_lawyer_profile(
        self, user: User, update_data: LawyerProfileUpdate
    ) -> LawyerProfile:
        if user.role != UserRole.LAWYER:
            raise AuthorizationError("Only lawyers can update lawyer profiles")

        profile = self.get_lawyer_profile(user.id)

        updated_fields = {}
        for field, value in update_data.model_dump(exclude_unset=True).items():
            if field == "phone":
                user.phone = value
                updated_fields["phone"] = value
            else:
                setattr(profile, field, value)
                updated_fields[field] = value

        self.db.commit()
        self.db.refresh(profile)

        if updated_fields:
            self._log_audit(
                "PROFILE_UPDATED",
                user.id,
                {"updated_fields": list(updated_fields.keys())},
            )

        return profile

    def submit_verification(
        self, user: User, req: LawyerVerificationCreate
    ) -> LawyerVerification:
        if user.role != UserRole.LAWYER:
            raise AuthorizationError("Only lawyers can submit verifications")

        profile = self.get_lawyer_profile(user.id)

        # Check if already pending
        existing = (
            self.db.query(LawyerVerification)
            .filter(
                LawyerVerification.lawyer_profile_id == profile.id,
                LawyerVerification.status.in_(
                    [VerificationStatus.PENDING, VerificationStatus.UNDER_REVIEW]
                ),
            )
            .first()
        )

        if existing:
            raise ValidationError("A verification request is already in progress")

        verification = LawyerVerification(
            lawyer_profile_id=profile.id,
            enrollment_number=req.enrollment_number,
            state_bar_council=req.state_bar_council,
            status=VerificationStatus.PENDING,
        )
        self.db.add(verification)
        self.db.commit()
        self.db.refresh(verification)

        self._log_audit(
            "LAWYER_VERIFICATION_SUBMITTED",
            user.id,
            {"verification_id": str(verification.id)},
        )
        return verification

    def get_lawyer_availabilities(self, user: User) -> list[LawyerAvailability]:
        if user.role != UserRole.LAWYER:
            raise AuthorizationError("Only lawyers can view their availability settings")
        profile = self.get_lawyer_profile(user.id)
        return (
            self.db.query(LawyerAvailability)
            .filter(LawyerAvailability.lawyer_profile_id == profile.id)
            .order_by(LawyerAvailability.day_of_week.asc(), LawyerAvailability.start_time.asc())
            .all()
        )

    def create_lawyer_availability(
        self, user: User, req: LawyerAvailabilityCreate
    ) -> LawyerAvailability:
        if user.role != UserRole.LAWYER:
            raise AuthorizationError("Only lawyers can configure availability")
        profile = self.get_lawyer_profile(user.id)

        # Check for overlapping availability windows on the same day of week
        existing_windows = (
            self.db.query(LawyerAvailability)
            .filter(
                LawyerAvailability.lawyer_profile_id == profile.id,
                LawyerAvailability.day_of_week == req.day_of_week,
                LawyerAvailability.is_active.is_(True),
            )
            .all()
        )
        for win in existing_windows:
            if req.start_time < win.end_time and win.start_time < req.end_time:
                raise ValidationError(
                    "Availability window overlaps with an existing configured window for this day"
                )

        availability = LawyerAvailability(
            lawyer_profile_id=profile.id,
            day_of_week=req.day_of_week,
            start_time=req.start_time,
            end_time=req.end_time,
            slot_duration_minutes=req.slot_duration_minutes,
            is_active=req.is_active,
        )
        self.db.add(availability)
        self.db.commit()
        self.db.refresh(availability)

        self._log_audit(
            "LAWYER_AVAILABILITY_CREATED",
            user.id,
            {
                "availability_id": str(availability.id),
                "day_of_week": req.day_of_week,
                "start_time": str(req.start_time),
                "end_time": str(req.end_time),
            },
        )
        return availability

    def update_lawyer_availability(
        self, user: User, availability_id: uuid.UUID, req: LawyerAvailabilityUpdate
    ) -> LawyerAvailability:
        if user.role != UserRole.LAWYER:
            raise AuthorizationError("Only lawyers can update availability")
        profile = self.get_lawyer_profile(user.id)

        availability = (
            self.db.query(LawyerAvailability)
            .filter(
                LawyerAvailability.id == availability_id,
                LawyerAvailability.lawyer_profile_id == profile.id,
            )
            .first()
        )
        if not availability:
            raise ResourceNotFoundError("Availability record not found")

        new_start = req.start_time if req.start_time is not None else availability.start_time
        new_end = req.end_time if req.end_time is not None else availability.end_time

        if new_end <= new_start:
            raise ValidationError("end_time must be strictly after start_time")

        # Check overlap with other windows on the same day
        other_windows = (
            self.db.query(LawyerAvailability)
            .filter(
                LawyerAvailability.lawyer_profile_id == profile.id,
                LawyerAvailability.day_of_week == availability.day_of_week,
                LawyerAvailability.id != availability.id,
                LawyerAvailability.is_active.is_(True),
            )
            .all()
        )
        is_active = req.is_active if req.is_active is not None else availability.is_active
        if is_active:
            for win in other_windows:
                if new_start < win.end_time and win.start_time < new_end:
                    raise ValidationError(
                        "Updated availability window overlaps with an existing configured window for this day"
                    )

        if req.start_time is not None:
            availability.start_time = req.start_time
        if req.end_time is not None:
            availability.end_time = req.end_time
        if req.slot_duration_minutes is not None:
            availability.slot_duration_minutes = req.slot_duration_minutes
        if req.is_active is not None:
            availability.is_active = req.is_active

        self.db.commit()
        self.db.refresh(availability)

        self._log_audit(
            "LAWYER_AVAILABILITY_UPDATED",
            user.id,
            {"availability_id": str(availability.id)},
        )
        return availability

    def delete_lawyer_availability(
        self, user: User, availability_id: uuid.UUID
    ) -> None:
        if user.role != UserRole.LAWYER:
            raise AuthorizationError("Only lawyers can delete availability")
        profile = self.get_lawyer_profile(user.id)

        availability = (
            self.db.query(LawyerAvailability)
            .filter(
                LawyerAvailability.id == availability_id,
                LawyerAvailability.lawyer_profile_id == profile.id,
            )
            .first()
        )
        if not availability:
            raise ResourceNotFoundError("Availability record not found")

        self.db.delete(availability)
        self.db.commit()

        self._log_audit(
            "LAWYER_AVAILABILITY_DELETED",
            user.id,
            {"availability_id": str(availability_id)},
        )

    def get_public_lawyer_availabilities(
        self, lawyer_id: uuid.UUID
    ) -> list[LawyerAvailability]:
        profile = self.get_public_lawyer_profile(lawyer_id)
        return (
            self.db.query(LawyerAvailability)
            .filter(
                LawyerAvailability.lawyer_profile_id == profile.id,
                LawyerAvailability.is_active.is_(True),
            )
            .order_by(LawyerAvailability.day_of_week.asc(), LawyerAvailability.start_time.asc())
            .all()
        )
