# LCC PHASE 3 — BUSINESS LOGIC, DOMAIN WORKFLOW & STATE INTEGRITY AUDIT FINDINGS

---

# SECTION 0: CROSS-PHASE OAUTH STATE RECONCILIATION

```text
PHASE 1 SEC-FIND-03:
MEDIUM

PHASE 2 DB-FIND-09:
MEDIUM

PHASE 3 OAUTH STATE IMPLEMENTATION:
[VERIFIED]

OAUTH STATE STORAGE:
Process Memory (_consumed_oauth_states dict in app/core/oauth_security.py:138)

REDIS USED FOR OAUTH STATE:
NO

REDIS USED FOR OTHER AUTH SESSION STATE:
NO (Redis used for user presence & distributed locks; refresh sessions stored in PostgreSQL)

CROSS-PHASE CONTRADICTION:
RESOLVED

FINAL SEVERITY:
MEDIUM
```

### Complete Source-Level Trace of OAuth State Lifecycle:
1. **OAuth Authorization Initiation:** Initiated via `GET /api/v1/auth/google/login` which invokes `GoogleOAuthService.get_authorization_url` (`app/domain/auth/google_oauth_service.py:44-90`).
2. **State Generation:** Handled by `app/core/oauth_security.py:generate_oauth_state` (lines 96-135). Generates a cryptographic nonce via `secrets.token_urlsafe(32)`, validates redirect URI against allowed origins, and creates an Ed25519-signed JWT with a 10-minute expiry (`exp = now + 10m`) and unique `jti` (`secrets.token_urlsafe(16)`).
3. **State Persistence:** None. The state token is self-contained and stateless, transmitted in the query string parameter to Google (`https://accounts.google.com/o/oauth2/v2/auth?state=<jwt>&...`).
4. **State Retrieval:** Returned by Google in the HTTP callback query parameters (`GET /api/v1/auth/google/callback?code=...&state=...`).
5. **State Consumption:** Handled by `app/core/oauth_security.py:verify_oauth_state(state_token)` (lines 146-185). Decodes the JWT using `settings.JWT_PUBLIC_KEY`, validates `exp`, `iss` (`legal-case-companion`), and `aud` (`lcc_oauth_state`).
6. **Replay Detection:** Extracts `jti` claim; checks `if jti in _consumed_oauth_states: raise AuthenticationError("OAuth state has already been used. Replay detected.")`.
7. **Expiration Pruning:** Prunes expired records older than 15 minutes: `if _consumed_oauth_states[k] < now_ts - 900: _consumed_oauth_states.pop(k, None)`.
8. **Callback Validation:** Validates `nonce`, `purpose`, and verifies `redirect_uri` matches request origin.
9. **Multi-Worker Behavior:** `_consumed_oauth_states` is a standard Python module-level dictionary (`_consumed_oauth_states: dict[str, float] = {}`) residing in process heap memory. In multi-worker Uvicorn/Gunicorn deployments or containerized replicas, state consumed on Worker A is completely invisible to Worker B. A state token can therefore be replayed against another worker within its 10-minute validity window. Furthermore, process restarts wipe the replay tracking table entirely.
10. **Redis / Session-Store Usage:**
    - Static analysis confirms Redis (`app/core/redis.py`) is used exclusively for distributed presence tracking (`app/domain/consultations/presence_service.py`) and optional locking (`app/core/locking.py`).
    - Redis is NOT used for OAuth state tokens.
    - Redis is NOT used for authentication session storage (refresh tokens are stored in the PostgreSQL `refresh_token_sessions` table).
    - The preliminary Phase 3 claim that `DB-FIND-09` was "handled via Redis session store" was factually incorrect and is hereby formally retracted and reconciled with Phase 1 and Phase 2.

---

# SECTION 1: DOMAIN BUSINESS LOGIC FINDINGS

### Finding ID: BL-FIND-01
**Severity:** HIGH  
**Classification:** [VERIFIED]  
**Title:** Bypass of Lawyer Verification Gates via Direct Case Participant Addition  

**Affected Domain:** Cases & Workflows / Lawyer Profile & Verification  

**Exact File(s):**  
- `app/domain/cases/case_service.py`  
- `app/api/v1/cases.py`  
- `app/core/authorization.py`  
- `app/domain/documents/document_service.py`  

