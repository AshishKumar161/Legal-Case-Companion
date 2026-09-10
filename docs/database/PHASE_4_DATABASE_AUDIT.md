# Comprehensive Database, Migration & Concurrency Audit — Phase 4

## 1. Executive Summary

Phase 4 of the Legal Case Companion (LCC) production hardening focused on database correctness, Alembic migration safety, schema integrity, transaction boundaries, concurrency controls, and SQLAlchemy 2.0 modernization.

### Key Audit Metrics:
- **Alembic Graph**: 52 linear revisions; 0 branch points; 0 merge points; single head `w1a2b3c4d5e6`.
- **SQLAlchemy 2.0 Deprecations**: Reduced from 13 legacy `Query.get()` warnings to **0 warnings**.
- **Migration Safety**: Audited all 52 migration files; eliminated all instances of swallowed exceptions (`except Exception: pass`); implemented automatic data preservation and rollback symmetry in `25500e9a54c3`.
- **Concurrency & Locking**: Implemented atomic database updates and `SELECT FOR UPDATE` patterns across booking, refunds, and quota accounting.

---

## 2. Transaction Safety & Ordering Audit

Critical workflows were audited against the standard transactional boundary lifecycle:
```text
BEGIN
  → VALIDATE (check invariants, availability, quotas)
  → DB CHANGES (stage updates, insert audit records)
  → EXTERNAL SIDE EFFECT (Stripe / Agora / Twilio API calls)
  → COMMIT (finalize database transaction)
  → POST-COMMIT ACTION (send webhooks, dispatch asynchronous notifications)
```

### 2.1 Consultation Booking & Escrow Payment
1. **BEGIN**: Open database transaction.
2. **VALIDATE**: Ensure lawyer availability slot is not already booked (`AppointmentStatus.CONFIRMED`), client has sufficient quota, and cohort rules allow booking.
3. **DB CHANGES**: Mark appointment status as `PENDING_PAYMENT` with a lock on the lawyer's availability record.
4. **EXTERNAL SIDE EFFECT**: Call Stripe API to create `PaymentIntent` with client client_secret. If Stripe call fails, transaction automatically rolls back.
5. **COMMIT**: Commit `appointment` and `consultation` records with `PaymentIntent` ID.
6. **POST-COMMIT ACTION**: Dispatch notification to client and lawyer.

### 2.2 Payment Refund & Cancellation
1. **BEGIN**: Open transaction.
2. **VALIDATE**: Ensure consultation is eligible for refund (not already refunded, meeting not held, within cancellation window).
3. **DB CHANGES**: Transition consultation status to `REFUND_PENDING` with an idempotency lock on `payment_id`.
4. **EXTERNAL SIDE EFFECT**: Dispatch Stripe refund request.
5. **COMMIT**: On Stripe confirmation, transition status to `REFUNDED` and write to `evidence_custody_log` and `audit_events`.
6. **POST-COMMIT ACTION**: Dispatch refund confirmation email.

### 2.3 AI Token Quota & Budget Enforcement
1. **BEGIN**: Open transaction.
2. **VALIDATE**: Check remaining token budget for user / tenant.
3. **DB CHANGES**: Execute atomic update:
   ```sql
   UPDATE users SET ai_tokens_used = ai_tokens_used + :tokens
   WHERE id = :user_id AND (ai_tokens_used + :tokens) <= ai_tokens_limit;
   ```
4. **COMMIT**: Ensure budget deduction is committed before calling LLM inference.

---

## 3. Concurrency & Race Condition Safeguards

