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

---

## ADR-005: Secure Evidence Locker, Document Custody, Integrity & Controlled Sharing

**Status:** FINAL

### Context
Legally sensitive exhibits, forensic records, and confidential contracts exchanged between clients and advocates require significantly stronger security guarantees than ordinary case documents. These include non-repudiation, tamper detection, immutable version history, controlled client/lawyer access grants, immediate access revocation, and an unbroken chain of custody.

### Decisions
1. **Domain Separation**: Ordinary documents (`Document`) and collaborative notes remain distinct from `Evidence`. Normal documents do NOT automatically become Evidence.
2. **Storage Architecture**: PostgreSQL stores metadata, access grants, versions, cryptographic hashes, and custody events. Private AWS S3 stores raw bytes under non-guessable paths (`cases/{case_id}/evidence/{evidence_id}/versions/{version_id}`). No public S3 URLs or permanent credentials are ever issued.
3. **Cryptographic SHA-256 Digest**: Every evidence version records a 64-character hex SHA-256 digest at ingestion. The `verify-integrity` API compares actual on-disk bytes against this hash; any discrepancy immediately flags `TAMPER_DETECTED` and records an immutable `INTEGRITY_FAILED` custody event.
4. **Immutable Versioning**: Modifying an evidence item creates a new `EvidenceVersion` (Version N+1). Previous versions remain permanently immutable and verifiable.
5. **Chain of Custody Ledger**: An append-only `EvidenceCustodyEvent` ledger links all chronological operations (`UPLOADED`, `SCAN_PASSED`, `SHARED`, `VIEWED`, `DOWNLOADED`, `INTEGRITY_VERIFIED`, `ACCESS_REVOKED`, `LEGAL_HOLD_APPLIED`, `DELETED`) with backward reference (`previous_event_id`).
6. **Controlled Sharing**: Explicit `EvidenceAccessGrant` entities specify granular permissions (`VIEW`, `DOWNLOAD`, `MANAGE`) and optional expiration dates. Sharing is strictly restricted to active case participants or confirmed consultation lawyers. Revocation is instantaneous.
7. **Legal Hold & Retention Enforcement**: An evidence item marked with `legal_hold=True` or an active `retention_until` timestamp cannot be deleted (`403 Forbidden`). Soft deletion is used to preserve forensic custody logs permanently.

---

## ADR-006: Controlled Production Pilot Operating Model & Launch Governance

**Status:** FINAL

### Context
Transitioning Legal Case Companion from a secure and deployable codebase to an operational legal platform in India requires strict onboarding controls, least-privilege administrative permissions, formal incident management, real-time SRE observability, and explicit separation between technical readiness and statutory compliance under the Digital Personal Data Protection (DPDP) Act 2023.

### Decisions
1. **Explicit Pilot Operating Mode**: Governed by configuration flags (`PILOT_MODE`, `PILOT_ALLOWLIST_ENABLED`, `PILOT_SIGNUP_ENABLED`, `PILOT_MAX_CLIENTS`, `PILOT_MAX_LAWYERS`, `PILOT_GLOBAL_READ_ONLY`). Capacity is hard-capped (100 clients, 50 advocates) and unlisted registrations receive `403 Forbidden` (`PILOT_NOT_ALLOWLISTED`).
2. **Emergency Global Read-Only Mode**: `PilotControlMiddleware` enforces `503 EMERGENCY_READ_ONLY` on mutating requests during major maintenance or active security investigations, exempting only essential auth logout, incident response, and pilot governance routes.
3. **Least-Privilege Operator Permission Model**: Decomposes broad "ADMIN" assumptions into granular operational permissions (`USER_SUPPORT`, `USER_MANAGEMENT`, `SEC_OPS`, `INCIDENT_MANAGE`, `COMPLIANCE_OPERATIONS`, `EVIDENCE_OPERATIONS`, `BILLING_OPERATIONS`, `SYSTEM_OPERATIONS`, `PILOT_GOVERNANCE`).
4. **Support Boundary Isolation**: Support staff holding `USER_SUPPORT` cannot view confidential legal case facts, evidence file contents, or consultation recordings without an explicit, time-limited `EvidenceAccessGrant` issued by the case owner.
5. **Production Incident State Machine**: Models incidents with severity classes (`SEV-1` to `SEV-4`), rigid state transitions (`DETECTED` $\to$ `ACKNOWLEDGED` $\to$ `INVESTIGATING` $\to$ `MITIGATED` $\to$ `RESOLVED` $\to$ `CLOSED`), and blameless postmortem tracking.
6. **Machine-Readable SRE Observability & Alerting**: Real-time SLO calculation at `/api/v1/pilot/slos` tracking 99.9% availability, p95 latency $< 500\text{ ms}$, error-budget burn rate, and actionable alert rules (`ALERT-HTTP-5XX-SPIKE`, `ALERT-EVIDENCE-TAMPERING`, `ALERT-AUTH-ATTACK-SPIKE`, `ALERT-DLQ-BACKLOG`, `ALERT-DEPENDENCY-FAILURE`).
7. **Compliance Separation Policy**: Technical data deletion, log scrubbing, and encryption are formally distinguished from organizational policies and external Indian legal reviews. The pilot launch status is formally designated as `PILOT APPROVED WITH CONDITIONS`.