**Exact Function/Class/Symbol:**  
- `CaseService.add_participant` (`app/domain/cases/case_service.py:511-580`)  
- `cases.add_case_participant` (`app/api/v1/cases.py:200-215`)  
- `authorize_case_access` (`app/core/authorization.py:23-35`)  
- `authorize_case_modification` (`app/core/authorization.py:38-47`)  
- `authorize_document_access` (`app/core/authorization.py:76-105`)  
- `DocumentService.generate_download_url` (`app/domain/documents/document_service.py:465-495`)  

**Evidence:**  
In `app/domain/cases/case_service.py`, `add_participant` validates that `requested_role == ParticipantRole.LAWYER` and `target_user.role == UserRole.LAWYER`, and confirms `target_user.account_status == AccountStatus.ACTIVE` (lines 530–545). However, it completely omits checking whether `lawyer_profile.verification_status == "APPROVED"`. In contrast, `grant_lawyer_access` (lines 665–675) strictly checks:
```python
lawyer_profile = self.db.query(LawyerProfile).filter(
    LawyerProfile.user_id == req.lawyer_user_id,
    LawyerProfile.deleted_at.is_(None),
).first()
if not lawyer_profile or lawyer_profile.verification_status != "APPROVED":
    raise ValidationError("Case access can only be granted to verified lawyers")
```

**Subsequent Authorization & Data Access Trace (11-Point Verification):**
1. *Post-Participant Authorization Check:* Once added, `_get_case_participant(db, case_id, user.id)` returns an active `CaseParticipant` record with role `LAWYER`.
2. *Membership Requirement:* `authorize_case_access` and `authorize_document_access` require ONLY active `CaseParticipant` membership (`status == ParticipantStatus.ACTIVE`).
3. *Verification Requirement in Downstream Checks:* NO downstream case or document endpoint checks `lawyer_profile.verification_status`.
4. *Role Requirement:* Checks `user.role` only for lawyer-private notes; case participation itself grants access.
5. *Case Role Checking:* Modification endpoints check `participant_role != VIEWER`. Since the user is added as `LAWYER`, this check passes.
6. *Account Status:* Checked only at insertion time; not re-evaluated during `_get_case_participant`.
7. *Ownership Requirement:* Ownership is only checked for case deletion and participant management; general case reading, updating, and document downloading do not require ownership.
8. *Document vs Evidence Grant Requirements:*
   - **Documents (`Document` model):** NO individual grant required. `authorize_document_access` automatically inherits access from the parent case (`if doc.case_id: authorize_case_access(...)`).
   - **Evidence (`Evidence` model):** Evidence Locker items require an explicit `EvidenceAccessGrant` (or creator/case OWNER role). However, adding the unverified lawyer as an active participant satisfies the prerequisite gate for the case owner to grant them evidence access via `share_evidence` (`app/domain/evidence/evidence_service.py:577-582`). Furthermore, if the user is added as `ParticipantRole.OWNER`, they receive immediate full access to all evidence items.
9. *Document Retrieval by Unverified Lawyer:* **YES [VERIFIED].** An unverified lawyer can call `GET /api/v1/cases/{case_id}/documents` to list all case files and call `GET /api/v1/cases/{case_id}/documents/{document_id}/download` to receive presigned S3 URLs and download confidential case files in `SAFE` security status.
10. *Evidence Retrieval by Unverified Lawyer:* **CONDITIONAL [VERIFIED].** If added as `ParticipantRole.OWNER`, immediate full evidence download is possible. If added as `ParticipantRole.LAWYER`, evidence access requires an explicit grant, but the participant addition unlocks grant eligibility.
11. *Modification of Case Resources:* **YES [VERIFIED].** An unverified lawyer can update case metadata (`PATCH /cases/{case_id}`), create tasks, manage deadlines, upload new documents, and append lawyer-private case notes.

**Failure Scenario:**  
An unverified user registers an account with role `LAWYER`. Their Bar Council verification is in `PENDING`, `DRAFT`, `REJECTED`, or `REVOKED` status. An unwitting or colluding case owner calls `POST /api/v1/cases/{case_id}/participants` with `participant_role: LAWYER`. The request succeeds. The unverified user immediately downloads all confidential client documents, views case activity, updates case status, and writes legal notes, completely circumventing statutory advocate verification.

**Business Impact:**  
Breaches statutory bar compliance and platform guarantees that only verified advocates may review client legal matters. Creates severe regulatory liability under Bar Council of India rules for enabling unverified legal practice.

