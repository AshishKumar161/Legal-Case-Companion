STATUS: FINAL (API Architecture Conventions) / DECISION REQUIRED (Product-specific API fields)

AUTHORITY: DERIVED FROM PROJECT SOURCE OF TRUTH

SOURCE DOCUMENTS:
- docs/00_PROJECT_CONTEXT.md
- docs/01_SYSTEM_ARCHITECTURE.md
- docs/02_DATABASE_DESIGN.md
- docs/04_AUTHORIZATION_SECURITY.md

IMPLEMENTATION STATUS: NOT STARTED

# API Specification & Contract

## 1. API VERSIONING
**FINAL:** The API uses a single, global versioning strategy in the URL path.
- **Path format:** `/api/v1/...`
- **Backward compatibility:** Additions (new fields, new endpoints) are allowed within v1. Breaking changes (removing fields, changing types) require a new version (e.g., v2).
- **Deprecation:** Endpoints to be deprecated must include an `X-API-Deprecation-Date` header before removal.

## 2. BASE RESOURCE CONVENTIONS
**FINAL:** Resources are represented using plural nouns. Action-style URLs are avoided unless an operation genuinely represents a state transition or action (e.g., login, complete).
- Examples: `/api/v1/cases`, `/api/v1/documents`, `/api/v1/users`
- Action exception: `/api/v1/auth/login`

## 3. ERROR FORMAT & HTTP STATUS CODES
**FINAL:** All API errors must return a standardized JSON structure.
```json
{
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "The requested resource could not be found.",
    "details": null,
    "request_id": "req_123456789"
  }
}
```
**Status Codes:**
- **200 OK:** Successful GET/PUT/PATCH.
- **201 Created:** Successful POST.
- **202 Accepted:** Asynchronous processing started.
- **204 No Content:** Successful DELETE.
- **400 Bad Request:** Malformed request.
- **401 Unauthorized:** Missing or invalid authentication token.
- **403 Forbidden:** Authenticated, but insufficient permissions.
- **404 Not Found:** Resource does not exist or user lacks permission to know it exists (to prevent enumeration).
- **409 Conflict:** State conflict or idempotency conflict.
- **422 Unprocessable Entity:** Validation failure.
- **429 Too Many Requests:** Rate limit exceeded.
- **500 Internal Server Error:** Unexpected failure. Stack traces must NEVER be exposed.

## 4. PAGINATION, FILTERING, & SORTING
**FINAL:**
- **Pagination Strategy:** Cursor-based pagination is the standard for large or mutable collections.
  - Request: `?page_size=20&cursor=abc123_uuid`
  - Response payload includes: `items` (array), `next_cursor` (string/null), `has_more` (boolean).
  - Exception: Simple admin lists or static reference data may use offset pagination.
- **Filtering & Sorting:** Uses standardized query parameters.
  - Filters: `?status=OPEN`, `?role=LAWYER`, `?created_before=2024-01-01T00:00:00Z`
  - Sorting: `?sort=created_at&order=desc`
- **Search:** Domain-specific (e.g., `GET /api/v1/lawyers?search=taxes`). No arbitrary/global full-text database expressions.

## 5. IDEMPOTENCY
**FINAL:** Idempotency is required for state-mutating operations prone to network retries (e.g., payments, bookings).
- **Header:** `Idempotency-Key: <UUID>`
- **Behavior:** If a request is received with an existing idempotency key, the backend returns the cached original 2xx/4xx response without re-executing the logic.
- **Scope:** Required on `POST /api/v1/consultations`, `POST /api/v1/consultations/{id}/payments`, and Webhooks.

## 6. AUTHORIZATION REQUIREMENTS
**FINAL:** Every protected resource endpoint must explicitly document its authentication, role, and resource authorization requirements. The API must **never** rely on UUID unguessability for authorization. 
- Example: Accessing a Case requires the user's `User.id` to have an active `CaseParticipant` link to the `case_id`.

