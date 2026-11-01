# LCC PHASE 2 — DATABASE, ORM, MIGRATION & DATA INTEGRITY AUDIT FINDINGS

---

## DB-FIND-01: [CRITICAL] Four Core Relational Tables Missing from Alembic Migrations

- Finding ID: `DB-FIND-01`
- Severity: `CRITICAL`
- Status: `[VERIFIED]`
- Related Phase 1 Finding: `SEC-FIND-02`

Location:
- `app/models/auth.py:40` (`EmailVerificationToken`)
- `app/models/auth.py:65` (`PasswordResetToken`)
- `app/models/consultation.py` / `app/models/consultation_document.py` (`consultation_documents`)
- `app/models/message.py:12` / `app/models/direct_message.py` (`DirectMessage`)
- `migrations/versions/` (54 migration files)

Evidence:
Comparison of SQLAlchemy `Base.metadata.tables` (84 tables) against the Alembic migration history (54 version files generating 81 distinct tables) reveals that exactly 4 tables have never been created in any Alembic migration:
1. `email_verification_tokens`
2. `password_reset_tokens`
3. `consultation_documents`
4. `direct_messages`

Technical Explanation:
When deployed to production, database schemas are created exclusively via `alembic upgrade head`. The local development fallback `Base.metadata.create_all(bind=engine)` in `app/main.py:78` only executes when `ENVIRONMENT in ("development", "test") and DATABASE_URL.startswith("sqlite")`. Production environments run PostgreSQL and rely exclusively on Alembic. Furthermore, pytest fixtures in `tests/conftest.py` call `Base.metadata.create_all()`, masking this defect during CI/CD test runs.

Failure Scenario:
A fresh deployment or staging environment is provisioned with PostgreSQL and upgraded via `alembic upgrade head`. A user requests password recovery (`POST /api/v1/auth/forgot-password`) or verifies their email OTP (`POST /api/v1/auth/email/verify/otp`). The application throws an unhandled `psycopg2.errors.UndefinedTable: relation "password_reset_tokens" does not exist`, resulting in a fatal HTTP 500 error and complete failure of user onboarding and account recovery.

Impact:
Complete denial of service for password resets, email verifications, consultation document attachments, and direct messaging on any production PostgreSQL database.

Remediation Direction:
Generate a new Alembic migration revision creating all 4 missing tables with exact column types, foreign keys, indexes, and constraints matching their SQLAlchemy ORM declarations.

Required Tests:
- `tests/integration/test_migration_and_recovery_rehearsal.py` executed against a clean PostgreSQL container using `alembic upgrade head`.

---

## DB-FIND-02: [HIGH] Missing Soft-Delete Constraints on 152 ORM Relationships Leads to Historical Data Leaks

- Finding ID: `DB-FIND-02`
- Severity: `HIGH`
- Status: `[VERIFIED]`

Location:
- `app/models/case.py`
- `app/models/document.py`
- `app/models/consultation.py`
- `app/models/evidence.py`
- `app/models/bundle.py`
- `app/models/user.py`
- `app/api/v1/` (33 router queries without explicit `deleted_at.is_(None)`)

Evidence:
An automated traversal of all 84 model mappers in `Base.registry.mappers` and 67 router query sites identified:
1. **36 models** inherit from `SoftDeleteMixin` (`deleted_at`).
2. **152 ORM relationships** target soft-delete models (135 ManyToOne scalar references and 17 OneToMany parent-child collections).
3. **0 of the 152 relationships** declare `deleted_at.is_(None)` within their `primaryjoin` definitions.
4. **33 router query sites** across `app/api/v1/` query soft-delete models directly without filtering `Model.deleted_at.is_(None)` (e.g. `Consultation` by ID in `consultations.py:1245`, `calendar.py:45`).
Machine-readable dataset recorded in `docs/audit/phase-2/soft-delete-inventory.json`.