**Security/Data Integrity/Availability Impact:**  
Attorney-client privileged files, unredacted client disclosures, and sensitive litigation documents are exposed to unvetted third parties.

**Existing Mitigation:**  
`grant_lawyer_access` endpoint enforces verification, but `add_participant` provides an ungated bypass path.

**Missing Control:**  
`CaseService.add_participant` must query `LawyerProfile` for the target user and enforce `lawyer_profile.verification_status == VerificationStatus.APPROVED` before allowing assignment of `ParticipantRole.LAWYER` or `ParticipantRole.OWNER`.

**Test Coverage:**  
`tests/integration/test_case_operations_and_workflow.py` tests valid participant addition, but lacks any negative test verifying that unapproved lawyers are rejected.

**Confidence:** HIGH (`[VERIFIED]`)  

**Related Phase 1 Finding:** `AUTH-VERIF-02` (Inconsistent Lawyer Profile Verification Enforcement)  
**Related Phase 2 Finding:** None  

---

### Finding ID: BL-FIND-02
**Severity:** MEDIUM  
**Classification:** [VERIFIED]  
**Title:** Permissive Metadata, Participant, and Note Modification on Closed/Archived Cases  

**Affected Domain:** Cases & Workflows / Evidence Management  

**Exact File(s):**  
- `app/domain/cases/case_service.py`  
- `app/domain/evidence/evidence_service.py`  
- `app/core/authorization.py`  

**Exact Function/Class/Symbol:**  
- `CaseService.update_case` (lines 418–475)  
- `CaseService.add_participant` (lines 511–580)  
- `CaseService.remove_participant` (lines 933–984)  
- `CaseService.create_note` (lines 1464–1500)  
- `EvidenceService.init_upload` (lines 120–160)  

**Evidence:**  
In `app/domain/cases/case_workflow_service.py:137`, task and deadline mutations enforce case active status:
```python
if case.status in (CaseStatus.CLOSED, CaseStatus.CANCELLED):
    raise BusinessRuleError(f"Cannot mutate workflow elements on a {case.status.value} case")
```
However, this check is absent across core `CaseService` and `EvidenceService` methods. Specifically:
1. `CaseService.update_case`: While `ALLOWED_CASE_TRANSITIONS` prevents changing status out of `CLOSED` or `CANCELLED`, requests updating `title` or `description` execute without checking `case_.status`.
2. `CaseService.add_participant` and `remove_participant`: Call `authorize_participant_management`, which only checks if `case.deleted_at.is_(None)` and `participant.participant_role == OWNER`. It never checks `case.status in (CaseStatus.CLOSED, CaseStatus.CANCELLED)`.
3. `CaseService.create_note`: Appends case notes to closed cases without restriction.
4. `EvidenceService.init_upload`: Calls `authorize_case_access` and stages new evidence uploads on closed cases without verifying case lifecycle state.

**Failure Scenario:**  
A legal matter is resolved and transitioned to `CLOSED`. Months later, an authorized participant alters the case title and description, adds a new external viewer or lawyer participant, appends informal case notes, or initiates evidence uploads. The audit record reflects changes on a closed legal case, violating case immutability expectations required for legal dispute resolution and regulatory recordkeeping.

**Business Impact:**  
Compromises legal case record finality and integrity. In legal practice, once a matter is closed, its participants, core metadata, and record set must be locked to prevent retroactive alterations.

**Security/Data Integrity/Availability Impact:**  
Data integrity violation; post-closure modification allows unmonitored participant additions and documentation changes on sealed matters.

**Existing Mitigation:**  
`CaseWorkflowService` protects deadlines and tasks, but core case management and evidence staging omit the check.

**Missing Control:**  
`authorize_case_modification`, `authorize_participant_management`, and `CaseService.update_case` must reject any state mutations when `case.status in (CaseStatus.CLOSED, CaseStatus.CANCELLED)`, unless an administrative unarchive workflow is invoked.

**Test Coverage:**  
`tests/integration/test_case_operations_and_workflow.py` verifies that `status` cannot be changed out of `CLOSED`, but contains zero tests asserting that title updates, participant changes, notes, or evidence uploads are rejected on closed cases.

**Confidence:** HIGH (`[VERIFIED]`)  

