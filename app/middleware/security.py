from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Applies hardened production security headers to all HTTP responses."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Enforce HTTPS connections (HSTS - 1 year with subdomains and preload)
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains; preload"
        )

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Prevent clickjacking / framing
        response.headers["X-Frame-Options"] = "DENY"

        # Content Security Policy (Strict sandbox for REST APIs, functional CSP for docs)
        if request.url.path.startswith(("/docs", "/redoc", "/api/v1/docs", "/api/v1/redoc", "/api/v1/openapi.json")):
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "img-src 'self' data: https://fastapi.tiangolo.com; frame-ancestors 'none'"
            )
        else:
            response.headers["Content-Security-Policy"] = (
                "default-src 'none'; frame-ancestors 'none'; sandbox"
            )

        # Privacy and Referrer protection
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Cross-Origin isolation
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        origin = request.headers.get("origin")
        from app.core.config import settings
        allowed_origins = [str(o) for o in (settings.BACKEND_CORS_ORIGINS or [])]
        if origin and (origin in allowed_origins or "*" in allowed_origins):
            response.headers["Cross-Origin-Resource-Policy"] = "cross-origin"
        else:
            response.headers["Cross-Origin-Resource-Policy"] = "same-site"

        # Restrict dangerous browser features / hardware APIs
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=(), payment=()"
        )

        return response
