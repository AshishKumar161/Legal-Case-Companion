# Architecture Decision Register

## Database Identity Strategy

**Status:** FINAL

### Decisions
- **Primary key:** UUID
- **UUID version:** UUIDv7
- **UUID generation:** Application-generated
- **Implementation library:** Implementation detail, not part of this architectural decision
- **Foreign keys:** UUID
- **Default FK delete behavior:** ON DELETE RESTRICT
- **CASCADE:** Only for strictly dependent entities where explicitly justified
- **Public resource identifier:** Same UUID as the database primary key
- **Timestamps:** TIMESTAMPTZ
- **`created_at`:** PostgreSQL database-generated (server-side default)
- **`updated_at`:** PostgreSQL database-managed, using a database-side mechanism such as a trigger
- **Soft deletion:** Core legal/business entities use `deleted_at`
- **Hard deletion:** Only explicitly classified ephemeral/strictly dependent records
- **Audit fields:** `created_by`, `updated_by`, `deleted_by` where applicable
- **Audit history:** Separate append-only audit/event mechanism

### Security Principle
UUIDs reduce predictable sequential enumeration compared with sequential numeric identifiers, but UUIDs are not a security boundary and do not replace authorization. Every protected resource must enforce authentication, ownership validation, role checks, and resource-level authorization.
UUIDv7 identifiers must not be treated as secrets, authentication credentials, authorization tokens, or security capabilities.

### Impact
- **Database schema:** All PKs and FKs must use native UUID types.
- **API design:** URLs will expose UUIDs directly.
- **Authorization:** IDOR must be prevented by explicit resource-ownership checks.
- **Indexing:** UUIDv7 provides time-ordered identifiers and generally offers better B-tree insertion locality than fully random UUIDv4 identifiers for insertion-heavy workloads.
- **Migrations:** Alembic will generate UUID types, server-side defaults for `created_at`, and database triggers/mechanisms for `updated_at`.
- **Future implementation:** App-side generation of UUIDv7 allows SQLAlchemy to have IDs populated before flush, simplifying object relationships. SQLAlchemy `onupdate` is ORM/application behavior and does not satisfy the requirement for database-authoritative timestamps. A database-side mechanism such as a trigger must be implemented later. User soft deletion must not cascade-delete legal/business records. Audit logs remain append-only and are not deleted as part of normal lifecycle operations.

---

## Authentication & Security Strategy

**Status:** FINAL

### Decisions

**FINAL:**
- **Authentication model:** JWT access tokens with server-controlled opaque cryptographically random refresh-token sessions.
- **Password hashing:** Argon2id.
- **JWT signing algorithm:** EdDSA. (Preferred over RS256 for better performance and smaller key sizes).
- **Access-token TTL:** 15 minutes.
- **Refresh-token TTL:** Absolute lifetime 30 days, inactivity expiration 7 days.
- **Access-token architecture:** JWT with minimal claims (`sub`, `role`, `iss`, `aud`, `iat`, `exp`, `jti`). No mutable authorization state.
- **Refresh-token architecture:** Opaque token. Server stores a secure hash.
- **Refresh-token rotation:** Strict rotation on every use.
- **Refresh-token reuse detection:** Presentation of a revoked/used token revokes the entire token family/session and triggers a security event.
- **Refresh-token browser storage:** `HttpOnly` + `Secure` + `SameSite` cookie. `localStorage` is explicitly rejected.
- **CSRF mechanism:** Double-submit cookie pattern + Origin/Referer validation for the refresh endpoint.
- **Logout architecture:** Single-session (revoke family) and all-device (revoke all sessions).
- **Session model:** Session ID, user ID, token family ID, timestamps, and device/IP metadata.
- **Roles:** CLIENT, LAWYER, ADMIN.
- **MFA Policy:** Admin (Required), Lawyer (Recommended), Client (None initially). Sensitive operations require step-up authentication.
- **Resource-level authorization:** Mandatory RBAC + resource-level relationship checks. Knowing a UUID never grants access.
- **Client/lawyer isolation:** Clients access own data; lawyers access assigned cases via explicit mappings.
- **Document upload security:** Max size 10MB. Upload → quarantine → validate → malware scan → mark safe. Documents MUST NOT enter AI pipeline before validation.
- **Document security:** Private S3 bucket. Pre-signed URLs generated only AFTER authorization and safety validation succeeds. Raw objects never exposed.
- **Rate limiting:** Configurable via environment. Strict IP and account limits for login, registration, and APIs.
- **Audit security:** Append-only event logging for sensitive operations. No logging of passwords, tokens, or secrets.
- **Account lifecycle:** ACTIVE, SUSPENDED, SOFT_DELETED. Suspension/deletion revokes all sessions. Soft delete MUST NOT cascade to legal history.
- **Secrets management:** Environment variables / Render configuration. Never committed to source control.
- **AI security boundaries:** Retrieved legal documents are UNTRUSTED CONTENT (potential prompt injection). Authorization is enforced prior to context retrieval.

