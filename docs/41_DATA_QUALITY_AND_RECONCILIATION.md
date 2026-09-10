# 41 — DATA QUALITY, INTEGRITY & RECONCILIATION RUNBOOK

## 1. Operational Integrity & Reconciliation Architecture (Part S)

Over time, network partitions, worker timeouts, and user abandonments can introduce orphan records, stale leases, or impossible state transitions. The Reconciliation Engine detects and corrects these discrepancies without manual SQL intervention.

### Core Repair Invariants
1. **Idempotent Execution**: Running the reconciliation job once or multiple times produces the identical clean state.
2. **Audit Non-Repudiation**: Every repair records a high-priority `AuditEvent` linking the `DataQualityRun` ID and affected record IDs.
3. **Bounded Impact**: Repairs are restricted to safe, predictable state corrections (e.g. resetting stale worker leases, cancelling expired consultation bookings). No irreversible cascading deletions of legitimate customer data are performed.
4. **Dry-Run Default**: The audit mode (`repair=False`) is the safe inspection default; repairs require explicit operator authorization (`repair=True`).

---

## 2. Catalog of Automated Data Quality Checks

| Check Name | Target Domain | Anomaly Condition | Idempotent Repair Action |
| :--- | :--- | :--- | :--- |
| `stale_running_jobs` | Background Workers | Job status is `RUNNING` for $> 30\text{ minutes}$ | Resets status to `PENDING`, increments `retry_count` |
| `expired_consultations`| Consultations | Status is `REQUESTED` with `scheduled_time < now - 24h` | Updates status to `CANCELLED` |
| `orphaned_participants`| Case Access | `CaseParticipant` references non-existent `case_id` | Deletes broken participant row |
| `orphaned_evidence` | Evidence Locker | `EvidenceVersion` references deleted/missing `Evidence` | Deletes dangling version record |
| `custody_chain_gaps` | Chain of Custody | `previous_event_id` missing from custody ledger | Flags integrity anomaly for SecOps forensic review |

---

## 3. Operational Execution Playbook

### Running an Audit Inspection:
```bash
curl -X POST "https://api.legalcasecompanion.in/api/v1/data-quality/reconcile?repair=false" \
  -H "Authorization: Bearer <OPERATOR_TOKEN>"
```

### Running an Automated Reconciliation Repair:
```bash
curl -X POST "https://api.legalcasecompanion.in/api/v1/data-quality/reconcile?repair=true" \
  -H "Authorization: Bearer <OPERATOR_TOKEN>"
```

### Reviewing Historical Audit Runs:
```bash
curl -X GET "https://api.legalcasecompanion.in/api/v1/data-quality/runs" \
  -H "Authorization: Bearer <OPERATOR_TOKEN>"
```
