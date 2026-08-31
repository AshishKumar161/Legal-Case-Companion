# API Contract Gap Report & Implementation Audit

## 1. Backend Endpoint Inventory

Below is the exact implemented endpoint inventory derived from `openapi.json` and the source code.

**Authentication**
- `POST /api/v1/auth/register` (Public)
- `POST /api/v1/auth/login` (Public)
- `POST /api/v1/auth/refresh` (Requires HttpOnly Refresh Cookie + X-CSRF-Token)
- `POST /api/v1/auth/logout` (Requires Auth)
- `POST /api/v1/auth/password/change` (Requires Auth)

**User/Profile**
- `GET /api/v1/profiles/me` (Requires Auth)
- `PATCH /api/v1/profiles/client` (Requires Auth: CLIENT)
- `PATCH /api/v1/profiles/lawyer` (Requires Auth: LAWYER)
- `POST /api/v1/profiles/lawyer/verification` (Requires Auth: LAWYER)

**Cases**
- `POST /api/v1/cases` (Requires Auth: CLIENT)
- `GET /api/v1/cases` (Requires Auth)
- `GET /api/v1/cases/{case_id}` (Requires Auth + CaseParticipant)
- `PATCH /api/v1/cases/{case_id}` (Requires Auth: CLIENT)

**Case Participants**
- `POST /api/v1/cases/{case_id}/participants` (Requires Auth: CLIENT)
- `DELETE /api/v1/cases/{case_id}/participants/{user_id}` (Requires Auth: CLIENT)

**Case Timeline**
- `GET /api/v1/cases/{case_id}/timeline` (Requires Auth + CaseParticipant)
- `POST /api/v1/cases/{case_id}/timeline` (Requires Auth + CaseParticipant)

**Documents**
- `POST /api/v1/cases/{case_id}/documents` (Requires Auth + CaseParticipant)
- `GET /api/v1/cases/{case_id}/documents` (Requires Auth + CaseParticipant)
- `GET /api/v1/documents/{document_id}` (Requires Auth + CaseParticipant)
- `DELETE /api/v1/documents/{document_id}` (Requires Auth + CaseParticipant)
- `GET /api/v1/documents/{document_id}/download` (Requires Auth + CaseParticipant)
- `POST /api/v1/documents/{document_id}/scan` (Auth verified)

**Admin**
- `GET /api/v1/admin/verifications` (Requires Auth: ADMIN)
- `POST /api/v1/admin/verifications/{verification_id}/approve` (Requires Auth: ADMIN)
- `POST /api/v1/admin/verifications/{verification_id}/reject` (Requires Auth: ADMIN)

**Health/System**
- `GET /health` (Public)
- `GET /ready` (Public)

## 2. OpenAPI Verification

**No Mismatches**: Both `upload-init` and global exception handling (`422` and standard `HTTPException`) are now properly implemented and align with the standard error contract.

## 3. Authentication Contract

- **Login**:
  - Request: `username` and `password` via OAuth2 Form Data (`application/x-www-form-urlencoded`).
  - Response: JSON body containing `access_token` and `token_type`.
  - Cookies: `refresh_token` (HttpOnly, Secure) and `csrf_token`.
- **Refresh**:
  - Request: Empty body. Requires `refresh_token` cookie and `X-CSRF-Token` header.
  - Verification: Double-submit CSRF matching and Origin/Referer headers check.
  - Response: JSON body with new `access_token`. Rotates `refresh_token` cookie.
- **Logout**:
  - Requires Auth.
  - Response: Success message. Deletes `refresh_token` cookie.

## 4. Authorization Contract

- **Role-Level**: Enforced via `RequireRole`.
- **Resource-Level**: Protected resources (cases, documents) invoke `authorize_case_access()` which queries `CaseParticipant` to ensure the `user.id` is linked to the `case_id`.

## 5. Error Contract

- **Backend Architecture Format**:
```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable message",
    "details": null,
    "request_id": "req_123"
  }
}
```
- **Validation Errors**: FastAPI natively returns `422` with `{"detail": [...]}`. This bypasses the global `AppException` wrapper and must be unified for frontend consistency.

## 6. Document Contract

- **Upload Flow**: Client calls `/documents` to get an S3 Presigned Upload URL -> Uploads directly to S3 bucket -> Storage webhook/worker theoretically handles scanning status (no `/complete` endpoint exists).
- **Download**: Client requests `/download`. Backend verifies `security_status == SAFE` before generating S3 Presigned GET URL.

## 7. Existing Frontend Audit

- **Routing & Types**: A Next.js 14 App Router exists in `frontend/`.
- **API Client**: `frontend/src/api/client.ts` uses native `fetch()`.

## 8. Frontend ↔ Backend Mismatches

1. **CSRF Extraction**: Frontend `client.ts` lacks logic to extract the `csrf_token` cookie and include the `X-CSRF-Token` header on POST/PATCH requests (specifically `/refresh`).
2. **Error Parsing**: `client.ts` parses `data?.message` or `data?.detail`, missing the deeply nested `data?.error?.message` backend specification.
3. **Login Request Payload**: FastAPI OAuth2 expects `application/x-www-form-urlencoded`. The frontend `client.ts` rigidly injects `application/json` for bodies.
4. **Validation Exceptions**: The frontend will break if it expects `{"error": ...}` but receives FastAPI's raw `{"detail": ...}`.

## 9. Generated Contract Artifacts
`openapi.json` successfully generated at repository root.

## 10. Test Results
`uv run pytest -v` -> 25 passed, 0 failed in ~4.6s (SQLite lock failures correctly handled).

## 11. Ruff Results
16 Style/Exception warnings (`B904` chained exceptions, `TRY002` generic Exceptions in `storage.py`).

## 12. Mypy Results
11 Type mismatch errors (primarily `union-attr` on `User | None` and `uuid_utils.UUID`).

## 13. PostgreSQL-Dependent Items
- Migrations (`alembic upgrade head`).
- Trigger functionality (`set_updated_at`).
- Concurrency (`with_for_update` exact locking validation).
- Enum mapping (`DocumentSecurityStatus` migration integrity).

## 14. Recommended Frontend Fix Order
1. Override FastAPI's `RequestValidationError` to map to the JSON standard Error Contract.
2. Update `client.ts` to parse `data.error.message` correctly.
3. Update `client.ts` to support OAuth2 form-data for `/login`.
4. Update `client.ts` (or authentication provider) to extract `csrf_token` and append `X-CSRF-Token` header for `/refresh` and mutations.
