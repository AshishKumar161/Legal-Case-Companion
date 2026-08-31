import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class Token(BaseModel):
    access_token: str
    token_type: str


class LoginRequest(BaseModel):
    email: str
    password: str


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str


class GoogleAuthUrlResponse(BaseModel):
    authorization_url: str
    state: str


class GoogleCallbackRequest(BaseModel):
    code: str
    state: str
    redirect_uri: str | None = None


class GoogleDirectAuthRequest(BaseModel):
    id_token: str
    nonce: str | None = None


class GoogleLinkRequest(BaseModel):
    code: str | None = None
    state: str | None = None
    id_token: str | None = None
    redirect_uri: str | None = None


class ExternalIdentityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider: str
    email: str
    email_verified: bool
    created_at: datetime