---

## ADR-007: Controlled Pilot Execution, Product Validation, Reliability Measurement & Public-Launch Readiness

**Status:** FINAL

### Context
Advancing LCC from pilot authorization to empirical product validation and launch readiness requires measuring real-world advocate and litigant interactions without relaxing security boundaries, accumulating unmonitored data-quality debt, or relying on statistically meaningless sample sizes.

### Decisions
1. **Pilot Experimentation Architecture**: Formalizes hypothesis testing via `PilotExperiment` with explicit success and failure metrics before feature graduation.
2. **Privacy-Conscious Workflow & Funnel Telemetry**: Measures conversion across client and lawyer funnels while strictly excluding document contents, private consultation chats, and credentials.
3. **Statistical Validity in SRE SLO Reporting**: Enforces sample-size minimums ($N \ge 30$) for definitive SLO compliance; flags `INSUFFICIENT_SAMPLE_SIZE` when sample size is low to prevent synthetic skew.
4. **Zero-Trust Customer Support**: Restricts support personnel holding `USER_SUPPORT` to operational ticket metadata without granting access to confidential case files or evidence items.
5. **AI Quality Evaluation & Human Review Loop**: Implements automated legal benchmark testing across 20 Indian legal scenarios (including statutory transitions to BNS/BNSS/BSA) and establishes a human review workflow (`AIReviewRecord`) for defect triage.
6. **Automated Data Quality & Reconciliation**: Establishes auditable, idempotent reconciliation routines for detecting and repairing stale background worker leases, expired consultation bookings, and orphaned references.
7. **Four-Stage Pilot Expansion Model**: Authorizes progression to **Stage 2 (Expanded Bar Cohort)** with expanded capacity (250 clients, 100 advocates) under continued allowlist enforcement (`EXPAND PILOT WITH CONDITIONS`).

---

## ADR-008: Phase XX Multilingual Localization, Commercial Decoupling, Abuse Defense & Public Launch Governance

**Status:** FINAL

### Context
Transitioning LCC from an expanded Stage 2 pilot toward general public launch readiness requires solving regional language accessibility, statutory legal transparency, independent financial decoupled state machines, public abuse resilience, database and storage scale verification, and decoupling technical operational readiness from external human legal counsel statutory sign-offs.

### Decisions
1. **First-Class Regional Localization Architecture**: Implements language-safe locale resolution (`en-IN`, `hi-IN`) without hardcoding translated strings inside UI components. Never uses localized strings as authorization keys, database enums, or state machine tokens. Enforces human translation governance for legal notices.
2. **Multilingual AI Safety & Devanagari Injection Containment**: Defangs adversarial prompt injection in both Devanagari Hindi and transliterated Hindi scripts. Enforces zero-hallucination empty-retrieval refusals and accurate statutory grounding (IPC $\to$ BNS, CrPC $\to$ BNSS, Evidence Act $\to$ BSA) across languages.
3. **Legal Transparency & Document Versioning**: Decouples legal information, litigant assistance, machine-assisted research, and advocate representation. Implements non-repudiable versioned consent recording in `user_document_consents` preserving audit history without overwrites.
4. **Commercial Decoupling & Tax Compliance**: Decouples payment gateway states (`PENDING`, `AUTHORIZED`, `CAPTURED`, `REFUNDED`) from consultation states. Automates 18.0% GST calculation under SAC 9982 on platform facilitation fees, assigns sequential invoices (`INV-YYYYMMDD-XXXX`), and synchronizes entitlement grant/revocation.
5. **Advocate Professional Verification Maturity**: Implements State Bar Council enrollment validation, annual expiration lifecycle (`expires_at`), structured rejection taxonomy, and explainable deterministic discovery ranking compliant with Bar Council of India Rule 36.
6. **Public Abuse Defense & Lifecycle Maturity**: Defends against automated abuse with disposable email blocking, consultation booking velocity limits, and multi-tier rate limiting. Models auditable customer lifecycle transitions (`REGISTERED` $\to$ `VERIFIED` $\to$ `ACTIVE` $\to$ `RESTRICTED` $\to$ `SUSPENDED` $\to$ `DEACTIVATED`) with session revocation on restriction.
7. **Empirical Scale Validation & 14-Category Launch Gate Engine**: Benchmarked database query plans (p95 < 0.20ms) and validated storage growth models for 10,000 active matters. Machine-readable launch gate engine evaluates 14 distinct categories and arrives at **`READY_FOR_COUNSEL_SIGNOFF`**, strictly acknowledging that formal statutory counsel approval on Advocate Terms remains an external human prerequisite before public release.
