import time
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.metrics import metrics_collector


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware collecting HTTP request counts, status codes, and latency distributions."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        start_time = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start_time) * 1000.0

        # Redact raw dynamic UUID path segments to keep endpoint cardinality low
        path = request.url.path
        metrics_collector.record_http_request(
            method=request.method,
            path=path,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
        return response
