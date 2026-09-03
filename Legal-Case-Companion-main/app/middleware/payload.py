from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """
    Rejects requests where the Content-Length header exceeds the maximum allowed size.
    Prevents trivial memory exhaustion attacks before parsing JSON bodies.
    """

    def __init__(self, app, max_upload_size: int = 5 * 1024 * 1024):  # default 5MB
        super().__init__(app)
        self.max_upload_size = max_upload_size

    async def dispatch(self, request: Request, call_next):
        if request.method in ["POST", "PUT", "PATCH"]:
            content_length = request.headers.get("content-length")
            if content_length:
                try:
                    length_val = int(content_length)
                    # Video recordings allow up to 250MB
                    effective_limit = (
                        250 * 1024 * 1024
                        if "/video/recording/upload" in request.url.path
                        else self.max_upload_size
                    )
                    if length_val > effective_limit:
                        return JSONResponse(
                            status_code=413,
                            content={
                                "error": {
                                    "code": "PAYLOAD_TOO_LARGE",
                                    "message": f"Payload size exceeds the limit of {effective_limit} bytes.",
                                }
                            },
                        )
                except (ValueError, TypeError):
                    return JSONResponse(
                        status_code=400,
                        content={
                            "error": {
                                "code": "INVALID_CONTENT_LENGTH",
                                "message": "Invalid Content-Length header provided.",
                            }
                        },
                    )
        return await call_next(request)