## 7. AUTHENTICATION API
- `POST /api/v1/auth/register` (Public)
- `POST /api/v1/auth/login` (Public, returns JWT access token in body, refresh token in HttpOnly cookie)
- `POST /api/v1/auth/refresh` (Requires valid HttpOnly refresh cookie)
- `POST /api/v1/auth/logout` (Requires Auth, revokes current session)
- `POST /api/v1/auth/logout-all` (Requires Auth, revokes all sessions)
- `GET /api/v1/auth/me` (Requires Auth)
- `POST /api/v1/auth/password-reset/request` (Public)
- `POST /api/v1/auth/password-reset/confirm` (Public)
- `GET /api/v1/auth/sessions` (Requires Auth)
- `DELETE /api/v1/auth/sessions/{session_id}` (Requires Auth, cannot delete current session)

## 8. USER & PROFILE API
- `GET /api/v1/client-profile` / `PATCH /api/v1/client-profile` (Requires Auth: CLIENT)
- `GET /api/v1/lawyer-profile` / `PATCH /api/v1/lawyer-profile` (Requires Auth: LAWYER)
*Note: Clients/Lawyers can NEVER modify `role`, `account_status`, `verification_status`, or audit fields via these endpoints.*

## 9. LAWYER DISCOVERY & VERIFICATION API
- `GET /api/v1/lawyers` (Requires Auth. Search & filter by `location`, `practice_area`, `search` keywords, `min_fee`, `max_fee`, `verified_only`, with pagination. Excludes sensitive data.)
- `GET /api/v1/lawyers/{user_id}` (Requires Auth. Returns safe public profile. Inactive/suspended returns 404.)
- `POST /api/v1/profiles/lawyer/verification` (Requires Auth: LAWYER. Submits Bar Council enrollment details.)
- `GET /api/v1/admin/verifications` (Requires Auth: ADMIN. Lists pending verification requests.)
- `POST /api/v1/admin/verifications/{verification_id}/approve` (Requires Auth: ADMIN. Approves lawyer verification.)
- `POST /api/v1/admin/verifications/{verification_id}/reject` (Requires Auth: ADMIN. Rejects lawyer verification.)

## 10. CASE & WORKSPACE API
- `POST /api/v1/cases` (Requires Auth: CLIENT/OWNER)
- `GET /api/v1/cases` (Requires Auth. Supports `status`, `search`, `created_after`, `created_before`, `skip`, `limit`)
- `GET /api/v1/cases/{case_id}` (Requires Auth & CaseParticipant link)
- `PATCH /api/v1/cases/{case_id}` (Requires Auth: CLIENT/OWNER. Validates lifecycle transitions)
- `DELETE /api/v1/cases/{case_id}` (Requires Auth: CLIENT/OWNER. Soft-deletes case)
- `GET /api/v1/cases/{case_id}/workspace` (Unified workspace: case details, permissions, participants, lawyer profile, document count, task summary, deadlines, notes count, recent timeline)

**Participants:**
- `GET /api/v1/cases/{case_id}/participants`
- `POST /api/v1/cases/{case_id}/participants` (Assigns participant / LAWYER with role validation)
- `PATCH /api/v1/cases/{case_id}/participants/{user_id}` (Updates role, prevents demoting final owner)
- `DELETE /api/v1/cases/{case_id}/participants/{user_id}` (Revokes access, prevents removing final owner)

**Timeline:**
- `GET /api/v1/cases/{case_id}/timeline` (System-generated chronological audit timeline)

**Tasks:**
- `POST /api/v1/cases/{case_id}/tasks` (Creates task with priority, due date, participant assignment)
- `GET /api/v1/cases/{case_id}/tasks` (Lists tasks with optional status and owner filters)
- `GET /api/v1/cases/{case_id}/tasks/{task_id}` (Retrieves task by ID)
- `PATCH /api/v1/cases/{case_id}/tasks/{task_id}` (Updates task, automatically sets `completed_at` on completion)
- `DELETE /api/v1/cases/{case_id}/tasks/{task_id}` (Soft-deletes task)

