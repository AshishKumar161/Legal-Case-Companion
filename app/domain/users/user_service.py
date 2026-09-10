from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.core.identifiers import generate_uuid7
from app.core.security import hash_password, normalize_email
from app.models.audit import AuditEvent
from app.models.user import AccountStatus, ClientProfile, LawyerProfile, User, UserRole
from app.schemas.user import UserCreate


class UserService:
    def __init__(self, db: Session):
        self.db = db

    def get_user_by_email(self, email: str) -> User | None:
        if not email or not isinstance(email, str):
            return None
        try:
            normalized_email = normalize_email(email)
        except ValueError:
            normalized_email = email.strip().lower()

        return (
            self.db.query(User)
            .filter(User.email == normalized_email, User.deleted_at.is_(None))
            .first()
        )

    def get_user_by_id(self, user_id) -> User | None:
        return (
            self.db.query(User)
            .filter(User.id == user_id, User.deleted_at.is_(None))
            .first()
        )

    def register_user(self, user_in: UserCreate) -> User:
        try:
            normalized_email = normalize_email(user_in.email)
        except ValueError as e:
            raise AppException(
                status_code=400,
                code="INVALID_EMAIL",
                message=str(e),
            ) from e

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

    def delete_user_account(
        self,
        user_id: Any,
        reason: str | None = None,
        ip_address: str | None = None,
    ) -> User:
        """Safely soft-deletes and anonymizes user account while preserving custody and audit integrity."""
        from app.models.auth import RefreshTokenSession

        user = self.get_user_by_id(user_id)
        if not user:
            raise AppException(
                status_code=404,
                code="USER_NOT_FOUND",
                message="User not found",
            )

        now = datetime.now(UTC)

        # 1. Revoke all active sessions
        self.db.query(RefreshTokenSession).filter(
            RefreshTokenSession.user_id == user.id,
            RefreshTokenSession.revoked_at.is_(None),
        ).update({"revoked_at": now})

        # 2. Anonymize PII in User model
        user.email = f"deleted_{user.id}@anonymized.local"
        user.account_status = AccountStatus.DEACTIVATED
        user.deleted_at = now

        # 3. Anonymize PII in associated profiles
        if user.role == UserRole.CLIENT:
            client_prof = self.db.query(ClientProfile).filter(ClientProfile.user_id == user.id).first()
            if client_prof:
                client_prof.full_name = "Anonymized Client"
                client_prof.location = None
        elif user.role == UserRole.LAWYER:
            lawyer_prof = self.db.query(LawyerProfile).filter(LawyerProfile.user_id == user.id).first()
            if lawyer_prof:
                lawyer_prof.full_name = "Anonymized Lawyer"
                lawyer_prof.location = None

        # 4. Record audit event
        audit = AuditEvent(
            id=generate_uuid7(),
            actor_user_id=user.id,
            event_type="ACCOUNT_DELETED",
            entity_type="user",
            entity_id=user.id,
            action="delete_account",
            timestamp=now,
            metadata_={"reason": reason or "User requested deletion", "ip": ip_address},
        )
        self.db.add(audit)

        self.db.commit()
        self.db.refresh(user)
        return user
