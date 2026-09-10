# Legal Case Companion (LCC) — Architectural Decision Record (ADR)

**Document Version:** 1.0.0  
**Date:** September 2026  
**Status:** Approved & Authoritative  

---

## 1. Authentication Token Storage Architecture

### Context & Requirements
Legal Case Companion is an India-focused legal technology platform serving two distinct user personas: **Advocates** and **Clients**. In day-to-day legal practice and administrative validation, users frequently need to maintain simultaneous active sessions—for example, an advocate consulting on one matter while auditing client-side intake in a separate tab, or staging and verifying real-time WebRTC instant video calls across two browser windows.

### Comparison of Evaluated Options

| Criteria | Option A: `sessionStorage` + Double-Submit CSRF (Implemented) | Option B: `httpOnly` Domain Cookies |
| :--- | :--- | :--- |
| **Multi-Tab Isolation** | **Native isolation**: Each tab possesses an isolated `sessionStorage` store. Tab A can be logged in as Advocate, Tab B as Client. | **Domain-wide collision**: Cookies are shared across all tabs of the domain. Logging into Tab B immediately clobbers the session in Tab A. |
| **XSS Vulnerability** | Tokens accessible to JavaScript; mitigated via strict Content Security Policy (CSP), subresource integrity, and input sanitization. | Script cannot read token directly; however, XSS can still execute arbitrary authenticated requests via browser cookie injection. |
| **CSRF Resistance** | Naturally immune to classic ambient credential CSRF; augmented by backend Double-Submit CSRF protection on state-mutating routes. | Highly vulnerable to ambient credential transmission without explicit SameSite=Strict and custom header/CSRF token validation. |
| **Multi-Tenant / Multi-Role Testing** | Seamless without incognito mode or separate browser profiles. | Requires separate incognito windows or different browser installations. |
| **Storage Hygiene** | Automatically destroyed on tab close. Legacy `localStorage` keys are explicitly purged via `_purgeLegacyLocalStorageKeys()`. | Persists across browser restarts unless configured as temporary session cookies. |

### Decision: Option A (`sessionStorage` with Multi-Layered Defense)
We deliberately maintain Option A for frontend token persistence.

**Compensating Security Controls:**
1. **Short Access Token Lifespan:** Access tokens expire after 15 minutes and use asymmetric Ed25519 cryptographic signatures with strict verification.
2. **Double-Submit CSRF Defense:** Critical financial and mutation endpoints require cryptographic CSRF validation.
3. **Content Security Policy (CSP):** The Next.js frontend enforces strict CSP preventing unauthorized third-party script execution.
4. **Active Storage Sanitation:** `frontend/src/api/session.ts` actively cleans legacy `localStorage` keys to prevent cross-session leakage.

---

## 2. AI Provider Abstractions: `AIProvider` vs. `LLMProvider`

### Context
The repository contains two service modules dealing with artificial intelligence:
- `app/services/ai_provider.py` (`AIProvider`)
- `app/services/llm_provider.py` (`LLMProvider`)

An architectural review was performed to assess whether these modules represent redundant duplicates that should be merged, or distinct domain layers.

### Distinct Architectural Responsibilities

#### 1. `AIProvider` (`app/services/ai_provider.py`)
- **Primary Domain:** Document Intelligence & Vector Embeddings.
- **Responsibilities:**
  - Generating semantic vector embeddings (`text-embedding-3-small`).
  - Integration with vector storage and hybrid search indexing.
  - Chunking and pre-processing evidentiary filings and legal case documents.
  - Cost tracking and token usage budgets for background batch indexing.

#### 2. `LLMProvider` (`app/services/llm_provider.py`)
- **Primary Domain:** Interactive Legal Copilot & Statutory Synthesis.
- **Responsibilities:**
  - Orchestrating complex prompt chains with constitutional and statutory citation instructions.
  - Enforcing strict legal safety guardrails (preventing unauthorized practice of law disclaimers).
  - Extracting structured legal entities (IPC/BNS sections, limitation periods, court hierarchies).
  - Real-time conversational streaming for interactive case chat.

### Decision
**Keep Abstractions Separated.**  
`AIProvider` and `LLMProvider` operate on different operational life cycles (batch document vectorization vs. real-time legal assistant synthesis). Merging them into a single monolithic class would violate the Single Responsibility Principle and couple vector retrieval to conversational prompt management. Both providers continue to consume standardized settings from `app.core.config.settings`.

---

## 3. Historical Documentation Drift Notice

### Context
Earlier project documentation (e.g. initial `project_report.md` or early phase README drafts) describes an initial Proof of Concept (Phases 1-2) with basic CRUD functionality and simplified mock data.

### Current Reality: Phase 10 Production Platform
The active codebase reflects **Phase 10 (Commercial Operations, Real-Time P2P WebRTC, and Production Governance)**, including:
1. **Server-Authoritative Financial Integrity:** Dual-entry reconciliation, statutory GST (SAC 9982) tax breakdown, double-payout guards, and deterministic `Decimal` banking rounding (`ROUND_HALF_EVEN`).
2. **Real-Time Video System:** Native P2P WebRTC signaling with mesh fallback, Redis distributed presence tracking, and TURN traversal.
3. **Evidence Locker:** ClamAV malware scanning, S3 server-side encryption, and strict multi-tenant role-based access control (RBAC).
4. **Structural Database Foundation:** Monotonic, verified Alembic migration graph with zero dangling branch heads.

When reconciling documentation against code, the live implementation in `app/` and `tests/` is authoritative.

---

## 4. Commercial Operations & Transaction Reliability (Phase 10.2)

### 4.1. Commercial State Machines

The commercial ecosystem coordinates four interdependent state lifecycles:

#### A. Payment State Machine
```text
           [CREATED]
               │
               ▼
           [PENDING]
          ╱         ╲
         ▼           ▼
   [SUCCEEDED]    [FAILED] (Terminal)
   (CAPTURED)
     ╱      ╲
    ▼        ▼
[PARTIALLY  [REFUNDED] (Terminal)
 REFUNDED]
```
- **Terminal States:** `SUCCEEDED` (unless refunded), `FAILED`, `REFUNDED`.
- **Invariants:** Out-of-order `payment_intent.payment_failed` webhooks cannot downgrade a `SUCCEEDED` payment.

#### B. Consultation Lifecycle Synchronization
- When `payment_intent.succeeded` is received by the webhook handler:
  - If consultation is `REQUESTED` or `ACCEPTED`, its status automatically transitions to `PAID`.
  - A `CommercialTransaction` record is atomically created (if absent) and marked `CAPTURED`.
  - Client entitlement quota is granted.

#### C. Refund Lifecycle
```text
[INITIATED] ──► [with_for_update() Lock] ──► [Check sum(refunds) + target <= gross]
                                                   │
                       ┌───────────────────────────┴──────────────────────────┐
                       ▼                                                      ▼
             [PARTIALLY_REFUNDED]                                         [REFUNDED]
          (Remaining balance > 0)                                   (Remaining balance == 0)
                                                                               │
                                                                   [Revoke Entitlements]
                                                                  [Cancel Consultation]
```
- **Cumulative Refund Invariant:** `Σ(succeeded_refund_amounts) <= gross_captured_amount`.
- Concurrency protection via row-level locks prevents race conditions where two simultaneous partial refund requests both observe the same remaining balance.

