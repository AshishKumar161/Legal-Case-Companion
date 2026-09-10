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
    """Verifies an access JWT using the active Ed25519 public key (or prior key during rotation).

    Validates issuer, audience, pinned algorithm, and that the token type is ``"access"``.
    """
    # 1. Inspect unverified header to reject alg=none or wrong algorithms explicitly
    try:
        unverified_header = jwt.get_unverified_header(token)
    except Exception as e:
        raise jwt.InvalidTokenError(f"Malformed token header: {e}") from e

    token_alg = unverified_header.get("alg")
    if token_alg != settings.ALGORITHM:
        raise jwt.InvalidTokenError(
            f"Invalid JWT algorithm '{token_alg}'. Only '{settings.ALGORITHM}' is permitted."
        )

    # 2. Verify with primary active public key
    public_key = serialization.load_pem_public_key(settings.JWT_PUBLIC_KEY.encode())
    try:
        payload = jwt.decode(
            token,
            public_key,  # type: ignore[arg-type]
            algorithms=[settings.ALGORITHM],
            audience="legal-case-companion",
            issuer="legal-case-companion",
        )
    except (jwt.InvalidSignatureError, jwt.DecodeError) as sig_err:
        # 3. If signature verification failed, check against JWT_PREVIOUS_PUBLIC_KEY for zero-downtime rotation
        if settings.JWT_PREVIOUS_PUBLIC_KEY:
            prev_key = serialization.load_pem_public_key(
                settings.JWT_PREVIOUS_PUBLIC_KEY.encode()
            )
            payload = jwt.decode(
                token,
                prev_key,  # type: ignore[arg-type]
                algorithms=[settings.ALGORITHM],
                audience="legal-case-companion",
                issuer="legal-case-companion",
            )
        else:
            raise sig_err

    # 4. Validate token type to prevent confusion attacks
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


DISPOSABLE_EMAIL_DOMAINS = {
    "mailinator.com",
    "tempmail.com",
    "10minutemail.com",
    "guerrillamail.com",
    "throwawaymail.com",
    "yopmail.com",
    "trashmail.com",
    "sharklasers.com",
    "dispostable.com",
    "temp-mail.org",
    "fakeinbox.com",
    "getairmail.com",
    "maildrop.cc",
    "mohmal.com",
    "burnermail.io",
    "mytemp.email",
    "nada.ltd",
    "crazymailing.com",
}

COMMON_DOMAIN_TYPOS = {
    "gmai.com": "gmail.com",
    "gmaill.com": "gmail.com",
    "gamil.com": "gmail.com",
    "gmial.com": "gmail.com",
    "hotmial.com": "hotmail.com",
    "yaho.com": "yahoo.com",
    "outlok.com": "outlook.com",
}


def normalize_email(email: str, check_deliverability: bool | None = None) -> str:
    """Normalizes and validates an email address.

    Blocks disposable domains, detects provider typos, and performs MX domain
    deliverability lookup for real addresses.
    """
    clean_email = email.strip()
    if "@" not in clean_email:
        raise ValueError("Invalid email format: missing '@'")

    domain = clean_email.split("@")[-1].lower()

    # 1. Block disposable / temporary email services
    if domain in DISPOSABLE_EMAIL_DOMAINS:
        raise ValueError(
            "Disposable or temporary email addresses are not permitted. Please use a valid, permanent email address."
        )

    # 2. Check for common domain typos
    if domain in COMMON_DOMAIN_TYPOS:
        suggested = COMMON_DOMAIN_TYPOS[domain]
        raise ValueError(
            f"Invalid email domain '{domain}'. Did you mean '{suggested}'?"
        )

    # 3. Deliverability lookup
    if check_deliverability is None:
        if domain in ("example.com", "example.org", "test.com", "localhost") or not settings.EMAIL_CHECK_DELIVERABILITY:
            check_deliverability = False
        else:
            check_deliverability = True

    try:
        email_info = validate_email(clean_email, check_deliverability=check_deliverability)
        return email_info.normalized.lower()
    except EmailNotValidError as e:
        raise ValueError(str(e)) from e
