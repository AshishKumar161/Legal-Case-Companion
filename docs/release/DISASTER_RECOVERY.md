# Disaster Recovery & Continuity Runbook

**Date:** 2026-09-10  
**Phase:** Phase 12: Production Readiness & Hardening  

---

## 1. Recovery Objectives (RPO & RTO)

| System Component | Recovery Point Objective (RPO) | Recovery Time Objective (RTO) | Backup Mechanism |
| :--- | :--- | :--- | :--- |
| **PostgreSQL Database** | **<= 1 Hour** | **<= 15 Minutes** | Hourly automated snapshots + daily full dump + continuous WAL archiving |
| **AWS S3 Object Storage** | **<= 0 Seconds** | **<= 5 Minutes** | S3 bucket versioning + cross-region replication (CRR) |
| **Redis Cache & State** | **<= 5 Minutes** | **<= 2 Minutes** | Ephemeral cache & presence; automated cluster failover |
| **Background Workers** | **<= 0 Seconds** | **<= 2 Minutes** | Database-backed transactional outbox with 5-minute lease auto-recovery |

---

## 2. Automated Backup Strategy

### Automated PostgreSQL Dumps
- **Frequency:** Every 6 hours automated snapshots + daily full pg_dump.
- **Retention Policy:**
  - Hourly snapshots: 48 hours
  - Daily backups: 30 days
  - Monthly archives: 365 days (encrypted at rest via AES-256)
- **Backup Command:**
  ```bash
  pg_dump -Fc -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -f "/backups/lcc_backup_$(date +%Y%m%d_%H%M%S).dump"
  ```

### S3 Document & Evidence Locker Protection
- All client case evidence and generated PDF bundles stored in S3 feature:
  - **Bucket Versioning:** Enabled. Overwritten or deleted objects retain immutable prior versions.
  - **Default Encryption:** Server-Side Encryption with AWS KMS (`aws:kms`).
  - **MFA Delete:** Required for permanent object version purging.

---

## 3. Step-by-Step Restoration Runbook

### Scenario A: PostgreSQL Database Recovery
1. **Isolate Traffic**: Place frontend in maintenance mode or scale backend API replicas to 0 to prevent incoming writes during restoration:
   ```bash
   docker compose -f docker-compose.prod.yml stop backend worker scheduler
   ```
2. **Locate Latest Verified Backup**: Identify the most recent clean dump from the secure backup vault:
   ```bash
   BACKUP_FILE="/backups/lcc_backup_latest.dump"
   sha256sum "$BACKUP_FILE"
   ```
3. **Restore to Clean Database Instance**:
   ```bash
   pg_restore --clean --if-exists -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -v "$BACKUP_FILE"
   ```
4. **Execute Data Integrity Verification**:
   Run the automated database integrity verification script:
   ```bash
   python scripts/verify_backup_restore.py
   ```
   Verify that all critical tables (`users`, `cases`, `court_cases`, `documents`, `consultations`, `payments`, `notifications`, `case_participants`) match expected row counts.
5. **Re-align Alembic Migration State**:
   ```bash
   alembic current
   alembic upgrade head
   ```
6. **Resume Application Traffic**:
   ```bash
   docker compose -f docker-compose.prod.yml start backend worker scheduler
   curl -f http://localhost:8000/api/v1/health/ready
   ```

### Scenario B: Background Worker Crash / Lease Recovery
- In the event of a worker container crash, uncompleted jobs remain in `status = RUNNING` with `locked_until = <timestamp>`.
- When the 5-minute lease expires, the scheduler or next active worker automatically resets the job state to `PENDING` or claims it directly via `SKIP LOCKED`.
- **Manual Intervention (Emergency Force Release)**:
  ```bash
  python -c "from app.db.database import SessionLocal; from app.domain.jobs.job_service import JobService; db = SessionLocal(); JobService(db).reclaim_expired_leases()"
  ```

### Scenario C: Redis Unavailability
- If Redis crashes or undergoes maintenance, `app/core/redis.py` gracefully degrades:
  - Session tokens continue to be verified cryptographically via Ed25519 public key.
  - Room presence falls back to polling mode.
  - Video signaling continues via WebRTC STUN/TURN fallback.
