# Phase 9: Operational Recovery & Incident Runbooks

## 1. Operational Philosophy

Operational recovery in Legal Case Companion (LCC) adheres to the **"Zero Manual Database Edits"** principle. Manually mutating database rows via `psql` or database GUIs is strictly prohibited because it bypasses audit trails, triggers, outbox events, and foreign key cascades.

All recovery procedures utilize:
1. **Automated Background Reconcilers** (Scheduled jobs with idempotency keys)
2. **Authoritative Admin API Endpoints** (Guarded by `RequireRole([UserRole.ADMIN])`)
3. **Audited CLI Management Scripts** (Logging operator identity and correlation IDs)

---

## 2. Standard Operating Recovery Runbooks

### Runbook 1: Stuck Payment / Missing Webhook
- **Symptom**: Client was charged by payment gateway, but consultation remains in `REQUESTED` or `ACCEPTED` state due to network partition during webhook delivery.
- **Diagnostic Command**:
  ```bash
  python -m scripts.ops.inspect_payment --consultation-id <UUID>
  ```
- **Automated Resolution**:
  The `reprocess_stale_or_failed_webhooks` job runs every 10 minutes:
  - Queries Stripe API using `provider_payment_id`.
  - Verifies charge status.
  - Idempotently marks `payment.status = SUCCEEDED` and `consultation.status = PAID`.
- **Manual Trigger**:
  ```bash
  python -m scripts.ops.reprocess_webhooks --stale-minutes 5 --limit 50
  ```
- **Audit Impact**: Emits `PAYMENT_RECONCILED` with operator ID.

---

### Runbook 2: Failed Refund Recovery
- **Symptom**: Client cancelled consultation, policy engine authorized refund, but Stripe API timed out. Payment remains in `SUCCEEDED` instead of `REFUNDED`.
- **Diagnostic Query**:
  ```sql
  SELECT id, consultation_id, amount, status, provider_payment_id 
  FROM payments 
  WHERE status = 'SUCCEEDED' 
    AND consultation_id IN (SELECT id FROM consultations WHERE status = 'CANCELLED');
  ```
- **Operator Remediation**:
  Execute idempotent refund via Admin API:
  ```bash
  curl -X POST "https://api.lcc.internal/api/v1/admin/payments/{payment_id}/retry-refund" \
    -H "Authorization: Bearer $ADMIN_TOKEN" \
    -H "X-Request-ID: $(uuidgen)" \
    -d '{"reason": "Automated recovery of failed cancellation refund"}'
  ```
- **Safety Invariant**: Idempotency key `lcc_rfd_{payment_id}` prevents double refund even if executed multiple times.

---

### Runbook 3: Stuck Consultation / Abandoned Meeting
- **Symptom**: Consultation remains in `IN_PROGRESS` hours after scheduled duration because participants closed browser tabs without clicking "End Call".
- **Automated Resolution**:
  The `stale_meeting_cleanup_job` executes every 15 minutes:
  - Finds meetings where `status = ACTIVE` and last heartbeat > 15 minutes ago.
  - Automatically transitions meeting to `ENDED` and consultation to `COMPLETED`.
- **Manual Operator Command**:
  ```bash
  python -m scripts.ops.cleanup_stale_meetings --max-idle-minutes 15
  ```

---

### Runbook 4: Dead-Letter Outbox Event Recovery
- **Symptom**: Outbox event exhausted max attempts (5) and moved to `DEAD_LETTER` (e.g. downstream SMTP provider experienced extended outage).
- **Inspection Command**:
  ```sql
  SELECT id, event_type, aggregate_type, aggregate_id, attempt_count, last_error, scheduled_at 
  FROM outbox_events 
  WHERE status = 'DEAD_LETTER' 
  ORDER BY scheduled_at DESC LIMIT 20;
  ```
- **Re-queue Procedure**:
  Once downstream dependency is restored, reset event status to `PENDING`:
  ```bash
  python -m scripts.ops.requeue_dead_letters --event-type NOTIFICATION_DISPATCH --batch-size 100
  ```
- **Safety**: Target event handlers are strictly idempotent.

---

### Runbook 5: Failed Document / Evidence Processing
- **Symptom**: Document upload completed, but malware scanner crashed or timed out. Document stuck in `STAGED` / `PENDING_SCAN`.
- **Automated Resolution**:
  Worker lease expires in 60s. Any available worker claims the job and re-runs scanner.
- **Manual Reprocess**:
  ```bash
  curl -X POST "https://api.lcc.internal/api/v1/cases/{case_id}/evidence/{evidence_id}/rescan" \
    -H "Authorization: Bearer $ADMIN_TOKEN"
  ```

---

### Runbook 6: AI Quota Desynchronization
- **Symptom**: Network drop during AI generation caused client quota counter to drift from actual statutory query ledger.
- **Resolution Command**:
  ```bash
  python -m scripts.ops.reconcile_ai_quotas --user-id <UUID>
  ```
- Recalculates total tokens consumed from `audit_events` and realigns `commercial_entitlements`.

---

## 3. Operator Checklist Before Declaring Incident Resolved

1. Confirm `GET /health/readiness` returns HTTP 200 across all pods.
2. Confirm zero events in `outbox_events` stuck in `PROCESSING` past their lease window.
3. Confirm zero orphaned `video_meetings` in `ACTIVE` state with 0 connected peers.
4. Verify Prometheus metric `lcc_error_rate_5xx` returned to <0.01%.
5. Review generated audit entries for all executed operator commands.
