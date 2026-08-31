from collections.abc import Awaitable, Callable
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.identifiers import generate_uuid7

# Context variable to hold the correlation ID for the current request
correlation_id_ctx: ContextVar[str] = ContextVar("correlation_id", default="-")


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Middleware to ensure every request has a correlation ID.

    If 'X-Request-ID' is provided by the client, it is sanitized and used.
    Otherwise, a new UUIDv7 identifier is generated.
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # Get from header or generate a new UUIDv7 (Phase 1)
        correlation_id = request.headers.get("X-Request-ID", str(generate_uuid7()))

        # Sanitize to prevent log injection
        correlation_id = correlation_id[:36].replace("\n", "").replace("\r", "")

        # Set context variable
        token = correlation_id_ctx.set(correlation_id)

        try:
            # Add to request state for easy access in routes
            request.state.correlation_id = correlation_id
            response = await call_next(request)

            # Always return the correlation ID to the client
            response.headers["X-Request-ID"] = correlation_id
            return response
        finally:
            correlation_id_ctx.reset(token)