| Operation | Potential Race Condition | Vulnerability Without Protection | Database Mechanism | Regression Test Coverage |
|---|---|---|---|---|
| **Consultation Booking** | Simultaneous booking of the same lawyer slot | Double booking | Row-level locking (`with_for_update`) on availability slot + unique index on `(lawyer_id, scheduled_at)` | `test_session_and_concurrency.py` |
| **Instant Consultation** | Multiple clients claiming the same instant lawyer | Multiple clients matched to single lawyer | Atomic state change (`UPDATE appointments SET lawyer_id = ... WHERE status = 'WAITING'`) | `test_consultations_advanced.py` |
| **Refund Request** | Concurrent refund triggers for same payment | Double refund on Stripe | Unique constraint on `refund_requests.payment_id` + idempotency key | `test_payment_hardening.py` |
| **AI Quota Tracking** | Rapid parallel LLM prompts exceeding monthly cap | Quota bypass | Atomic `WHERE (tokens_used + :cost) <= token_budget` | `test_ai_quota_and_budget.py` |
| **Appointment Reminders** | Distributed workers scanning pending reminders | Duplicate SMS/email sent | `SELECT FOR UPDATE SKIP LOCKED` on reminder queue + unique constraint on `(appointment_id, reminder_stage)` | `test_appointment_reminders.py` |
| **Stale Meeting Cleanup** | Multi-worker sweeping of expired video rooms | Duplicate teardown events | Atomic status update `WHERE status = 'ACTIVE' AND expires_at < NOW()` | `test_video_cleanup_cron.py` |

---

## 4. Index & Query Performance Optimization

Frequently queried access paths and background scanner indexes:

1. **`appointments (lawyer_id, scheduled_at)`**:
   - **Query**: Calendar availability lookups and conflict detection.
   - **Benefit**: Replaces table scans with targeted B-tree range scans.
   - **Write Cost**: Low; updated once per appointment.
2. **`appointments (status, scheduled_at)`**:
   - **Query**: Background reminder and auto-completion cron scanners.
   - **Benefit**: Index-only scan for pending appointments.
3. **`consultations (stripe_payment_intent_id)`**:
   - **Query**: Webhook reconciliation lookups from Stripe webhooks.
   - **Benefit**: $O(1)$ unique index lookup.
4. **`video_meetings (room_id, status)`**:
   - **Query**: Real-time WebRTC signaling join queries.
   - **Benefit**: Eliminates table scan during session negotiation.
5. **`evidence_custody_log (case_id, recorded_at)`**:
   - **Query**: Audit chain verification queries.
   - **Benefit**: Fast sequential scans ordered by timestamp.

---

## 5. SQLAlchemy 2.0 Modernization

### Identified Deprecations:
- Legacy warning: `LegacyAPIWarning: The Query.get() method is considered legacy as of the 1.x series of SQLAlchemy and becomes a legacy construct in 2.0. The method is now available as Session.get().`
- Instances: 13 occurrences across integration test suites:
  - 8 in [`tests/integration/test_document_security_and_websocket_signaling.py`](file:///c:/Users/akuma/OneDrive/Desktop/lcc/Legal-Case-Companion-main/tests/integration/test_document_security_and_websocket_signaling.py)
  - 5 in [`tests/integration/test_v1_e2e_product_journeys.py`](file:///c:/Users/akuma/OneDrive/Desktop/lcc/Legal-Case-Companion-main/tests/integration/test_v1_e2e_product_journeys.py)

### Modernization Fix:
- Replaced all `db.query(Model).get(id)` with `db.get(Model, id)`.
- Verified 0 warnings remain during execution.

---

## 6. Database Connection & Session Configuration

1. **Pooling & Pre-Ping**:
   - `pool_pre_ping=True` configured on the SQLAlchemy engine to detect and discard stale or closed connections before handing them to requests.
   - PostgreSQL engine configured with:
     - `pool_size = settings.DB_POOL_SIZE` (default 20)
     - `max_overflow = settings.DB_MAX_OVERFLOW` (default 10)
     - `pool_timeout = settings.DB_POOL_TIMEOUT` (default 30)
     - `pool_recycle = settings.DB_POOL_RECYCLE` (default 1800)
2. **Statement Timeout & Security**:
   - Connection parameter `-c statement_timeout=5000` prevents run-away queries from consuming worker capacity.
   - In production and staging, `sslmode="require"` is strictly enforced.
3. **Session Lifecycle**:
   - Standard `get_db()` FastAPI dependency enforces explicit session closure in `finally: db.close()`.
   - Background tasks instantiate dedicated, short-lived sessions via `SessionLocal()` and guarantee disposal via context managers.
