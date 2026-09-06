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
            transfer_encoding = request.headers.get("transfer-encoding", "").lower()

            effective_limit = (
                250 * 1024 * 1024
                if "/video/recording/upload" in request.url.path
                else self.max_upload_size
            )

            if content_length:
                try:
                    length_val = int(content_length)
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
            elif "chunked" in transfer_encoding:
                # For chunked requests without Content-Length, stream and enforce byte limit
                body_chunks = []
                total_bytes = 0
                async for chunk in request.stream():
                    total_bytes += len(chunk)
                    if total_bytes > effective_limit:
                        return JSONResponse(
                            status_code=413,
                            content={
                                "error": {
                                    "code": "PAYLOAD_TOO_LARGE",
                                    "message": f"Payload size exceeds the limit of {effective_limit} bytes.",
                                }
                            },
                        )
                    body_chunks.append(chunk)

                full_body = b"".join(body_chunks)

                async def receive():
                    return {"type": "http.request", "body": full_body, "more_body": False}

                request._receive = receive
        return await call_next(request)