**Related Phase 1 Finding:** None  
**Related Phase 2 Finding:** `DB-FIND-07` (Audit Event Immutability and Persistence Gaps)  

---

### Finding ID: BL-FIND-03
**Severity:** HIGH  
**Classification:** [VERIFIED]  
**Title:** Silent Refund Swallowing on Consultation Cancellation Leaving Inconsistent Terminal Financial State  

**Affected Domain:** Consultations / Commercial Payments  

**Exact File(s):**  
- `app/domain/consultations/consultation_service.py`  

**Exact Function/Class/Symbol:**  
- `ConsultationService.cancel_consultation` (lines 1045–1110)  

**Evidence:**  
In `ConsultationService.cancel_consultation`, the consultation status is committed as `CANCELLED` prior to processing the refund:
```python
consultation.status = ConsultationStatus.CANCELLED
self.db.commit()
self.db.refresh(consultation)
...
if economics.refund_eligible and economics.refund_amount > Decimal("0.00"):
    txn = self.db.query(CommercialTransaction).filter(
        CommercialTransaction.consultation_id == consultation.id
    ).first()
    if txn and txn.status in (TransactionStatus.CAPTURED, TransactionStatus.AUTHORIZED):
        try:
            commercial_svc = CommercialService(self.db)
            commercial_svc.process_refund(...)
        except Exception as e:
            logger.warning(
                "Automatic cancellation refund failed for consultation %s: %s",
                consultation.id,
                e,
            )
```
If `process_refund` fails (e.g., Stripe API timeout, network drop, card error, or database exception), the error is caught by `except Exception:` and swallowed with only a warning log. Because the method already committed `consultation.status = ConsultationStatus.CANCELLED`, any subsequent attempt to retry `cancel_consultation` hits the idempotency guard:
```python
if consultation.status == ConsultationStatus.CANCELLED:
    return consultation  # Idempotent
```
The retry short-circuits immediately without ever attempting to re-execute the refund. Furthermore, no background job or dead-letter queue is enqueued to retry the failed refund.

**Failure Scenario:**  
A client cancels an upcoming consultation within the 100% refund eligibility window. The database commits the consultation status to `CANCELLED`. During the refund call, the payment gateway experiences a brief transient network timeout. The exception is logged and swallowed; the client receives a 200 OK response indicating successful cancellation. However, the commercial transaction remains `CAPTURED`, the client's money is not refunded, and retrying the cancellation endpoint returns immediately without issuing the refund.

**Business Impact:**  
Direct client financial harm, billing disputes, chargebacks, and potential consumer protection violations due to unreturned funds on cancelled bookings.

**Security/Data Integrity/Availability Impact:**  
State divergence between consultation domain (`CANCELLED`) and commercial payment domain (`CAPTURED`), leaving an un-reconciled financial invariant violation.

**Existing Mitigation:**  
Periodic manual reconciliation; no automated retry mechanism exists in code.

**Missing Control:**  
Either execute cancellation and refund within an atomic two-phase commit / saga, or if refund fails, revert `consultation.status` back to previous state, or persist a pending refund job to the Outbox table for guaranteed retry.

**Test Coverage:**  
`tests/integration/test_consultation_lifecycle_production.py` tests successful cancellation refunds, but lacks tests simulating refund failure during cancellation.

**Confidence:** HIGH (`[VERIFIED]`)  

**Related Phase 1 Finding:** None  
**Related Phase 2 Finding:** `DB-FIND-10` (External Side Effects vs Database Transactions)  

---

### Finding ID: BL-FIND-04
**Severity:** MEDIUM  
**Classification:** [VERIFIED]  
**Title:** Post-Consultation Commercial Refund Inappropriately Reverts Completed Consultation to CANCELLED State  

**Affected Domain:** Payments & Billing / Consultations  

**Exact File(s):**  
- `app/domain/payments/commercial_service.py`  

**Exact Function/Class/Symbol:**  
- `CommercialService.process_refund` (lines 250–265)  

**Evidence:**  
In `app/domain/payments/commercial_service.py`, when a full refund is executed on a transaction, lines 253–257 perform an unconditional state mutation on the associated consultation:
```python
# Update consultation if full refund
if not is_partial:
    consultation = self.db.query(Consultation).filter(
        Consultation.id == txn.consultation_id
    ).first()
    if consultation:
        consultation.status = ConsultationStatus.CANCELLED
        consultation.updated_at = now
```
`process_refund` does not inspect `consultation.status`. Even if the consultation was already `COMPLETED` (i.e. the legal consultation meeting was held, notes written, and time spent), issuing a commercial full refund (e.g., following a customer satisfaction settlement or billing dispute) unconditionally forces `consultation.status = ConsultationStatus.CANCELLED`. This directly violates the terminal invariant enforced in `ConsultationService.cancel_consultation`:
`"Cannot cancel consultation in terminal 'COMPLETED' state"`.

