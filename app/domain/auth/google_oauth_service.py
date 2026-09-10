"""Google OAuth 2.0 / OpenID Connect Service.

Handles authorization URL generation, authorization code exchange,
and cryptographic ID token verification using Google's public JWKS.
"""

import logging
import uuid
from typing import Any
from urllib.parse import urlencode

import httpx
import jwt
from jwt import PyJWKClient

from app.core.config import settings
from app.core.exceptions import AuthenticationError
from app.core.oauth_security import generate_oauth_state, validate_redirect_uri

logger = logging.getLogger(__name__)


class GoogleOAuthService:
    def __init__(
        self,
        jwks_client: PyJWKClient | None = None,
        http_client: httpx.Client | None = None,
    ):
        self._jwks_client = jwks_client
        self._http_client = http_client

    @property
    def jwks_client(self) -> PyJWKClient:
        if self._jwks_client is None:
            self._jwks_client = PyJWKClient(
                settings.GOOGLE_JWKS_URI,
                cache_keys=True,
                max_cached_keys=16,
                cache_jwk_set=True,
                lifespan=3600,
            )
        return self._jwks_client

    def get_authorization_url(
        self,
        return_url: str | None = None,
        purpose: str = "login",
        user_id: uuid.UUID | None = None,
        redirect_uri: str | None = None,
    ) -> tuple[str, str, str]:
        """Builds the Google OAuth 2.0 authorization URL with signed state and nonce.

        Returns (auth_url, state_token, nonce).
        """
        logger.info(
            "google_oauth.start: initiating Google OAuth authorization URL creation",
            extra={"purpose": purpose, "has_user_id": bool(user_id)},
        )

        client_id = settings.GOOGLE_CLIENT_ID
        if not client_id:
            logger.warning("google_oauth.error: GOOGLE_CLIENT_ID is not configured")
            raise AuthenticationError("Google OAuth is not configured")

        effective_redirect_uri = validate_redirect_uri(redirect_uri)

        state_token, nonce = generate_oauth_state(
            purpose=purpose,
            return_url=return_url,
            user_id=str(user_id) if user_id else None,
            redirect_uri=effective_redirect_uri,
        )

        params = {
            "client_id": client_id,
            "redirect_uri": effective_redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state_token,
            "nonce": nonce,
            "access_type": "offline",
            "prompt": "consent",
        }

        auth_url = f"{settings.GOOGLE_AUTH_URI}?{urlencode(params)}"
        logger.info(
            "google_oauth.authorization_url_created: authorization URL generated successfully",
            extra={"purpose": purpose, "redirect_uri": effective_redirect_uri},
        )
        return auth_url, state_token, nonce

    def exchange_code_for_tokens(
        self, code: str, redirect_uri: str | None = None
    ) -> dict[str, Any]:
        """Exchanges authorization code for tokens with Google's token endpoint."""
        client_id = settings.GOOGLE_CLIENT_ID
        client_secret = settings.GOOGLE_CLIENT_SECRET
        effective_redirect_uri = validate_redirect_uri(redirect_uri)

        if not client_id or not client_secret or not effective_redirect_uri:
            logger.warning("google_oauth.error: incomplete Google OAuth credentials for code exchange")
            raise AuthenticationError("Google OAuth credentials are not fully configured")

        logger.info(
            "google_oauth.code_exchange_started: exchanging code with Google token endpoint",
            extra={"redirect_uri": effective_redirect_uri},
        )

        payload = {
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": effective_redirect_uri,
            "grant_type": "authorization_code",
        }

        try:
            if self._http_client:
                response = self._http_client.post(
                    settings.GOOGLE_TOKEN_URI, data=payload, timeout=10.0
                )
            else:
                with httpx.Client(timeout=10.0) as client:
                    response = client.post(settings.GOOGLE_TOKEN_URI, data=payload)

            if response.status_code != 200:
                logger.warning(
                    f"google_oauth.code_exchange_failed: status {response.status_code}"
                )
                raise AuthenticationError("Failed to exchange code with Google")

            logger.info("google_oauth.code_exchange_success: successfully exchanged authorization code")
            return response.json()
        except httpx.RequestError as e:
            logger.error(f"google_oauth.network_error: during token exchange: {e}")
            raise AuthenticationError("Google identity provider unavailable") from e

    def validate_id_token(
        self,
        id_token: str,
        expected_nonce: str | None = None,
        override_public_key: Any = None,
    ) -> dict[str, Any]:
        """Cryptographically validates a Google OpenID Connect ID token.

        Validates signature against Google's JWKS, issuer, audience, expiry,
        subject, email, email_verified, and nonce.
        """
        if not id_token or not id_token.strip():
            raise AuthenticationError("Missing Google ID token")

        client_id = settings.GOOGLE_CLIENT_ID

        try:
            if override_public_key:
                signing_key_obj = override_public_key
            else:
                signing_key = self.jwks_client.get_signing_key_from_jwt(id_token)
                signing_key_obj = signing_key.key

            claims = jwt.decode(
                id_token,
                signing_key_obj,
                algorithms=["RS256"],
                audience=client_id if client_id else None,
                issuer=settings.GOOGLE_ISSUERS,
                options={
                    "verify_aud": bool(client_id),
                    "verify_iss": True,
                    "verify_exp": True,
                },
            )
        except jwt.ExpiredSignatureError as e:
            raise AuthenticationError("Google ID token has expired") from e
        except jwt.InvalidIssuerError as e:
            raise AuthenticationError("Invalid Google token issuer") from e
        except jwt.InvalidAudienceError as e:
            raise AuthenticationError("Invalid Google token audience") from e
        except Exception as e:
            logger.warning(f"Google ID token validation failed: {e}")
            raise AuthenticationError("Invalid Google ID token signature") from e

        # Validate subject claim
        sub = claims.get("sub")
        if not sub or not isinstance(sub, str) or not sub.strip():
            raise AuthenticationError("Google ID token missing valid subject identifier")

        # Validate email claim
        email = claims.get("email")
        if not email or not isinstance(email, str) or not email.strip():
            raise AuthenticationError("Google ID token missing email claim")

        # Validate email verification
        email_verified = claims.get("email_verified")
        if email_verified is not True:
            raise AuthenticationError(
                "Google account email is not verified. Unverified accounts cannot authenticate."
            )

        # Validate nonce if expected
        if expected_nonce:
            token_nonce = claims.get("nonce")
            if token_nonce != expected_nonce:
                raise AuthenticationError("OAuth nonce mismatch")

        logger.info(
            "google_oauth.id_token_verified: Google ID token validated cryptographically",
            extra={"email_verified": email_verified},
        )
        return claims
