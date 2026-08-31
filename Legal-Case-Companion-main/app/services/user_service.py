from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.core.identifiers import generate_uuid7
from app.core.security import hash_password, normalize_email
from app.models.user import AccountStatus, ClientProfile, LawyerProfile, User, UserRole
from app.schemas.user import UserCreate


class UserService:
    def __init__(self, db: Session):
        self.db = db

    def get_user_by_email(self, email: str) -> User | None:
        normalized_email = normalize_email(email)
        return (
            self.db.query(User)
            .filter(User.email == normalized_email, User.deleted_at == None)
            .first()
        )

    def get_user_by_id(self, user_id) -> User | None:
        return (
            self.db.query(User)
            .filter(User.id == user_id, User.deleted_at == None)
            .first()
        )

    def register_user(self, user_in: UserCreate) -> User:
        normalized_email = normalize_email(user_in.email)

        if self.get_user_by_email(normalized_email):
            raise AppException(
                status_code=400,
                code="EMAIL_EXISTS",
                message="A user with this email already exists.",
            )

        requested_role = UserRole(user_in.role)
        if requested_role == UserRole.ADMIN:
            raise AppException(
                status_code=403, code="FORBIDDEN", message="Cannot register as ADMIN"
            )

        user = User(
            id=generate_uuid7(),
            email=normalized_email,
            password_hash=hash_password(user_in.password),
            role=requested_role,
            account_status=AccountStatus.ACTIVE,
        )
        self.db.add(user)

        if user.role == UserRole.CLIENT:
            self.db.add(
                ClientProfile(
                    id=generate_uuid7(), user_id=user.id, full_name=user_in.full_name
                )
            )
        elif user.role == UserRole.LAWYER:
            self.db.add(
                LawyerProfile(
                    id=generate_uuid7(), user_id=user.id, full_name=user_in.full_name
                )
            )

        self.db.flush()

        from app.models.audit import AuditEvent

        audit = AuditEvent(
            id=generate_uuid7(),
            actor_user_id=user.id,
            event_type="REGISTRATION",
            entity_type="user",
            entity_id=user.id,
            action="register",
            timestamp=datetime.now(UTC),
            metadata_={},
        )
        self.db.add(audit)

        self.db.commit()
        self.db.refresh(user)
        return user