**Failure Scenario:**  
A lawyer conducts a 60-minute video consultation with a client. The lawyer marks the meeting `COMPLETED`, adds notes, and links the matter to a case. Later, the client complains about video resolution issues, and customer support issues a courtesy full refund via `POST /api/v1/commercial/refund`. `CommercialService.process_refund` overwrites `consultation.status` to `CANCELLED`. As a result, the consultation appears in historical reports as if it never occurred, advocate attendance metrics are corrupted, and automated payout calculations that rely on non-cancelled sessions are invalidated.

**Business Impact:**  
Distorts lawyer performance metrics, platform audit records, tax reporting, and advocate compensation calculations.

**Security/Data Integrity/Availability Impact:**  
Corrupts state machine integrity by reverting a terminal `COMPLETED` entity back to `CANCELLED`.

**Existing Mitigation:**  
None. The code does not check prior status before overwriting.

**Missing Control:**  
`process_refund` must check `if consultation.status != ConsultationStatus.COMPLETED:` before updating `consultation.status = ConsultationStatus.CANCELLED`, or maintain refund state solely on `CommercialTransaction` and `RefundRecord` without mutating consultation lifecycle history.

**Test Coverage:**  
`tests/integration/test_payment_workflow_comprehensive.py` tests refunds of pending/scheduled bookings, but contains zero tests refunding a transaction linked to a `COMPLETED` consultation.

**Confidence:** HIGH (`[VERIFIED]`)  

**Related Phase 1 Finding:** None  
**Related Phase 2 Finding:** None  

---

### Finding ID: BL-FIND-05
**Severity:** MEDIUM  
**Classification:** [VERIFIED]  
**Title:** Implicit Case Participant Insertion with Commit Side Effect During Thread Read and Direct Messaging  

**Affected Domain:** Messaging & Collaboration / Cases & Workflows  

**Exact File(s):**  
- `app/api/v1/messages.py`  

**Exact Function/Class/Symbol:**  
- `_resolve_active_case_between` (lines 170–195)  
- `send_direct_message` (lines 530–575)  

**Evidence:**  
In `app/api/v1/messages.py`, read operations (such as resolving thread context in `GET /api/v1/messages/threads/{partner_id}`) and write operations (`POST /api/v1/messages`) contain logic that automatically mutates and commits case participants without owner authorization:
Lines 170–194:
```python
if consultation and consultation.case:
    shared_case = consultation.case
    # Ensure lawyer is enrolled as a participant
    lawyer_user_id = user1_id if lp1 else user2_id
    existing_p = db.query(CaseParticipant).filter(
        CaseParticipant.case_id == shared_case.id,
        CaseParticipant.user_id == lawyer_user_id,
    ).first()
    if not existing_p:
        lawyer_part = CaseParticipant(
            id=generate_uuid7(),
            case_id=shared_case.id,
            user_id=lawyer_user_id,
            participant_role=ParticipantRole.LAWYER,
            status=ParticipantStatus.ACTIVE,
            joined_at=datetime.now(UTC),
        )
        db.add(lawyer_part)
        db.commit()
```
And lines 540–574:
```python
if case_id_str:
    case_uuid = uuid.UUID(case_id_str)
    # Ensure sender is enrolled as participant
    part = db.query(CaseParticipant).filter(...).first()
    if not part:
        new_p = CaseParticipant(..., participant_role=role, status=ParticipantStatus.ACTIVE)
        db.add(new_p)
    # Ensure recipient is enrolled as participant
    recip_part = db.query(CaseParticipant).filter(...).first()
    if not recip_part:
        new_rp = CaseParticipant(..., participant_role=r_role, status=ParticipantStatus.ACTIVE)
        db.add(new_rp)
```
This behavior:
1. Executes database mutation and `db.commit()` inside an expected idempotent HTTP GET operation.
2. Automatically grants `CaseParticipant` access with `ACTIVE` status without checking case owner authorization (`authorize_participant_management`).
3. Enrolls users even if the case is `CLOSED` or `CANCELLED`.
4. Bypasses lawyer verification checks (`BL-FIND-01`).

