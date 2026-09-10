"""Persistence repository for Consultation entities and video meetings."""

from uuid import UUID
from sqlalchemy.orm import Session

from app.models.consultation import Consultation, ConsultationStatus
from app.models.video_meeting import VideoMeeting


class ConsultationRepository:
    """Encapsulates persistence operations for Consultation domain models."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, consultation_id: UUID) -> Consultation | None:
        """Retrieves a consultation by UUID, excluding soft-deleted records."""
        return (
            self.db.query(Consultation)
            .filter(Consultation.id == consultation_id, Consultation.deleted_at.is_(None))
            .first()
        )

    def list_by_client(
        self,
        client_id: UUID,
        status: ConsultationStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Consultation]:
        """Lists active consultations for a client."""
        query = self.db.query(Consultation).filter(
            Consultation.client_id == client_id,
            Consultation.deleted_at.is_(None),
        )
        if status:
            query = query.filter(Consultation.status == status)
        return query.order_by(Consultation.created_at.desc()).offset(offset).limit(limit).all()

    def list_by_lawyer(
        self,
        lawyer_id: UUID,
        status: ConsultationStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Consultation]:
        """Lists active consultations for a lawyer."""
        query = self.db.query(Consultation).filter(
            Consultation.lawyer_id == lawyer_id,
            Consultation.deleted_at.is_(None),
        )
        if status:
            query = query.filter(Consultation.status == status)
        return query.order_by(Consultation.created_at.desc()).offset(offset).limit(limit).all()

    def get_video_meeting(self, consultation_id: UUID) -> VideoMeeting | None:
        """Retrieves the video meeting associated with a consultation."""
        return (
            self.db.query(VideoMeeting)
            .filter(VideoMeeting.consultation_id == consultation_id)
            .first()
        )
