import uuid

from sqlalchemy.orm import Session

from app.core.exceptions import ValidationError
from app.core.identifiers import generate_uuid7
from app.models.consultation import ConsultationStatus
from app.models.message import Message
from app.models.user import User
from app.schemas.message import MessageCreate
from app.services.consultation_service import ConsultationService

INELIGIBLE_MESSAGE_STATUSES = {
    ConsultationStatus.CANCELLED,
    ConsultationStatus.COMPLETED,
    ConsultationStatus.REJECTED,
    ConsultationStatus.NO_SHOW,
}


class MessageService:
    def __init__(self, db: Session):
        self.db = db
        self.consultation_service = ConsultationService(db)

    def send_message(
        self, user: User, consultation_id: uuid.UUID, req: MessageCreate
    ) -> Message:
        consultation = self.consultation_service._get_consultation(consultation_id)
        self.consultation_service._authorize_consultation_access(user, consultation)

        if consultation.status in INELIGIBLE_MESSAGE_STATUSES:
            raise ValidationError(
                f"Cannot send messages to a consultation in {consultation.status.value} state"
            )

        msg = Message(
            id=generate_uuid7(),
            consultation_id=consultation.id,
            sender_id=user.id,
            content=req.content,
        )
        self.db.add(msg)
        self.db.commit()
        self.db.refresh(msg)
        return msg

    def get_messages(self, user: User, consultation_id: uuid.UUID) -> list[Message]:
        consultation = self.consultation_service._get_consultation(consultation_id)
        self.consultation_service._authorize_consultation_access(user, consultation)

        messages = (
            self.db.query(Message)
            .filter(
                Message.consultation_id == consultation.id, Message.deleted_at.is_(None)
            )
            .order_by(Message.created_at.asc())
            .all()
        )

        return messages
