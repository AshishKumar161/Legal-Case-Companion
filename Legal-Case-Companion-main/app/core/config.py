from datetime import datetime

from pydantic import AnyHttpUrl, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=True, extra="ignore"
    )

    PROJECT_NAME: str = "Legal Case Companion"
    APP_VERSION: str = "1.0.0"
    RELEASE_ID: str = "prod-2026.09.04"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    API_V1_STR: str = "/api/v1"

    # JWT Configuration (Ed25519 / EdDSA)
    JWT_PRIVATE_KEY: str = Field(default="", min_length=0)
    JWT_PUBLIC_KEY: str = Field(default="", min_length=0)
    JWT_PREVIOUS_PUBLIC_KEY: str | None = None
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
            if env in ("development", "test") and (
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

    @field_validator("JWT_PREVIOUS_PUBLIC_KEY")
    @classmethod
    def validate_prev_jwt_key(cls, v: str | None) -> str | None:
        if v and "-----BEGIN" not in v:
            raise ValueError("JWT_PREVIOUS_PUBLIC_KEY must be a valid PEM encoded string")
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

    # Perimeter / Host Validation Configuration
    RENDER_EXTERNAL_HOSTNAME: str | None = None
    ALLOWED_HOSTS: list[str] = Field(default_factory=list)

    # CSRF Configuration (Phase 6)
    CSRF_SECRET_KEY: str = Field(default="")

    # S3 / Storage Configuration (Phase 10, 16)
    AWS_S3_BUCKET_NAME: str = "lcc-secure-documents"
    AWS_REGION: str = "ap-south-1"
    AWS_ACCESS_KEY_ID: str | None = None
    AWS_SECRET_ACCESS_KEY: str | None = None
    AWS_WEBHOOK_SECRET: str | None = None

    # Antivirus / Malware Scanner Configuration (ClamAV)
    CLAMAV_HOST: str | None = None
    CLAMAV_PORT: int = 3310

    # WebRTC / TURN Relay Configuration (Coturn / Managed TURN)
    TURN_SERVER_URL: str | None = None
    TURN_USERNAME: str | None = None
    TURN_CREDENTIAL: str | None = None
    TURN_STATIC_AUTH_SECRET: str | None = None

    # Stripe & Sandbox Payment Configuration
    STRIPE_API_KEY: str | None = None
    STRIPE_WEBHOOK_SECRET: str | None = None
    ENABLE_TEST_PAYMENTS: bool = Field(default=True)

    # Redis & Distributed Presence Configuration
    REDIS_URL: str | None = None
    REDIS_KEY_PREFIX: str = "lcc"
    PRESENCE_TTL_SECONDS: int = 45
    PRESENCE_HEARTBEAT_INTERVAL_SECONDS: int = 15
    INSTANT_CALL_RING_TIMEOUT_SECONDS: int = 60

    # Email Configuration
    EMAIL_PROVIDER: str = "console"  # console, smtp, sendgrid, ses
    EMAIL_CHECK_DELIVERABILITY: bool = False
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

    # Commercial & Tax Configuration (Phase 10)
    COMMERCIAL_PLATFORM_FEE_PERCENT: float = 10.0
    COMMERCIAL_GST_PERCENT: float = 18.0

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
    AI_INTEGRATION_ENABLED: bool = True
    OPENAI_API_KEY: str | None = None
    OPENAI_MAX_RETRIES: int = 3

    # RAG Settings
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_TIMEOUT_SECONDS: float = 15.0
    RETRIEVAL_TOP_K: int = 5
    RETRIEVAL_SIMILARITY_THRESHOLD: float = 0.7

    # Business & Legal Policy Boundaries (Pending Business/Legal Policy Finalization)
    DOCUMENT_RETENTION_DAYS: int | None = None  # None represents indefinite retention pending formal policy
    CANCELLATION_REFUND_POLICY_MODE: str = "PENDING_BUSINESS_DECISION"  # Options: MANUAL_REVIEW, AUTOMATIC_TIERED, PENDING_BUSINESS_DECISION
    CLIENT_LATE_CANCELLATION_CUTOFF_HOURS: int = 2
    CLIENT_LATE_CANCELLATION_REFUND_PERCENT: float = 50.0

    # Video Recording Storage Configuration
    LOCAL_RECORDING_STORAGE_PATH: str = "./storage/recordings"

    # Native Video & LiveKit SFU Configuration
    LIVEKIT_URL: str | None = None
    LIVEKIT_API_KEY: str | None = None
    LIVEKIT_API_SECRET: str | None = None

    # Phase XVIII Pilot & Launch Governance Controls
    PILOT_MODE: bool = False
    PILOT_ALLOWLIST_ENABLED: bool = False
    PILOT_SIGNUP_ENABLED: bool = True
    PILOT_MAX_CLIENTS: int = 100
    PILOT_MAX_LAWYERS: int = 50
    PILOT_START_TIME: datetime | None = None
    PILOT_END_TIME: datetime | None = None
    PILOT_GLOBAL_READ_ONLY: bool = False
    PILOT_DISABLED_FEATURES: list[str] = Field(default_factory=list)

    # Phase XX Public Onboarding & Launch Governance Controls
    # Supported modes: "CONTROLLED", "INVITE_ONLY", "VERIFIED_PROFESSIONAL", "PUBLIC"
    ONBOARDING_MODE: str = "CONTROLLED"
    PUBLIC_REGISTRATION_ENABLED: bool = False
    REQUIRE_IDENTITY_VERIFICATION: bool = True
    REQUIRE_TERMS_ACCEPTANCE: bool = True
    BAR_ASSOCIATION_ALLOWLIST: list[str] = Field(
        default_factory=lambda: [
            "Bar Council of Delhi",
            "Bar Council of Maharashtra & Goa",
            "Bar Council of Karnataka",
            "Bar Council of Tamil Nadu and Puducherry",
            "Supreme Court Bar Association",
            "Delhi High Court Bar Association",
        ]
    )

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

        valid_environments = ("development", "test", "staging", "production")
        if self.ENVIRONMENT not in valid_environments:
            raise ValueError(
                f"Invalid ENVIRONMENT '{self.ENVIRONMENT}'. Must be one of: {', '.join(valid_environments)}."
            )

        # In local/development/test, ensure standard origins are present
        if self.ENVIRONMENT in ("development", "test"):
            dev_origins = ["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:8000", "http://127.0.0.1:8000"]
            current_cors = [str(o) for o in self.BACKEND_CORS_ORIGINS]
            for origin in dev_origins:
                if origin not in current_cors:
                    current_cors.append(origin)
            self.BACKEND_CORS_ORIGINS = current_cors

        # Resolve ALLOWED_HOSTS based on environment if not explicitly set
        if not self.ALLOWED_HOSTS:
            if self.ENVIRONMENT in ("staging", "production"):
                prod_hosts = [
                    "legalcasecompanion.in",
                    "api.legalcasecompanion.in",
                    "www.legalcasecompanion.in",
                ]
                if self.RENDER_EXTERNAL_HOSTNAME:
                    prod_hosts.append(self.RENDER_EXTERNAL_HOSTNAME)
                self.ALLOWED_HOSTS = prod_hosts
            else:
                self.ALLOWED_HOSTS = [
                    "localhost",
                    "127.0.0.1",
                    "testserver",
                ]

        if self.ENVIRONMENT in ("staging", "production"):
            self.DEBUG = False
            if self.ENVIRONMENT == "production":
                self.ENABLE_TEST_PAYMENTS = False

            # Require PostgreSQL in staging and production
            if "sqlite" in self.DATABASE_URL.lower():
                raise ValueError(
                    f"{self.ENVIRONMENT.capitalize()} requires PostgreSQL. SQLite is strictly forbidden in {self.ENVIRONMENT}."
                )

            # Require database TLS in staging and production
            if "sslmode=disable" in self.DATABASE_URL.lower():
                raise ValueError(
                    f"DATABASE_URL must not disable SSL (sslmode=disable) in {self.ENVIRONMENT}."
                )

            # Require Google OAuth configuration only if enabled
            if self.GOOGLE_OAUTH_ENABLED and (
                not self.GOOGLE_CLIENT_ID or not self.GOOGLE_CLIENT_SECRET
            ):
                raise ValueError(
                    f"GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET are required when GOOGLE_OAUTH_ENABLED is True in {self.ENVIRONMENT}"
                )

            # Require production/staging JWT keys
            if (
                not self.JWT_PRIVATE_KEY
                or not self.JWT_PUBLIC_KEY
                or "<set-in-environment>" in str(self.JWT_PRIVATE_KEY)
                or "<set-in-environment>" in str(self.JWT_PUBLIC_KEY)
            ):
                raise ValueError(
                    f"JWT_PRIVATE_KEY and JWT_PUBLIC_KEY are required in {self.ENVIRONMENT}"
                )

            # Require CSRF in staging and production
            if (
                not self.CSRF_SECRET_KEY
                or self.CSRF_SECRET_KEY == "mock-secret-for-dev"
                or len(self.CSRF_SECRET_KEY) < 32
            ):
                raise ValueError(
                    f"CSRF_SECRET_KEY must be a secure secret (min 32 chars) in {self.ENVIRONMENT}"
                )

            # Require AWS S3 configuration
            if not self.AWS_S3_BUCKET_NAME:
                raise ValueError(f"AWS_S3_BUCKET_NAME is required in {self.ENVIRONMENT}")
            if not self.AWS_WEBHOOK_SECRET:
                raise ValueError(
                    f"AWS_WEBHOOK_SECRET is required in {self.ENVIRONMENT} for trusted malware events"
                )

            # Require Stripe configuration
            if not self.STRIPE_API_KEY or not self.STRIPE_WEBHOOK_SECRET:
                raise ValueError(
                    f"STRIPE_API_KEY and STRIPE_WEBHOOK_SECRET are required in {self.ENVIRONMENT}"
                )

            # Require Redis configuration
            if not self.REDIS_URL:
                raise ValueError(
                    f"REDIS_URL is required in {self.ENVIRONMENT} for shared presence and real-time state"
                )

            # AI integration is optional. The core platform operates cleanly without any AI credentials.
            # If OPENAI_API_KEY is provided, AI features will be active; otherwise stubs/fallbacks will be used.

            # Require valid Email provider
            if self.EMAIL_PROVIDER == "console":
                raise ValueError(f"EMAIL_PROVIDER cannot be 'console' in {self.ENVIRONMENT}")
            if self.EMAIL_PROVIDER == "sendgrid" and not self.SENDGRID_API_KEY:
                raise ValueError("SENDGRID_API_KEY is required when using SendGrid")

        # Validate Pilot Settings across all environments
        if self.PILOT_START_TIME and self.PILOT_END_TIME:
            if self.PILOT_START_TIME >= self.PILOT_END_TIME:
                raise ValueError("PILOT_START_TIME must be strictly before PILOT_END_TIME")
        if self.PILOT_MODE:
            if self.PILOT_MAX_CLIENTS <= 0:
                raise ValueError("PILOT_MAX_CLIENTS must be greater than 0 when PILOT_MODE is enabled")
            if self.PILOT_MAX_LAWYERS <= 0:
                raise ValueError("PILOT_MAX_LAWYERS must be greater than 0 when PILOT_MODE is enabled")

        return self


settings = Settings()  # type: ignore[call-arg]
