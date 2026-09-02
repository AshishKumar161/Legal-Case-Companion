import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.admin import router as admin_router
from app.api.v1.ai import router as ai_router
from app.api.v1.ai_conversations import router as ai_conversations_router
from app.api.v1.analytics import router as analytics_router
from app.api.v1.assistant import router as assistant_router
from app.api.v1.audit import router as audit_router
from app.api.v1.auth import limiter
from app.api.v1.auth import router as auth_router
from app.api.v1.case_intelligence import router as case_intelligence_router
from app.api.v1.cases import router as cases_router
from app.api.v1.consultations import router as consultations_router
from app.api.v1.documents import router as documents_router
from app.api.v1.feedback import router as feedback_router
from app.api.v1.health import root_router as root_health_router
from app.api.v1.health import router as health_router
from app.api.v1.lawyers import router as lawyers_router
from app.api.v1.legal_authority import router as legal_authority_router
from app.api.v1.notifications import router as notifications_router
from app.api.v1.payments import router as payments_router
from app.api.v1.profiles import router as profiles_router
from app.api.v1.search import router as search_router
from app.api.v1.video_signaling import router as video_signaling_router
from app.api.v1.webhooks import router as webhooks_router
from app.api.v1.workflow import router as workflow_router
from app.core.config import settings
from app.core.exceptions import AppException
from app.core.logging import correlation_id_ctx, setup_logging
from app.middleware.correlation_id import CorrelationIdMiddleware
from app.middleware.metrics import MetricsMiddleware
from app.middleware.payload import RequestSizeLimitMiddleware
from app.middleware.security import SecurityHeadersMiddleware

# Initialize logging
setup_logging(settings.LOG_LEVEL)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan handler to ensure database tables are created in development/local runtimes."""
    if settings.ENVIRONMENT != "production" or settings.DATABASE_URL.startswith("sqlite"):
        import app.models  # noqa: F401
        from app.db.database import engine
        from app.models.base import Base

        Base.metadata.create_all(bind=engine)
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

# Middleware stack (executed in reverse registration order: Security -> Metrics -> PayloadLimit -> CorrelationId)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(MetricsMiddleware)
app.add_middleware(RequestSizeLimitMiddleware, max_upload_size=5_242_880)  # 5MB limit
app.add_middleware(CorrelationIdMiddleware)

# CORS configuration
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
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
                "message": str(exc.detail),
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
app.include_router(search_router, prefix=settings.API_V1_STR)
app.include_router(legal_authority_router, prefix=settings.API_V1_STR)
app.include_router(payments_router, prefix=settings.API_V1_STR)
app.include_router(notifications_router, prefix=settings.API_V1_STR)
app.include_router(lawyers_router, prefix=settings.API_V1_STR)
app.include_router(ai_router, prefix=settings.API_V1_STR)
app.include_router(assistant_router, prefix=settings.API_V1_STR)
app.include_router(ai_conversations_router, prefix=settings.API_V1_STR)
app.include_router(feedback_router, prefix=settings.API_V1_STR)
app.include_router(analytics_router, prefix=settings.API_V1_STR)
app.include_router(admin_router, prefix=settings.API_V1_STR)
app.include_router(audit_router, prefix=settings.API_V1_STR)
app.include_router(health_router, prefix=settings.API_V1_STR)
app.include_router(webhooks_router, prefix=settings.API_V1_STR)
app.include_router(video_signaling_router, prefix=settings.API_V1_STR)
