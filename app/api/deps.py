import uuid
from typing import Any

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.exceptions import AuthenticationError, AuthorizationError
from app.core.security import verify_access_token
from app.db.database import get_db
from app.models.operator import OperationalPermission
from app.models.user import AccountStatus, User
from app.domain.users.user_service import UserService

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

    # Phase 4 & Phase 14: Active, verified, and onboarding registered accounts are permitted
    if user.account_status not in (AccountStatus.ACTIVE, AccountStatus.VERIFIED, AccountStatus.REGISTERED):
        raise AuthenticationError("User is inactive")

    return user


optional_security = HTTPBearer(auto_error=False)


def get_optional_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(optional_security),
    db: Session = Depends(get_db),
) -> User | None:
    """Extract authenticated user if bearer token is present and valid; returns None otherwise."""
    if not credentials or not credentials.credentials:
        return None
    token = credentials.credentials
    try:
        payload = verify_access_token(token)
        user_id_str = payload.get("sub")
        if not user_id_str:
            return None
        user_id = uuid.UUID(user_id_str)
        user_service = UserService(db)
        user = user_service.get_user_by_id(user_id)
        if not user or user.account_status != AccountStatus.ACTIVE:
            return None
        return user
    except Exception:
        return None


def get_current_admin_user(current_user: User = Depends(get_current_user)) -> User:
    from app.models.user import UserRole

    if current_user.role != UserRole.ADMIN:
        raise AuthorizationError("Admin access required")
    return current_user


class RequireRole:
    """Dependency that checks the current user has one of the allowed roles.

    Accepts both ``UserRole`` enum members, lists/tuples of roles, and plain strings for
    backward compatibility.
    """

    def __init__(self, allowed_roles: Any):
        if isinstance(allowed_roles, (list, tuple, set)):
            self.allowed_roles = list(allowed_roles)
        else:
            self.allowed_roles = [allowed_roles]

    def __call__(self, current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in self.allowed_roles:
            raise AuthorizationError("Not authorized to access this resource")
        return current_user


class RequireOperatorPermission:
    """Dependency enforcing fine-grained operational permissions under the least-privilege principle.

    Requires the caller to be an active User with UserRole.ADMIN AND hold the specific
    operational permission in UserOperatorPermission (unless SYSTEM_OPERATIONS super-privilege applies).
    """

    def __init__(self, permission: "OperationalPermission"):
        self.permission = permission

    def __call__(
        self,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        from app.core.config import settings
        from app.models.operator import OperationalPermission, UserOperatorPermission
        from app.models.user import UserRole

        if current_user.role != UserRole.ADMIN:
            raise AuthorizationError("Admin access required")

        # 1. Check explicit active permission grant
        has_perm = (
            db.query(UserOperatorPermission)
            .filter(
                UserOperatorPermission.user_id == current_user.id,
                UserOperatorPermission.permission == self.permission,
                UserOperatorPermission.revoked_at.is_(None),
            )
            .first()
        )
        if has_perm:
            return current_user

        # 2. Check if user holds SYSTEM_OPERATIONS acting as global system administrator
        is_super = (
            db.query(UserOperatorPermission)
            .filter(
                UserOperatorPermission.user_id == current_user.id,
                UserOperatorPermission.permission == OperationalPermission.SYSTEM_OPERATIONS,
                UserOperatorPermission.revoked_at.is_(None),
            )
            .first()
        )
        if is_super:
            return current_user

        # 3. If user has any permissions assigned, they are restricted to those assigned
        any_perm = (
            db.query(UserOperatorPermission)
            .filter(
                UserOperatorPermission.user_id == current_user.id,
            )
            .first()
        )
        if any_perm:
            raise AuthorizationError(
                f"Missing required operational permission: {self.permission.value}"
            )

        # 4. In staging/production, explicit permissions are strictly required
        if settings.ENVIRONMENT in ("staging", "production"):
            raise AuthorizationError(
                f"Missing required operational permission: {self.permission.value}"
            )

        return current_user


require_authenticated_user = get_current_user
require_role = RequireRole
require_operator_permission = RequireOperatorPermission


def require_case_access(
    case_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """FastAPI dependency to authorize and return a Case the current user can access."""
    from app.core.authorization import authorize_case_access

    return authorize_case_access(db, current_user, case_id)


def require_case_modification(
    case_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """FastAPI dependency to authorize and return a Case the current user can modify (non-viewers)."""
    from app.core.authorization import authorize_case_modification

    return authorize_case_modification(db, current_user, case_id)


def require_case_owner(
    case_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """FastAPI dependency to authorize and return a Case where current user is Owner or Admin."""
    from app.core.authorization import authorize_participant_management

    return authorize_participant_management(db, current_user, case_id)


def require_consultation_access(
    consultation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """FastAPI dependency to authorize and return a Consultation the current user participates in."""
    from app.core.authorization import authorize_consultation_access

    return authorize_consultation_access(db, current_user, consultation_id)


def require_document_access(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """FastAPI dependency to authorize and return a Document the current user can access."""
    from app.core.authorization import authorize_document_access

    return authorize_document_access(db, current_user, document_id)


def require_evidence_access(
    evidence_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """FastAPI dependency to authorize access to an Evidence Locker item."""
    from app.core.authorization import authorize_evidence_access

    evidence, _ = authorize_evidence_access(db, current_user, evidence_id, required_level="VIEW")
    return evidence


def require_evidence_management(
    evidence_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """FastAPI dependency to authorize management privileges on an Evidence Locker item."""
    from app.core.authorization import authorize_evidence_management

    return authorize_evidence_management(db, current_user, evidence_id)

