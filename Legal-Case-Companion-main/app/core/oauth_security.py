"""OAuth 2.0 / OpenID Connect Security Helpers.

Provides cryptographically signed OAuth state tokens, nonce generation,
and strict open-redirect validation.
"""

import logging
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlparse

import jwt
from cryptography.hazmat.primitives import serialization

from app.core.config import settings
from app.core.exceptions import AuthenticationError

logger = logging.getLogger(__name__)


def generate_nonce() -> str:
    """Generates a cryptographically secure random nonce."""
    return secrets.token_urlsafe(32)


def validate_return_url(return_url: str | None) -> str:
    """Validates that a return URL is either a safe relative path or belongs to allowed origins.

    Prevents open redirect attacks. Returns a safe fallback ("/dashboard") if invalid.
    """
    default_url = "/dashboard"
    if not return_url or not return_url.strip():
        return default_url

    clean_url = return_url.strip()

    # Reject protocol-relative URLs (e.g. //attacker.com) and javascript: schemes
    if clean_url.startswith(("//", "\\\\")):
        return default_url

    parsed = urlparse(clean_url)

    # Relative paths starting with / (e.g. /cases/123, /dashboard)
    if not parsed.netloc and parsed.path.startswith("/"):
        return clean_url

    # Absolute URLs: check scheme and allowed origins
    if parsed.scheme in ("http", "https"):
        origin = f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
        allowed = [str(o).rstrip("/") for o in settings.GOOGLE_ALLOWED_REDIRECT_ORIGINS]
        if origin in allowed:
            return clean_url

    return default_url


def generate_oauth_state(
    purpose: str = "login",
    return_url: str | None = None,
    user_id: str | None = None,
    nonce: str | None = None,
) -> tuple[str, str]:
    """Generates a signed OAuth state token and nonce.

    The state token is short-lived (10 minutes) and signed with Ed25519.
    """
    if not nonce:
        nonce = generate_nonce()

    safe_return_url = validate_return_url(return_url)
    now = datetime.now(UTC)
    expire = now + timedelta(minutes=10)

    payload: dict[str, Any] = {
        "iss": "legal-case-companion",
        "aud": "lcc_oauth_state",
        "iat": now,
        "exp": expire,
        "jti": secrets.token_urlsafe(16),
        "purpose": purpose,
        "nonce": nonce,
        "return_url": safe_return_url,
    }
    if user_id:
        payload["user_id"] = str(user_id)

    private_key = serialization.load_pem_private_key(
        settings.JWT_PRIVATE_KEY.encode(), password=None
    )
    state_token = jwt.encode(payload, private_key, algorithm=settings.ALGORITHM)  # type: ignore[arg-type]

    return state_token, nonce


def verify_oauth_state(state_token: str) -> dict[str, Any]:
    """Verifies and decodes an OAuth state token.

    Raises AuthenticationError if invalid, tampered, or expired.
    """
    if not state_token:
        raise AuthenticationError("OAuth state parameter missing")

    try:
        public_key = serialization.load_pem_public_key(
            settings.JWT_PUBLIC_KEY.encode()
        )
        payload = jwt.decode(
            state_token,
            public_key,  # type: ignore[arg-type]
            algorithms=[settings.ALGORITHM],
            audience="lcc_oauth_state",
            issuer="legal-case-companion",
        )
        return payload
    except jwt.ExpiredSignatureError as e:
        raise AuthenticationError("OAuth state has expired. Please try again.") from e
    except jwt.InvalidTokenError as e:
        raise AuthenticationError("Invalid OAuth state parameter") from e
