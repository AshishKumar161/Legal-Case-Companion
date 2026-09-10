"""Users & Administration Domain package."""

from typing import Any

__all__ = [
    "AdminService",
    "LifecycleService",
    "OperatorService",
    "ProfileService",
    "SupportService",
    "UserService",
]


def __getattr__(name: str) -> Any:
    if name == "AdminService":
        from app.domain.users.admin_service import AdminService

        return AdminService
    if name == "LifecycleService":
        from app.domain.users.lifecycle_service import LifecycleService

        return LifecycleService
    if name == "OperatorService":
        from app.domain.users.operator_service import OperatorService

        return OperatorService
    if name == "ProfileService":
        from app.domain.users.profile_service import ProfileService

        return ProfileService
    if name == "SupportService":
        from app.domain.users.support_service import SupportService

        return SupportService
    if name == "UserService":
        from app.domain.users.user_service import UserService

        return UserService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
