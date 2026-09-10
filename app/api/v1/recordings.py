import os
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.api.v1.auth import limiter
from app.core.exceptions import ResourceNotFoundError, ValidationError
from app.models.user import User
from app.domain.consultations.video_recording_service import VideoRecordingService

router = APIRouter(prefix="/recordings", tags=["recordings"])


def _send_file_range(
    file_path: str,
    range_header: str | None,
    mime_type: str = "video/webm",
) -> Response:
    file_size = os.path.getsize(file_path)

    base_headers = {
        "Content-Type": mime_type,
        "Accept-Ranges": "bytes",
        "Cache-Control": "private, no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
        "Content-Disposition": f'inline; filename="consultation_{os.path.basename(file_path)}"',
        "X-Content-Type-Options": "nosniff",
    }

    if not range_header:
        def iter_full_file():
            with open(file_path, "rb") as f:
                while chunk := f.read(65536):
                    yield chunk

        headers = {
            **base_headers,
            "Content-Length": str(file_size),
        }
        return StreamingResponse(iter_full_file(), status_code=status.HTTP_200_OK, headers=headers)

    # Parse Range: bytes=start-end
    try:
        range_val = range_header.strip().lower()
        if not range_val.startswith("bytes="):
            raise ValueError("Invalid range prefix")

        parts = range_val.replace("bytes=", "").split("-")
        start_str = parts[0].strip()
        end_str = parts[1].strip() if len(parts) > 1 else ""

        start = int(start_str) if start_str else 0
        end = int(end_str) if end_str else file_size - 1

        if start >= file_size or end >= file_size or start > end:
            return Response(
                status_code=status.HTTP_416_RANGE_NOT_SATISFIABLE,
                headers={"Content-Range": f"bytes */{file_size}", **base_headers},
            )

        content_length = end - start + 1

        def iter_range_file():
            with open(file_path, "rb") as f:
                f.seek(start)
                bytes_left = content_length
                while bytes_left > 0:
                    read_size = min(65536, bytes_left)
                    chunk = f.read(read_size)
                    if not chunk:
                        break
                    yield chunk
                    bytes_left -= len(chunk)

        headers = {
            **base_headers,
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Content-Length": str(content_length),
        }
        return StreamingResponse(
            iter_range_file(),
            status_code=status.HTTP_206_PARTIAL_CONTENT,
            headers=headers,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid Range header: {e}",
        ) from e


@router.post(
    "/{recording_id}/playback-ticket",
    response_model=dict[str, Any],
)
@limiter.limit("30/minute")
def request_playback_ticket(
    request: Request,
    recording_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Request an ephemeral, single-purpose media playback ticket for authorized consultation streaming.
    Ticket is strictly valid for 60 seconds and bound to the requesting user and recording ID.
    Replaces long-lived bearer tokens in query parameters to prevent token leakage in browser history/logs.
    """
    service = VideoRecordingService(db)
    try:
        ticket = service.generate_playback_ticket(user=current_user, recording_id=recording_id)
    except ResourceNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    return {
        "recording_id": str(recording_id),
        "ticket": ticket,
        "expires_in_seconds": 60,
        "token_type": "ephemeral_media_ticket",
    }


@router.get(
    "/{recording_id}/play",
)
@limiter.limit("60/minute")
def play_recording(
    request: Request,
    recording_id: UUID,
    range: str | None = Header(None),
    ticket: str | None = Query(None, description="Ephemeral 60s media playback ticket"),
    db: Session = Depends(get_db),
):
    """
    Authorized streaming playback endpoint for video recordings.
    Supports HTTP Range requests (206 Partial Content) for seeking.
    Strictly forbids unauthorized access (returns 404 IDOR defense).
    Requires either:
    1) Authorization: Bearer <access_token> header, OR
    2) ?ticket=<playback_ticket> query parameter (ephemeral 60s ticket).
    Raw bearer access tokens in query parameters are strictly forbidden and rejected with 401.
    """
    # 1. Reject raw bearer tokens in query string (Phase 5)
    if request.query_params.get("token"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Passing bearer access tokens in query parameters is forbidden for security. "
            "Use the Authorization header or request an ephemeral playback ticket via POST /recordings/{id}/playback-ticket.",
        )

    # 2. Resolve user via ticket or Authorization header
    service = VideoRecordingService(db)
    current_user: User | None = None

    if ticket:
        try:
            current_user = service.verify_playback_ticket(ticket=ticket, expected_recording_id=recording_id)
        except ValidationError as val_err:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(val_err)) from val_err
    else:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            raw_token = auth_header.replace("Bearer ", "").strip()
            from app.core.security import verify_access_token
            from app.models.user import AccountStatus
            from app.domain.users.user_service import UserService

            try:
                payload = verify_access_token(raw_token)
                user_id_str = payload.get("sub")
                if not user_id_str:
                    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token missing subject claim")
                user_id = UUID(user_id_str)
            except Exception as e:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token") from e

            current_user = UserService(db).get_user_by_id(user_id)
            if not current_user or current_user.account_status != AccountStatus.ACTIVE:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User inactive or not found")
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated. Provide an Authorization header or an ephemeral playback ticket via ?ticket=.",
            )

    try:
        recording, physical_path = service.get_recording_for_playback(
            user=current_user,
            recording_id=recording_id,
        )
    except ResourceNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    return _send_file_range(
        file_path=str(physical_path),
        range_header=range,
        mime_type=recording.mime_type or "video/webm",
    )