Examples:
- `Case.documents -> Document`
- `Case.deadlines -> CaseDeadline`
- `Case.hearings -> CaseHearing`
- `EvidenceBundle.items -> EvidenceBundleItem`
- `User.client_profile -> ClientProfile`
- `Consultation.messages -> Message`

Technical Explanation:
SQLAlchemy does not filter soft-deleted rows automatically unless a custom `with_loader_criteria` hook is attached to the `Session` or an explicit `primaryjoin` clause includes `and_(Parent.id == Child.parent_id, Child.deleted_at.is_(None))`. Consequently, navigating relationships in Python (e.g. `len(case.deadlines)` or serializing `case.documents`) automatically loads archived, soft-deleted rows. Furthermore, while report services manually append `.filter(Model.deleted_at.is_(None))`, direct sub-resource endpoints frequently query by primary key without soft-delete filters, allowing access to soft-deleted entities.

Failure Scenario:
A client archives or soft-deletes a sensitive draft document. When an advocate or report generator loads `case.documents`, the ORM eagerly loads the soft-deleted document along with active documents. If the serializer iterates over `case.documents` without explicit application-level filtering, the soft-deleted document's metadata or content leaks back into the client response.

Impact:
Data leakage of deleted/archived legal documents, dead tasks, and withdrawn case claims in API responses and administrative summaries.

Remediation Direction:
1. Implement a global SQLAlchemy ORM execution listener (`@event.listens_for(Session, "do_orm_execute")`) applying `with_loader_criteria(SoftDeleteMixin, lambda cls: cls.deleted_at.is_(None))`.
2. Explicitly specify `primaryjoin` conditions with `deleted_at.is_(None)` on core domain relationships.

Required Tests:
- `tests/integration/test_case_access_and_document_confidentiality.py` asserting soft-deleted documents are omitted when accessing `case.documents`.

---

## DB-FIND-03: [MEDIUM] Non-Concurrent Index Creation in 137 Migrations Causes Table-Level Locking on Production

- Finding ID: `DB-FIND-03`
- Severity: `MEDIUM`
- Status: `[VERIFIED]`

Location:
- `migrations/versions/` (137 `op.create_index` calls across 54 migration files)

Evidence:
AST analysis of all 54 migration files identified **137 `op.create_index` operations** created without `postgresql_concurrently=True`.

Technical Explanation:
In PostgreSQL, executing standard `CREATE INDEX` acquires a `SHARE` lock on the target table. This lock blocks all concurrent `INSERT`, `UPDATE`, and `DELETE` operations on the table until index building completes. On high-volume tables (e.g. `audit_events`, `notifications`, `documents`, `messages`), running migrations without `CONCURRENTLY` during active business hours causes transaction queueing, connection pool exhaustion, and request timeouts.

Failure Scenario:
An operator runs `alembic upgrade head` on a live production PostgreSQL database during active user hours. The migration attempts to build indexes on `audit_events` and `notifications`. The resulting `SHARE` lock blocks all concurrent user logins and notification writes, exhausting the connection pool (`DB_POOL_TIMEOUT=30s`) and triggering HTTP 500 errors across the application.

Impact:
Production downtime and transaction timeouts during schema migration deployment.

Remediation Direction:
1. Update existing and future migrations to use `op.create_index(..., postgresql_concurrently=True)`.
2. Disable transaction wrappers (`commit_block`) for concurrent index migrations in Alembic.

Required Tests:
- Live migration lock inspection tests in staging environments.

---

## DB-FIND-04: [MEDIUM] Missing Database Indexes on High-Growth Chat Table Foreign Keys

- Finding ID: `DB-FIND-04`
- Severity: `MEDIUM`
- Status: `[VERIFIED]`

Location:
- `app/models/message.py:19-24` (`Message` model)
  - `consultation_id: Mapped[uuid.UUID]`
  - `sender_id: Mapped[uuid.UUID]`

