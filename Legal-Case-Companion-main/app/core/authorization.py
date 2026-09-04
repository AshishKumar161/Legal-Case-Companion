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


def authorize_consultation_access(
    db: Session,
    user: User,
    consultation_id: uuid.UUID,
    for_update: bool = False,
):
    from app.models.consultation import Consultation
    from app.models.user import ClientProfile, LawyerProfile

    query = db.query(Consultation).filter(
        Consultation.id == consultation_id,
        Consultation.deleted_at.is_(None),
    )
    if for_update and db.bind and db.bind.dialect.name == "postgresql":
        query = query.with_for_update()

    consultation = query.first()
    if not consultation:
        raise ResourceNotFoundError("Consultation not found")

    if user.role == UserRole.ADMIN:
        return consultation

    # Verify user matches either the client or lawyer profile associated with the consultation
    is_client = (
        db.query(ClientProfile)
        .filter(
            ClientProfile.id == consultation.client_id,
            ClientProfile.user_id == user.id,
        )
        .first()
    )
    if is_client:
        return consultation

    is_lawyer = (
        db.query(LawyerProfile)
        .filter(
            LawyerProfile.id == consultation.lawyer_id,
            LawyerProfile.user_id == user.id,
        )
        .first()
    )
    if is_lawyer:
        return consultation

    # If linked to a case, check active participant access
    if consultation.case_id:
        part = _get_case_participant(db, consultation.case_id, user.id)
        if part:
            return consultation

    raise ResourceNotFoundError("Consultation not found")


def authorize_recording_access(
    db: Session,
    user: User,
    recording_id: uuid.UUID,
):
    from app.models.video_recording import VideoRecording

    rec = (
        db.query(VideoRecording)
        .filter(
            VideoRecording.id == recording_id,
            VideoRecording.deleted_at.is_(None),
        )
        .first()
    )
    if not rec:
        raise ResourceNotFoundError("Recording not found")

    if user.role == UserRole.ADMIN:
        return rec

    con = rec.consultation
    if con:
        if con.client and con.client.user_id == user.id:
            return rec
        if con.lawyer and con.lawyer.user_id == user.id:
            return rec

    if rec.case_id:
        part = _get_case_participant(db, rec.case_id, user.id)
        if part:
            return rec

    raise ResourceNotFoundError("Recording not found")


def authorize_evidence_access(
    db: Session,
    user: User,
    evidence_id: uuid.UUID,
    required_level: str = "VIEW",
):
    """Authorizes access to an Evidence Locker item.

    Enforces:
    1. Evidence exists and is not soft-deleted.
    2. Case authorization: User must be an authorized participant for the parent case.
    3. User must be:
       - Platform Admin
       - Creator of the evidence item
       - Active Case OWNER participant
       - Holder of an active, unrevoked, unexpired EvidenceAccessGrant satisfying required_level
    Raises ResourceNotFoundError if unauthorized.
    """
    from datetime import UTC, datetime

    from app.models.evidence import Evidence, EvidenceAccessGrant

    evidence = (
        db.query(Evidence)
        .filter(Evidence.id == evidence_id, Evidence.deleted_at.is_(None))
        .first()
    )
    if not evidence:
        raise ResourceNotFoundError("Evidence not found")

    # 1. Enforce case-level access boundary
    authorize_case_access(db, user, evidence.case_id)

    # 2. Platform Admin has system-level access
    if user.role == UserRole.ADMIN:
        return evidence, None

    # 3. Creator has full access
    if evidence.created_by_user_id == user.id:
        return evidence, None

    # 4. Case OWNER has full management access
    part = _get_case_participant(db, evidence.case_id, user.id)
    if part and part.participant_role == ParticipantRole.OWNER:
        return evidence, None

    # 5. Check explicit EvidenceAccessGrant
    now = datetime.now(UTC)
    grant = (
        db.query(EvidenceAccessGrant)
        .filter(
            EvidenceAccessGrant.evidence_id == evidence_id,
            EvidenceAccessGrant.grantee_user_id == user.id,
            EvidenceAccessGrant.revoked_at.is_(None),
        )
        .first()
    )

    if grant:
        # Verify expiration if set
        if grant.expires_at is not None:
            expires_at = grant.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=UTC)
            if expires_at <= now:
                raise ResourceNotFoundError("Evidence not found")

        # Check access level hierarchy
        level = grant.access_level.value if hasattr(grant.access_level, "value") else str(grant.access_level)
        req = required_level.value if hasattr(required_level, "value") else str(required_level)

        if req == "VIEW" or req == "DOWNLOAD" and level in ("DOWNLOAD", "MANAGE") or req == "MANAGE" and level == "MANAGE":
            return evidence, grant

    raise ResourceNotFoundError("Evidence not found")


def authorize_evidence_management(
    db: Session,
    user: User,
    evidence_id: uuid.UUID,
):
    """Authorizes management actions on an Evidence item (versioning, sharing, revocation, deletion)."""
    evidence, _ = authorize_evidence_access(db, user, evidence_id, required_level="MANAGE")
    return evidence