**Notes:**
- `POST /api/v1/cases/{case_id}/notes` (Creates matter note; supports private author-only notes)
- `GET /api/v1/cases/{case_id}/notes` (Lists public notes + author's own private notes)
- `GET /api/v1/cases/{case_id}/notes/{note_id}` (Gets note by ID with privacy boundary)
- `PATCH /api/v1/cases/{case_id}/notes/{note_id}` (Updates note by author or case owner)
- `DELETE /api/v1/cases/{case_id}/notes/{note_id}` (Soft-deletes note by author or case owner)

## 11. DOCUMENT API (PRESIGNED S3 FLOW)
**FINAL FLOW:**
1. `POST /api/v1/cases/{case_id}/documents/upload-init` (Auth & CaseParticipant required. Returns short-lived S3 upload URL for quarantine bucket).
2. Client uploads directly to S3.
3. `POST /api/v1/documents/{document_id}/complete` (Backend verifies S3 object exists, updates status to `VALIDATING`/`SCANNING`).
4. Webhooks/Workers process scan.
5. `GET /api/v1/cases/{case_id}/documents` (Lists documents. AI/RAG access strictly blocked unless `status == SAFE`).
6. `GET /api/v1/documents/{document_id}/download` (Auth & CaseParticipant required. Returns short-lived S3 GET URL).

## 12. CONSULTATION & PAYMENT API
**Consultations:**
- `POST /api/v1/consultations` (Requires Auth: CLIENT. Requests consultation with verified lawyer)
- `POST /api/v1/cases/{case_id}/consultations` (Requires Auth: CLIENT. Requests consultation linked directly to case)
- `GET /api/v1/consultations` (Requires Auth. Supports `case_id`, `status`, `skip`, `limit`)
- `GET /api/v1/cases/{case_id}/consultations` (Requires Auth: Case participant. Lists case consultations)
- `GET /api/v1/consultations/{consultation_id}` (Requires Auth: Client, assigned Lawyer, or Admin)
- `POST /api/v1/consultations/{consultation_id}/accept` (Requires Auth: Assigned LAWYER)
- `POST /api/v1/consultations/{consultation_id}/reject` (Requires Auth: Assigned LAWYER. Supports rejection `reason`)
- `POST /api/v1/consultations/{consultation_id}/schedule` (Requires Auth: Client or assigned Lawyer. Updates time & sets `SCHEDULED`)
- `POST /api/v1/consultations/{consultation_id}/confirm` (Requires Auth: Assigned LAWYER. Backwards compatible confirm/schedule)
- `POST /api/v1/consultations/{consultation_id}/cancel` (Requires Auth: Client, assigned Lawyer, or Admin. Supports cancel `reason`)
- `POST /api/v1/consultations/{consultation_id}/complete` (Requires Auth: Assigned Lawyer or Admin. Sets `completed_at` timestamp)
- `POST /api/v1/consultations/{consultation_id}/payments` (Requires Auth: CLIENT. Creates PaymentIntent)
- `POST /api/v1/consultations/{consultation_id}/messages` (Requires Auth: Consultation participants)
- `GET /api/v1/consultations/{consultation_id}/messages` (Requires Auth: Consultation participants)

**Payments:**
- `GET /api/v1/payments/{payment_id}` (Requires Auth: Payer or Admin)
- `GET /api/v1/consultations/{consultation_id}/payments` (Requires Auth: Consultation participants)
- `POST /api/v1/payments/webhooks/stripe` (Public with `Stripe-Signature` validation. Idempotent webhook handler)

## 13. NOTIFICATIONS API
- `GET /api/v1/notifications` (Requires Auth. Supports `is_read`, `skip`, `limit`)
- `GET /api/v1/notifications/unread-count` (Requires Auth. Returns `unread_count`)
- `POST /api/v1/notifications/{notification_id}/read` (Requires Auth: Notification recipient)
- `POST /api/v1/notifications/{notification_id}/unread` (Requires Auth: Notification recipient)
- `POST /api/v1/notifications/read-all` (Requires Auth. Marks all user notifications as read)
- `DELETE /api/v1/notifications/{notification_id}` (Requires Auth: Notification recipient. Soft-deletes)

## 14. ADMIN, AUDIT, & AI APIs
- **Admin:** Explicitly scoped endpoints (e.g., `POST /api/v1/admin/lawyer-verifications/{verification_id}/approve`). No generic "/admin/everything". Requires ADMIN role.
- **Audit:** `GET /api/v1/admin/audit-events`. Restricted to specific Admin scopes. Secrets never exposed.
- **AI:** `POST /api/v1/cases/{case_id}/ai/sessions`. Must authenticate, authorize case via CaseParticipant, retrieve ONLY `SAFE` authorized documents, and use explicit context.

## 14. DECISION REQUIRED ITEMS
The following are unresolved product decisions:
- Exact video provider integration for Consultations.
- Exact payment provider (e.g., Stripe, Razorpay) and webhook schemas.
- Exact notification provider and delivery API.
- Detailed AI prompt structures and message tracking schema.
- MFA implementation details (if/when implemented).

## Pagination & Phase 5 Updates

All list endpoints (\GET /cases\, \GET /cases/{case_id}/timeline\, \GET /admin/verifications\) now support pagination via \skip\ and \limit\ query parameters, returning a standardized \PaginatedResponse\ structure:

\\\json
{
  \
items\: [],
  \total\: 0,
  \skip\: 0,
  \limit\: 20
}
\\\

## Admin Verification Endpoints

- \GET /api/v1/admin/verifications\: Fetch pending LawyerVerification profiles (Requires ADMIN)
- \POST /api/v1/admin/verifications/{id}/approve\: Approves verification and logs VERIFICATION_APPROVED event.
- \POST /api/v1/admin/verifications/{id}/reject\: Rejects verification and logs VERIFICATION_REJECTED event.

## 15. NATIVE VIDEO & RECORDING APIs

- `GET /api/v1/consultations/{consultation_id}/video/join`: Generates role-scoped, room-scoped video access token. (Requires Auth: Participant)
- `GET /api/v1/consultations/{consultation_id}/video/ice-servers`: Returns STUN/TURN traversal configurations. (Requires Auth: Participant)
- `GET /api/v1/consultations/{consultation_id}/video/ws?token={video_token}`: Bidirectional WebSocket signaling relay for SDP offers, answers, ICE candidates, ephemeral in-meeting chat, and media toggles.
- `GET /api/v1/consultations/{consultation_id}/video/recording/consent-status`: Returns dual-consent status for client and lawyer. (Requires Auth: Participant)
- `POST /api/v1/consultations/{consultation_id}/video/recording/consent`: Grants or revokes participant recording consent. (Requires Auth: Participant)
- `POST /api/v1/consultations/{consultation_id}/video/recording/start`: Starts recording session. Fails if mutual consent is absent. (Requires Auth: Participant)
- `POST /api/v1/consultations/{consultation_id}/video/recording/stop`: Stops active recording session and transitions to UPLOADING. (Requires Auth: Participant)
- `POST /api/v1/consultations/{consultation_id}/video/recording/upload`: Streams raw binary recording into local storage, computes SHA-256 checksum, and marks status as AVAILABLE. (Requires Auth: Participant)
- `GET /api/v1/consultations/{consultation_id}/recordings`: Lists all finalized recordings for the consultation. (Requires Auth: Participant)
- `POST /api/v1/recordings/{recording_id}/playback-ticket`: Exchanges bearer authentication for an ephemeral, 60-second media ticket. (Requires Auth: Participant)
- `GET /api/v1/recordings/{recording_id}/play`: Authenticated HTTP 206 range-streaming playback endpoint. Accepts `Authorization: Bearer` or `?ticket=`. Query parameter `?token=` is strictly rejected with 401. Serves non-caching security headers.

