import uuid

from sqlalchemy.orm import Session

from app.core.exceptions import AuthorizationError, ResourceNotFoundError
from app.models.case import Case, CaseParticipant, ParticipantRole, ParticipantStatus
from app.models.document import Document
from app.models.user import User, UserRole


def _get_case_participant(db: Session, case_id: uuid.UUID, user_id: uuid.UUID):
    return (
        db.query(CaseParticipant)
        .filter(
            CaseParticipant.case_id == case_id,
            CaseParticipant.user_id == user_id,
            CaseParticipant.status == ParticipantStatus.ACTIVE,
        )
        .first()
    )


def authorize_case_access(db: Session, user: User, case_id: uuid.UUID) -> Case:
    case_ = db.query(Case).filter(Case.id == case_id, Case.deleted_at.is_(None)).first()
    if not case_:
        raise ResourceNotFoundError()

    if user.role == UserRole.ADMIN:
        return case_

    participant = _get_case_participant(db, case_id, user.id)
    if not participant:
        raise ResourceNotFoundError()  # Obscures existence from unauthorized users

    return case_


def authorize_case_modification(db: Session, user: User, case_id: uuid.UUID) -> Case:
    case_ = authorize_case_access(db, user, case_id)
    if user.role == UserRole.ADMIN:
        return case_

    participant = _get_case_participant(db, case_id, user.id)
    if not participant or participant.participant_role == ParticipantRole.VIEWER:
        raise AuthorizationError("Insufficient permissions to modify this case")

    return case_


def authorize_participant_management(
    db: Session, user: User, case_id: uuid.UUID
) -> Case:
    case_ = authorize_case_access(db, user, case_id)
    if user.role == UserRole.ADMIN:
        return case_

    participant = _get_case_participant(db, case_id, user.id)
    if not participant or participant.participant_role != ParticipantRole.OWNER:
        raise AuthorizationError("Only case owners can manage participants")

    return case_


def authorize_case_deletion(db: Session, user: User, case_id: uuid.UUID) -> Case:
    case_ = authorize_case_access(db, user, case_id)
    if user.role == UserRole.ADMIN:
        return case_

    participant = _get_case_participant(db, case_id, user.id)
    if not participant or participant.participant_role != ParticipantRole.OWNER:
        raise AuthorizationError("Only case owners can delete this case")

    return case_


def authorize_document_access(
    db: Session,
    user: User,
    document_id: uuid.UUID,
    case_id: uuid.UUID | None = None,
) -> Document:
    doc = (
        db.query(Document)
        .filter(Document.id == document_id, Document.deleted_at.is_(None))
        .first()
    )
    if not doc:
        raise ResourceNotFoundError()

    if case_id is not None and doc.case_id != case_id:
        raise ResourceNotFoundError()

    if user.role == UserRole.ADMIN:
        return doc

    # User must have access to the underlying case
    if doc.case_id:
        authorize_case_access(db, user, doc.case_id)
        return doc

    if doc.uploaded_by == user.id:
        return doc

    raise ResourceNotFoundError()


def authorize_document_modification(
    db: Session,
    user: User,
    document_id: uuid.UUID,
    case_id: uuid.UUID | None = None,
) -> Document:
    doc = authorize_document_access(db, user, document_id, case_id=case_id)
    if user.role == UserRole.ADMIN:
        return doc

    if doc.case_id:
        # Check if user has modification rights on the case
        participant = _get_case_participant(db, doc.case_id, user.id)
        if not participant or participant.participant_role == ParticipantRole.VIEWER:
            raise AuthorizationError("Insufficient permissions to modify this document")
        return doc

    if doc.uploaded_by == user.id:
        return doc

    raise AuthorizationError("Insufficient permissions to modify this document")


def authorize_document_deletion(
    db: Session,
    user: User,
    document_id: uuid.UUID,
    case_id: uuid.UUID | None = None,
) -> Document:
    doc = authorize_document_access(db, user, document_id, case_id=case_id)
    if user.role == UserRole.ADMIN:
        return doc

    if doc.case_id:
        participant = _get_case_participant(db, doc.case_id, user.id)
        if not participant:
            raise ResourceNotFoundError()
        if participant.participant_role == ParticipantRole.OWNER:
            return doc
        if participant.participant_role == ParticipantRole.LAWYER:
            if doc.uploaded_by == user.id:
                return doc
            raise AuthorizationError(
                "Assigned lawyers can only delete documents they uploaded themselves"
            )
        raise AuthorizationError("Viewers cannot delete documents")

    if doc.uploaded_by == user.id:
        return doc

    raise AuthorizationError("Insufficient permissions to delete this document")
