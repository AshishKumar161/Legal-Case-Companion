import logging

from datetime import UTC, datetime

from fastapi import APIRouter, Cookie, Depends, Request, Response, status
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.csrf import (
    generate_csrf_token,
    set_csrf_cookie,
    validate_csrf_token,
    validate_origin,
)
from app.core.exceptions import AppException, AuthenticationError, ValidationError
from app.core.security import verify_password
from app.core.oauth_security import verify_oauth_state
from app.db.database import get_db
from app.models.user import ClientProfile, LawyerProfile, User, UserRole
from app.schemas.auth import (
    EmailOTPVerifyRequest,
    EmailVerificationConfirm,
    EmailVerificationRequest,
    EmailVerificationResponse,
    ExternalIdentityResponse,
    GoogleAuthUrlResponse,
    GoogleCallbackRequest,
    GoogleDirectAuthRequest,
    GoogleLinkRequest,
    LoginRequest,
    LogoutRequest,
    PasswordChangeRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    PasswordResetResponse,
    RefreshRequest,
    Token,
)
from app.schemas.user import CurrentUserResponse, UserCreate, UserResponse
from app.services.auth_service import AuthService
from app.services.google_oauth_service import GoogleOAuthService
from app.services.user_service import UserService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])
_rate_limit_storage_uri = (
    settings.REDIS_URL
    if settings.REDIS_URL and settings.ENVIRONMENT.lower() == "production"
    else "memory://"
)
limiter = Limiter(key_func=get_remote_address, storage_uri=_rate_limit_storage_uri)


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    is_production = settings.ENVIRONMENT == "production"
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=is_production,
        samesite="strict" if is_production else "lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        path=f"{settings.API_V1_STR}/auth",
    )


def _validate_pilot_registration(db: Session, user_in: UserCreate) -> None:
    # Phase XX: Check if onboarding is restricted to invite-only participants
    if getattr(settings, "ONBOARDING_MODE", "CONTROLLED") == "INVITE_ONLY":
        from app.models.pilot import AllowlistStatus, PilotAllowlistEntry

        normalized_email = user_in.email.strip().lower()
        domain = normalized_email.split("@")[-1] if "@" in normalized_email else ""
        entry = (
            db.query(PilotAllowlistEntry)
            .filter(
                PilotAllowlistEntry.status == AllowlistStatus.ACTIVE,
                (
                    (PilotAllowlistEntry.identifier == normalized_email)
                    | (PilotAllowlistEntry.identifier == domain)
                ),
            )
            .first()
        )
        if not entry:
            raise AppException(
                status_code=status.HTTP_403_FORBIDDEN,
                code="INVITE_ONLY_REGISTRATION",
                message="Registration is currently restricted to invited participants.",
            )

    if not settings.PILOT_MODE:
        return

    # 1. Signups allowed check
    if not settings.PILOT_SIGNUP_ENABLED:
        raise AppException(
            status_code=status.HTTP_403_FORBIDDEN,
            code="PILOT_SIGNUP_DISABLED",
            message="New user signups are paused during this pilot phase.",
        )

    # 2. Pilot Timeframe check
    now = datetime.now(UTC)
    if settings.PILOT_START_TIME:
        start_time = settings.PILOT_START_TIME
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=UTC)
        if now < start_time:
            raise AppException(
                status_code=status.HTTP_403_FORBIDDEN,
                code="PILOT_NOT_STARTED",
                message="The pilot phase has not started yet.",
            )
    if settings.PILOT_END_TIME:
        end_time = settings.PILOT_END_TIME
        if end_time.tzinfo is None:
            end_time = end_time.replace(tzinfo=UTC)
        if now > end_time:
            raise AppException(
                status_code=status.HTTP_403_FORBIDDEN,
                code="PILOT_CONCLUDED",
                message="The pilot phase has ended.",
            )

    # 3. Capacity checks
    if user_in.role == UserRole.CLIENT:
        active_clients = (
            db.query(func.count(User.id))
            .filter(User.role == UserRole.CLIENT, User.deleted_at.is_(None))
            .scalar()
            or 0
        )
        if active_clients >= settings.PILOT_MAX_CLIENTS:
            raise AppException(
                status_code=status.HTTP_403_FORBIDDEN,
                code="PILOT_CAPACITY_REACHED",
                message="Pilot client capacity has been reached.",
            )
    elif user_in.role == UserRole.LAWYER:
        active_lawyers = (
            db.query(func.count(User.id))
            .filter(User.role == UserRole.LAWYER, User.deleted_at.is_(None))
            .scalar()
            or 0
        )
        if active_lawyers >= settings.PILOT_MAX_LAWYERS:
            raise AppException(
                status_code=status.HTTP_403_FORBIDDEN,
                code="PILOT_CAPACITY_REACHED",
                message="Pilot lawyer capacity has been reached.",
            )

    # 4. Allowlist checks
    if settings.PILOT_ALLOWLIST_ENABLED:
        from app.models.pilot import AllowlistStatus, PilotAllowlistEntry

        normalized_email = user_in.email.strip().lower()
        domain = normalized_email.split("@")[-1] if "@" in normalized_email else ""

        entry = (
            db.query(PilotAllowlistEntry)
            .filter(
                PilotAllowlistEntry.status == AllowlistStatus.ACTIVE,
                (
                    (PilotAllowlistEntry.identifier == normalized_email)
                    | (PilotAllowlistEntry.identifier == domain)
                ),
            )
            .first()
        )
        if not entry:
            raise AppException(
                status_code=status.HTTP_403_FORBIDDEN,
                code="PILOT_NOT_ALLOWLISTED",
                message="This email address is not approved for the production pilot.",
            )
        if entry.valid_until:
            valid_until = entry.valid_until
            if valid_until.tzinfo is None:
                valid_until = valid_until.replace(tzinfo=UTC)
            if now > valid_until:
                raise AppException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    code="PILOT_ALLOWLIST_EXPIRED",
                    message="Pilot allowlist approval for this user has expired.",
                )
        if entry.role_target and entry.role_target != user_in.role:
            raise AppException(
                status_code=status.HTTP_403_FORBIDDEN,
                code="PILOT_ROLE_MISMATCH",
                message=f"Allowlist entry is restricted to role {entry.role_target.value}.",
            )


