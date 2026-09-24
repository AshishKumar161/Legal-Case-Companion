import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Request, Response, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.v1.admin import router as admin_router
from app.api.v1.ai import router as ai_router
from app.api.v1.ai_conversations import router as ai_conversations_router
from app.api.v1.ai_review import router as ai_review_router
from app.api.v1.analytics import router as analytics_router
from app.api.v1.assistant import router as assistant_router
from app.api.v1.advisor import router as advisor_router
from app.api.v1.audit import router as audit_router
from app.api.v1.auth import limiter
from app.api.v1.auth import router as auth_router
from app.api.v1.bundles import router as bundles_router
from app.api.v1.case_intelligence import router as case_intelligence_router
from app.api.v1.cases import router as cases_router
from app.api.v1.commercial import router as commercial_router
from app.api.v1.compliance import router as compliance_router
from app.api.v1.consultations import router as consultations_router
from app.api.v1.data_quality import router as data_quality_router
from app.api.v1.documents import router as documents_router
from app.api.v1.evidence import router as evidence_router
from app.api.v1.attention import router as attention_router
from app.api.v1.calendar import router as calendar_router
from app.api.v1.change_feed import router as change_feed_router
from app.api.v1.court_cases import router as court_cases_router
from app.api.v1.experiments import router as experiments_router
from app.api.v1.feedback import router as feedback_router
from app.api.v1.health import root_router as root_health_router
from app.api.v1.health import router as health_router
from app.api.v1.incidents import router as incidents_router
from app.api.v1.kyc import router as kyc_router
from app.api.v1.launch_gates import router as launch_gates_router
from app.api.v1.lawyers import router as lawyers_router
from app.api.v1.legal_authority import router as legal_authority_router
from app.api.v1.legal_documents import router as legal_documents_router
from app.api.v1.localization import router as localization_router
from app.api.v1.messages import router as messages_router
from app.api.v1.notifications import router as notifications_router
from app.api.v1.payments import router as payments_router
from app.api.v1.pilot import router as pilot_router
from app.api.v1.profiles import router as profiles_router
from app.api.v1.recordings import router as recordings_router
from app.api.v1.search import router as search_router
from app.api.v1.support import router as support_router
from app.api.v1.trust import router as trust_router
from app.api.v1.verification import router as verification_router
from app.api.v1.video_signaling import router as video_signaling_router
from app.api.v1.webhooks import router as webhooks_router
from app.api.v1.workflow import router as workflow_router
from app.core.config import settings
from app.core.exceptions import AppException
from app.core.logging import correlation_id_ctx, setup_logging
from app.middleware.correlation_id import CorrelationIdMiddleware
from app.middleware.metrics import MetricsMiddleware
from app.middleware.payload import RequestSizeLimitMiddleware
from app.middleware.pilot import PilotControlMiddleware
from app.middleware.security import SecurityHeadersMiddleware

