"""Persistence repository for User entities and associated profiles."""

from uuid import UUID
from sqlalchemy.orm import Session

from app.models.user import ClientProfile, LawyerProfile, User


class UserRepository:
    """Encapsulates persistence operations for User and Profile domain models."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, user_id: UUID) -> User | None:
        """Retrieves a user by UUID, excluding soft-deleted accounts."""
        return self.db.query(User).filter(User.id == user_id, User.deleted_at.is_(None)).first()

    def get_by_id_include_deleted(self, user_id: UUID) -> User | None:
        """Retrieves a user by UUID including soft-deleted accounts."""
        return self.db.query(User).filter(User.id == user_id).first()

    def get_by_email(self, email: str) -> User | None:
        """Retrieves a user by normalized lowercase email, excluding soft-deleted accounts."""
        return (
            self.db.query(User)
            .filter(User.email == email.strip().lower(), User.deleted_at.is_(None))
            .first()
        )

    def get_advocate_profile(self, user_id: UUID) -> LawyerProfile | None:
        """Retrieves the advocate profile for a user."""
        return (
            self.db.query(LawyerProfile)
            .filter(LawyerProfile.user_id == user_id)
            .first()
        )

    def get_client_profile(self, user_id: UUID) -> ClientProfile | None:
        """Retrieves the client profile for a user."""
        return (
            self.db.query(ClientProfile)
            .filter(ClientProfile.user_id == user_id)
            .first()
        )

    def exists_by_email(self, email: str) -> bool:
        """Checks if an active user exists with the given email."""
        return (
            self.db.query(User.id)
            .filter(User.email == email.strip().lower(), User.deleted_at.is_(None))
            .first()
            is not None
        )
