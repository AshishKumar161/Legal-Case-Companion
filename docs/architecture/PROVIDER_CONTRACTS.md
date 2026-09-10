# Provider Contracts Specification

This document formally specifies the behavioral contracts, interface invariants, expected errors, and compliance criteria for all external provider integrations across the Legal Case Companion (LCC) platform.

---

## 1. Storage Provider Contract (`StorageProvider`)

Implemented by:
- `S3StorageProvider` (Production / Staging)
- `LocalMockStorageProvider` (Development / Testing)

### Contract Invariants:
1. **Object Key Integrity**:
   - Must validate key with `validate_storage_object_key()`.
   - Must reject path traversal (`..`), absolute paths (`/`, `\`, Windows drive letters), control characters, and query/fragment characters (`?`, `#`).
   - Must reject empty strings or keys exceeding 1024 characters with `ValidationError`.
2. **Deterministic Existence State**:
   - `object_exists(object_key: str) -> bool` must accurately report whether the object is stored.
   - Must return `False` for non-existent or deleted objects.
3. **Download & Upload Presigning**:
   - Must return a valid URL string with properly encoded object key query parameters.
   - Presigned upload URLs must enforce bounded expiration (`expires_in`).
4. **Binary Retrieval & Deletion**:
   - `get_object_bytes(key)` must return `bytes` if the object exists, or `None` if absent.
   - `delete_object(key)` must remove the object and return `True` on successful deletion.

---

## 2. Recording Storage Provider Contract (`RecordingStorageProvider`)

Implemented by:
- `S3RecordingStorageProvider` (Production / Staging)
- `LocalRecordingStorageProvider` (Development / Testing)

### Contract Invariants:
1. **Namespace Isolation**:
   - Every recording must be stored under the `consultations/` namespace.
   - Object path structure: `consultations/{consultation_id}/{recording_id}.{extension}`.
2. **Integrity & Checksum**:
   - `save_recording(...)` must calculate and return SHA-256 checksum and total byte size.
3. **Path Traversal Guards**:
   - Direct filesystem paths or S3 keys attempting to escape the base directory must raise `ValidationError`.

---

## 3. Video Meeting Provider Contract (`VideoMeetingProvider`)

Implemented by:
- `LiveKitMeetingProvider` (Production / Staging)
- `InternalWebRTCMeetingProvider` (Development / Internal Fallback)
- `MockVideoMeetingProvider` (Testing)

### Contract Invariants:
1. **Room Generation**:
   - `create_meeting_room(consultation)` must return a dictionary containing a unique `room_id` and valid `ice_servers`.
2. **Access Token Generation**:
   - `generate_access_token(user, meeting, role, expires_in_seconds)` must return a cryptographically signed token bound to the specific room, user, consultation, and role.
   - Tokens must have bounded expiration (default: 3600 seconds).
3. **Access Token Verification**:
   - `verify_access_token(token, ...)` must verify the cryptographic signature and validate contextual bindings (`expected_room_id`, `expected_user_id`, `expected_consultation_id`, `expected_role`).
   - Expired or tampered tokens must raise `ValidationError`.
4. **Environment Isolation**:
   - Production/staging must prohibit default credentials (`"devkey"`, `"secret"`), raising `ConfigurationError`.

---

## 4. Payment Provider Contract (`PaymentProvider`)

Implemented by:
- `StripePaymentProvider` (Production / Staging)
- `MockPaymentProvider` (Development / Testing)

### Contract Invariants:
1. **Server-Side Intent Creation**:
   - `create_payment_intent(amount, currency, payment_id, idempotency_key)` must create an intent and return `(client_secret, provider_id)`.
   - Must use the provided `idempotency_key` to guarantee at-most-once creation.
2. **Intent Retrieval**:
   - `retrieve_payment_intent(provider_payment_id)` must fetch current provider intent state.
3. **Refund Processing**:
   - `create_refund(provider_payment_id, amount, idempotency_key)` must execute an idempotent refund with the gateway.
4. **Webhook Processing**:
   - Signature verification must be performed before any domain state mutation.
   - Webhooks must enforce timestamp replay protection (tolerance `<= 300` seconds) and deduplication via `ProcessedWebhookEvent`.

---

## 5. Email Provider Contract (`EmailProvider`)

Implemented by:
- `SMTPEmailProvider` (Production / Staging)
- `SendGridEmailProvider` (Production / Staging)
- `SESEmailProvider` (Production / Staging)
- `ConsoleEmailProvider` (Development)

### Contract Invariants:
1. **Header Injection Defense**:
   - `to_email` must pass `validate_email_recipient()`, rejecting any CRLF characters (`\r`, `\n`).
   - `subject` must pass `sanitize_email_subject()`, rejecting any CRLF characters (`\r`, `\n`).
2. **Bounded Execution**:
   - Sockets and HTTP connections must have an explicit 10.0-second timeout.
3. **Environment Isolation**:
   - `ConsoleEmailProvider` is strictly forbidden in production and staging environments.
