"""Auth & Identity Domain package."""

from typing import Any

__all__ = ["AuthService", "GoogleOAuthService", "SessionCleanupService"]


def __getattr__(name: str) -> Any:
    if name == "AuthService":
        from app.domain.auth.auth_service import AuthService

        return AuthService
    if name == "GoogleOAuthService":
        from app.domain.auth.google_oauth_service import GoogleOAuthService

        return GoogleOAuthService
    if name == "SessionCleanupService":
        from app.domain.auth.session_cleanup_service import SessionCleanupService

        return SessionCleanupService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