Evidence:
Inspection of `Base.metadata.tables["messages"]` reveals that while `Message` defines foreign keys to `consultations.id` and `users.id`, neither column declares `index=True`, and no table-level index exists.

Technical Explanation:
When users join a consultation room or open chat history, the application queries:
```sql
SELECT * FROM messages WHERE consultation_id = :cid AND deleted_at IS NULL ORDER BY created_at ASC;
```
Without a B-tree index on `consultation_id`, PostgreSQL must perform a sequential scan (`Seq Scan`) across the entire `messages` table for every chat load or WebSocket polling request.

Failure Scenario:
As the consultation volume grows to tens of thousands of messages, loading chat history for any individual consultation causes significant CPU spikes, prolonged query latencies exceeding `statement_timeout` (30s), and database thread saturation.

Impact:
Severe query degradation and connection pool starvation during live video consultation chat.

Remediation Direction:
Add an index to `Message.consultation_id` and a composite index on `(consultation_id, created_at)` in a new Alembic migration.

Required Tests:
- `tests/performance/test_retrieval_and_authority_benchmarks.py` asserting indexed index scan on consultation message retrieval.

---

## DB-FIND-05: [MEDIUM] Architectural Discrepancy: Documentation Claims pgvector While Implementation Uses In-Memory Python Cosine Calculation

- Finding ID: `DB-FIND-05`
- Severity: `MEDIUM`
- Status: `[VERIFIED]`

Location:
- `app/models/ai.py:62` (`DocumentChunk.embedding`)
- `app/domain/ai/retrieval_service.py:29-41, 100` (`cosine_similarity()`)
- `app/domain/ai/legal_authority_retrieval.py:19`
- `migrations/versions/` (no `CREATE EXTENSION vector`)

Evidence:
Documentation across `docs/06_AI_INTEGRATION.md` and `docs/15_ARCHITECTURE_DECISION_REGISTER.md` states that semantic search is powered by PostgreSQL's `pgvector` extension.
However, code inspection proves:
1. No migration executes `CREATE EXTENSION IF NOT EXISTS vector`.
2. `DocumentChunk.embedding` is mapped as `SQLiteCompatibleArray(Float)` (PostgreSQL `FLOAT[]` / `ARRAY`), not `vector`.
3. `RetrievalService` executes `query.all()`, loading all document chunks into Python process memory, then calculates similarity in a Python loop using `cosine_similarity()`.

Technical Explanation:
Python-side cosine similarity is viable for small pilots with few document chunks per case. However, it completely bypasses database-side HNSW/IVFFlat vector indexing, requiring large allocations of Python memory and data transfer over the database wire.

Failure Scenario:
A complex litigation matter containing 50 documents with 10,000 text chunks is searched. The application executes `query.all()`, transferring 10,000 768-dimensional float arrays (~30 MB of raw float data) from PostgreSQL to the Python worker, causing severe memory spikes, GC pauses, and high search latencies.

Impact:
High server memory consumption, slow search response times, and failure to meet the architecture's claimed scalability targets.

Remediation Direction:
Adopt native `pgvector` (`pgvector.sqlalchemy.Vector(768)`) with an HNSW index in PostgreSQL for production, retaining Python cosine similarity only as a fallback for local SQLite testing.

Required Tests:
- `tests/evaluation/test_legal_authority_benchmark.py` validating retrieval latency and vector indexing.

---

## DB-FIND-06: [MEDIUM] Missing Composite Unique Constraints on Multi-Tenant Assignment Tables

- Finding ID: `DB-FIND-06`
- Severity: `MEDIUM`
- Status: `[VERIFIED]`

Location:
- `app/models/evidence.py` (`evidence_access_grants`)
- `app/models/operator.py` (`user_operator_permissions`)
- `app/models/court_case.py` (`user_followed_cases`)