### Impact
- **Security:** Maximum protection against token theft, XSS, and CSRF vulnerabilities through strict token boundaries and HttpOnly cookies.
- **Infrastructure:** Requires malware scanning infrastructure and Redis/DB-backed session tracking and rate limiting.
- **Development:** Developers must implement double-submit CSRF and robust rate limiting middleware prior to handling business logic.

**DECISION REQUIRED:**
None.

---

## Domain Model Strategy

**Status:** FINAL

### Decisions

**FINAL:**
- **Core Entities:** `User`, `ClientProfile`, `LawyerProfile`, `LawyerVerification`, `Case`, `CaseParticipant`, `Document`, `Consultation`, `Payment`, `AuditEvent`, `RefreshTokenSession`, `CaseTimelineEvent`.
- **Rejected Entities:** `DocumentAccess` (Authorization derived from CaseParticipant), `DocumentVersion` (Not required for V1).
- **Proposed/Later Phase Entities:** AI models, Notifications, Tasks/Deadlines, LawyerAvailability.
- **Authorization:** Enforced via `CaseParticipant`.
- **Soft Deletion (`deleted_at`):** Strict application to `User`, `ClientProfile`, `LawyerProfile`, `Case`, `Document`, `Consultation`.
- **Immutable/Append-Only:** `AuditEvent`, `Payment`, `LawyerVerification`, `RefreshTokenSession`, `CaseTimelineEvent` MUST NOT be soft-deleted.

### Impact
- **Database Schema:** Defined the authoritative 12 core tables.
- **Development:** Developers have a strict blueprint for SQLAlchemy ORM models.

---

## ADR-004: Native In-App Video Meeting & Recording Architecture

**Status:** FINAL

### Context
Legal consultations between advocates and clients require high confidentiality, verified identities, privileged record-keeping, and compliance with Indian legal privacy norms. External tools (Google Meet, Zoom, MS Teams, external Jitsi) leak meeting metadata and lack unified BOLA protection, in-app audit trails, and dual-consent safeguards.

### Decisions
1. **Zero External Redirects**: The entire consultation workflow (negotiation, media, chat, notes, recording, playback) is strictly hosted natively within LCC.
2. **Deterministic Provider Policy**:
   - **Production**: LiveKit SFU is strictly required. Missing configuration raises `ConfigurationError`. Silent fallback to P2P is forbidden.
   - **Development/Test**: Internal WebRTC P2P mesh allowed.
3. **Multi-Tier Authorization Hierarchy**: Video infrastructure is never the source of authorization. LCC Identity Auth → Consultation BOLA Authorization → Meeting Token → Room/SFU Tracks.
4. **Dual-Consent Recording**: Recording requires independent, explicit consent from both Client and Counsel recorded in PostgreSQL (`video_recording_consents`).
5. **Ephemeral Media Playback Tickets**: Primary bearer access tokens in query parameters are rejected with HTTP 401. Authorized users exchange their bearer credentials for a 60-second, single-purpose ticket (`POST /api/v1/recordings/{id}/playback-ticket`) bound to `(user_id, recording_id)` for browser `<video>` playback.
6. **Cryptographic Integrity Verification**: SHA-256 hash is computed on ingestion and checked prior to streaming playback to reject modified or corrupted storage files.
7. **Security Headers**: Private, anti-caching headers (`Cache-Control: private, no-cache, no-store, must-revalidate`, `X-Content-Type-Options: nosniff`) are served on media streams.
8. **In-Meeting Continuous Indicator**: Prominent `🔴 RECORDING` badge continuously visible across all viewport states and controls.