**Failure Scenario:**  
A client and lawyer previously held a consultation that was linked to a case. Later, a user views the message thread or sends a direct chat message mentioning the case. The router automatically injects the lawyer (or recipient) as an active case participant and commits to the database. The case owner never approved adding this participant, yet the recipient is now granted case-level access rights across the platform.

**Business Impact:**  
Subverts case access control policies and business authorization workflows. Violates principle of least privilege in legal matter management.

**Security/Data Integrity/Availability Impact:**  
Unauthorized participant creation, side effects on read requests, and potential breach of confidential case materials.

**Existing Mitigation:**  
None. The router helper automatically executes the insertion whenever thread context is resolved.

**Missing Control:**  
Remove implicit `CaseParticipant` creation from messages router. Case participation must only be granted through explicit case service endpoints (`add_participant` or `grant_lawyer_access`) with proper authorization checks.

**Test Coverage:**  
`tests/integration/test_messages.py` tests standard message transmission, but does not assert whether participant side effects occur during read requests.

**Confidence:** HIGH (`[VERIFIED]`)  

**Related Phase 1 Finding:** `AUTHZ-CASE-01` (Case Participant Authorization Bypass)  
**Related Phase 2 Finding:** `DB-FIND-08` (Direct Database Queries in API Routers)  

---

### Finding ID: BL-FIND-06
**Severity:** LOW  
**Classification:** [VERIFIED]  
**Title:** Broad Exception Swallowing Across 46 Critical Workflow Handlers Compromising Error Visibility and Compensating Sagas  

**Affected Domain:** Cross-Domain (Consultations, Auth, Notifications, Documents, Payments)  

**Exact File(s):**  
- `app/domain/consultations/consultation_service.py` (lines 125, 1093, 1267)  
- `app/domain/notifications/notification_service.py` (lines 187, 240)  
- `app/domain/auth/auth_service.py` (lines 618, 742)  
- `app/domain/email/email_service.py` (line 120)  
- 42 additional occurrences cataloged in `docs/audit/phase-3/broad_exceptions.json`  

**Evidence:**  
Static AST scan across `app/domain/` and `app/api/v1/` identified 91 `except Exception:` blocks, of which 46 swallow or log errors without re-raising, initiating compensating transactions, or enqueuing dead-letter retries. Key examples include:
- `consultation_service.py:1093`: Automatic cancellation refund failure caught and logged with `logger.warning`, leaving customer un-refunded (`BL-FIND-03`).
- `notification_service.py:187`: WebSocket real-time push failure swallowed, causing notification badge state to diverge from database state.
- `auth_service.py:618`: Session cleanup failure swallowed silently.
- `email_service.py:120`: SMTP dispatch failures logged without scheduling retries in outbox queue.

**Failure Scenario:**  
A downstream subsystem (Stripe, SMTP server, Redis channel, or WebSocket broker) experiences transient downtime. The core business operation succeeds in committing its primary database record, but secondary side effects fail silently. The caller receives HTTP 200 OK, but no compensating rollback occurs, no alert is raised, and no persistent retry queue recovers the operation.

**Business Impact:**  
Clients and lawyers experience dropped notifications, missing confirmation emails, and un-refunded payments with zero automated self-healing.

**Security/Data Integrity/Availability Impact:**  
State divergence between distributed components; loss of error traceability.

**Existing Mitigation:**  
Error logging to standard application logs.

**Missing Control:**  
Use explicit transactional Outbox pattern for all external side effects; replace broad `except Exception:` with specific exception handlers and dead-letter queue enqueuing.

**Test Coverage:**  
Existing integration tests run against mocks that succeed, masking error handling deficits in failure paths.

**Confidence:** HIGH (`[VERIFIED]`)  

**Related Phase 1 Finding:** None  
**Related Phase 2 Finding:** `DB-FIND-10` (External Side Effects vs Database Transactions)  

---

### Finding ID: BL-FIND-07
**Severity:** LOW  
**Classification:** [VERIFIED]  
**Title:** Business Logic and State Mutation Fragmentation Across 45 API Router Modules  

**Affected Domain:** Architecture & Domain Boundary Integrity  