Evidence:
Inspection of `Base.metadata.tables` confirms that while `case_participants` declares `UniqueConstraint("case_id", "user_id")` and `user_external_identities` declares `UniqueConstraint("provider", "provider_subject")`, the following assignment tables have **no database-enforced unique constraints**:
1. `evidence_access_grants`: No unique constraint on `(evidence_id, grantee_user_id)`.
2. `user_operator_permissions`: No unique constraint on `(user_id, permission)`.
3. `user_followed_cases`: No unique constraint on `(user_id, court_case_id)`.

Technical Explanation:
Uniqueness is checked solely in application code (e.g. `if existing: return`). Under concurrent API requests (e.g. double-click or parallel automated requests), two requests can simultaneously pass the check-then-act query and insert duplicate active permission or grant rows.

Failure Scenario:
Two concurrent requests grant an operator permission or case access grant. Both insert identical rows. When revocation is subsequently attempted, a query revoking only one row leaves the duplicate active grant in place, failing to fully revoke access.

Impact:
Data duplication, race conditions during permission granting, and potential privilege lingering during revocation.

Remediation Direction:
Add composite unique constraints (`UniqueConstraint("user_id", "permission")`, `UniqueConstraint("evidence_id", "grantee_user_id")`, `UniqueConstraint("user_id", "court_case_id")`) in an Alembic migration.

Required Tests:
- `tests/security/test_operator_permissions.py` testing concurrent permission assignment idempotency.

---

## DB-FIND-07: [LOW] Lack of Database-Level Immutability Rules on Audit Events Table

- Finding ID: `DB-FIND-07`
- Severity: `LOW`
- Status: `[VERIFIED]`

Location:
- `app/models/audit.py:11-26` (`AuditEvent` model)
- `migrations/versions/`

Evidence:
The `audit_events` table contains no `updated_at` column and no `deleted_at` column, and the REST API exposes no mutating routes for audit events. However, no PostgreSQL database-level rules or triggers exist to prevent `UPDATE` or `DELETE` operations executed directly via SQL.

Technical Explanation:
Indian legal standards (such as Section 63 of the Bharatiya Sakshya Adhiniyam, 2023) require electronic records and audit logs to possess verifiable tamper-evident immutability. Application-level immutability does not prevent administrative database users or compromised database accounts from modifying audit rows.

Failure Scenario:
An adversary gaining database access modifies or deletes audit logs to conceal unauthorized access to client evidence. Because no database rule prevents DML on `audit_events`, the audit record is silently altered without trace.

Impact:
Vulnerability of audit log integrity against direct database tampering.

Remediation Direction:
Add PostgreSQL rules or triggers on `audit_events`:
```sql
CREATE RULE no_update_audit AS ON UPDATE TO audit_events DO INSTEAD NOTHING;
CREATE RULE no_delete_audit AS ON DELETE TO audit_events DO INSTEAD NOTHING;
```

Required Tests:
- Migration tests verifying `UPDATE` and `DELETE` on `audit_events` are rejected.

---

## DB-FIND-08: [LOW] Direct db.query() Bypasses of Domain Service Layers in 20 API Routers

- Finding ID: `DB-FIND-08`
- Severity: `LOW`
- Status: `[VERIFIED]`

Location:
- 20 router modules in `app/api/v1/` (`messages.py`, `consultations.py`, `analytics.py`, `pilot.py`, `calendar.py`, `court_cases.py`, etc.)

Evidence:
Static AST analysis found 160 direct `db.query()` calls inside API route handlers rather than delegating data access through domain services or repositories.
Top occurrences:
- `app/api/v1/messages.py`: 41 direct queries
- `app/api/v1/consultations.py`: 23 direct queries
- `app/api/v1/analytics.py`: 23 direct queries
- `app/api/v1/pilot.py`: 17 direct queries
- `app/api/v1/calendar.py`: 10 direct queries

Technical Explanation:
Direct queries in router functions scatter business rules and authorization filters across HTTP transport logic. While no SQL injection exists (parameter binding is used), manual filtering creates inconsistency where some router endpoints forget soft-delete checks or duplicate joins.

