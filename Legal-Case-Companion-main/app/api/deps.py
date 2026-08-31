import uuid

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.exceptions import AuthenticationError, AuthorizationError
from app.core.security import verify_access_token
from app.db.database import get_db
from app.models.user import AccountStatus, User
from app.services.user_service import UserService

security = HTTPBearer()


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    token = credentials.credentials
    try:
        payload = verify_access_token(token)
        user_id_str = payload.get("sub")
        if not user_id_str:
            raise AuthenticationError("Token missing subject claim")
    except jwt.ExpiredSignatureError as e:
        raise AuthenticationError("Access token has expired") from e
    except jwt.PyJWTError as e:
        raise AuthenticationError("Could not validate credentials") from e

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError as e:
        raise AuthenticationError("Invalid user ID in token") from e

    user_service = UserService(db)
    user = user_service.get_user_by_id(user_id)

    if not user:
        raise AuthenticationError("User not found")

    # Phase 4: Compare against enum, not string
    if user.account_status != AccountStatus.ACTIVE:
        raise AuthenticationError("User is inactive")

    return user


class RequireRole:
    """Dependency that checks the current user has one of the allowed roles.

    Accepts both ``UserRole`` enum members and plain strings for
    backward compatibility.
    """

    def __init__(self, allowed_roles: list):
        self.allowed_roles = allowed_roles

    def __call__(self, current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in self.allowed_roles:
            raise AuthorizationError("Not authorized to access this resource")
        return current_user