@router.post(
    "/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
@limiter.limit("5/minute")
def register(request: Request, user_in: UserCreate, db: Session = Depends(get_db)):
    _validate_pilot_registration(db, user_in)
    user_service = UserService(db)
    user = user_service.register_user(user_in)

    auth_service = AuthService(db)
    ip_address = request.client.host if request.client else None
    try:
        auth_service.request_email_verification(user.email, ip_address=ip_address)
    except Exception as e:
        logger.warning(f"Failed to dispatch initial verification email: {e}")

    return user


@router.post("/login", response_model=Token)
@limiter.limit("15/minute")
def login(
    request: Request,
    response: Response,
    login_req: LoginRequest,
    db: Session = Depends(get_db),
):
    auth_service = AuthService(db)
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    access_token, refresh_token = auth_service.login(login_req, ip_address, user_agent)

    _set_refresh_cookie(response, refresh_token)

    # Phase 6: Issue CSRF token on login
    csrf_token = generate_csrf_token()
    set_csrf_cookie(response, csrf_token)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "refresh_token": refresh_token,
    }


@router.post("/refresh", response_model=Token)
@limiter.limit("20/minute")
def refresh(
    request: Request,
    response: Response,
    body: RefreshRequest | None = None,
    refresh_token: str = Cookie(None),
    db: Session = Depends(get_db),
):
    active_refresh = (body.refresh_token if body and body.refresh_token else None) or refresh_token
    if not active_refresh:
        raise AuthenticationError("Refresh token missing")

    # Phase 6: Validate CSRF token and Origin on the refresh endpoint
    try:
        validate_csrf_token(request)
        validate_origin(request)
    except ValueError as e:
        logger.warning(f"CSRF validation failed: {e}")
        raise AuthenticationError("CSRF validation failed") from e

    auth_service = AuthService(db)
    ip_address = request.client.host if request.client else None

    new_access, new_refresh = auth_service.refresh(active_refresh, ip_address)

    _set_refresh_cookie(response, new_refresh)

    # Re-issue CSRF token on rotation
    csrf_token = generate_csrf_token()
    set_csrf_cookie(response, csrf_token)

    return {
        "access_token": new_access,
        "token_type": "bearer",
        "refresh_token": new_refresh,
    }


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    body: LogoutRequest | None = None,
    refresh_token: str = Cookie(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    active_refresh = (body.refresh_token if body and body.refresh_token else None) or refresh_token
    auth_service = AuthService(db)
    if active_refresh:
        auth_service.logout(active_refresh, current_user.id)

    response.delete_cookie(key="refresh_token", path=f"{settings.API_V1_STR}/auth")
    response.delete_cookie(key="csrf_token", path="/")
    response.delete_cookie(key="csrf_token", path=f"{settings.API_V1_STR}/auth")
    return {"detail": "Logged out successfully"}


@router.get("/me", response_model=CurrentUserResponse)
def get_current_user_identity(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Authoritative current user identity and profile details."""
    full_name = None
    location = None
    if current_user.role == UserRole.CLIENT:
        client_profile = (
            db.query(ClientProfile).filter(ClientProfile.user_id == current_user.id).first()
        )
        if client_profile:
            full_name = client_profile.full_name
            location = client_profile.location
    elif current_user.role == UserRole.LAWYER:
        lawyer_profile = (
            db.query(LawyerProfile).filter(LawyerProfile.user_id == current_user.id).first()
        )
        if lawyer_profile:
            full_name = lawyer_profile.full_name
            location = lawyer_profile.location
    elif current_user.role == UserRole.ADMIN:
        full_name = "System Administrator"

    return CurrentUserResponse(
        id=current_user.id,
        email=current_user.email,
        account_status=(
            current_user.account_status.value
            if hasattr(current_user.account_status, "value")
            else str(current_user.account_status)
        ),
        role=(
            current_user.role.value
            if hasattr(current_user.role, "value")
            else str(current_user.role)
        ),
        full_name=full_name,
        location=location,
    )


@router.post("/password/change")
@limiter.limit("5/minute")
def change_password(
    request: Request,
    req: PasswordChangeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    auth_service = AuthService(db)
    auth_service.change_password(current_user.id, req)
    return {"detail": "Password changed successfully"}


@router.post("/password/reset/request", response_model=PasswordResetResponse)
@router.post("/forgot-password", response_model=PasswordResetResponse)
@limiter.limit("5/minute")
def request_password_reset(
    request: Request,
    req: PasswordResetRequest,
    db: Session = Depends(get_db),
):
    """Requests a password reset link with anti-enumeration defense.

    Returns an identical success message whether or not the email address exists.
    """
    auth_service = AuthService(db)
    ip_address = request.client.host if request.client else None
    auth_service.request_password_reset(req.email, ip_address=ip_address)
    return {
        "detail": "If an account exists with this email address, a password reset link has been dispatched."
    }


@router.post("/password/reset/confirm", response_model=PasswordResetResponse)
@router.post("/reset-password", response_model=PasswordResetResponse)
@limiter.limit("5/minute")
def confirm_password_reset(
    request: Request,
    req: PasswordResetConfirm,
    db: Session = Depends(get_db),
):
    """Validates the reset token, updates password, and revokes all active sessions."""
    auth_service = AuthService(db)
    ip_address = request.client.host if request.client else None
    auth_service.confirm_password_reset(
        token=req.token,
        new_password=req.new_password,
        ip_address=ip_address,
    )
    return {
        "detail": "Password has been successfully reset. Please log in with your new credentials."
    }


@router.post("/email/verify/request", response_model=EmailVerificationResponse)
@limiter.limit("5/minute")
def request_email_verification(
    request: Request,
    req: EmailVerificationRequest,
    db: Session = Depends(get_db),
):
    """Requests an email verification token with anti-enumeration protection."""
    auth_service = AuthService(db)
    ip_address = request.client.host if request.client else None
    auth_service.request_email_verification(req.email, ip_address=ip_address)
    return {
        "detail": "If an account exists with this email address, a verification link has been dispatched."
    }


@router.post("/email/verify/confirm", response_model=EmailVerificationResponse)
@limiter.limit("10/minute")
def confirm_email_verification(
    request: Request,
    req: EmailVerificationConfirm,
    db: Session = Depends(get_db),
):
    """Confirms email verification token."""
    auth_service = AuthService(db)
    auth_service.confirm_email_verification(req.token)
    return {"detail": "Email address has been successfully verified."}


@router.post("/email/verify/otp", response_model=Token)
@limiter.limit("10/minute")
def verify_email_otp(
    request: Request,
    response: Response,
    req: EmailOTPVerifyRequest,
    db: Session = Depends(get_db),
):
    """Validates 6-digit email OTP, sets session cookies, and returns access token for immediate login."""
    auth_service = AuthService(db)
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    user, access_token, refresh_token = auth_service.verify_email_otp(
        email=req.email,
        otp=req.otp,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    _set_refresh_cookie(response, refresh_token)
    csrf_token = generate_csrf_token()
    set_csrf_cookie(response, csrf_token)

    return Token(access_token=access_token, token_type="bearer", return_url="/dashboard")


# ==========================================
# Google OAuth 2.0 / OpenID Connect Endpoints
# ==========================================


@router.get("/google/login", response_model=GoogleAuthUrlResponse)
@limiter.limit("10/minute")
def google_login_init(
    request: Request,
    return_url: str | None = None,
    redirect_uri: str | None = None,
):
    """Initiates Google OAuth 2.0 authorization code flow.

    Returns the Google authorization URL with signed state and nonce parameters.
    """
    google_service = GoogleOAuthService()
    auth_url, state_token, _ = google_service.get_authorization_url(
        return_url=return_url,
        purpose="login",
        redirect_uri=redirect_uri,
    )
    return {"authorization_url": auth_url, "state": state_token}


def _process_google_callback(
    code: str,
    state: str,
    redirect_uri: str | None,
    request: Request,
    response: Response,
    db: Session,
) -> Token:
    """Internal helper to process Google OAuth callback and issue LCC session tokens."""
    logger.info("google_oauth.callback_received: processing Google OAuth callback")

    # 1. Verify signed state token and extract claims
    state_payload = verify_oauth_state(state)
    if state_payload.get("purpose") != "login":
        logger.warning("google_oauth.invalid_purpose: OAuth state is not for login")
        raise AuthenticationError("Invalid OAuth state purpose")

    nonce = state_payload.get("nonce")
    state_redirect_uri = state_payload.get("redirect_uri")
    safe_return_url = state_payload.get("return_url") or "/dashboard"
    logger.info("google_oauth.state_verified: OAuth state token verified successfully")

    # 2. Enforce deterministic redirect URI matching between authorization and token exchange
    effective_redirect_uri = redirect_uri or state_redirect_uri or settings.GOOGLE_REDIRECT_URI
    if redirect_uri and state_redirect_uri and redirect_uri.rstrip("/") != state_redirect_uri.rstrip("/"):
        logger.warning(
            "google_oauth.redirect_uri_mismatch: callback redirect_uri does not match state redirect_uri"
        )
        raise AuthenticationError("OAuth redirect URI mismatch")

    # 3. Exchange authorization code for tokens
    google_service = GoogleOAuthService()
    tokens = google_service.exchange_code_for_tokens(
        code, redirect_uri=effective_redirect_uri
    )
    id_token = tokens.get("id_token")
    if not id_token:
        logger.warning("google_oauth.error: No ID token returned by Google")
        raise AuthenticationError("No ID token returned by Google")

    # 4. Cryptographically validate Google ID token claims
    claims = google_service.validate_id_token(id_token, expected_nonce=nonce)

    # 5. Authenticate or create LCC user and session
    auth_service = AuthService(db)
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    user, access_token, refresh_token = auth_service.authenticate_google_identity(
        claims, ip_address=ip_address, user_agent=user_agent
    )
    logger.info(
        "google_oauth.identity_resolved: Google identity mapped to LCC user",
        extra={"user_id": str(user.id), "role": user.role.value},
    )

    # 6. Set session cookies
    _set_refresh_cookie(response, refresh_token)
    csrf_token = generate_csrf_token()
    set_csrf_cookie(response, csrf_token)
    logger.info("google_oauth.session_created: session tokens and security cookies issued")
    logger.info("google_oauth.success: Google OAuth login completed successfully")

    return Token(
        access_token=access_token,
        token_type="bearer",
        refresh_token=refresh_token,
        return_url=safe_return_url,
    )


@router.get("/google/callback", response_model=Token)
@limiter.limit("20/minute")
def google_callback_get(
    request: Request,
    response: Response,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
):
    """GET callback handler for Google OAuth redirect."""
    if error:
        logger.warning(f"Google OAuth authorization error: {error}")
        raise AuthenticationError(f"Google authorization failed: {error}")

    if not code or not state:
        raise AuthenticationError("Missing required code or state parameter")

    return _process_google_callback(
        code=code,
        state=state,
        redirect_uri=None,
        request=request,
        response=response,
        db=db,
    )


@router.post("/google/callback", response_model=Token)
@limiter.limit("20/minute")
def google_callback_post(
    request: Request,
    response: Response,
    callback_req: GoogleCallbackRequest,
    db: Session = Depends(get_db),
):
    """POST callback handler for single-page applications and native clients."""
    return _process_google_callback(
        code=callback_req.code,
        state=callback_req.state,
        redirect_uri=callback_req.redirect_uri,
        request=request,
        response=response,
        db=db,
    )


@router.post("/google/direct", response_model=Token)
@limiter.limit("20/minute")
def google_direct_auth(
    request: Request,
    response: Response,
    auth_req: GoogleDirectAuthRequest,
    db: Session = Depends(get_db),
):
    """Directly authenticates a verified Google ID token (e.g. from Google One Tap or native clients)."""
    google_service = GoogleOAuthService()
    claims = google_service.validate_id_token(
        auth_req.id_token, expected_nonce=auth_req.nonce
    )

    auth_service = AuthService(db)
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    _, access_token, refresh_token = auth_service.authenticate_google_identity(
        claims, ip_address=ip_address, user_agent=user_agent
    )

    _set_refresh_cookie(response, refresh_token)
    csrf_token = generate_csrf_token()
    set_csrf_cookie(response, csrf_token)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "refresh_token": refresh_token,
    }


@router.post("/google/link", response_model=ExternalIdentityResponse)
@limiter.limit("10/minute")
def google_link_account(
    request: Request,
    link_req: GoogleLinkRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Links a Google identity to the currently authenticated LCC user account."""
    google_service = GoogleOAuthService()
    id_token = link_req.id_token
    expected_nonce = None

    if link_req.code and link_req.state:
        state_payload = verify_oauth_state(link_req.state)
        if state_payload.get("purpose") != "link":
            raise AuthenticationError("OAuth state is not for account linking")
        if state_payload.get("user_id") and state_payload["user_id"] != str(current_user.id):
            raise AuthenticationError("OAuth state user mismatch")
        expected_nonce = state_payload.get("nonce")

        tokens = google_service.exchange_code_for_tokens(
            link_req.code, redirect_uri=link_req.redirect_uri
        )
        id_token = tokens.get("id_token")

    if not id_token:
        raise AuthenticationError("Missing Google ID token or authorization code")

    claims = google_service.validate_id_token(id_token, expected_nonce=expected_nonce)

    auth_service = AuthService(db)
    ip_address = request.client.host if request.client else None
    identity = auth_service.link_google_identity(
        current_user.id, claims, ip_address=ip_address
    )
    return identity


@router.post("/google/unlink")
@limiter.limit("10/minute")
def google_unlink_account(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Unlinks Google identity from the currently authenticated user account."""
    auth_service = AuthService(db)
    ip_address = request.client.host if request.client else None
    auth_service.unlink_google_identity(current_user.id, ip_address=ip_address)
    return {"detail": "Google account unlinked successfully"}


@router.get("/identities", response_model=list[ExternalIdentityResponse])
def get_user_identities(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns all external identities linked to the authenticated user."""
    auth_service = AuthService(db)
    return auth_service.get_user_identities(current_user.id)


class AccountDeleteRequest(BaseModel):
    password: str | None = None
    reason: str | None = None


@router.delete("/account")
@limiter.limit("5/minute")
def delete_user_account_endpoint(
    request: Request,
    response: Response,
    req: AccountDeleteRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Safely deletes and anonymizes the authenticated user account with session revocation."""
    if current_user.password_hash:
        if not req or not req.password:
            raise ValidationError("Password confirmation is required to delete account")
        if not verify_password(req.password, current_user.password_hash):
            raise AuthenticationError("Invalid password confirmation")

    user_service = UserService(db)
    ip_address = request.client.host if request.client else None
    user_service.delete_user_account(
        user_id=current_user.id,
        reason=req.reason if req else None,
        ip_address=ip_address,
    )

    # Clear cookies
    response.delete_cookie(key="refresh_token", path=f"{settings.API_V1_STR}/auth")
    response.delete_cookie(key="csrf_token", path="/")
    return {"detail": "Account successfully deleted and personal data anonymized"}


