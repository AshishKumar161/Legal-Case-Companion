import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from cryptography.hazmat.primitives import serialization
from email_validator import EmailNotValidError, validate_email

from app.core.config import settings

ph = PasswordHasher()


def hash_password(password: str) -> str:
    """Hashes a password using Argon2id."""
    return ph.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a password against an Argon2id hash."""
    try:
        return ph.verify(hashed_password, plain_password)
    except VerifyMismatchError:
        return False


def create_access_token(subject: str, role: str) -> str:
    """Creates a short-lived access JWT signed with Ed25519.

    Claims include a ``type`` field set to ``"access"`` to prevent token
    confusion attacks (Phase 4 hardening).
    """
    expire = datetime.now(UTC) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode: dict[str, Any] = {
        "sub": subject,
        "iss": "legal-case-companion",
        "aud": "legal-case-companion",
        "exp": expire,
        "iat": datetime.now(UTC),
        "jti": secrets.token_urlsafe(16),
        "role": role,
        "type": "access",
    }

    private_key = serialization.load_pem_private_key(
        settings.JWT_PRIVATE_KEY.encode(), password=None
    )

    encoded_jwt = jwt.encode(to_encode, private_key, algorithm=settings.ALGORITHM)  # type: ignore[arg-type]
    return encoded_jwt


def verify_access_token(token: str) -> dict[str, Any]:
    """Verifies an access JWT using the Ed25519 public key.

    Validates issuer, audience, and that the token type is ``"access"``.
    """
    public_key = serialization.load_pem_public_key(settings.JWT_PUBLIC_KEY.encode())
    payload = jwt.decode(
        token,
        public_key,  # type: ignore[arg-type]
        algorithms=[settings.ALGORITHM],
        audience="legal-case-companion",
        issuer="legal-case-companion",
    )

    # Phase 4: Validate token type to prevent confusion attacks
    token_type = payload.get("type")
    if token_type != "access":
        raise jwt.InvalidTokenError("Invalid token type")

    return payload


def generate_refresh_token() -> str:
    """Generates a cryptographically secure opaque refresh token."""
    return secrets.token_urlsafe(32)


def hash_refresh_token(token: str) -> str:
    """Hashes the refresh token for secure database storage using SHA-256."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def normalize_email(email: str) -> str:
    """Normalizes and validates an email address."""
    try:
        email_info = validate_email(email.strip(), check_deliverability=False)
        return email_info.normalized.lower()
    except EmailNotValidError as e:
        raise ValueError(str(e)) from e