# Initialize logging
setup_logging(settings.LOG_LEVEL)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan handler to ensure database tables are created only in development/test runtimes."""
    if settings.ENVIRONMENT in ("development", "test") and settings.DATABASE_URL.startswith("sqlite"):
        import app.models  # noqa: F401
        from app.db.database import engine
        from app.models.base import Base

        Base.metadata.create_all(bind=engine)
        # Ensure schema compatibility for dynamic profile columns in SQLite
        try:
            with engine.begin() as conn:
                res = conn.exec_driver_sql("PRAGMA table_info(client_profiles)").fetchall()
                existing_cols = {row[1] for row in res}
                new_cols = [
                    ("phone", "VARCHAR(20)"),
                    ("date_of_birth", "VARCHAR(20)"),
                    ("gender", "VARCHAR(20)"),
                    ("id_type", "VARCHAR(50)"),
                    ("id_number", "VARCHAR(100)"),
                    ("address", "TEXT"),
                    ("city", "VARCHAR(100)"),
                    ("state", "VARCHAR(100)"),
                    ("pincode", "VARCHAR(20)"),
                    ("kyc_document_storage_key", "VARCHAR(512)"),
                    ("kyc_document_filename", "VARCHAR(255)"),
                    ("kyc_status", "VARCHAR(50) DEFAULT 'PENDING'"),
                    ("kyc_submitted_at", "DATETIME"),
                    ("kyc_verified_at", "DATETIME"),
                    ("kyc_rejection_reason", "TEXT"),
                ]
                for col_name, col_type in new_cols:
                    if col_name not in existing_cols:
                        conn.exec_driver_sql(f"ALTER TABLE client_profiles ADD COLUMN {col_name} {col_type}")
        except Exception as e:
            logger.debug(f"Schema compatibility check notice: {e}")
        logger.info("Local/development database tables initialized.")
    yield


# Application Bootstrap
app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.1.0",
    description="India-focused Legal Case Companion Backend Foundation",
    docs_url=f"{settings.API_V1_STR}/docs",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

# Middleware stack (executed in reverse registration order: Security -> PilotControl -> Metrics -> PayloadLimit -> CorrelationId)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(PilotControlMiddleware)
app.add_middleware(MetricsMiddleware)
app.add_middleware(RequestSizeLimitMiddleware, max_upload_size=5_242_880)  # 5MB limit
app.add_middleware(CorrelationIdMiddleware)

# CORS configuration
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_origin_regex=r"https://.*\.trycloudflare\.com",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Trusted Host validation (protects against Host header poisoning and cache pollution)
if settings.ALLOWED_HOSTS:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.ALLOWED_HOSTS,
    )


# Standardized Error Handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    request_id = correlation_id_ctx.get()
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "The request contains invalid or missing fields.",
                "details": jsonable_encoder(exc.errors()),
                "request_id": request_id,
            }
        },
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    request_id = correlation_id_ctx.get()
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": "HTTP_ERROR",
                "message": exc.detail,
                "details": None,
                "request_id": request_id,
            }
        },
    )


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    request_id = correlation_id_ctx.get()
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
                "request_id": request_id,
            }
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = correlation_id_ctx.get()
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred.",
                "details": None,
                "request_id": request_id,
            }
        },
    )


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    request_id = correlation_id_ctx.get()
    return JSONResponse(
        status_code=429,
        content={
            "error": {
                "code": "RATE_LIMIT_EXCEEDED",
                "message": "Rate limit exceeded.",
                "details": None,
                "request_id": request_id,
            }
        },
    )


app.state.limiter = limiter

# Root Health Endpoints (for load balancers & orchestrator root probes)
app.include_router(root_health_router)

# Versioned API Routers (/api/v1)
app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(profiles_router, prefix=settings.API_V1_STR)
app.include_router(cases_router, prefix=settings.API_V1_STR)
app.include_router(case_intelligence_router, prefix=settings.API_V1_STR)
app.include_router(workflow_router, prefix=settings.API_V1_STR)
app.include_router(consultations_router, prefix=settings.API_V1_STR)
app.include_router(documents_router, prefix=settings.API_V1_STR)
app.include_router(evidence_router, prefix=settings.API_V1_STR)
app.include_router(bundles_router, prefix=settings.API_V1_STR)
app.include_router(search_router, prefix=settings.API_V1_STR)
app.include_router(legal_authority_router, prefix=settings.API_V1_STR)
app.include_router(payments_router, prefix=settings.API_V1_STR)
app.include_router(notifications_router, prefix=settings.API_V1_STR)
app.include_router(lawyers_router, prefix=settings.API_V1_STR)
app.include_router(ai_router, prefix=settings.API_V1_STR)
app.include_router(assistant_router, prefix=settings.API_V1_STR)
app.include_router(ai_conversations_router, prefix=settings.API_V1_STR)
app.include_router(advisor_router, prefix=settings.API_V1_STR)
app.include_router(feedback_router, prefix=settings.API_V1_STR)
app.include_router(analytics_router, prefix=settings.API_V1_STR)
app.include_router(admin_router, prefix=settings.API_V1_STR)
app.include_router(audit_router, prefix=settings.API_V1_STR)
app.include_router(recordings_router, prefix=settings.API_V1_STR)
app.include_router(health_router, prefix=settings.API_V1_STR)
app.include_router(webhooks_router, prefix=settings.API_V1_STR)
app.include_router(video_signaling_router, prefix=settings.API_V1_STR)
app.include_router(incidents_router, prefix=settings.API_V1_STR)
app.include_router(pilot_router, prefix=settings.API_V1_STR)
app.include_router(experiments_router, prefix=settings.API_V1_STR)
app.include_router(support_router, prefix=settings.API_V1_STR)
app.include_router(ai_review_router, prefix=settings.API_V1_STR)
app.include_router(data_quality_router, prefix=settings.API_V1_STR)
app.include_router(localization_router, prefix=settings.API_V1_STR)
app.include_router(compliance_router, prefix=settings.API_V1_STR)
app.include_router(legal_documents_router, prefix=settings.API_V1_STR)
app.include_router(trust_router, prefix=settings.API_V1_STR)
app.include_router(commercial_router, prefix=settings.API_V1_STR)
app.include_router(verification_router, prefix=settings.API_V1_STR)
app.include_router(kyc_router, prefix=settings.API_V1_STR)
app.include_router(launch_gates_router, prefix=settings.API_V1_STR)
app.include_router(court_cases_router, prefix=settings.API_V1_STR)
app.include_router(calendar_router, prefix=settings.API_V1_STR)
app.include_router(attention_router, prefix=settings.API_V1_STR)
app.include_router(change_feed_router, prefix=settings.API_V1_STR)
app.include_router(messages_router, prefix=settings.API_V1_STR)


# Local Storage Emulation Routes (handles presigned PUT upload and GET download for local development)
@app.put("/mock-storage/upload")
async def mock_storage_upload(request: Request, key: str = Query(...)):
    if settings.ENVIRONMENT in ("production", "staging"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    from app.core.exceptions import ValidationError
    from app.core.storage import get_storage_provider, validate_storage_object_key

    # Guard against path traversal sequences in object keys
    try:
        key = validate_storage_object_key(key)
    except ValidationError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid storage key") from err

    body = await request.body()
    storage = get_storage_provider()
    content_type = request.headers.get("content-type", "application/octet-stream")
    storage.put_object_bytes(key, body, content_type)
    return Response(status_code=status.HTTP_200_OK)


@app.get("/mock-storage/download")
async def mock_storage_download(
    key: str = Query(...),
    disposition: str | None = Query(None),
    content_type: str | None = Query(None),
):
    if settings.ENVIRONMENT in ("production", "staging"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    from app.core.exceptions import ValidationError
    from app.core.storage import get_storage_provider, validate_storage_object_key

    # Guard against path traversal sequences in object keys
    try:
        key = validate_storage_object_key(key)
    except ValidationError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid storage key") from err

    storage = get_storage_provider()
    data = storage.get_object_bytes(key)
    if data is None:
        data = f"Legal Case Companion Authenticated Document\nObject Key: {key}\nStatus: Verified SAFE".encode("utf-8")
    media_type = content_type or "application/octet-stream"
    headers = {}
    if disposition:
        headers["Content-Disposition"] = disposition
    return Response(content=data, media_type=media_type, headers=headers)