Failure Scenario:
An engineer adds a new filter or privacy constraint to a domain entity. Because 20 routers query the database directly instead of calling a centralized service method, the new filter is not applied to the ad-hoc router queries, creating inconsistent query behavior.

Impact:
Maintenance overhead, potential soft-delete filter omission, and architectural fragmentation.

Remediation Direction:
Refactor direct `db.query()` calls in routers into dedicated domain service methods or repository classes.

Required Tests:
- Repository unit tests validating encapsulated data access.

---

## DB-FIND-09: [MEDIUM] Distributed In-Memory OAuth State Store Vulnerable to Multi-Worker Inconsistency and Replay Risks

- Finding ID: `DB-FIND-09`
- Severity: `MEDIUM`
- Status: `[VERIFIED]`
- Related Phase 1 Finding: `SEC-FIND-03`

Cross-Phase Severity Reconciliation:
- SEC-FIND-03 Phase 1 severity: MEDIUM
- DB-FIND-09 Phase 2 severity: MEDIUM
- Severity change: NO
- Justification: In Phase 1, SEC-FIND-03 was classified as MEDIUM due to the failure of single-use replay guarantees in distributed multi-worker environments. In Phase 2, this finding was initially filed as INFO on the grounds that Google authorization codes are also single-use on Google's authorization server. However, an in-memory process dictionary violates distributed single-use guarantees, exposes the state validation layer to TOCTOU race windows across concurrent workers, and breaks audit traceability across the verification pipeline. To maintain strict cross-phase consistency and accurately reflect the absence of distributed persistence (Redis or PostgreSQL unlogged table), the severity is restored to MEDIUM.

Location:
- `app/core/oauth_security.py:138`
- Symbol: `_consumed_oauth_states: dict[str, float] = {}`
- Function: `verify_oauth_state(state_token: str)` (`app/core/oauth_security.py:146-186`)

Evidence:
Single-use tracking for Google OAuth state tokens is maintained in a Python process-level in-memory dictionary `_consumed_oauth_states`. No database table (PostgreSQL) or distributed cache (Redis) is utilized for tracking consumed state `jti` identifiers.

Technical Explanation:
In a production deployment running multiple Gunicorn/Uvicorn worker processes or horizontal Kubernetes pods, memory is not shared across processes. When Worker A processes an OAuth callback and records the token's `jti` in its local dictionary at line 184, Worker B has no record of that `jti`. An attacker who captures an in-flight callback URL can attempt concurrent replay against alternate worker instances within the 10-minute validity window.

Failure Scenario:
Under high traffic, a user completes Google OAuth login on Worker A. A network adversary with access to proxy logs or browser history replays the authorization callback to Worker B. Worker B's in-memory dictionary does not contain the `jti`, bypassing the local replay check. While Google's upstream token endpoint rejects reused authorization codes, the application's internal CSRF/state protection layer is rendered ineffective across worker boundaries.

Impact:
Loss of defense-in-depth against OAuth state token replay across distributed application instances.

Remediation Direction:
Replace `_consumed_oauth_states` with a distributed Redis key (`SET oauth_state:<jti> 1 EX 600 NX`) or an unlogged PostgreSQL table with a TTL cleanup routine.

Required Tests:
- `tests/security/test_oauth_security.py` executing concurrent verification across isolated state store mocks.

---

## DB-FIND-10: [MEDIUM] Non-Atomic External Side Effects, Storage Orphanage, and Premature Webhook Deduplication Lockout

- Finding ID: `DB-FIND-10`
- Severity: `MEDIUM`
- Status: `[VERIFIED]`