#### D. Advocate Payout Lifecycle
```text
[ELIGIBLE] ──► [PENDING] ──► [PAID / SETTLED] (Terminal)
                  │
                  ▼
              [FAILED] ──► [REVERSED] (Terminal)
```
- **Guards:** Payouts cannot be issued on `REFUNDED` or uncaptured transactions. Duplicate payout requests raise `PAYOUT_ALREADY_EXISTS`.

---

### 4.2. Database-Level Webhook Deduplication

Payment gateways (Stripe) guarantee *at-least-once* webhook delivery. Relying purely on in-memory or application-level `if not processed` flags introduces double-credit or double-booking race conditions during concurrent retries.

**Architecture Implemented:**
- **Table:** `processed_webhook_events` (`app.models.webhook.ProcessedWebhookEvent`).
- **Unique Constraint:** `uq_webhook_event_provider` on `(event_id, provider)`.
- **Atomic Registration:** Before executing any business side effects, a row is inserted in `PROCESSING` status within an atomic nested transaction / savepoint.
- If a concurrent webhook delivery arrives with the same `event_id`, the database constraint triggers a rollback to the savepoint and the handler safely returns `{"status": "already_processed"}` without executing duplicate side effects.
- Upon completion of side effects, status updates to `PROCESSED`.

---

### 4.3. Multi-Provider Separation: Inbound Collection vs. Outbound Disbursement

- **Inbound Client Collections (STRIPE):** Stripe handles PCI-DSS Level 1 compliant card and international collection, webhook signature verification (`verify_stripe_webhook_signature`), and instant capture.
- **Outbound Advocate Disbursements (RAZORPAYX):** Domestic Indian advocate payouts are processed via RazorpayX bank account / UPI / IMPS rails. This separation matches Indian banking and RBI regulatory requirements for marketplace disbursements.

---

### 4.4. Cancellation & No-Show Economics (`CancellationPolicyService`)

The platform deterministically maps operational disruptions to financial entitlements using exact `Decimal` arithmetic:
1. **Advocate Cancellation / Advocate No-Show:** 100% client refund, ₹0 advocate payout, ₹0 platform fee.
2. **Platform Technical / Infrastructure Failure:** 100% client refund, ₹0 advocate payout.
3. **Client Cancellation (> 2 hours prior):** 100% client refund.
4. **Client Late Cancellation (≤ 2 hours prior):**
   - Under `AUTOMATIC_TIERED` mode: 50% client refund, 50% advocate compensation.
   - Under `PENDING_BUSINESS_DECISION` mode (default): Flags transaction for manual administrative review.
5. **Client No-Show:** 0% client refund. Advocate is entitled to their reserved net compensation.

---

### 4.5. Immutable Financial Snapshots

To prevent historical transactions from changing meaning when advocate hourly rates, platform fee percentages, or GST tax rates change in future configuration:
- Every `CommercialTransaction` persists an immutable `financial_snapshot` inside its `metadata_` field at the exact moment of creation:
  ```json
  {
    "base_consultation_fee": 2500.0,
    "platform_fee_percent": 10.0,
    "applied_gst_rate_percent": 18.0,
    "platform_fee": 250.0,
    "tax_amount": 45.0,
    "net_advocate_amount": 2250.0,
    "currency": "INR",
    "created_at_utc": "2026-09-06T05:30:00Z"
  }
  ```
- Any future price or tax changes apply strictly to new transactions. Historical records and invoices remain auditable and legally immutable.

---

### 4.6. Frontend Authority Principle

The frontend is strictly presentation-only. No authoritative tax or platform fee math (`fee * 0.18`) is permitted in browser code:
- Consultation cards and directory previews render figures returned by `/api/v1/consultations/pricing-preview` or clearly indicate "Itemized at checkout".
- All actual charges, taxes, and splits are calculated server-side in `Decimal`.

---

### 4.7. Historical Tax Extraction & Authoritative Dual-Entry Reconciliation

Historical reconciliation operates strictly on the actual applied tax amount stored with each transaction, rather than dynamically reconstructing tax from current configuration or a hardcoded `18%`:
- **Tax Extraction Source:** `CommercialService._extract_stored_tax()` reads the tax directly from `metadata_["financial_snapshot"]["tax_amount"]` or the authoritative column `CommercialTransaction.tax_amount`.
- **Authoritative Balance Invariant:**
  ```text
  gross_amount = platform_fee + net_advocate_amount
  platform_fee = platform_net_revenue + tax_amount
  allocated_funds = total_payouts_settled + advocate_payouts_pending + active_platform_fees
  unallocated_variance = (gross_volume - total_refunds_processed) - allocated_funds == 0.00
  ```
- **Configuration Independence:** Even if future statutory tax regulations modify the GST rate (e.g., from 18% to 12% or 28%), historical reconciliation reports remain mathematically exact and deterministic.

---

### 4.8. Zero-Fallback Webhook Secret Security Policy

All webhook signature verification requires an explicitly configured production secret:
- **Zero Fallback Invariant:** If `STRIPE_WEBHOOK_SECRET` is unset or empty in production, the webhook handler immediately raises `HTTP 500 ("STRIPE_WEBHOOK_SECRET not configured")`.
- Under no circumstances does production code fall back to static test credentials (e.g. `whsec_test_secret_123`).
- Synthetic test secrets are isolated strictly to automated unit/integration test fixtures in `tests/conftest.py`.

---

## 5. Real-Time Video, Recording & Telemetry Reliability (Phase 10.3)

### 5.1. Video Session State Machine

The video consultation meeting lifecycle enforces explicit transitions to prevent drift between real-time media and consultation business state:

```text
       [SCHEDULED / CREATED]
                 │
                 ▼ (Participant joins within window)
              [READY]
                 │
                 ▼ (Advocate or system starts call)
              [ACTIVE]
             ╱        ╲
(Temporary  ▼          ▼ (Consultation finishes)
network loss)      [COMPLETED] (Terminal)
      [RECONNECTING]   │
            │          ▼
            └──► [ACTIVE]
```

- **Business State vs. Real-Time State:** WebRTC connection state belongs to the presentation/signaling layer; the backend `VideoMeeting` and `Consultation` models remain the authoritative source of truth.
- **Terminal State Protection:** Reconnection attempts or join requests to consultations in `COMPLETED`, `CANCELLED`, or `NO_SHOW` are rejected with HTTP 422 (`ValidationError`) and cannot reopen terminal meetings.

---

### 5.2. Session Restoration & Multi-Tab Isolation

When a participant experiences a network disconnect, page reload, or browser restart:
1. **Deterministic Session Restoration (`POST /api/v1/consultations/{id}/video/reconnect`):**
   - The server validates the participant's authorization (BOLA defense).
   - Looks up the existing authoritative `VideoMeeting` record without provisioning redundant rooms.
   - Reissues a fresh, cryptographically signed room access token (HMAC-SHA256 / LiveKit JWT) bound to the existing room.
2. **Multi-Tab Concurrency:**
   - Multiple browser tabs opened by the same authorized user are safely associated with the existing meeting room.
   - Secondary tabs receive independent valid access tokens and do not terminate or invalidate previous active sessions.

---

### 5.3. Recording Lifecycle State Machine & Duplicate Prevention

Video recording enforces explicit lifecycle states and mutual consent:

```text
    [NOT_STARTED]
          │ (Dual consent verified)
          ▼
      [STARTING]
          │
          ▼
     [RECORDING]
          │
          ▼
     [PROCESSING] ◄── [FAILED] (Bounded retry allowed)
          │
          ▼
     [AVAILABLE] (Terminal — duplicate upload forbidden)
```

