import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import AuthenticationError, ConflictError
from app.core.identifiers import generate_uuid7
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    normalize_email,
    verify_password,
)
from app.models.audit import AuditEvent
from app.models.auth import RefreshTokenSession, UserExternalIdentity
from app.models.user import AccountStatus, ClientProfile, User, UserRole
from app.schemas.auth import LoginRequest, PasswordChangeRequest
from app.services.user_service import UserService

logger = logging.getLogger(__name__)


class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.user_service = UserService(db)

    def log_audit_event(
        self,
        event_type: str,
        user_id: uuid.UUID | None = None,
        metadata: dict | None = None,
        action: str = "authenticate",
    ):
        """Create an audit event. Metadata must NEVER contain raw tokens or passwords."""
        event = AuditEvent(
            id=generate_uuid7(),
            event_type=event_type,
            entity_type="user" if user_id else "system",
            entity_id=user_id,
            action=action,
            actor_user_id=user_id,
            timestamp=datetime.now(UTC),
            metadata_=metadata or {},
        )
        self.db.add(event)

    def _create_user_session(
        self,
        user: User,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[str, str]:
        """Internal helper to create a refresh session and issue Ed25519 access + opaque refresh token."""
        access_token = create_access_token(str(user.id), user.role.value)
        refresh_token_raw = generate_refresh_token()
        refresh_token_hashed = hash_refresh_token(refresh_token_raw)

        family_id = generate_uuid7()
        now = datetime.now(UTC)

        session = RefreshTokenSession(
            id=generate_uuid7(),
            user_id=user.id,
            token_family_id=family_id,
            token_hash=refresh_token_hashed,
            created_at=now,
            last_used_at=now,
            expires_at=now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            revoked_at=None,
            device_metadata=user_agent,
            ip_metadata=ip_address,
        )
        self.db.add(session)
        return access_token, refresh_token_raw

    def login(
        self,
        login_request: LoginRequest,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[str, str]:
        """Returns access_token, unhashed_refresh_token"""
        user = self.user_service.get_user_by_email(login_request.email)

        if (
            not user
            or not user.password_hash
            or not verify_password(login_request.password, user.password_hash)
        ):
            if user:
                self.log_audit_event(
                    "LOGIN_FAILED",
                    user.id,
                    {"reason": "invalid_credentials", "ip": ip_address},
                    action="login",
                )
                self.db.commit()
            else:
                # Phase 11: Log auth failures even for unknown users (limited metadata, no user ID)
                logger.info(
                    f"Login attempt for non-existent email from IP {ip_address}"
                )
            raise AuthenticationError("Invalid authentication credentials")

        if user.account_status != AccountStatus.ACTIVE:
            raise AuthenticationError("Account is inactive")

        access_token, refresh_token_raw = self._create_user_session(
            user, ip_address=ip_address, user_agent=user_agent
        )

        self.log_audit_event(
            "LOGIN_SUCCESS",
            user.id,
            {"ip": ip_address, "method": "password"},
            action="login",
        )
        self.db.commit()

        return access_token, refresh_token_raw

    def authenticate_google_identity(
        self,
        claims: dict[str, Any],
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[User, str, str]:
        """Authenticates a user via verified Google OIDC claims.

        Performs:
          1. Provider subject lookup (provider="GOOGLE", provider_subject=claims["sub"])
          2. Existing user lookup by verified email (with safe auto-linking)
          3. New user registration with default role CLIENT and ClientProfile
          4. Refresh token session creation and audit event logging.

        Returns (user, access_token, refresh_token_raw).
        """
        provider_subject = str(claims["sub"]).strip()
        raw_email = str(claims["email"]).strip()
        email = normalize_email(raw_email)
        name = claims.get("name") or email.split("@")[0]
        picture = claims.get("picture")

        # 1. Check if identity already exists
        identity = (
            self.db.query(UserExternalIdentity)
            .filter(
                UserExternalIdentity.provider == "GOOGLE",
                UserExternalIdentity.provider_subject == provider_subject,
            )
            .first()
        )

        if identity:
            user = self.user_service.get_user_by_id(identity.user_id)
            if not user or user.deleted_at is not None:
                raise AuthenticationError("User account is deleted")
            if user.account_status != AccountStatus.ACTIVE:
                raise AuthenticationError("Account is inactive")

            access_token, refresh_token_raw = self._create_user_session(
                user, ip_address=ip_address, user_agent=user_agent
            )
            self.log_audit_event(
                "GOOGLE_LOGIN_SUCCESS",
                user.id,
                {"provider": "GOOGLE", "provider_subject": provider_subject, "ip": ip_address},
                action="login",
            )
            self.db.commit()
            return user, access_token, refresh_token_raw

        # 2. Check if a user with matching email already exists
        existing_user = self.user_service.get_user_by_email(email)
        if existing_user:
            if existing_user.account_status != AccountStatus.ACTIVE:
                raise AuthenticationError("Account is inactive")

            # Safe link: Google email is cryptographically verified
            new_identity = UserExternalIdentity(
                id=generate_uuid7(),
                user_id=existing_user.id,
                provider="GOOGLE",
                provider_subject=provider_subject,
                email=email,
                email_verified=True,
                provider_metadata={"name": name, "picture": picture},
            )
            self.db.add(new_identity)
            self.log_audit_event(
                "GOOGLE_IDENTITY_LINKED",
                existing_user.id,
                {"provider": "GOOGLE", "provider_subject": provider_subject, "ip": ip_address},
                action="link_identity",
            )

            access_token, refresh_token_raw = self._create_user_session(
                existing_user, ip_address=ip_address, user_agent=user_agent
            )
            self.log_audit_event(
                "GOOGLE_LOGIN_SUCCESS",
                existing_user.id,
                {"provider": "GOOGLE", "provider_subject": provider_subject, "ip": ip_address},
                action="login",
            )
            self.db.commit()
            return existing_user, access_token, refresh_token_raw

        # 3. Create new user with default role CLIENT
        new_user = User(
            id=generate_uuid7(),
            email=email,
            password_hash=None,
            role=UserRole.CLIENT,
            account_status=AccountStatus.ACTIVE,
        )
        self.db.add(new_user)
        self.db.flush()

        # Create ClientProfile
        client_profile = ClientProfile(
            id=generate_uuid7(),
            user_id=new_user.id,
            full_name=name,
        )
        self.db.add(client_profile)

        # Create UserExternalIdentity
        new_identity = UserExternalIdentity(
            id=generate_uuid7(),
            user_id=new_user.id,
            provider="GOOGLE",
            provider_subject=provider_subject,
            email=email,
            email_verified=True,
            provider_metadata={"name": name, "picture": picture},
        )
        self.db.add(new_identity)

        self.log_audit_event(
            "GOOGLE_IDENTITY_CREATED",
            new_user.id,
            {"provider": "GOOGLE", "provider_subject": provider_subject, "ip": ip_address},
            action="register",
        )

        access_token, refresh_token_raw = self._create_user_session(
            new_user, ip_address=ip_address, user_agent=user_agent
        )
        self.log_audit_event(
            "GOOGLE_LOGIN_SUCCESS",
            new_user.id,
            {"provider": "GOOGLE", "provider_subject": provider_subject, "ip": ip_address},
            action="login",
        )
        self.db.commit()

        return new_user, access_token, refresh_token_raw

    def link_google_identity(
        self,
        current_user_id: uuid.UUID,
        claims: dict[str, Any],
        ip_address: str | None = None,
    ) -> UserExternalIdentity:
        """Explicitly links a verified Google identity to an existing authenticated user."""
        provider_subject = str(claims["sub"]).strip()
        email = normalize_email(str(claims["email"]).strip())
        name = claims.get("name")
        picture = claims.get("picture")

        # Verify Google sub is not already linked to another user
        existing_identity = (
            self.db.query(UserExternalIdentity)
            .filter(
                UserExternalIdentity.provider == "GOOGLE",
                UserExternalIdentity.provider_subject == provider_subject,
            )
            .first()
        )
        if existing_identity:
            if existing_identity.user_id == current_user_id:
                return existing_identity
            raise ConflictError("Google account is already linked to another user")

        # Verify user does not already have a Google identity linked
        user_existing = (
            self.db.query(UserExternalIdentity)
            .filter(
                UserExternalIdentity.user_id == current_user_id,
                UserExternalIdentity.provider == "GOOGLE",
            )
            .first()
        )
        if user_existing:
            raise ConflictError("User already has a linked Google account")

        new_identity = UserExternalIdentity(
            id=generate_uuid7(),
            user_id=current_user_id,
            provider="GOOGLE",
            provider_subject=provider_subject,
            email=email,
            email_verified=True,
            provider_metadata={"name": name, "picture": picture},
        )
        self.db.add(new_identity)
        self.log_audit_event(
            "GOOGLE_IDENTITY_LINKED",
            current_user_id,
            {"provider": "GOOGLE", "provider_subject": provider_subject, "ip": ip_address},
            action="link_identity",
        )
        self.db.commit()
        return new_identity

    def unlink_google_identity(
        self,
        current_user_id: uuid.UUID,
        ip_address: str | None = None,
    ) -> None:
        """Unlinks Google identity from the current user.

        Requires that the user has a password set or another external identity.
        """
        user = self.user_service.get_user_by_id(current_user_id)
        if not user:
            raise AuthenticationError("User not found")

        identity = (
            self.db.query(UserExternalIdentity)
            .filter(
                UserExternalIdentity.user_id == current_user_id,
                UserExternalIdentity.provider == "GOOGLE",
            )
            .first()
        )
        if not identity:
            raise AuthenticationError("No linked Google account found")

        # Safety check: prevent account lockout
        other_identities_count = (
            self.db.query(UserExternalIdentity)
            .filter(
                UserExternalIdentity.user_id == current_user_id,
                UserExternalIdentity.id != identity.id,
            )
            .count()
        )
        if not user.password_hash and other_identities_count == 0:
            raise ConflictError(
                "Cannot unlink Google account without setting a password first"
            )

        self.db.delete(identity)
        self.log_audit_event(
            "GOOGLE_IDENTITY_UNLINKED",
            current_user_id,
            {"provider": "GOOGLE", "ip": ip_address},
            action="unlink_identity",
        )
        self.db.commit()

    def refresh(
        self, refresh_token_raw: str, ip_address: str | None = None
    ) -> tuple[str, str]:
        """Rotates token. Returns new access_token, new unhashed_refresh_token.

        Expiry semantics (per 04_AUTHORIZATION_SECURITY.md):
          - Absolute expiry: ``expires_at`` — hard deadline, cannot be extended.
          - Inactivity expiry: ``last_used_at`` + REFRESH_TOKEN_INACTIVITY_DAYS —
            session expires if not used within the inactivity window.
          - Token reuse: If a revoked token is presented, the entire family is
            revoked (replay / theft detection).
        """
        hashed_input = hash_refresh_token(refresh_token_raw)

        # Find session and lock it for update to prevent concurrent refresh race conditions
        session = (
            self.db.query(RefreshTokenSession)
            .filter(RefreshTokenSession.token_hash == hashed_input)
            .with_for_update()
            .first()
        )

        if not session:
            raise AuthenticationError("Invalid refresh token")

        now = datetime.now(UTC)

        # Token reuse detection
        if session.revoked_at is not None:
            # Revoke entire family — possible token theft
            self.db.query(RefreshTokenSession).filter(
                RefreshTokenSession.token_family_id == session.token_family_id,
                RefreshTokenSession.revoked_at == None,
            ).update({"revoked_at": now})

            self.log_audit_event(
                "SECURITY_EVENT",
                session.user_id,
                {
                    "event": "refresh_token_reuse_detected",
                    "family_id": str(session.token_family_id),
                    "ip": ip_address,
                },
                action="refresh",
            )
            self.db.commit()
            raise AuthenticationError("Invalid refresh token")

        # Absolute expiry check
        expires_at = (
            session.expires_at.replace(tzinfo=UTC)
            if session.expires_at.tzinfo is None
            else session.expires_at
        )
        if expires_at < now:
            session.revoked_at = now
            self.db.commit()
            raise AuthenticationError("Refresh token expired")

        # Phase 5 FIX: Inactivity TTL check uses last_used_at, NOT created_at.
        # last_used_at tracks when the token was last rotated/used, so a session
        # that is actively being used will not be expired by inactivity.
        last_used_at = (
            session.last_used_at.replace(tzinfo=UTC)
            if session.last_used_at.tzinfo is None
            else session.last_used_at
        )
        inactivity_limit = now - timedelta(days=settings.REFRESH_TOKEN_INACTIVITY_DAYS)
        if last_used_at < inactivity_limit:
            session.revoked_at = now
            self.db.commit()
            raise AuthenticationError("Refresh token expired due to inactivity")

        user = self.user_service.get_user_by_id(session.user_id)
        if not user or user.account_status != AccountStatus.ACTIVE:
            raise AuthenticationError("User is inactive or deleted")

        # Rotate: revoke the used token, issue new one in same family
        session.revoked_at = now

        new_refresh_token_raw = generate_refresh_token()
        new_refresh_token_hashed = hash_refresh_token(new_refresh_token_raw)
        new_access_token = create_access_token(str(user.id), user.role.value)

        new_session = RefreshTokenSession(
            id=generate_uuid7(),
            user_id=user.id,
            token_family_id=session.token_family_id,
            token_hash=new_refresh_token_hashed,
            created_at=now,
            last_used_at=now,
            expires_at=session.expires_at,  # Inherit absolute expiration
            revoked_at=None,
            ip_metadata=ip_address,
        )
        self.db.add(new_session)

        self.log_audit_event(
            "TOKEN_REFRESH",
            user.id,
            {"family_id": str(session.token_family_id), "ip": ip_address},
            action="refresh",
        )
        self.db.commit()

        return new_access_token, new_refresh_token_raw

    def logout(self, refresh_token_raw: str, user_id: uuid.UUID):
        """Revokes the current session"""
        if not refresh_token_raw:
            return

        hashed_input = hash_refresh_token(refresh_token_raw)
        session = (
            self.db.query(RefreshTokenSession)
            .filter(
                RefreshTokenSession.token_hash == hashed_input,
                RefreshTokenSession.user_id == user_id,
            )
            .first()
        )

        if session and session.revoked_at is None:
            session.revoked_at = datetime.now(UTC)
            self.log_audit_event(
                "LOGOUT",
                user_id,
                {"family_id": str(session.token_family_id)},
                action="logout",
            )
            self.db.commit()

    def change_password(self, user_id: uuid.UUID, req: PasswordChangeRequest):
        user = self.user_service.get_user_by_id(user_id)
        if not user or not verify_password(req.current_password, user.password_hash):
            raise AuthenticationError("Invalid current password")

        user.password_hash = hash_password(req.new_password)

        # Revoke all sessions on password change
        self.db.query(RefreshTokenSession).filter(
            RefreshTokenSession.user_id == user.id,
            RefreshTokenSession.revoked_at == None,
        ).update({"revoked_at": datetime.now(UTC)})

        self.log_audit_event(
            "PASSWORD_CHANGE",
            user_id,
            {"action": "password_changed_sessions_revoked"},
            action="password_change",
        )
        self.db.commit()
