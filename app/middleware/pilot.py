from collections.abc import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings


class PilotControlMiddleware(BaseHTTPMiddleware):
    """Enforces controlled pilot mode constraints: emergency read-only mode and disabled features."""

    # Explicit paths permitted to mutate state even during emergency read-only mode
    EMERGENCY_ALLOWED_MUTATION_PREFIXES = (
        "/api/v1/auth/logout",
        "/api/v1/incidents",
        "/api/v1/pilot",
        "/api/v1/admin/audit",
    )

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path
        method = request.method.upper()

        # 1. Emergency Global Read-Only Mode enforcement
        if settings.PILOT_GLOBAL_READ_ONLY:
            if method in ("POST", "PUT", "PATCH", "DELETE"):
                # Check if this endpoint is exempted for incident response / operational safety
                is_exempt = any(path.startswith(prefix) for prefix in self.EMERGENCY_ALLOWED_MUTATION_PREFIXES)
                if not is_exempt:
                    return JSONResponse(
                        status_code=503,
                        content={
                            "error": {
                                "code": "EMERGENCY_READ_ONLY",
                                "message": "Platform is temporarily in emergency read-only mode for operational safety and maintenance.",
                                "request_id": getattr(request.state, "request_id", None),
                            }
                        },
                    )

        # 2. Pilot Feature Disablement enforcement
        if settings.PILOT_DISABLED_FEATURES:
            for disabled_feature in settings.PILOT_DISABLED_FEATURES:
                feature_tag = disabled_feature.lower().strip()
                if feature_tag and feature_tag in path.lower() and method in ("POST", "PUT", "PATCH", "DELETE"):
                    return JSONResponse(
                        status_code=503,
                        content={
                            "error": {
                                "code": "FEATURE_DISABLED_IN_PILOT",
                                "message": f"Feature '{disabled_feature}' is temporarily disabled for the production pilot.",
                                "request_id": getattr(request.state, "request_id", None),
                            }
                        },
                    )

        return await call_next(request)