- **Dual Consent Invariant:** Both the Client and the Advocate must submit explicit affirmative consent (`VideoRecordingConsent`) before recording can be initiated.
- **Duplicate Upload Prevention:** Once a recording reaches `AVAILABLE`, subsequent upload requests are rejected (`ValidationError`) to prevent tampering or overwriting recorded evidence.
- **Bounded Retry:** Recordings in `FAILED` status (e.g. from network timeout) are safely retryable via `finalize_upload()`.

---

### 5.4. S3 Security Model, Traversal Guards & Ephemeral Playback Tickets

All recording media is stored in private, non-public storage:
- **Private Storage Adapter (`S3RecordingStorageProvider`):** S3 objects are uploaded with private ACL and server-side encryption (`AES256`).
- **Path Traversal Guards:** Object keys are validated against `_validate_safe_object_key()` to reject any path traversal characters (`..`, `/`, `\`, null bytes).
- **Ephemeral Media Playback Tickets (`mpt_...`):**
  - Streaming endpoints never expose direct storage paths or permanent URLs.
  - Playback requests generate a single-use, 60-second cryptographically bound ticket tied to `(user_id, recording_id)`.
  - HTTP 206 Partial Content range requests are verified against the ticket.

---

### 5.5. Recording Integrity & Cryptographic Checksums

During upload finalization:
- The server streams the payload and computes a cryptographic SHA-256 digest (`checksum_sha256`).
- Zero-byte uploads are rejected (`ValidationError: Uploaded recording file is empty`).
- On playback retrieval, the storage provider validates file presence and verifies the stored checksum against the physical media to detect bit-rot or tampering.

---

### 5.6. Structured Telemetry & Metrics

Real-time lifecycle events are tracked through `VideoTelemetryService` with correlation IDs:
- **Correlation Fields:** `request_id`, `consultation_id`, `room_id`, `user_id`, `role`, `recording_id`, `provider`.
- **Zero Sensitive Data Invariant:** Telemetry sanitizes all payloads to prevent logging JWTs, credentials, secrets, or raw media streams.
- **Metrics Registry (`VideoMetricsRegistry`):** Tracks operational counters (`video_room_created_total`, `video_reconnect_total`, `recording_upload_failures_total`) and latency histograms (`recording_upload_duration_seconds`) without high-cardinality PII labels.

---

### 5.7. Stale Session Cleanup

Unattended or abandoned video rooms are prevented from accumulating:
- `VideoMeetingService.cleanup_stale_meetings(max_idle_hours=2)` queries active meetings past their scheduled window without active participant heartbeats and transitions them to `COMPLETED`.

---

## 6. Background Operations & Scheduled Maintenance Architecture (Phase 10.4)

### 6.1. Architecture Decision: PostgreSQL-Backed Transactional Workers vs. External Brokers

We explicitly select **Option A / C (PostgreSQL-Backed Transactional Job Engine)** over introducing external message brokers (Celery / RabbitMQ):
- **Transactional Consistency:** Enqueueing a background job commits in the exact same database transaction as the business mutation (e.g. document upload, evidence ingestion, outbox event). This eliminates two-phase commit bugs and orphaned queue messages.
- **Render Deployment Simplicity:** Render already provisions dedicated containerized workers: `lcc-worker` (`python -m app.worker`) and `lcc-scheduler` (`python -m app.scheduler`). Adding a Celery broker daemon (RabbitMQ or Redis broker) would increase cost, deployment failure surfaces, and operational complexity without technical benefit for current throughput requirements.
- **Concurrency & Multi-Worker Safety:** PostgreSQL's native `SELECT ... FOR UPDATE SKIP LOCKED` allows multiple parallel worker containers (`limit=10`) to claim distinct jobs concurrently with zero race conditions or table-locking bottlenecks.

---

### 6.2. Job Lifecycle State Machine & Classification

Every background task (`app.models.job.BackgroundJob`) progresses through an explicit state lifecycle:

```text
              [PENDING]
                  │ (Worker claims lease via SKIP LOCKED)
                  ▼
              [RUNNING]
             ╱    │    ╲
 (Success)  ▼     │     ▼ (Permanent error: ValidationError, ResourceNotFoundError, etc.)
  [SUCCEEDED]     │    [FAILED] (Terminal)
                  ▼ (Transient error: backoff < max_attempts)
             [RETRYING]
                  │ (attempt_count >= max_attempts)
                  ▼
            [DEAD_LETTER] (Terminal)
```

- **Permanent Error Classification:** Domain violations, missing foreign entities, or validation errors terminate immediately to `FAILED` with `error_category = "PERMANENT"` without futile retries.
- **Transient Error Classification:** Network glitches, database connection timeouts, and provider 5xx errors enter exponential backoff (`backoff_seconds = (2 ** attempt_count) * 5`).
- **Dead-Letter State:** Jobs exhausting `max_attempts` transition to `DEAD_LETTER` with `error_category = "TRANSIENT_EXHAUSTED"`. Dead-letter records are never deleted and remain auditable.

---

### 6.3. Idempotent Production Maintenance Jobs

1. **Stale Video Meeting Cleanup (`STALE_MEETING_CLEANUP`):**
   - Invokes `VideoMeetingService.cleanup_stale_meetings(max_idle_hours=2)`.
   - Transitions abandoned `ACTIVE` meetings past scheduled end + 2 hours to `ENDED` and consultations to `COMPLETED`.
   - Repeated execution is completely safe (finds 0 active meetings once cleaned).
2. **Recording Upload Retry (`RECORDING_UPLOAD_RETRY`):**
   - Invokes `VideoRecordingService.retry_pending_and_failed_recordings()`.
   - Restores recordings in `FAILED` or `PROCESSING` if valid media exists in storage. Computes SHA-256 and updates to `AVAILABLE`.
   - Marks permanently missing recordings past `max_age_minutes=60` as `FAILED` to prevent indefinite processing hangs.
3. **Webhook Reprocessing (`WEBHOOK_REPROCESS`):**
   - Invokes `PaymentService.reprocess_stale_or_failed_webhooks()`.
   - Re-evaluates `ProcessedWebhookEvent` records stuck in `PROCESSING` or `FAILED`.
   - If payment already succeeded in domain models, finalizes webhook record as `PROCESSED` without double-crediting or duplicate side effects.
4. **Commercial Reconciliation Check (`COMMERCIAL_RECONCILIATION`):**
   - Invokes `CommercialService.get_settlement_reconciliation()`.
   - Scans dual-entry accounts for variance and flags discrepancies.
   - Strictly 100% read-only: never mutates historical monetary numbers or invents funds.
5. **Expired Session & Token Cleanup (`EXPIRED_SESSION_CLEANUP`):**
   - Invokes `SessionCleanupService.cleanup_expired_sessions()`.
   - Prunes `RefreshTokenSession` expired > 30 days ago (preserving forensic security audit history).
   - Prunes `EmailVerificationToken` expired > 7 days ago.

---

### 6.4. Multi-Worker Lease Safety & Stale Job Recovery

- **Atomic Leasing:** `JobService.claim_jobs()` sets `locked_by = worker_id` and `locked_until = now + lease_seconds` (default 60s).
- **Worker Crash Recovery:** If a worker container crashes or is abruptly terminated during a job, `reclaim_stale_jobs()` recovers jobs where `locked_until < now`, returning them to `RETRYING` (or `DEAD_LETTER` if max attempts reached).

---

### 6.5. Admin Controls & Reprocessing Visibility

- **Visibility Endpoints:** `GET /api/v1/admin/jobs` and `GET /api/v1/admin/jobs/stats` expose full job queue health and diagnostics to authenticated administrators (`UserRole.ADMIN`).
- **Controlled Replay:** `POST /api/v1/admin/jobs/{job_id}/execute` allows an authorized administrator to manually trigger execution of a failed job. Replay strictly executes through the same idempotent domain handlers.

---

## 7. Evidence Locker V1: Production Architecture, Exhibit Management & Case Timeline Integration

### 7.1. Context & Architectural Principles
The Evidence Locker is the authoritative repository for evidentiary filings, forensic digital assets, contracts, orders, and court exhibits in Legal Case Companion. It serves legal proceedings where provenance, custody, and cryptographic integrity must withstand courtroom scrutiny under the Indian Evidence Act / Bharatiya Sakshya Adhiniyam (BSA), 2023.

### 7.2. Evidence Lifecycle State Machine
```text
[INIT UPLOAD] ──> [STAGED] ──> [VIRUS/MAGIC SCAN] ──> [SHA-256 INTEGRITY] ──> [ACTIVE]
                                       │                                         │
                                       ▼                                         ▼
                                  [QUARANTINED]                            [LEGAL HOLD]
                                                                                 │
                                                                   (Blocks deletion & archive)
                                                                                 │
                                                                                 ▼
                                                                            [ARCHIVED]
                                                                                 │
                                                                                 ▼
                                                                           [RESTORED]
```

1. **Staged Uploads:** Files are initially deposited into an isolated staging storage prefix (`evidence-staging/`). They cannot be directly referenced or downloaded.
2. **Magic-Byte & Malware Scan:** Content types are verified against magic byte signatures; files are scanned via ClamAV heuristic engine before moving to the private storage prefix.
3. **Cryptographic SHA-256 Integrity:** File digests are computed at ingestion and pinned in `EvidenceVersion.sha256_hash`. Any subsequent integrity check verifies stored bytes against this original digest.
4. **Legal Hold Guardrail:** When `legal_hold = True`, destructive actions (`ARCHIVE`, `DELETE`, `PURGE`) are strictly rejected with HTTP 403 `LEGAL_HOLD_ACTIVE`.
5. **Safe Archival & Restoration:** Deletion is staged through `ARCHIVED` status. Active legal holds prevent transition. Archival and restoration are logged as immutable custody actions.

### 7.3. Exhibit Management & Concurrency Safety
Exhibits represent evidence formally marked and submitted for court hearings.

1. **Deterministic Numbering Convention:**
   Exhibits are indexed using standard common-law sequential lettering (`Exhibit A` .. `Exhibit Z`, `Exhibit AA` .. `Exhibit ZZ`).
2. **Collision Prevention via Pessimistic Locking & Database Constraints:**
   - Sequential allocation utilizes database-level pessimistic locking (`with_for_update()`) on the parent `Case` row during numbering calculation.
   - Enforced by a composite unique constraint in PostgreSQL/SQLite:
     `UniqueConstraint("case_id", "exhibit_number", name="uq_case_exhibit_number")`.
   - Any concurrent race is trapped by database constraint enforcement and mapped to HTTP 409 `EXHIBIT_COLLISION`.
3. **Version-Aware Immutability:**
   Every `CaseExhibit` binds directly to an explicit `evidence_version_id`. If a newer version of the underlying evidence is uploaded later (e.g. Version 2 or 3), existing court exhibits remain pinned to their historical version, guaranteeing evidentiary integrity.
4. **Court Hearing & Timeline Integration:**
   - An exhibit can be linked to a specific `CaseHearing` via `hearing_id`.
   - Marking an exhibit automatically creates an authoritative `CaseTimelineEvent` (`event_type = TimelineEventType.EXHIBIT_MARKED`) containing exhibit title, sequential letter, and hearing metadata. The timeline remains informational while the Evidence Locker is authoritative.

### 7.4. Server-Side Bounded Listing & Search
- All search and filtering occurs server-side; unbounded `.all()` queries are strictly prohibited.
- `q` search queries match title, original filename, description, exhibit numbers, and normalized tags.
- Bounded pagination defaults to 20 items (max 100), ordered deterministically by `(created_at DESC, id DESC)`.
- Tag filtering uses case-insensitive exact matching over JSON-normalized tag sets.

### 7.5. Atomic Batch Operations & Tenant Isolation
Batch mutations (`ASSIGN_CATEGORY`, `ADD_TAGS`, `REMOVE_TAGS`, `ARCHIVE`, `RESTORE`) enforce fail-closed tenant boundaries:
- The total fetched accessible items must exactly equal the requested ID list (`len(items) == len(requested_ids)`).
- If any ID in the batch belongs to a foreign tenant, is inaccessible to the caller's role, or fails legal hold constraints, the entire transaction is rolled back and rejected with HTTP 403/404, preventing partial or unauthorized modifications.
- Request payload size is bounded to 50 items.

### 7.6. Secure Ephemeral Preview Architecture
- Direct, permanent, or public S3 URLs are strictly prohibited.
- Viewing and downloading utilize server-generated presigned URLs with short 60-second TTLs (`expires_in = 60`).
- Safe browser rendering is restricted to safe MIME categories (`application/pdf`, `image/*`). Executables, scripts, and untyped binaries cannot be previewed in-browser and require authenticated download.

---

## 8. Court Hearing Management, Evidentiary Bundles & Bharatiya Sakshya Adhiniyam (BSA) Section 63 Certificates (Phase 11)

### 8.1. Context & Objective
Phase 11 transforms the Case + Evidence Locker + Exhibits + Timeline architecture into a practical, courtroom-ready preparation workflow. It establishes server-side evidentiary bundles, deterministic Bates numbering, dual-layer cryptographic manifests, controlled hearing lifecycle state transitions, and a statutory electronic record certificate preparation workflow under Section 63(4) of the Bharatiya Sakshya Adhiniyam (BSA), 2023.

### 8.2. Court Hearing Lifecycle & Authoritative Separation
1. **Model Reuse & Extensions:**
   `CaseHearing` retains its authoritative role without duplicating court case or timeline entities. Extended attributes include `court_number`, `hearing_type`, and `next_date`.
2. **Hearing State Machine:**
   ```text
   SCHEDULED ──> ADJOURNED (requires next_date; records adjournment reason)
             ├──> CONCLUDED / COMPLETED (terminal; cannot be silently rewritten)
             ├──> RESCHEDULED
             └──> CANCELLED
   ```
3. **Timeline Cross-Referencing:**
   Status transitions (adjourning, completing, scheduling) emit immutable `CaseTimelineEvent` instances. The timeline remains a read cross-reference; the `CaseHearing` record remains the authoritative source of truth.
4. **Exhibit Association:**
   Hearings link directly to marked `CaseExhibit` instances through the foreign key `CaseExhibit.hearing_id`. Exhibit references remain strictly pinned to immutable `evidence_version_id` values.

### 8.3. Evidentiary Bundle Concept & Immutability Guarantee
1. **Derivative Artifact Principle:**
   `Original Evidence ≠ Generated Court Bundle`. Original files in the Evidence Locker are never modified, stamped, watermarked, or converted. The bundle is a derived, standalone court submission document.
2. **State Progression:**
   ```text
   DRAFT ──> GENERATING ──> FINALIZED (Immutable sealed state)
         └──> FAILED
   ```
3. **Immutability Enforcement:**
   Once finalized, a bundle's status transitions to `FINALIZED`, `finalized_at` is set, and `bundle_sha256` is recorded. Any attempt to update, add items, or re-finalize a finalized bundle is strictly rejected with HTTP 409 `BUNDLE_FINALIZED`. If the user requires changes, a new bundle instance must be created.
4. **Concurrency Locking:**
   Bundle finalization acquires a row-level lock on `EvidenceBundle` (`with_for_update()`) inside an atomic transaction. Concurrent attempts to finalize the same logical bundle fail deterministically.

### 8.4. Deterministic Exhibit Ordering & Bates Numbering
1. **Natural Exhibit Ordering:**
   Bundle items are sorted strictly using natural exhibit numbering (`Exhibit A`, `Exhibit B` ... `Exhibit Z`, `Exhibit AA` ...). Stripping prefixes and parsing alphabetic / numeric markers prevents dependency on random UUIDs or database insertion order.
2. **Sequential Bates Numbering:**
   - Format: `{bates_prefix}{bates_number:06d}` (e.g., `LCC000001`, `LCC000002`).
   - Bates numbers are assigned sequentially across all pages of all included exhibits and burned onto page footers in the generated PDF.
   - For non-PDF binary formats (e.g. video, audio, archive), an official exhibit divider / placeholder page is generated and Bates stamped, preserving manifest sequence without corrupting original binaries.
   - Bates start and end ranges are immutably recorded in `EvidenceBundleItem.bates_start` and `bates_end`.

### 8.5. Cryptographic Manifest & Dual-Layer Hashing
1. **Item Manifest:**
   Each `EvidenceBundleItem` stores the exact `sha256_hash`, `mime_type`, `file_size_bytes`, `page_count`, and `evidence_version_id`.
2. **Bundle Integrity Digest:**
   The finalized PDF bundle itself is hashed (`SHA-256`) immediately upon compilation, and stored in `EvidenceBundle.bundle_sha256`.
3. **No Credential / Ephemeral URL Leakage:**
   The bundle manifest stores only deterministic content digests, filenames, and item metadata. Presigned URLs and storage keys are never persisted in the manifest.

### 8.6. Bharatiya Sakshya Adhiniyam (BSA), 2023 — Section 63(4) Certificate Workflow
1. **Statutory Alignment:**
   Implements a preparation workflow based on Section 63(4) and the Schedule of the Bharatiya Sakshya Adhiniyam, 2023 (replacing Section 65B of the Indian Evidence Act, 1872).
2. **No Invented Facts:**
   LCC auto-populates objective, cryptographically verifiable facts (bundle title, item filenames, SHA-256 digests, timestamps). Physical facts (device description, serial number, lawful control, operational integrity) cannot be verified by software and MUST be supplied and confirmed by a human declarant (`is_confirmed = True`).
3. **Clear Draft Status & Legal Disclaimer:**
   Generated certificates are explicitly titled **"Certificate Preparation Draft"** (`is_draft = True`). The system explicitly disclaims guarantees of judicial admissibility or court acceptance, maintaining legal safety.

### 8.7. eCourts Integration Boundary & Provenance
1. **No CAPTCHA / Access Control Bypassing:**
   Official eCourts systems employ CAPTCHA and anti-automation controls. Scraping or bypassing these controls is strictly prohibited.
2. **Provider Adapter & Manual Import Fallback:**
   `ECourtsProvider` provides an extensible provider interface. When official authorized APIs are absent, the application supports verified manual cause list imports (`retrieval_method = "MANUAL_VERIFIED"`).
3. **Provenance Integrity:**
   All imported court listings retain `source`, `source_reference`, `retrieved_at`, and official disclaimers noting that online court data does not constitute certified judicial records.

### 8.8. Authorization, Storage & Auditing
1. **Authorization Matrix:**
   Only case members with appropriate roles (Owner, Client, Assigned Lawyer) may create, finalize, or access bundles. Callers must possess explicit authorization to all included evidence versions.
2. **Private S3 Storage & Short-Lived Access:**
   Bundles and certificate PDFs are stored under private S3 keys (`bundles/{case_id}/{bundle_id}.pdf`). Downloads are issued via short-lived presigned URLs (60-second TTL).
3. **Immutable Audit Events:**
   Actions log structured `AuditEvent` records: `BUNDLE_CREATED`, `BUNDLE_GENERATION_STARTED`, `BUNDLE_FINALIZED`, `BUNDLE_DOWNLOADED`, and `BUNDLE_CERTIFICATE_PREPARED`.

---

## 9. Case Operations, Deadlines, Tasks & Workflow Automation (Phase 12)

### 9.1. Architectural Philosophy & Zero-AI Invariant
1. **Deterministic Operations, Not Legal Advice:**
   Operational workflows (hearing prep, document submission, client follow-up, compliance deadlines) are structured, deterministic tools to coordinate human activity. The system strictly forbids LLM-based automatic task drafting, OCR, RAG, automated deadline interpretation, or unsolicited legal advice.
2. **Separation of Concerns:**
   - **Case Timeline:** Immutably records *historical event telemetry* (`TASK_CREATED`, `DEADLINE_COMPLETED`, etc.). It is never the queryable source of current task or deadline state.
   - **Case Tasks & Deadlines:** Actionable, stateful operational workflow objects scoped strictly to cases with explicit state machines.

### 9.2. Domain Models & Relational Integrity
1. **CaseTask (`app/models/task.py`):**
   - **Identity & Scope:** `id` (UUID), `case_id` (FK to `cases.id`).
   - **Metadata:** `title` (max 255 chars), `description` (text), `priority` (`LOW`, `MEDIUM`, `HIGH`, `URGENT`), `status` (`PENDING`, `IN_PROGRESS`, `BLOCKED`, `COMPLETED`, `CANCELLED`).
   - **Actor Scoping:** `created_by` (FK to `users.id`), `assigned_to` (FK to `users.id` with case membership validation).
   - **Lifecycle Timestamps:** `due_at` (timezone-aware UTC), `completed_at`, `created_at`, `updated_at`.
   - **Operational Links:** `linked_evidence_id` (FK to `evidence.id`), `linked_hearing_id` (FK to `case_hearings.id`), `linked_deadline_id` (FK to `case_deadlines.id`).
2. **CaseDeadline (`app/models/workflow.py`):**
   - **Identity & Scope:** `id` (UUID), `case_id` (FK to `cases.id`).
   - **Metadata:** `title`, `description`, `due_at` (UTC), `status` (`UPCOMING`, `DUE_SOON`, `OVERDUE`, `COMPLETED`, `CANCELLED`).
   - **Provenance Tracking:** `source` (e.g. `MANUAL`, `COURT_ORDER`, `ECOURTS_SYNC`), `source_reference` (order or filing number), `retrieval_method` (`MANUAL_VERIFIED`), `retrieved_at`, `confirmed_by_user_id`.
   - **Operational Links:** `linked_hearing_id` (FK to `case_hearings.id`), `linked_task_id` (FK to `case_tasks.id`), `created_by_user_id`.

### 9.3. Task State Machine & Terminal State Freeze
1. **Valid Lifecycle Transitions:**
   - `PENDING` -> `IN_PROGRESS`, `CANCELLED`
   - `IN_PROGRESS` -> `BLOCKED`, `COMPLETED`, `CANCELLED`
   - `BLOCKED` -> `IN_PROGRESS`, `CANCELLED`
2. **Terminal State Freeze:**
   - Once marked `COMPLETED` or `CANCELLED`, tasks are frozen against general mutation via `PATCH /cases/{case_id}/tasks/{task_id}`.
   - Any attempt to update a frozen task via PATCH returns `HTTP 400 Bad Request`.
3. **Explicit Audited Reopen:**
   - Reopening is supported solely via dedicated `POST /cases/{case_id}/tasks/{task_id}/reopen`.
   - Reopening transitions task back to `IN_PROGRESS` and emits an explicit `TASK_REOPENED` audit event.

### 9.4. Authorization Matrix & Multi-Tenant BOLA/IDOR Defense
1. **Case Membership + Role Enforcement:**
   Every workflow endpoint enforces `authorize_case_access(db, user, case_id)`.
   - **Client:** Can manage own case tasks/deadlines; cannot assign tasks to unrelated users outside the case.
   - **Assigned Lawyer:** Can create, reassign, complete, and batch-operate on tasks/deadlines for assigned cases.
   - **Unassigned Lawyer / Random User:** Receives `HTTP 404 Not Found` (existence masking) preventing metadata leakage.
2. **Fine-Grained Assignment Guard:**
   Assignees MUST have an active association with the target case (as client, owner, or assigned lawyer). Assigning tasks to arbitrary system users or across case boundaries is strictly rejected with `HTTP 400 Bad Request`.
3. **Batch Operation Fail-Closed Architecture:**
   Batch operations (`POST /cases/{case_id}/tasks/batch`) enforce a maximum batch limit of 50 items. Every task in the batch must belong to `case_id`. If any task ID does not belong to the case, the transaction rolls back completely with `HTTP 404 Not Found`.

### 9.5. Automated Reminders & Background Processing
1. **Idempotent Notification Delivery:**
   `ReminderService.process_task_reminders(hours_ahead=24)` and `process_overdue_deadlines_and_tasks()` run periodically.
   - Reminders record delivery keys to prevent duplicate worker executions or notification storms.
   - Notification content adheres to least-privilege principles (task title and due date only; never leaking confidential evidence or private lawyer notes).
2. **Authoritative Server-Side Overdue Calculation:**
   Deadlines past `due_at` with active statuses (`UPCOMING`, `DUE_SOON`) are automatically detected and transitioned to `OVERDUE` server-side, notifying case participants. Frontend calculations are purely display hints and never authoritative.

### 9.6. Deterministic Workflow Templates
1. **Four Standard Operational Templates:**
   - `HEARING_PREPARATION`: Auto-generates structured preparation tasks (review order, bundle finalization, client prep, counsel briefing) scheduled at relative offsets (T-10, T-5, T-2, T-1 days before hearing).
   - `POST_HEARING_FOLLOWUP`: Auto-generates follow-up tasks (obtain certified copy of order, update next hearing date, client debrief).
   - `EVIDENCE_PREPARATION`: Generates Section 63 BSA certificate draft, chain of custody review, and exhibit collation tasks.
   - `NEW_CONSULTATION`: Generates conflict check, client onboarding, and initial dossier review tasks.
2. **Zero-AI Rule:**
   All templates are deterministically coded and parameterized by dates and assignees. Every generated task is fully editable and cancelable by case members. No mandatory legal outcomes or unvetted tasks are forced on users.

### 9.7. Operational Case Health Telemetry
The `GET /cases/{case_id}/workflow/health-summary` endpoint returns real-time deterministic operational health metrics:
- `next_hearing_date`: Earliest upcoming hearing date.
- `overdue_tasks_count`: Total active tasks past due date.
- `active_deadlines_count`: Total open deadlines.
- `unreviewed_evidence_count`: Evidence items lacking reviewed status.
- `timeline_activity_count`: Number of recorded case timeline events in the last 7 days.
These indicators provide situational awareness without fabricating predictive legal scores.

---

## 10. Lawyer Operational Dashboard & Unified Calendar (Phase 13)

### 10.1. Context & Operational Purpose
Advocates managing multiple concurrent legal matters require a unified, high-density operational command center answering five fundamental operational questions at a glance:
1. What do I need to do today? (Today's Operational Agenda)
2. What hearings are coming up? (Upcoming Hearings Radar with bundle & task readiness)
3. What deadlines are approaching? (Statutory Limitation & Filing Cutoffs)
4. Which matters need attention? (Operational Attention Radar)
5. Are there urgent or overdue items? (KPI Telemetry Strip)

Under the application's strict **Zero-AI mandate**, the operational dashboard is strictly a server-side deterministic aggregation and projection layer over authoritative relational records. No LLM summaries, predictive case win probabilities, or AI legal risk scores are generated.

### 10.2. Server-Side Bounded Aggregation Architecture
To maintain sub-200ms response times across 500+ active cases, 1,000+ tasks, and 1,000+ deadlines without memory exhaustion:
1. **Case-Scoped Membership Resolution:**
   Every dashboard query begins by discovering the authenticated lawyer's explicitly authorized active matters via `CaseParticipant` (`user_id == current_user.id`, `status == ACTIVE`, `deleted_at IS NULL`).
2. **Zero N+1 Query Execution:**
   Aggregates are performed via purpose-built SQL queries utilizing `IN (:user_case_ids)` clauses, indexed composite keys, and `func.count()`, `func.sum()` group-by projections. All secondary relations (task counts, bundle statuses, exhibit tallies) are mapped in memory via dictionary lookups in single-pass queries.
3. **Strict Date Range Bounding:**
   - Default query window: 14 days ahead.
   - Allowed window: 1 to 90 days max (`days_ahead` parameter).
   - Custom ranges (`date_from`, `date_to`) enforce `(date_to - date_from).days <= 90` and `date_to >= date_from`. Requests exceeding 90 days are strictly rejected with `HTTP 422 Unprocessable Content`.

### 10.3. Unified Calendar Projection Model
The Unified Calendar does not store duplicate records or denormalized calendar tables. Instead, it dynamically projects authoritative records into a standard `CalendarEventItem` schema:
- **`HEARING`**: Projected from `CaseHearing` (`hearing_at`, courtroom, bench, purpose, related exhibits and bundles).
- **`DEADLINE`**: Projected from `CaseDeadline` (`deadline_at`, title, limitation source, urgency indicator).
- **`TASK`**: Projected from `CaseTask` (`due_date`, priority, assignee, status).
- **`CONSULTATION`**: Projected from `Consultation` (`scheduled_at`, duration, client profile).

Every calendar event retains immutable source tracking:
- `source_type`: `HEARING` | `DEADLINE` | `TASK` | `CONSULTATION`
- `source_id`: UUID of the authoritative underlying record
- `case_id`: UUID of the parent case (with direct drill-down links to `/cases/{case_id}`)
- `color` & `category`: Standardized operational taxonomy (`COURT_HEARING`, `STATUTORY_DEADLINE`, `PREPARATION_TASK`, `CLIENT_CONSULTATION`).

### 10.4. Multi-Tenant Authorization Boundaries & Existence Masking
1. **Cross-Lawyer Isolation:**
   All queries strictly constrain data to cases where the authenticated lawyer is an active participant or owner. Aggregate queries never execute global `SELECT *` statements with post-hoc Python filtering.
2. **404 Existence Masking on Foreign Matters:**
   If a client requests a dashboard or calendar filtered by a foreign `case_id` where the lawyer has no active membership, the system returns `HTTP 404 Not Found` (rather than 403 Forbidden) to prevent adversaries from enumerating existence of confidential matters across law firms.
3. **Notification Isolation:**
   Notification queries and mark-as-read mutations strictly verify `recipient_user_id == current_user.id`. Cross-user notification manipulation is blocked at the database query level.

### 10.5. Timezone Handling Strategy
1. **Database & API Standard:**
   All database timestamps (`DateTime(timezone=True)`) and API wire payloads remain strictly UTC ISO-8601 strings (e.g. `2026-09-06T14:30:00Z`).
2. **Deterministic Court Date Boundary Protection:**
   Court hearings and statutory limitation deadlines in Indian jurisdictions operate on standard local court calendars (IST - Indian Standard Time, UTC+05:30). To prevent date shift bugs across midnight boundaries:
   - Wire datetimes are parsed as timezone-aware UTC.
   - Frontend components display local time using the browser's Intl formatting API or Indian Standard Time (IST) formatting (`time_display`), ensuring a 10:00 AM High Court hearing is not accidentally displayed on the prior day.

### 10.6. Real-Time Updates & Presence Integration
1. **WebSocket Event Subscription:**
   The dashboard subscribes to the existing authenticated WebSocket connection (`/api/v1/ws`) and listens for operational domain events:
   - `CONSULTATION_REQUESTED` / `CONSULTATION_ACCEPTED` / `CONSULTATION_CANCELLED`
   - `TASK_ASSIGNED` / `TASK_COMPLETED`
   - `DEADLINE_OVERDUE` / `HEARING_RESCHEDULED`
   - `NOTIFICATION_CREATED`
2. **Presence Heartbeat Maintenance:**
   The lawyer dashboard automatically maintains the lawyer's online availability through the existing 30-second presence heartbeat (`POST /api/v1/consultations/lawyer/presence/heartbeat`), seamlessly enabling incoming video consultation call modals without redundant business polling loops.

### 10.7. Distributed Worker Concurrency Locking
1. **Risk Addressed:**
   Prior phases identified a risk where multiple background Celery/scheduler workers running concurrently could process overdue deadlines or reminders simultaneously, resulting in duplicate client notifications or notification storms.
2. **Two-Tier Distributed Locking (`app/core/locking.py`):**
   - **Tier 1 (Primary):** Redis distributed lock using atomic `SET NX PX` with a 60-second time-to-live (TTL).
   - **Tier 2 (Fallback):** In environments lacking Redis, the lock transparently falls back to PostgreSQL session-level advisory locks via `SELECT pg_try_advisory_lock(:lock_id)`.
   - **Contention Behavior:** When a lock is held by Worker A, Worker B fails to acquire the lock immediately and skips the cycle cleanly (`skipped_due_to_lock: True`), eliminating duplicate processing while preserving job idempotency.

### 10.8. Data Freshness Guarantees
- **Dashboard & Calendar Views:** Request-time authoritative query. Every page load or date range change queries the primary database with fresh transaction isolation.
- **Needs Attention Radar:** Request-time evaluation with deterministic rules (overdue tasks, hearings within 24h, statutory deadlines within 48h, unverified evidence items).
- **Incoming Consultations & Calls:** Real-time push via WebSockets (< 500ms latency).

---

## 11. Advocate Onboarding, Bar Verification, KYC & Practice Compliance (Phase 14)

### 11.1. Regulatory & Statutory Framework
All onboarding, verification, and practice compliance logic is strictly grounded in primary Indian statutory authorities:

1. **Advocates Act, 1961 (Sections 17, 22, 30):**
   - *Requirement:* Every advocate practicing law in India must be entered on the roll maintained by a State Bar Council under Section 17, issued a certificate of enrollment under Section 22, and legally entitled to practice before all courts and tribunals under Section 30.
   - *Implementation:* The platform strictly enforces standardized enrollment format (`STATE/NUMBER/YEAR`, e.g., `D/1842/2016`, `MAH/4021/2018`) and requires an official State Bar Council enrollment certificate before an application can be submitted for review.

2. **Bar Council of India Rule 36 Proviso (Standards of Professional Conduct and Etiquette):**
   - *Requirement:* Section 49(1)(c) rules prohibit advocates from advertising, soliciting work, or displaying subjective ratings, superlative marketing, or commercial touting. The proviso permits advocates to publish factual information only: name, telephone numbers, email, enrollment details, professional qualifications, and areas of practice.
   - *Implementation:* The public verification badge (`PublicAdvocateVerificationBadgeResponse`) strictly displays factual credentials (`✓ Professional Enrollment Verified`, State Bar Council name, masked enrollment number, verification timestamp) accompanied by explicit statutory disclaimers. Misleading phrases such as "100% trusted advocate", "court-approved", "guaranteed qualified", or "certified by Bar Council" are strictly forbidden.

3. **BCI Certificate and Place of Practice (Verification) Rules, 2015:**
   - *Requirement:* Requires periodic verification of advocate credentials and issuance of a Certificate of Practice (COP) to distinguish active practitioners from non-practicing advocates.
   - *Implementation:* Configurable verification expiration (`expires_at`, default 365 days) with background scheduled review-due detection and re-verification reminders.

4. **Digital Personal Data Protection Act (DPDPA), 2023 & Aadhaar Act, 2016 (Section 29):**
   - *Requirement:* Data minimization, purpose limitation, sensitive credential protection, and strict prohibition against public display or unmasked logging of identity credentials.
   - *Implementation:* Zero storage of unnecessary identity documents; mandatory masking of enrollment numbers in public views (`D/****/2016`); exclusion of private reviewer notes and document IDs from public payloads; and short-lived S3 signed URLs (max 900 seconds) for reviewer inspection.

5. **Zero-AI Product Development Mandate:**
   - *Requirement:* No LLM, OCR, or heuristic AI algorithm may be used for document verification, legal classification, or advocate approval.
   - *Implementation:* All verification decisions require human review by authorized administrative personnel with roll provenance recording (`verification_source`, `source_reference`, `verification_method`).

### 11.2. Separation of Concerns & State Architecture
The system enforces strict domain separation:
```text
DOCUMENT UPLOADED ≠ DOCUMENT VERIFIED ≠ ADVOCATE VERIFIED ≠ LEGAL PRACTICE ELIGIBILITY
```

#### Advocate Verification State Machine
```text
      [DRAFT] (Document uploads in progress)
         │
         ▼ (Submit Application — requires valid State Bar Council Certificate)
     [PENDING]
         │
         ▼ (Reviewer claims dossier via pessimistic lock)
   [UNDER_REVIEW]
      ╱    │     ╲
     ▼     ▼      ▼
[APPROVED] [REJECTED] [NEEDS_INFO]
   │          │          │
   │          │          └─► Advocate resubmits ──► [PENDING]
   │          └────────────► Terminal or appeal
   │
   ▼ (Credential modification or administrative sanction)
[REVOKED]
```

### 11.3. Reviewer RBAC & Self-Approval Prevention
- **Authorized Roles:** Only administrative staff (`UserRole.ADMIN`) possess permissions to claim verification dossiers, inspect sensitive professional credentials, issue decisions (`APPROVE`, `REJECT`, `REQUEST_INFO`), or revoke verified status.
- **Self-Approval Protection:** The service guarantees `reviewer.id != profile.user_id`. An advocate who is also an administrator or attempts to bypass API constraints cannot review, approve, reject, or revoke their own verification application (`AuthorizationError: Self-approval prohibited`).
- **Mass Assignment Defense:** Pydantic schemas enforce `extra="forbid"`. Clients cannot forge `verification_status`, `verified_at`, or `reviewed_by` via request payloads.

### 11.4. Document Security & Storage Architecture
- **Private S3 Storage:** Verification documents are uploaded to isolated private storage keys (`verification/{lawyer_id}/{doc_id}.enc`) using server-side encryption (SSE-S3). Documents are never placed in public asset buckets.
- **Deterministic Validation:** File uploads undergo strict magic byte validation (`validate_file_magic_bytes`), filename sanitization (`secure_filename`), SHA-256 integrity calculation, and fail-closed malware scanning. Executable headers and disguised extensions are rejected.
- **Short-Lived Reviewer URLs:** Administrative inspection generates pre-signed URLs with a 15-minute expiration (`expires_in_seconds=900`). Every document access triggers an immutable audit log (`DOCUMENT_VIEWED`).

### 11.5. Verification Provenance & Audit Trails
Every verification transition records complete provenance in the relational database:
- `verification_source`: Authoritative registry consulted (e.g. `Bar Council of Delhi Official Roll Portal`).
- `source_reference`: Official roll record or registration ledger entry identifier.
- `verification_method`: `STATE_BAR_COUNCIL_PORTAL_CHECK` | `OFFICIAL_GAZETTE_VERIFICATION` | `MANUAL_DOCUMENT_AUDIT`.
- `reviewed_by` & `reviewed_at`: Unique administrative actor UUID and UTC timestamp.
- **Audit Logging:** Every transition creates an immutable `AuditEvent` and appends to `VerificationReviewEvent` to preserve complete multi-round review history without overwriting previous attempts.

### 11.6. Credential Invalidation & Revocation
- **Profile Change Invalidation:** If an advocate modifies critical verified credentials (`enrollment_number` or `state_bar_council`), the system triggers `invalidate_on_credential_change()`. The active verification is automatically revoked, account status demoted to `REGISTERED`, and public badge removed until a new application is reviewed and approved.
- **Administrative Revocation:** Authorized admins can revoke verification with mandatory structured reasons (`DISCIPLINARY_SANCTION`, `ENROLLMENT_CANCELLED`, `FRAUDULENT_SUBMISSION`). Revocation instantly strips public badge visibility and demotes account status.

### 11.7. Practice & Forum Guardrails
- Declarations of practice forums (High Court, District Courts, NCLT, CAT) are captured as declared practice interests without conflating declarations with legal certification.
- Case access remains strictly decoupled from advocate verification: case membership requires explicit participation assignment (`CaseParticipant`) and is never granted merely by possessing a verified advocate profile.

---

# 12. Phase 14.5: Production Stabilization, Unified Design System, Consultation Time Authority, & Cryptographic Evidence Sharing

### 12.1. Consultation Room Access & Server-Authoritative Time Engine
- **Root Cause of Defect:** Previously, client browsers attempted to evaluate join windows locally or experienced time zone skew between user devices and server clocks. When scheduled at 04:00 PM IST (10:30 UTC), room entry could be blocked or display confusing mismatch errors.
- **Architectural Solution:**
  - **Server-Authoritative Clock:** The backend (`VideoMeetingService.get_room_access_status`) is the single source of truth. All calculations execute strictly in UTC against `datetime.now(UTC)` and are formatted into Indian Standard Time (IST, UTC+05:30) for presentation.
  - **Dedicated Access Endpoint:** `GET /consultations/{id}/video/access-status` returns structured temporal metadata: `can_join`, `scheduled_start_utc`, `scheduled_start_ist`, `join_window_opens_utc`, `join_window_opens_ist`, `seconds_until_window_opens`, `room_state`, and human-friendly `message`.
  - **Pre-Join Waiting Room Card:** Before window opening, the frontend displays scheduled time (IST), room open time, a deterministic live countdown timer, and automated polling with `[ ↻ Refresh Status ]` and `[ Back to Consultations ]` fallback controls.
  - **Zero Heuristics / Zero AI:** Join eligibility is 100% deterministic based on consultation status, participant authorization (advocate or client), and the 15-minute pre-meeting window.

### 12.2. Network Security & Fetch Robustness
- **Browser CORP Alignment:** Fixed browser-level "TypeError: Failed to fetch" by configuring FastAPI security middleware to dynamically output `Cross-Origin-Resource-Policy: cross-origin` when requests originate from verified CORS allowed origins, avoiding rigid `same-site` rejection during cross-port Next.js development and reverse-proxy deployments.
- **Structured Error Hierarchy:** Replaced generic error strings in `frontend/src/api/client.ts` with typed error classes (`NetworkError`, `AuthenticationError`, `AuthorizationError`, `NotFoundError`, `ConflictError`, `ValidationError`, `RateLimitError`, `ServerError`) mapped through `createSpecificApiError`.
- **Relative Base URLs:** Browser-side API requests default to relative path `""` to leverage Next.js internal rewrites and transparent reverse-proxy headers, preventing hardcoded host/port binding issues.

### 12.3. Shared Design System Architecture
- **Unified Visual Hierarchy:** Introduced shared design primitives in `frontend/src/components/ui`:
  - `PageHeader`: Standardized title, eyebrow, status badges, contextual metadata, and top-level action buttons across Client, Advocate, and Admin surfaces.
  - `SectionHeader`: Structured section headers with record counts, badges, and contextual actions.
- **Design Tokens:** Standardized surface colors (`var(--surface-card)`), text hierarchies (`var(--text-primary)`, `var(--text-secondary)`, `var(--text-muted)`), border styling (`var(--border-subtle)`), and accent colors without introducing bloated CSS-in-JS frameworks or third-party UI libraries.
- **Role Parity without Workflow Conflation:** Advocate chambers, client vault, and administrative oversight share identical typography, spacing tokens, and card styling while preserving strict role isolation and server-enforced RBAC.

### 12.4. Controlled Evidence Sharing Architecture
- **Strict Private Storage:** Evidence items in the Evidence Locker are private to the depositor and case owner by default. Case participation alone does not automatically grant visibility into sensitive exhibits.
- **Explicit Scoped Grants:** Sharing generates an `EvidenceAccessGrant` tied to a specific evidence ID, recipient user UUID, granular permission (`VIEW` or `DOWNLOAD`), and optional ISO-8601 expiration timestamp.
- **Participant Scoping:** An evidence item can only be shared with verified participants of the associated case or counsel assigned through a confirmed consultation. Attempts to grant access to unrelated external users are rejected with `403 Forbidden`.
- **Immediate Revocation:** Revoking a grant (`POST /cases/{case_id}/evidence/{evidence_id}/revoke`) immediately terminates access. Presigned URLs are capped at 60 seconds, ensuring revoked users cannot reuse stale links.
- **Recipient Discovery:** Added `GET /api/v1/documents/shared-with-me` and case-scoped `GET /api/v1/cases/{case_id}/evidence-shared-with-me` allowing recipients to discover files explicitly shared with them.