**Exact File(s):**  
- 45 router modules under `app/api/v1/` (including `cases.py`, `messages.py`, `consultations.py`, `commercial.py`, `evidence.py`)  

**Exact Function/Class/Symbol:**  
- 159 direct `db.query()` calls  
- 28 direct `db.commit()` calls  
- 27 direct `db.add()` calls  
- 38 direct `.status =` mutations  

**Evidence:**  
In violation of the project's intended service-layer encapsulation pattern, API router modules frequently bypass domain services to execute raw ORM queries, mutate lifecycle status fields, and commit transactions directly. Specifically:
- `app/api/v1/messages.py`: Directly instantiates `CaseParticipant`, mutates status, and executes `db.commit()` (lines 193, 362, 435, 606).
- `app/api/v1/cases.py`: Directly queries `CaseParticipant` and `MatterRequest` instead of delegating to `CaseService`.
- `app/api/v1/commercial.py`: Mixes direct queries with `CommercialService` calls.

**Failure Scenario:**  
A business rule is updated in a domain service (such as adding verification checks or audit logging), but router endpoints that bypass the domain service continue executing legacy, un-gated queries and state mutations, leading to inconsistent behavior and security regressions.

**Business Impact:**  
High risk of logic drift, fragmented validation, and maintenance overhead across teams.

**Security/Data Integrity/Availability Impact:**  
Bypasses centralized domain invariants and audit event dispatching.

**Existing Mitigation:**  
Core workflows predominantly reside in `app/domain/`, but router leakage is prevalent in peripheral operations.

**Missing Control:**  
Refactor all router database interactions to delegate strictly through domain service classes; prohibit direct `db.commit()` and direct entity instantiation in API router functions.

**Test Coverage:**  
Test suite executes against API endpoints and validates existing behavior, but lacks linting or architectural boundary enforcement tests.

**Confidence:** HIGH (`[VERIFIED]`)  

**Related Phase 1 Finding:** None  
**Related Phase 2 Finding:** `DB-FIND-08` (Direct Database Queries in API Routers)  

---

### Finding ID: BL-FIND-08
**Severity:** LOW  
**Classification:** [VERIFIED]  
**Title:** Loss of Forensic Revocation History upon Re-sharing Revoked Evidence Access Grants  

**Affected Domain:** Evidence & Forensics  

**Exact File(s):**  
- `app/domain/evidence/evidence_service.py`  

**Exact Function/Class/Symbol:**  
- `EvidenceService.share_evidence` (lines 584–598)  

**Evidence:**  
In `app/domain/evidence/evidence_service.py`, when evidence is shared with a user who previously had access that was revoked, the method mutates the existing grant in-place:
```python
if grant:
    grant.access_level = req.access_level
    grant.expires_at = req.expires_at
    grant.revoked_at = None
    grant.revocation_reason = None
```
This in-place mutation overwrites and clears `revoked_at` and `revocation_reason` on the `EvidenceAccessGrant` record. While a `SHARED` event is appended to `EvidenceCustodyEvent`, the specific historical metadata explaining why the previous grant was revoked (e.g. security breach, conflict of interest, or court order) is erased from the access grant entity.

**Failure Scenario:**  
An evidence grant is formally revoked due to a legal conflict of interest, recording a detailed `revocation_reason`. Later, a case administrator carelessly re-shares the evidence with the same user. The revocation timestamp and reason are erased in-place from the database record, hindering legal discovery and compliance audits that inspect active and historical grant grants.

**Business Impact:**  
Impairs forensic auditability in litigation and legal compliance proceedings where evidence access history must be preserved without in-place erasure.

**Security/Data Integrity/Availability Impact:**  
Immutability violation on historical security revocation metadata.

**Existing Mitigation:**  
`EvidenceCustodyEvent` captures custody audit events, but the access grant table loses the historical revocation state.

**Missing Control:**  
Never clear `revoked_at` in-place; when re-granting access, either create a new `EvidenceAccessGrant` row or archive the previous grant to an `EvidenceGrantHistory` table.

**Test Coverage:**  
`tests/integration/test_evidence_e2e.py` verifies standard grant and revocation, but does not test re-granting access to a previously revoked recipient.

**Confidence:** HIGH (`[VERIFIED]`)  

**Related Phase 1 Finding:** None  
**Related Phase 2 Finding:** `DB-FIND-07` (Audit Event Immutability and Persistence Gaps)  

---
