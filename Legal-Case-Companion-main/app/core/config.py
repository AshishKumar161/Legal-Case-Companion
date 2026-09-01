from pydantic import AnyHttpUrl, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=True, extra="ignore"
    )

    PROJECT_NAME: str = "Legal Case Companion"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    API_V1_STR: str = "/api/v1"

    # JWT Configuration (Ed25519 / EdDSA)
    JWT_PRIVATE_KEY: str = Field(default="", min_length=0)
    JWT_PUBLIC_KEY: str = Field(default="", min_length=0)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    REFRESH_TOKEN_INACTIVITY_DAYS: int = 7
    ALGORITHM: str = "EdDSA"

    @model_validator(mode="before")
    @classmethod
    def populate_ephemeral_dev_keys(cls, data: object) -> object:
        if isinstance(data, dict):
            env = data.get("ENVIRONMENT", "development")
            priv = data.get("JWT_PRIVATE_KEY")
            pub = data.get("JWT_PUBLIC_KEY")
            if env != "production" and (
                not priv
                or not pub
                or "<set-in-environment>" in str(priv)
                or "<set-in-environment>" in str(pub)
            ):
                from cryptography.hazmat.primitives import serialization
                from cryptography.hazmat.primitives.asymmetric.ed25519 import (
                    Ed25519PrivateKey,
                )

                k = Ed25519PrivateKey.generate()
                data["JWT_PRIVATE_KEY"] = k.private_bytes(
                    serialization.Encoding.PEM,
                    serialization.PrivateFormat.PKCS8,
                    serialization.NoEncryption(),
                ).decode()
                data["JWT_PUBLIC_KEY"] = (
                    k.public_key()
                    .public_bytes(
                        serialization.Encoding.PEM,
                        serialization.PublicFormat.SubjectPublicKeyInfo,
                    )
                    .decode()
                )
        return data

    @field_validator("JWT_PRIVATE_KEY", "JWT_PUBLIC_KEY")
    @classmethod
    def validate_jwt_keys(cls, v: str) -> str:
        if "-----BEGIN" not in v:
            raise ValueError("JWT keys must be valid PEM encoded strings")
        return v

    # Database Configuration
    DATABASE_URL: str = Field(default="sqlite:///./test.db")
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: float = 30.0
    DB_POOL_RECYCLE: int = 1800
    DB_STATEMENT_TIMEOUT_MS: int = 30000

    # Logging Configuration
    LOG_LEVEL: str = "INFO"

    # CORS Configuration
    BACKEND_CORS_ORIGINS: list[AnyHttpUrl] | list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]

    # CSRF Configuration (Phase 6)
    CSRF_SECRET_KEY: str = Field(default="")

    # S3 / Storage Configuration (Phase 10, 16)
    AWS_S3_BUCKET_NAME: str = "lcc-secure-documents"
    AWS_REGION: str = "ap-south-1"
    AWS_ACCESS_KEY_ID: str | None = None
    AWS_SECRET_ACCESS_KEY: str | None = None
    AWS_WEBHOOK_SECRET: str | None = None

    # Stripe Configuration
    STRIPE_API_KEY: str | None = None
    STRIPE_WEBHOOK_SECRET: str | None = None

    # Email Configuration
    EMAIL_PROVIDER: str = "console"  # console, smtp, sendgrid, ses
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_TLS: bool = True
    SMTP_SSL: bool = False
    SENDGRID_API_KEY: str | None = None
    SES_ACCESS_KEY_ID: str | None = None
    SES_SECRET_ACCESS_KEY: str | None = None
    EMAIL_FROM: str = "noreply@legalcasecompanion.com"
    FRONTEND_URL: str = "http://localhost:3000"

    # Google OAuth / OpenID Connect Configuration
    GOOGLE_OAUTH_ENABLED: bool = False
    GOOGLE_CLIENT_ID: str | None = None
    GOOGLE_CLIENT_SECRET: str | None = None
    GOOGLE_REDIRECT_URI: str | None = None
    GOOGLE_AUTH_URI: str = "https://accounts.google.com/o/oauth2/v2/auth"
    GOOGLE_TOKEN_URI: str = "https://oauth2.googleapis.com/token"
    GOOGLE_JWKS_URI: str = "https://www.googleapis.com/oauth2/v3/certs"
    GOOGLE_ISSUERS: list[str] = ["https://accounts.google.com", "accounts.google.com"]
    GOOGLE_ALLOWED_REDIRECT_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]

    # External AI / Embedding Configuration
    OPENAI_API_KEY: str | None = None
    OPENAI_MAX_RETRIES: int = 3

    # RAG Settings
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_TIMEOUT_SECONDS: float = 15.0
    RETRIEVAL_TOP_K: int = 5
    RETRIEVAL_SIMILARITY_THRESHOLD: float = 0.7

    @field_validator("BACKEND_CORS_ORIGINS", "GOOGLE_ALLOWED_REDIRECT_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: str | list[str]) -> list[str] | str:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, str) and v.startswith("["):
            import json
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
            except (json.JSONDecodeError, TypeError, ValueError):
                return v
            return v
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        if self.GOOGLE_CLIENT_ID and not self.GOOGLE_REDIRECT_URI:
            self.GOOGLE_REDIRECT_URI = f"{self.FRONTEND_URL}/auth/callback"
        if self.GOOGLE_CLIENT_ID and not self.GOOGLE_OAUTH_ENABLED:
            self.GOOGLE_OAUTH_ENABLED = True

        # In local/development, ensure standard origins are present
        if self.ENVIRONMENT != "production":
            dev_origins = ["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:8000", "http://127.0.0.1:8000"]
            current_cors = [str(o) for o in self.BACKEND_CORS_ORIGINS]
            for origin in dev_origins:
                if origin not in current_cors:
                    current_cors.append(origin)
            self.BACKEND_CORS_ORIGINS = current_cors

        if self.ENVIRONMENT == "production":
            self.DEBUG = False

            # Require Google OAuth configuration only if enabled in production
            if self.GOOGLE_OAUTH_ENABLED and (
                not self.GOOGLE_CLIENT_ID or not self.GOOGLE_CLIENT_SECRET
            ):
                raise ValueError(
                    "GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET are required when GOOGLE_OAUTH_ENABLED is True in production"
                )

            # Require production JWT keys
            if (
                not self.JWT_PRIVATE_KEY
                or not self.JWT_PUBLIC_KEY
                or "<set-in-environment>" in str(self.JWT_PRIVATE_KEY)
                or "<set-in-environment>" in str(self.JWT_PUBLIC_KEY)
            ):
                raise ValueError(
                    "JWT_PRIVATE_KEY and JWT_PUBLIC_KEY are required in production"
                )

            # Require CSRF in production
            if (
                not self.CSRF_SECRET_KEY
                or self.CSRF_SECRET_KEY == "mock-secret-for-dev"
            ):
                raise ValueError(
                    "CSRF_SECRET_KEY must be a secure secret in production"
                )

            # Require AWS S3 configuration
            if not self.AWS_S3_BUCKET_NAME:
                raise ValueError("AWS_S3_BUCKET_NAME is required in production")
            if not self.AWS_WEBHOOK_SECRET:
                raise ValueError(
                    "AWS_WEBHOOK_SECRET is required in production for trusted malware events"
                )

            # Require Stripe configuration
            if not self.STRIPE_API_KEY or not self.STRIPE_WEBHOOK_SECRET:
                raise ValueError(
                    "STRIPE_API_KEY and STRIPE_WEBHOOK_SECRET are required in production"
                )

            # Require OpenAI configuration
            if not self.OPENAI_API_KEY:
                raise ValueError("OPENAI_API_KEY is required in production")

            # Require valid Email provider
            if self.EMAIL_PROVIDER == "console":
                raise ValueError("EMAIL_PROVIDER cannot be 'console' in production")
            if self.EMAIL_PROVIDER == "sendgrid" and not self.SENDGRID_API_KEY:
                raise ValueError("SENDGRID_API_KEY is required when using SendGrid")

        return self


settings = Settings()  # type: ignore[call-arg]
