"""
CSRF Protection — Double-Submit Cookie Pattern.

Per 04_AUTHORIZATION_SECURITY.md §5, the refresh endpoint must be protected
against CSRF attacks. This module implements:

1. **Double-submit cookie**: A CSRF token is set as a non-HttpOnly cookie
   (so JavaScript can read it) and must be sent back in the
   ``X-CSRF-Token`` request header.
2. **Origin / Referer validation**: The refresh endpoint validates that
   the ``Origin`` or ``Referer`` header matches allowed origins.
"""

import hmac
import secrets

from fastapi import Request, Response

from app.core.config import settings


def generate_csrf_token() -> str:
    """Generate a cryptographically secure CSRF token."""
    return secrets.token_urlsafe(32)


def set_csrf_cookie(response: Response, csrf_token: str) -> None:
    """Set the CSRF token as a non-HttpOnly cookie.

    The cookie is:
      - NOT HttpOnly → JavaScript can read it to include in headers.
      - Secure → Only sent over HTTPS (except in development).
      - SameSite=Strict → Never sent on cross-origin requests.
    """
    is_production = settings.ENVIRONMENT == "production"
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=False,  # JS must read this
        secure=is_production,
        samesite="strict",
        max_age=30 * 24 * 60 * 60,  # 30 days, aligned with refresh token
        path=f"{settings.API_V1_STR}/auth",
    )


def validate_csrf_token(request: Request) -> bool:
    """Validate the CSRF token from the double-submit cookie pattern.

    The cookie value (``csrf_token``) must match the header value
    (``X-CSRF-Token``). Both must be present and non-empty.

    Returns True if valid, raises ValueError otherwise.
    """
    cookie_token = request.cookies.get("csrf_token")
    header_token = request.headers.get("X-CSRF-Token")

    if not cookie_token or not header_token:
        raise ValueError("CSRF token missing")

    if not hmac.compare_digest(cookie_token, header_token):
        raise ValueError("CSRF token mismatch")

    return True


def validate_origin(request: Request) -> bool:
    """Validate the Origin or Referer header against allowed origins.

    Returns True if the origin is allowed, raises ValueError otherwise.
    Skips validation in development mode.
    """
    if settings.ENVIRONMENT != "production":
        return True

    origin = request.headers.get("Origin")
    referer = request.headers.get("Referer")

    allowed_origins = [str(o).rstrip("/") for o in settings.BACKEND_CORS_ORIGINS]

    if origin:
        if origin.rstrip("/") in allowed_origins:
            return True
        raise ValueError(f"Origin not allowed: {origin}")

    if referer:
        # Extract origin from referer (scheme + host)
        from urllib.parse import urlparse

        parsed = urlparse(referer)
        referer_origin = f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
        if referer_origin in allowed_origins:
            return True
        raise ValueError(f"Referer origin not allowed: {referer_origin}")

    raise ValueError("Neither Origin nor Referer header present")
