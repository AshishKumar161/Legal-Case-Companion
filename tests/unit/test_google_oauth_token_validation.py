import datetime
from unittest.mock import patch
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.core.config import settings
from app.core.exceptions import AuthenticationError
from app.domain.auth.google_oauth_service import GoogleOAuthService


@pytest.fixture
def rsa_keys():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    return private_key, public_key


def make_token(
    private_key,
    sub="sub-123",
    email="test@example.com",
    email_verified=True,
    exp_offset_seconds=300,
    iss="https://accounts.google.com",
    aud="test-client-id",
    nonce=None,
):
    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        "iss": iss,
        "aud": aud,
        "sub": sub,
        "email": email,
        "email_verified": email_verified,
        "iat": int(now.timestamp()),
        "exp": int((now + datetime.timedelta(seconds=exp_offset_seconds)).timestamp()),
    }
    if nonce:
        payload["nonce"] = nonce
    return jwt.encode(payload, private_key, algorithm="RS256")


def test_valid_google_token_accepted(rsa_keys):
    priv, pub = rsa_keys
    token = make_token(priv, aud="my-google-app")
    service = GoogleOAuthService()
    with patch.object(settings, "GOOGLE_CLIENT_ID", "my-google-app"):
        claims = service.validate_id_token(token, override_public_key=pub)
    assert claims["sub"] == "sub-123"
    assert claims["email"] == "test@example.com"


def test_token_expired_by_one_second_rejected(rsa_keys):
    priv, pub = rsa_keys
    token = make_token(priv, aud="my-google-app", exp_offset_seconds=-1)
    service = GoogleOAuthService()
    with patch.object(settings, "GOOGLE_CLIENT_ID", "my-google-app"):
        with pytest.raises(AuthenticationError) as exc_info:
            service.validate_id_token(token, override_public_key=pub)
    assert "expired" in str(exc_info.value).lower()


def test_token_expired_by_ten_seconds_rejected(rsa_keys):
    priv, pub = rsa_keys
    token = make_token(priv, aud="my-google-app", exp_offset_seconds=-10)
    service = GoogleOAuthService()
    with patch.object(settings, "GOOGLE_CLIENT_ID", "my-google-app"):
        with pytest.raises(AuthenticationError) as exc_info:
            service.validate_id_token(token, override_public_key=pub)
    assert "expired" in str(exc_info.value).lower()


def test_token_invalid_signature_rejected(rsa_keys):
    priv, pub = rsa_keys
    other_priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = make_token(other_priv, aud="my-google-app")
    service = GoogleOAuthService()
    with patch.object(settings, "GOOGLE_CLIENT_ID", "my-google-app"):
        with pytest.raises(AuthenticationError) as exc_info:
            service.validate_id_token(token, override_public_key=pub)
    assert "signature" in str(exc_info.value).lower() or "invalid" in str(exc_info.value).lower()


def test_token_wrong_audience_rejected(rsa_keys):
    priv, pub = rsa_keys
    token = make_token(priv, aud="attacker-client-id")
    service = GoogleOAuthService()
    with patch.object(settings, "GOOGLE_CLIENT_ID", "my-google-app"):
        with pytest.raises(AuthenticationError) as exc_info:
            service.validate_id_token(token, override_public_key=pub)
    assert "audience" in str(exc_info.value).lower()


def test_token_wrong_issuer_rejected(rsa_keys):
    priv, pub = rsa_keys
    token = make_token(priv, aud="my-google-app", iss="https://untrusted-idp.com")
    service = GoogleOAuthService()
    with patch.object(settings, "GOOGLE_CLIENT_ID", "my-google-app"):
        with pytest.raises(AuthenticationError) as exc_info:
            service.validate_id_token(token, override_public_key=pub)
    assert "issuer" in str(exc_info.value).lower()


def test_token_malformed_rejected(rsa_keys):
    _, pub = rsa_keys
    service = GoogleOAuthService()
    with patch.object(settings, "GOOGLE_CLIENT_ID", "my-google-app"):
        with pytest.raises(AuthenticationError) as exc_info:
            service.validate_id_token("not-a-valid.jwt-token", override_public_key=pub)
    assert "malformed" in str(exc_info.value).lower() or "invalid" in str(exc_info.value).lower()


def test_token_nonce_validation(rsa_keys):
    priv, pub = rsa_keys
    token = make_token(priv, aud="my-google-app", nonce="valid-nonce-123")
    service = GoogleOAuthService()
    with patch.object(settings, "GOOGLE_CLIENT_ID", "my-google-app"):
        # Match nonce succeeds
        claims = service.validate_id_token(token, expected_nonce="valid-nonce-123", override_public_key=pub)
        assert claims["nonce"] == "valid-nonce-123"

        # Mismatch nonce fails
        with pytest.raises(AuthenticationError) as exc_info:
            service.validate_id_token(token, expected_nonce="wrong-nonce", override_public_key=pub)
        assert "nonce" in str(exc_info.value).lower()


def test_missing_google_client_id_fails_closed(rsa_keys):
    priv, pub = rsa_keys
    token = make_token(priv, aud="my-google-app")
    service = GoogleOAuthService()
    # When GOOGLE_CLIENT_ID is None or empty, must fail closed
    with patch.object(settings, "GOOGLE_CLIENT_ID", None):
        with pytest.raises(AuthenticationError) as exc_info:
            service.validate_id_token(token, override_public_key=pub)
        assert "missing" in str(exc_info.value).lower() or "not configured" in str(exc_info.value).lower()

    with patch.object(settings, "GOOGLE_CLIENT_ID", "   "):
        with pytest.raises(AuthenticationError) as exc_info:
            service.validate_id_token(token, override_public_key=pub)
        assert "missing" in str(exc_info.value).lower() or "not configured" in str(exc_info.value).lower()

