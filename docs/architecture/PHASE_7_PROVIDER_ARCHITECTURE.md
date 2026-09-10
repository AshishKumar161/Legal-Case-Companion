# Phase 7: Provider Architecture & Infrastructure Hardening

## 1. Architectural Principles & Domain Decoupling

In accordance with Phase 7 requirements, Legal Case Companion (LCC) enforces strict decoupling between high-level business/domain logic and low-level third-party SDKs. Domain services interact strictly with abstract protocols rather than concrete vendor clients:

```
┌─────────────────────────────────────────────────────────────┐
│                       DOMAIN SERVICES                       │
│ (DocumentService, VideoMeetingService, PaymentService, etc.) │
└──────────────────────────────┬──────────────────────────────┘
                               │ (calls abstract protocols)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                     PROVIDER INTERFACES                     │
│  - StorageProvider        - VideoMeetingProvider             │
│  - PaymentProvider        - EmailProvider                   │
│  - RecordingStorageProvider                                 │
└──────────────┬──────────────────────────────┬───────────────┘
               │ (Production)                 │ (Dev / Test)
               ▼                              ▼
┌─────────────────────────────┐┌──────────────────────────────┐
│     CONCRETE PRODUCTION     ││       DETERMINISTIC          │
│          PROVIDERS          ││        TEST / MOCK           │
│ - S3StorageProvider         ││ - LocalMockStorageProvider   │
│ - S3RecordingStorageProvider││ - LocalRecordingStorage      │
│ - LiveKitMeetingProvider    ││ - MockVideoMeetingProvider   │
│ - StripePaymentProvider     ││ - MockPaymentProvider        │
│ - SMTPEmailProvider         ││ - ConsoleEmailProvider       │
│ - SendGridEmailProvider     ││                              │
│ - SESEmailProvider          ││                              │
└──────────────┬──────────────┘└──────────────────────────────┘
               │
               ▼
┌─────────────────────────────┐
│    EXTERNAL VENDOR SDKS     │
│  (boto3, stripe, jwt, etc.) │
└─────────────────────────────┘
```

---

## 2. Canonical Interfaces & Implementation Contracts

### 2.1 Object Storage (`app/core/storage.py`)
- **Protocol**: `StorageProvider`
  - `generate_presigned_upload_url(object_key: str, mime_type: str, expires_in: int) -> str`
  - `generate_presigned_download_url(object_key: str, expires_in: int, ...) -> str`
  - `delete_object(object_key: str) -> bool`
  - `get_object_bytes(object_key: str) -> bytes | None`
  - `put_object_bytes(object_key: str, data: bytes, mime_type: str) -> bool`
  - `object_exists(object_key: str) -> bool`
- **Path Traversal & Key Validation**: Every method executes `validate_storage_object_key(object_key)` before calling storage routines. Rejects directory traversal (`..`), query parameters (`?`), fragments (`#`), control characters (`\x00-\x1f`), absolute paths, and keys > 1024 chars.
- **Mock Fidelity**: `LocalMockStorageProvider` provisions valid typed placeholder bytes on presigned upload generation and verifies actual dictionary membership in `object_exists()`, guaranteeing zero unconditional success bypasses.

### 2.2 Recording Storage (`app/services/recording_storage.py`)
- **Protocol**: `RecordingStorageProvider`
  - `save_recording(consultation_id, recording_id, file_source, extension) -> (storage_path, bytes, sha256)`
  - `get_recording_path(storage_path) -> Path`
  - `recording_exists(storage_path) -> bool`
  - `delete_recording(storage_path) -> bool`
  - `get_file_size(storage_path) -> int`
- **Path Traversal Protection**: Both `LocalRecordingStorageProvider` and `S3RecordingStorageProvider` enforce directory namespace isolation (`consultations/`) and reject traversal attempts.

### 2.3 Video & Consultation Meetings (`app/services/video_meeting_service.py`)
- **Protocol**: `VideoMeetingProvider`
  - `create_meeting_room(consultation: Consultation) -> dict[str, Any]`
  - `generate_access_token(user: User, meeting: VideoMeeting, role: str, expires_in_seconds: int) -> str`
  - `verify_access_token(token: str, ...) -> dict[str, Any]`
- **Production Provider**: `LiveKitMeetingProvider` using JWT HS256 tokens bounded to 3600 seconds, strictly verifying room ID, consultation ID, user ID, and participant role.
- **Development/Fallback**: `InternalWebRTCMeetingProvider` using HMAC-SHA256 tokens with RFC 5766 CoTURN ephemeral credentials.

### 2.4 Payments & Refunds (`app/services/payment_service.py`)
- **Protocol**: `PaymentProvider`
  - `create_payment_intent(amount, currency, payment_id, idempotency_key) -> (client_secret, provider_id)`
  - `retrieve_payment_intent(provider_payment_id) -> dict[str, Any]`
  - `create_refund(provider_payment_id, amount, idempotency_key) -> dict[str, Any]`
- **Idempotency**: All payment intent creations and refunds inject deterministic idempotency keys (`lcc_pi_{id}`, `lcc_rfd_{id}`) to prevent duplicate charges or double refunds.

### 2.5 Email Communications (`app/services/email_service.py`)
- **Protocol**: `EmailProvider`
  - `send_email(to_email: str, subject: str, html_body: str) -> bool`
- **CRLF Injection Defense**: All concrete implementations validate `validate_email_recipient()` and `sanitize_email_subject()` to reject `\r` and `\n` control characters, eliminating header injection.

---

## 3. Environment Gating & Fail-Fast Guarantees

LCC strictly isolates development and testing behavior from production and staging environments:

| Environment | Mock Fallback Permitted? | Insecure Credentials Permitted? | Failure Mode |
| :--- | :--- | :--- | :--- |
| **Development** | YES (`LocalMockStorage`, `ConsoleEmail`, `MockPayment`) | YES (Local defaults: `"devkey"`, `"secret"`) | Graceful degradation to local mocks |
| **Testing** | YES (Deterministic in-memory mocks) | YES (Test secrets) | Deterministic in-memory execution |
| **Staging** | **NO** | **NO** | **Fail Fast (`ConfigurationError`)** |
| **Production** | **NO** | **NO** | **Fail Fast (`ConfigurationError`)** |

---

## 4. Timeout & Retry Policies

All external calls have strictly bounded connect and read timeouts to prevent worker starvation:

- **Boto3 (S3, SES)**:
  - `connect_timeout`: 5.0 seconds
  - `read_timeout`: 15.0 - 30.0 seconds
  - `max_attempts`: 3 (exponential backoff)
- **HTTP Client (httpx - SendGrid, Google OAuth)**:
  - `timeout`: 10.0 seconds total
  - Transient network error catching with normalized exception translation
- **SMTP Client**:
  - `timeout`: 10.0 seconds on socket operations
- **Redis Client**:
  - `socket_connect_timeout`: 2.0 seconds
  - `socket_timeout`: 2.0 seconds
