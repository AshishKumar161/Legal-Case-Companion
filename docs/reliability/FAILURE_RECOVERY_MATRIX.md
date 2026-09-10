# Phase 9: Cross-System Failure Recovery Matrix

## 1. Overview

Distributed systems fail at service boundaries. This matrix analyzes what happens when any discrete step in an end-to-end Legal Case Companion (LCC) workflow fails, detailing current behavior, persistent data state, automated recovery mechanisms, idempotency safety, user impact, and audit consequences.

---

## 2. Master Failure Recovery Matrix

| Workflow Step | Injected Failure | Current System Behavior | Persistent Data State | Expected Recovery Mechanism | Retry Safe? | User Impact | Audit Consequence |
|---|---|---|---|---|---|---|---|
| **Payment Intent Creation** | DB commit succeeds, but Stripe API times out | Endpoint catches timeout, does not commit orphaned payment row, raises 503 | DB rolled back; no orphaned payment created | Client retries request with same consultation ID; new intent generated | **YES** (Idempotent by consultation ID) | User sees retry prompt; no funds deducted | `PAYMENT_INTENT_FAILED` logged with provider error |
| **Payment Capture Webhook** | Stripe succeeds, but DB commit fails during webhook processing | Webhook handler returns 500; Stripe triggers automatic webhook retry schedule (up to 72h) | Stripe: `succeeded`; DB: `PaymentStatus.PENDING` | `reprocess_stale_or_failed_webhooks` background job or Stripe retry re-syncs state | **YES** (Deduplicated by Stripe `event_id`) | Minor delay in room state flip; funds safe | `WEBHOOK_FAILED` logged; succeeded upon retry |
| **Consultation Booking & Email** | DB commit succeeds, but SMTP provider is down | Consultation is committed; email dispatch logs warning or enqueues outbox event | DB: `ConsultationStatus.REQUESTED`; In-app notification created | Outbox worker retries email with exponential backoff up to 5 times | **YES** (Outbox event deduplication) | User sees booking confirmation immediately; email arrives after provider restores | `CONSULTATION_REQUESTED` committed; email retry logged |
| **Meeting Creation & Recording** | Video room created, but recording consent/storage fails | Room remains joinable; recording flag marked `FAILED`; meeting continues | DB: `VideoMeeting.status = ACTIVE`, `VideoRecording.status = FAILED` | Background job `RECORDING_UPLOAD_RETRY` retries upload from memory/disk buffer | **YES** (Idempotent recording session ID) | Meeting proceeds normally; participants notified recording disabled | `RECORDING_FAILED` audited; user notified |
| **AI Quota & LLM Timeout** | Quota reserved in DB, but LLM provider times out (30s) | AI exception handler catches timeout; immediately executes compensatory refund | DB: Client monthly quota restored to previous value | Client can resubmit query with lower context or switch to fallback provider | **YES** (Compensatory transaction applied) | User receives "AI service temporarily busy, quota not charged" | `AI_TIMEOUT` and `AI_QUOTA_REFUNDED` audited |
| **Scheduled Reminders** | Reminder persisted in DB, but notification provider fails | In-app reminder saved; external SMS/email delivery fails | DB: `CaseDeadline` active; `Reminder` marked `FAILED` | `ReminderService` scheduled worker claims failed reminders and retries with backoff | **YES** (Idempotency key `rem_{id}_{window}`) | In-app reminder visible; external alert delayed | `REMINDER_FAILED` logged with retry attempt count |
| **Frontend Network Drop (500/Drop)** | Server completes operation (e.g. consultation confirmed), but network drops response | Operation committed in DB; frontend receives network drop / timeout | DB: Consultation is `SCHEDULED`; Lawyer marked confirmed | Frontend refetches authoritative state via TanStack Query on reconnect or window focus | **YES** (Read query resynchronizes state) | Optimistic error resolved on background refetch | Authoritative state verified in `/workspace` |
| **Duplicate Webhook Delivery** | Stripe webhook delivered twice simultaneously | Second delivery matches unique `event_id` in `processed_webhook_events` table | DB: Single payment capture; single commercial transaction | Second delivery acknowledged with HTTP 200 without re-executing state mutation | **YES** (Strict `event_id` unique constraint) | Zero double charging or double crediting | Second event logged as `WEBHOOK_DEDUPLICATED` |
| **Evidence Upload & Worker Crash** | Document uploaded to S3, but virus scanner worker crashes halfway | Outbox event remains in `PROCESSING` state; worker lease expires after 60s | S3: File present; DB: `EvidenceStatus.STAGED`, version unactivated | Parallel worker instance re-claims lease after `locked_until < now` and finishes scan | **YES** (File is read-only during scan) | Document shows "Scanning..." for extra 60s, then activates | Scan completion audited upon worker restart |
| **Concurrent Slot Reservation** | Two clients attempt to book the exact same lawyer slot simultaneously | First transaction acquires pessimistic row lock on `LawyerProfile`; second raises 422 | DB: Exactly one consultation created; second transaction rolled back | Second user receives 422 with clear message: "Requested time slot is no longer available" | **YES** (Database row-lock boundary) | One client successfully books; other client selects alternative slot | Failed booking logged as `SLOT_CONFLICT` |
| **Advocate De-registration** | Lawyer profile deleted while consultation is scheduled | Service validates active bookings before allowing profile deletion | DB: Deletion rejected if future `SCHEDULED` consultations exist | Operator or lawyer must cancel/reschedule active consultations before profile removal | **YES** (Foreign key RESTRICT constraint) | Client consultation protected from sudden orphaned cancellation | Deletion rejection audited with blocker count |
| **Redis Outage / Eviction** | Redis server restarts or connection pool exhausted | System automatically falls back to thread-safe `InMemoryRedisClient` | Memory cache serves heartbeat TTLs and short-lived tickets | When Redis recovers, pool reconnects without application restart or dropped traffic | **YES** (Graceful degradation architectural pattern) | Zero downtime; transient cache warm-up | `REDIS_FALLBACK_ACTIVE` logged as warning |

---

## 3. Distributed Consistency Strategies

### Strategy 1: Atomicity via Database Boundary
Whenever possible, multi-step state mutations are enclosed within a single ACID database transaction. If any local database operation fails, `db.rollback()` guarantees zero partial data commits.

### Strategy 2: Compensatory Transactions for External Providers
External networks cannot be enclosed in a PostgreSQL transaction. When an external provider call fails after a database reservation:
1. Catch provider exception explicitly (`AIProviderError`, `StripeError`).
2. Execute a compensatory transaction (e.g. `quota.refund()`, `payment.mark_failed()`).
3. If the compensatory transaction itself fails, persist an event to the `OutboxEvent` table with `status = FAILED` for background reconciliation.

### Strategy 3: Deduplication via Unique Database Constraints
Network retries are guaranteed safe by enforcing unique constraints at the database storage layer:
- `payments.idempotency_key` (UNIQUE)
- `processed_webhook_events.event_id` (UNIQUE)
- `background_jobs.idempotency_key` (UNIQUE)
- `case_participants(case_id, user_id)` (UNIQUE)
- `consultations(lawyer_id, scheduled_at)` (EXCLUSION / Slot check with `with_for_update`)
