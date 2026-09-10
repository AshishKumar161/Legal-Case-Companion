# Phase 7: Complete Provider Inventory

This inventory documents all external integrations and infrastructure providers across the Legal Case Companion (LCC) repository, specifying their interface abstractions, concrete implementations, configuration parameters, authentication schemes, timeout/retry bounds, idempotency guarantees, error normalization, logging rules, test coverage, and lifecycle classification.

---

## 1. Provider Inventory Matrix

| Provider | Interface | Implementation | Configuration | Environment | Authentication | Timeout | Retry Policy | Idempotency | Webhooks | Error Handling | Logging | Test Implementation | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Object Storage (S3)** | `StorageProvider` (`app/core/storage.py`) | `S3StorageProvider` | `AWS_S3_BUCKET_NAME`, `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | Production, Staging | AWS SigV4 / IAM default credential chain | Connect: 5s, Read: 15s | Botocore max 3 attempts | Key path hashing & idempotency | N/A | `ClientError` caught, logged, re-raised safely | Object key & sanitized path (no secrets) | `LocalMockStorageProvider` | **KEEP** |
| **Mock Storage** | `StorageProvider` (`app/core/storage.py`) | `LocalMockStorageProvider` | In-memory `_storage_data` dictionary | Development, Testing | None (Internal mock routes require non-prod env) | Instant / local | None | Key-based in-memory overwrites | N/A | Safe key validation, `ValidationError` | Safe key logging | In-memory fixture & `/mock-storage/*` routes | **KEEP** |
| **Recording Storage (S3)** | `RecordingStorageProvider` (`app/services/recording_storage.py`) | `S3RecordingStorageProvider` | `AWS_S3_BUCKET_NAME`, `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | Production, Staging | AWS SigV4 / IAM default credential chain | Connect: 5s, Read: 30s | Botocore max 3 attempts | Deterministic S3 key (`consultations/{id}/{rec_id}.ext`) | N/A | Bounded exception logging, `ResourceNotFoundError` | Key namespace & payload byte count | `LocalRecordingStorageProvider` | **KEEP** |
| **Local Recording Storage** | `RecordingStorageProvider` (`app/services/recording_storage.py`) | `LocalRecordingStorageProvider` | `LOCAL_RECORDING_STORAGE_PATH` | Development, Testing | Filesystem permissions | OS filesystem I/O | None | Path normalization & collision check | N/A | Path traversal validation (`ValidationError`) | Absolute path masked, size & checksum logged | Real disk tempdir fixtures | **KEEP** |
| **Video SFU (LiveKit)** | `VideoMeetingProvider` (`app/services/video_meeting_service.py`) | `LiveKitMeetingProvider` | `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` | Production, Staging | JWT HMAC-SHA256 (`api_key` issuer, `api_secret` signing) | Explicit token TTL (1-2 hours) | Transient retry on room connect | Room ID deterministic generation | Room events webhook (if configured) | `ValidationError` on token tampering / expiration | Room ID, user ID, participant role | `MockVideoMeetingProvider` & `InternalWebRTCMeetingProvider` | **KEEP** |
| **Video P2P (Internal WebRTC)** | `VideoMeetingProvider` (`app/services/video_meeting_service.py`) | `InternalWebRTCMeetingProvider` | `CSRF_SECRET_KEY`, `JWT_PRIVATE_KEY`, `TURN_SERVER_URL`, `TURN_STATIC_AUTH_SECRET` | Development, Fallback | HMAC-SHA256 cryptographic join token + RFC 5766 CoTURN ephemeral credentials | Token expiration (120 mins) | Reconnect ICE gathering | Cryptographic nonce / UUIDv7 jti | None | Cryptographic signature validation | User ID, consultation ID, role | `InternalWebRTCMeetingProvider` | **KEEP** |
| **Mock Video Provider** | `VideoMeetingProvider` (`app/services/video_meeting_service.py`) | `MockVideoMeetingProvider` | None | Development, Testing | Prefix token validation (`mock_token_*`) | Instant | None | Deterministic mock room ID | None | `ValidationError` on invalid token | Mock room ID | Unit test fixtures | **KEEP** |
| **Payment Gateway (Stripe)** | `PaymentProvider` (`app/services/payment_service.py`) | `StripePaymentProvider` | `STRIPE_API_KEY`, `STRIPE_WEBHOOK_SECRET` | Production, Staging | Bearer API Key, `Idempotency-Key` HTTP header | 10.0s HTTP client timeout | Bounded transient retries with idempotency keys | `Idempotency-Key` header (`lcc_pi_*`, `lcc_rfd_*`) | `/api/v1/webhooks/stripe` (HMAC-SHA256 timestamped) | Normalized exceptions (`ValidationError`, `AuthorizationError`) | Transaction IDs, payment IDs, amounts (no PAN/CVV) | `MockPaymentProvider` | **KEEP** |
| **Mock Payment Provider** | `PaymentProvider` (`app/services/payment_service.py`) | `MockPaymentProvider` | In-memory `_intents` and `_refunds` | Development, Testing | In-memory test state | Instant | None | Idempotency key tracking in state dict | Simulated webhook injection | Deterministic validation | Payment ID, simulated amounts | State assertion fixtures | **KEEP** |
| **Email (SMTP)** | `EmailProvider` (`app/services/email_service.py`) | `SMTPEmailProvider` | `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_TLS`, `SMTP_SSL`, `EMAIL_FROM` | Production, Staging | Username & Password over TLS/SSL | Connect/Socket: 10.0s | Up to 3 bounded retries | Nonce / Message-ID binding | N/A | SMTPServerDisconnected / SMTPException logged | Recipient address, subject, status (no credentials) | `ConsoleEmailProvider` | **KEEP** |
| **Email (SendGrid)** | `EmailProvider` (`app/services/email_service.py`) | `SendGridEmailProvider` | `SENDGRID_API_KEY`, `EMAIL_FROM` | Production, Staging | Bearer API Token | HTTP: 10.0s (`httpx`) | Bounded transient retries | Idempotent message generation | N/A | Status code evaluation (200, 201, 202) | Recipient, subject, status | `ConsoleEmailProvider` | **KEEP** |
| **Email (AWS SES)** | `EmailProvider` (`app/services/email_service.py`) | `SESEmailProvider` | `AWS_REGION`, `SES_ACCESS_KEY_ID`, `SES_SECRET_ACCESS_KEY`, `EMAIL_FROM` | Production, Staging | AWS SigV4 / IAM credential chain | Connect: 5s, Read: 15s | Botocore max 3 attempts | Deterministic message delivery | N/A | ClientError normalized & logged | Recipient, subject, message ID | `ConsoleEmailProvider` | **KEEP** |
| **Console Email Provider** | `EmailProvider` (`app/services/email_service.py`) | `ConsoleEmailProvider` | None | Development, Local | None | Instant | None | Deterministic | N/A | CRLF injection validation | Terminal dispatch log | `ConsoleEmailProvider` | **KEEP** |
| **Google OAuth 2.0 / OIDC** | Implicit Google OIDC Flow (`app/services/google_oauth_service.py`) | `GoogleOAuthService` | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`, `GOOGLE_JWKS_URI` | All environments | OAuth 2.0 PKCE / Authorization Code + RS256 JWKS validation | HTTP: 10.0s (`httpx`) | Single retry on network failure | Cryptographic single-use `jti` in OAuth state | N/A | `AuthenticationError` on signature, audience, or issuer mismatch | Purpose, redirect URI, user ID (tokens never logged) | Mock JWKS / token override fixtures | **KEEP** |
| **Malware Webhook** | Webhook Router (`app/api/v1/webhooks.py`) | `aws_malware_webhook` | `AWS_WEBHOOK_SECRET` | Production, Staging, Dev | Bearer shared secret with constant-time `compare_digest` | 5.0s processing window | Idempotent scan result transition | Document state machine idempotency | `/api/v1/webhooks/aws/malware` | HTTP 401 Unauthorized / HTTP 500 | Document ID, scan outcome | Integration test fixtures | **KEEP** |
| **Redis Cache / Broker** | Redis Client (`app/core/redis.py`) | `RedisCache` | `REDIS_URL`, `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD` | Production, Staging, Dev | Redis AUTH / Password | Connect: 2s, Read/Write: 2s | 3 attempts with backoff | Atomic Redis transactions & distributed locks | N/A | `ConnectionError` handled with graceful in-memory fallback in dev | Connection status, latency (no secrets) | `MockRedisClient` | **KEEP** |

---

## 2. Classification Summary

- **KEEP (16)**:
  - `S3StorageProvider` & `LocalMockStorageProvider`
  - `S3RecordingStorageProvider` & `LocalRecordingStorageProvider`
  - `LiveKitMeetingProvider`, `InternalWebRTCMeetingProvider`, `MockVideoMeetingProvider`
  - `StripePaymentProvider` & `MockPaymentProvider`
  - `SMTPEmailProvider`, `SendGridEmailProvider`, `SESEmailProvider`, `ConsoleEmailProvider`
  - `GoogleOAuthService`
  - `aws_malware_webhook`
  - `RedisCache`
- **MERGE (0)**: No redundant provider duplicates detected.
- **REFACTOR (0)**: All required providers are cleanly abstracted behind domain protocols.
- **DEPRECATE (0)**: Obsolete development bypasses removed in Phase 7.
- **DELETE (0)**: Dead code cleared in prior stabilization phases.
- **UNKNOWN (0)**: Complete repository coverage verified.
