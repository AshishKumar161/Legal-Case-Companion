"""Persistence repository for Case entities and related models."""

from uuid import UUID
from sqlalchemy.orm import Session

from app.models.case import (
    Case,
    CaseParticipant,
    CaseStatus,
    ParticipantRole,
    ParticipantStatus,
)


class CaseRepository:
    """Encapsulates persistence operations for Case domain models."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, case_id: UUID) -> Case | None:
        """Retrieves a case by UUID, excluding soft-deleted records."""
        return (
            self.db.query(Case)
            .filter(Case.id == case_id, Case.deleted_at.is_(None))
            .first()
        )

    def get_by_id_and_owner(self, case_id: UUID, user_id: UUID) -> Case | None:
        """Retrieves an active case where the user is an active OWNER participant."""
        return (
            self.db.query(Case)
            .join(CaseParticipant, CaseParticipant.case_id == Case.id)
            .filter(
                Case.id == case_id,
                CaseParticipant.user_id == user_id,
                CaseParticipant.participant_role == ParticipantRole.OWNER,
                CaseParticipant.status == ParticipantStatus.ACTIVE,
                Case.deleted_at.is_(None),
            )
            .first()
        )

    def list_by_user(
        self,
        user_id: UUID,
        status: CaseStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Case]:
        """Lists active cases where the user is an active participant."""
        query = (
            self.db.query(Case)
            .join(CaseParticipant, CaseParticipant.case_id == Case.id)
            .filter(
                CaseParticipant.user_id == user_id,
                CaseParticipant.status == ParticipantStatus.ACTIVE,
                Case.deleted_at.is_(None),
            )
        )
        if status:
            query = query.filter(Case.status == status)
        return query.order_by(Case.created_at.desc()).offset(offset).limit(limit).all()

    def count_by_user(self, user_id: UUID, status: CaseStatus | None = None) -> int:
        """Counts active cases for a user participant."""
        query = (
            self.db.query(Case.id)
            .join(CaseParticipant, CaseParticipant.case_id == Case.id)
            .filter(
                CaseParticipant.user_id == user_id,
                CaseParticipant.status == ParticipantStatus.ACTIVE,
                Case.deleted_at.is_(None),
            )
        )
        if status:
            query = query.filter(Case.status == status)
        return query.count()