Location:
- `app/domain/payments/payment_service.py:297-314` (`create_payment_intent`)
- `app/domain/payments/payment_service.py:471-493, 597` (`handle_webhook`)
- `app/api/v1/documents.py:132-153` (`upload_case_document_direct`)
- `app/api/v1/consultations.py:1265-1277` (`upload_consultation_document`)
- `app/api/v1/kyc.py:189` (`upload_client_kyc_document`)
- `app/domain/auth/auth_service.py:602-618` (`request_password_reset`)
- `app/domain/notifications/notification_service.py:174-186` (`create_notification`)

Evidence:
A systematic 14-point audit of all database transactions executing external side effects (recorded in `docs/audit/phase-2/transaction-matrix.json`) revealed that external operations (S3/MinIO uploads, Stripe API calls, SMTP email dispatches) are executed without transactional consistency guarantees, transactional outbox patterns, or compensating rollbacks:
1. **Document Storage Write-Before-Commit**: In `upload_case_document_direct` and `upload_consultation_document`, files are written to S3 (`storage.put_object_bytes`) before `db.commit()`. If `db.commit()` fails or the process crashes, the uploaded binary blobs remain orphaned in object storage indefinitely with no database metadata pointing to them. Retries create new UUIDs, multiplying orphaned blobs.
2. **Stripe Payment Intent Write-Before-Commit**: In `create_payment_intent`, `self.provider.create_payment_intent` is invoked before `self.db.commit()`. A crash or commit failure leaves a live `PaymentIntent` in Stripe with no `Payment` record in the database. Subsequent webhook deliveries for that intent fail with `ResourceNotFoundError("Payment not found for provider ID")`.
3. **Premature Webhook Deduplication Lockout**: In `handle_webhook`, `ProcessedWebhookEvent` is committed with `status=PROCESSING` at line 489. If the subsequent business logic commit fails at line 597, `webhook_rec` remains stuck in `PROCESSING`. When Stripe automatically retries delivery, lines 471-475 inspect `existing_webhook.status in (PROCESSED, PROCESSING)` and immediately return `{"status": "already_processed"}`. Consequently, Stripe's automatic webhook retries are silenced and permanently discarded, leaving the payment and consultation in an unfinalized state.
4. **Synchronous Email Side Effects Outside Outbox**: Password reset tokens and verification OTPs are committed to the database before calling `email_provider.send_email()`. If SMTP dispatch fails (caught and logged in `SMTPEmailProvider`), the user never receives the email, but the token remains active in the database.

Technical Explanation:
Distributed state mutations between a relational database and external HTTP APIs (Stripe, S3, SMTP) cannot be made atomic without a two-phase protocol, compensating saga, or transactional outbox. Executing external calls immediately before or after `db.commit()` without retry reconciliation or compensating cleanup guarantees data drift under failure conditions.

Failure Scenario:
Stripe delivers a `payment_intent.succeeded` webhook. The application records `status=PROCESSING` and commits. During `CommercialTransaction` capture, a database lock timeout occurs on `self.db.commit()`. The transaction rolls back, but `ProcessedWebhookEvent` remains committed as `PROCESSING`. Stripe retries the webhook 5 minutes later; LCC's deduplication logic checks `status in (PROCESSED, PROCESSING)`, considers it already handled, and returns HTTP 200. The consultation is never marked `PAID`, the advocate is not notified, and the client's money is captured without booking confirmation.

Impact:
Permanent webhook processing lockout, unreferenced storage blob accumulation, and desynchronization between external payment providers and local database state.

Remediation Direction:
1. Modify `handle_webhook` deduplication: Only treat `status == PROCESSED` as `already_processed`. If `status == PROCESSING`, check elapsed time or allow idempotent state re-evaluation.
2. Wrap S3 upload and DB commit in a `try...except` block with compensating cleanup (`storage.delete_object(storage_key)` on DB commit failure).
3. Implement a transactional outbox table (`outbox_events`) for asynchronous email and notification dispatch.

Required Tests:
- `tests/integration/test_payment_resilience.py` simulating database commit failures during webhook ingestion.
- `tests/integration/test_document_upload_compensation.py` asserting storage cleanup on transaction rollback.
