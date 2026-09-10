# Phase 8: API Integration & Full-Stack Contract Architecture

## 1. Overview & Architectural Principles

Phase 8 established a unified, canonical frontend API client layer that bridges the Next.js frontend with the FastAPI backend. Prior to this phase, components frequently issued raw `fetch()` requests, duplicate URL parameters, and ad-hoc header construction.

The canonical architecture adheres to five core tenets:
1. **Single Point of Egress**: Every HTTP request passes through `frontend/src/lib/api/client.ts` with centralized auth header injection, CSRF handling, timeout management, and unified error parsing.
2. **Server-Authoritative Data Models**: TypeScript interfaces directly reflect backend Pydantic models. Enums (such as `CaseStatus`, `ParticipantRole`, `ConsultationStatus`) are strict subsets/supersets that avoid serialization drift.
3. **Idempotent Mutations**: Financial transactions, booking requests, and file uploads include client-generated UUIDv4/UUIDv7 idempotency keys.
4. **Resilient Error Envelopes**: HTTP errors (400, 401, 403, 404, 422, 429, 500) parse into typed `ApiError` structures containing human-friendly error messages without leaking stack traces.
5. **Session Isolation**: Authentication tokens are isolated to individual browser tabs via `sessionStorage` with UUID tab identifiers.

---

## 2. Canonical Domain Clients (`frontend/src/lib/api/`)

```
frontend/src/lib/api/
├── client.ts         # Axios/Fetch wrapper, token interceptor, blob download, ApiError class
├── auth.ts           # Login, Register, Logout, /me, OTP email verification, Refresh token
├── cases.ts          # Workspace, CRUD, Participants, Timeline events, Binary report streaming
├── documents.ts      # Presigned upload URLs, upload completion, consultation doc sharing
├── consultations.ts  # Scheduling, Reschedule, Cancel, Video Access-Status, Video Join, Reconnect
├── ai.ts             # Kanoon legal authority hybrid search, Copilot assistant streaming
├── payments.ts       # Payment intents with idempotency keys, Razorpay/test pay execution
├── verification.ts   # Advocate bar council queue, document review, approval/rejection
└── index.ts          # Canonical barrel export
```

### Key API Client Methods

| Module | Method | HTTP Route | Payload / Response | Contract Alignment |
|---|---|---|---|---|
| `auth` | `login()` | `POST /api/v1/auth/login` | `LoginCredentials` → `LoginResponse` | Verified access/refresh tokens |
| `auth` | `getMe()` | `GET /api/v1/auth/me` | None → `UserItem` | Authoritative user role & status |
| `cases` | `getWorkspace()` | `GET /api/v1/cases/{id}/workspace` | None → `CaseWorkspaceResponse` | Hydrates full 5-tab workspace |
| `cases` | `downloadReport()`| `GET /api/v1/cases/{id}/report` | `format: "markdown" \| "json"` → `Blob` | Streaming binary download |
| `documents` | `getPresignedUrl()`| `POST /api/v1/documents/upload-url`| `DocumentUploadInit` → `PresignedUrl` | Validates MIME & 50MB limit |
| `consultations`| `getAccessStatus()`| `GET /api/v1/consultations/{id}/video/access-status` | `bypass_time?: boolean` → `VideoRoomAccessStatusResponse` | UTC/IST countdown timing |
| `consultations`| `joinVideoMeeting()`| `GET /api/v1/consultations/{id}/video/join` | `bypass_time?: boolean` → `VideoJoinInfoResponse` | WebRTC credentials & ICE servers |
| `ai` | `searchLegalAuthorities()`| `POST /api/v1/legal-authorities/search`| `{query, top_k, search_mode}` → `SearchResults` | Kanoon hybrid search |
| `payments` | `createIntent()` | `POST /api/v1/payments/intent` | `PaymentIntentRequest` + Idempotency Key | Server determines fee |

---

## 3. Full-Stack Contract Testing (`tests/integration/test_phase_8_frontend_contracts.py`)

A dedicated pytest test suite was implemented to validate that the TypeScript client expectations strictly match FastAPI response envelopes:

```python
# Suite Summary: tests/integration/test_phase_8_frontend_contracts.py
class TestFrontendBackendContracts:
    def test_error_response_envelope_contract(self, client: TestClient): ...         # PASSED
    def test_auth_login_contract_matches_frontend_type(self, client: TestClient): ... # PASSED
    def test_case_workspace_contract_matches_frontend_type(self, client): ...       # PASSED
    def test_case_status_enums_contract(self): ...                                  # PASSED
    def test_participant_role_enums_contract(self): ...                             # PASSED
    def test_download_report_binary_blob_contract(self, client: TestClient): ...    # PASSED
    def test_legal_authorities_hybrid_search_contract(self, client: TestClient): ...# PASSED
    def test_consultation_video_join_contract(self, client: TestClient): ...        # PASSED
```

### Contract Alignments Resolved:
1. **CaseStatus Enums**: Frontend TypeScript `CaseItem['status']` union was missing `"CANCELLED"`. Added `"CANCELLED"` to align with backend `CaseStatus.CANCELLED`.
2. **Video Consultation Endpoints**: Frontend consultation client previously had legacy `getRoomToken` pointing to `/video/token`. Aligned with backend `/video/join` (returning `VideoJoinInfoResponse`) and `/video/access-status` (returning `VideoRoomAccessStatusResponse`).
3. **Report Downloads**: Verified binary streaming (`text/markdown` and `application/json` attachments) over `apiClient.blob()` with automatic browser download triggers.

---

## 4. Authentication & Isolated Session Lifecycle

### Tab-Scoped Session Isolation
To prevent role pollution when testing multiple personas (e.g. Advocate and Client simultaneously in adjacent tabs), tokens are scoped to individual tabs:
- Unique `tab_session_id` generated per browser tab and stored in `sessionStorage`.
- Token keys: `lcc_access_token_${tabId}` and `lcc_refresh_token_${tabId}`.
- Legacy `localStorage` tokens are actively purged on application bootstrap (`purgeLegacyGlobalStorage()`).

### Session Refresh & Expiry Handling
1. **Automated Pre-expiry Refresh**: If token expires within 2 minutes, `performTokenRefresh()` issues `POST /api/v1/auth/refresh` using the tab's refresh token.
2. **401 Unauthorized Interception**: Emits custom browser window event `lcc:session-expired:${tabId}`.
3. **Authoritative /me Hydration**: On application mount or navigation, `GET /api/v1/auth/me` verifies whether the account has been disabled, suspended, or had its role revoked.

---

## 5. Realtime WebSocket & WebRTC Integration

### Consultation Video Room Signaling
In `frontend/src/app/consultations/[id]/room/page.tsx`:
- **Join Authentication**: Cryptographic token issued by `/api/v1/consultations/{id}/video/join` is passed as query parameter `?token=...` to `wss://.../api/v1/consultations/{id}/video/ws`.
- **Signaling Messages**: Relays WebRTC `offer`, `answer`, `ice-candidate`, `chat`, and `screen-share` frames with payload size validation (capped at 64KB).
- **Heartbeat & Leak Prevention**: `pingIntervalRef` sends periodic ping frames. The interval is explicitly cleared in both `ws.onclose` and the `useEffect` unmount cleanup handler, preventing detached background timers.
- **Media Cleanup**: Local media tracks (`stream.getTracks()`) are stopped upon room exit to release camera and microphone hardware immediately.

---

## 6. File Uploads & Payment Integrity

### File Uploads
- Supported types: PDF, DOCX, PNG, JPG (maximum 50 MB).
- Security rule: Frontend checks MIME types for UX convenience, but relies strictly on server presigned URL generation, backend magic-byte verification, and asynchronous malware scanning.
- Progress reporting: Axios `onUploadProgress` updates visual progress bars.

### Commercial Payment Flows
- The frontend **never** calculates or overrides payment amounts. Consultation fees are fetched from the advocate's verified profile or server-computed order details.
- All checkout operations include a unique client idempotency key (`Idempotency-Key` header) to prevent duplicate charges on network retries.
