# Disaster Recovery & Incident Response Runbook (Phase XV)

## 1. Recovery Objectives (RPO / RTO)

| Subsystem | Metric | Target | Technical Mechanism |
|---|:---:|:---:|---|
| **PostgreSQL Database** | **RPO** | $\le 5\text{ minutes}$ | WAL-G continuous archiving + automated hourly snapshots |
| **PostgreSQL Database** | **RTO** | $\le 30\text{ minutes}$ | Automated point-in-time recovery (PITR) to standby instance |
| **Evidence Locker (S3)** | **RPO** | $0\text{ minutes}$ | S3 Object Versioning + Cross-Region Replication (CRR) |
| **Evidence Locker (S3)** | **RTO** | $\le 15\text{ minutes}$ | Multi-region failover endpoints |
| **Redis Cache / State** | **RTO** | $\le 5\text{ minutes}$ | Ephemeral state rebuild; presence re-heartbeats |

---

## 2. PostgreSQL Point-in-Time Recovery (PITR)

### Automated Backup Architecture
- **Continuous Archiving**: WAL (Write-Ahead Log) segments streamed to private, encrypted S3 backup bucket every 60 seconds.
- **Base Backups**: Full physical database snapshot generated every 24 hours.

### Restoration Procedure
1. Provision target PostgreSQL instance with identical major version (PostgreSQL 15).
2. Restore latest base backup prior to target incident epoch.
3. Configure `recovery.signal` and `restore_command` pointing to WAL archive bucket.
4. Execute recovery to specific target timestamp:
   ```sql
   recovery_target_time = '2026-09-04 02:00:00 UTC'
   recovery_target_action = 'promote'
   ```
5. **Post-Restore Integrity Validation Checklist**:
   - [ ] Verify user accounts and authentication sessions.
   - [ ] Verify active cases and participant memberships.
   - [ ] Query `evidence` and `evidence_versions` records against S3 object keys.
   - [ ] Run automated orphan reconciliation:
     ```python
     python -c "from app.db.database import SessionLocal; from app.services.evidence_service import EvidenceService; db = SessionLocal(); EvidenceService(db).reconcile_orphaned_evidence()"
     ```

---

## 3. Evidence Locker Storage Durability & Reconciliation

### S3 Configuration Standards
- **S3 Object Versioning**: Enabled unconditionally on production evidence buckets.
- **Server-Side Encryption**: SSE-KMS with customer-managed keys (CMK) and strict key rotation.
- **Public Access Block**: All 4 AWS S3 Public Access Block settings permanently enabled.
- **Bucket Policy**: Enforces TLS 1.3+ and restricts access solely to LCC backend IAM execution roles.

### Orphan Reconciliation Playbooks
The system provides automated detection for storage vs database divergence:

1. **Missing S3 Object (Data Loss / Out-of-band Deletion)**:
   - Run `reconcile_orphaned_evidence()`.
   - Identified records are flagged `TAMPER_DETECTED` and logged with `INTEGRITY_FAILED` custody events.
   - P1 security alert dispatched to DevOps oncall.
2. **Abandoned Uploads (Client Abandonment)**:
   - Run `reconcile_abandoned_uploads(hours_threshold=2)`.
   - Evidence records stuck in `UPLOADING` longer than 2 hours transition to `QUARANTINED` with reason logged in custody timeline.

---

## 4. Redis Outage & Failure Recovery

Redis handles ephemeral presence, incoming call queues, and WebSocket ticket validation. It is **never** the source of truth for persistent legal data.

### Behavior During Redis Outage
- **Web API**: Continues serving core database queries, case views, and document access without interruption.
- **Presence**: Falls back gracefully to in-memory tracking or reports lawyers as unavailable until Redis reconnects.
- **WebSocket Calls**: Fails closed for new connections (`503 Service Unavailable`); existing browser tabs receive notification to refresh when connectivity restores.
- **Recovery Action**:
  1. Restart Redis container / restore managed Redis cluster:
     ```bash
     docker compose -f docker-compose.prod.yml restart redis
     ```
  2. Verify Redis responsiveness:
     ```bash
     curl -f http://localhost:8000/api/v1/health/details
     ```
  3. Client heartbeats automatically re-register presence state within 30 seconds.

---

## 5. Security Incident Response Playbooks

### Incident 1: Evidence Tamper Alert (`TAMPER_DETECTED`)
- **Trigger**: `verify-integrity` detects mismatch between stored file SHA-256 and database recorded hash.
- **Immediate Containment**:
  1. Automated: Evidence status transitions to `QUARANTINED`, download access is blocked immediately.
  2. Security audit event `EVIDENCE_TAMPER_DETECTED` emitted with recorded vs computed hash.
- **Investigation**:
  1. Inspect `evidence_custody_events` for recent actor operations.
  2. Check AWS CloudTrail S3 data events for direct object PUT/POST/DELETE outside backend IAM roles.
  3. Verify whether S3 version history retains the authentic original version.
  4. If authentic version exists, restore object bytes and record an official administrative `INTEGRITY_VERIFIED` custody event.

### Incident 2: Malware Detection (`SCAN_FAILED`)
- **Trigger**: ClamAV or Heuristic signature flags uploaded bytes as malicious.
- **Automated Containment**:
  - File status set to `QUARANTINED`.
  - Item is never activated or rendered accessible.
  - Custody event `SCAN_FAILED` recorded with threat signature details.
- **Resolution**:
  - Review threat metadata.
  - If malicious: soft-delete evidence item (`status = DELETED`), retain custody records for legal forensics.

### Incident 3: Refresh Token Compromise / Reuse Alert
- **Trigger**: System detects a revoked refresh token being reused.
- **Automated Action**:
  - Immediately revokes the entire refresh token family.
  - Terminates all active sessions for that user.
  - Logs `REFRESH_TOKEN_REUSE_DETECTED` audit event.
- **Resolution**:
  - Notify affected user to reset password.
  - Verify if any unauthorized API requests were initiated during token lifespan.
