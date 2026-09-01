import logging

from fastapi import APIRouter, Cookie, Depends, Request, Response, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.csrf import (
    generate_csrf_token,
    set_csrf_cookie,
    validate_csrf_token,
    validate_origin,
)
from app.core.exceptions import AuthenticationError
from app.core.oauth_security import verify_oauth_state
from app.db.database import get_db
from app.models.user import User
from app.schemas.auth import (
    EmailVerificationConfirm,
    EmailVerificationRequest,
    EmailVerificationResponse,
    ExternalIdentityResponse,
    GoogleAuthUrlResponse,
    GoogleCallbackRequest,
    GoogleDirectAuthRequest,
    GoogleLinkRequest,
    LoginRequest,
    PasswordChangeRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    PasswordResetResponse,
    Token,
)
from app.schemas.user import UserCreate, UserResponse
from app.services.auth_service import AuthService
from app.services.google_oauth_service import GoogleOAuthService
from app.services.user_service import UserService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])
limiter = Limiter(key_func=get_remote_address)


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    is_production = settings.ENVIRONMENT == "production"
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=is_production,
        samesite="strict",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        path=f"{settings.API_V1_STR}/auth",
    )


@router.post(
    "/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
@limiter.limit("5/minute")
def register(request: Request, user_in: UserCreate, db: Session = Depends(get_db)):
    user_service = UserService(db)
    user = user_service.register_user(user_in)
    return user


@router.post("/login", response_model=Token)
@limiter.limit("5/minute")
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

    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/refresh", response_model=Token)
@limiter.limit("20/minute")
def refresh(
    request: Request,
    response: Response,
    refresh_token: str = Cookie(None),
    db: Session = Depends(get_db),
):
    if not refresh_token:
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

    new_access, new_refresh = auth_service.refresh(refresh_token, ip_address)

    _set_refresh_cookie(response, new_refresh)

    # Re-issue CSRF token on rotation
    csrf_token = generate_csrf_token()
    set_csrf_cookie(response, csrf_token)

    return {"access_token": new_access, "token_type": "bearer"}


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    refresh_token: str = Cookie(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    auth_service = AuthService(db)
    auth_service.logout(refresh_token, current_user.id)

    response.delete_cookie(key="refresh_token", path=f"{settings.API_V1_STR}/auth")
    response.delete_cookie(key="csrf_token", path=f"{settings.API_V1_STR}/auth")
    return {"detail": "Logged out successfully"}


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
    # 1. Verify signed state token and extract nonce
    state_payload = verify_oauth_state(state)
    nonce = state_payload.get("nonce")

    # 2. Exchange authorization code for tokens
    google_service = GoogleOAuthService()
    tokens = google_service.exchange_code_for_tokens(code, redirect_uri=redirect_uri)
    id_token = tokens.get("id_token")
    if not id_token:
        raise AuthenticationError("No ID token returned by Google")

    # 3. Cryptographically validate Google ID token claims
    claims = google_service.validate_id_token(id_token, expected_nonce=nonce)

    # 4. Authenticate or create LCC user and session
    auth_service = AuthService(db)
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    _, access_token, refresh_token = auth_service.authenticate_google_identity(
        claims, ip_address=ip_address, user_agent=user_agent
    )

    # 5. Set session cookies
    _set_refresh_cookie(response, refresh_token)
    csrf_token = generate_csrf_token()
    set_csrf_cookie(response, csrf_token)

    return Token(access_token=access_token, token_type="bearer")


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

    return {"access_token": access_token, "token_type": "bearer"}


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

