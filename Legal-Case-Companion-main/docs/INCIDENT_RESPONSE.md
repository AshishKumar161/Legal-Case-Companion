# Legal Case Companion (LCC) — Production Incident Response Playbook

This document defines operational response procedures for high-severity infrastructure and service incidents in production.

---

## 1. Incident Classification & Severity Levels

| Severity | Definition | Target Response | Target Resolution |
| :--- | :--- | :--- | :--- |
| **SEV-1 (Critical)** | Core platform offline; database unavailable; payment webhook failures; widespread video session collapse; data confidentiality threat. | < 15 minutes | < 2 hours |
| **SEV-2 (Major)** | Degradation of critical feature (e.g. ClamAV scanner down with documents staying quarantined; background worker stopped; email delays). | < 30 minutes | < 6 hours |
| **SEV-3 (Minor)** | Non-blocking operational issue; isolated user payment discrepancy; single container restart. | < 2 hours | Next business day |

---

## 2. Emergency Incident Playbooks

### Playbook 1: PostgreSQL Database Outage / Connection Pool Exhaustion
**Symptoms:** `/api/v1/health/ready` and `/readiness` return `HTTP 503 {"status": "not_ready", "database": "disconnected"}`. Backend logs display `TimeoutError: QueuePool limit of size 20 overflow 10 reached`.

**Immediate Actions:**
1. Check active database connections:
   ```sql
   SELECT count(*), state FROM pg_stat_activity GROUP BY state;
   ```
2. Identify long-running unindexed queries exceeding `DB_STATEMENT_TIMEOUT_MS`:
   ```sql
   SELECT pid, now() - query_start AS duration, query 
   FROM pg_stat_activity 
   WHERE state = 'active' AND (now() - query_start) > interval '30 seconds';
   ```
3. Terminate stuck backend connections if necessary:
   ```sql
   SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE pid <> pg_backend_pid() AND state = 'idle in transaction';
   ```
4. If the database instance crashed on Render / AWS RDS, trigger automatic failover or restart via hosting dashboard.

---

### Playbook 2: ClamAV Daemon Outage
**Symptoms:** Documents remain in `DocumentSecurityStatus.QUARANTINED` with processing error `"Malware scanner service is temporarily unavailable. Document remains quarantined."`. Backend logs display `ClamAV daemon connection failed (clamav:3310)`.

**Design Verification:**
* **Fail-Closed Guarantee:** Under Non-Negotiable Principle 9, the application **never** marks unverified documents as `SAFE`. Client case confidentiality and safety are preserved.

**Immediate Actions:**
1. Check ClamAV container status:
   ```bash
   docker ps -a | grep lcc_clamav
   docker logs --tail 50 lcc_clamav_prod
   ```
2. Check memory usage (ClamAV requires ~1.2 GB RAM for signature definitions):
   ```bash
   docker stats lcc_clamav_prod
   ```
3. Restart the ClamD daemon container:
   ```bash
   docker restart lcc_clamav_prod
   ```
4. Once the daemon reports healthy (`clamdscan --ping 3310`), the background worker's stale job recovery will automatically re-queue pending quarantined documents for scanning.

---

### Playbook 3: Payment Webhook Outage / Signature Failures
**Symptoms:** Consultations remain in `REQUESTED`/`ACCEPTED` after clients report successful payment. Logs display `Signature verification failed` or `Webhook signature timestamp expired`.

**Immediate Actions:**
1. Inspect Stripe dashboard webhook logs:
   - Navigate to **Stripe Dashboard → Developers → Webhooks → Endpoint `https://api.legalcasecompanion.in/api/v1/webhooks/stripe`**.
   - Check response codes (401, 400, or 500).
2. Verify secret synchronization:
   - Check `STRIPE_WEBHOOK_SECRET` in production `.env` / Render environment settings. Ensure the secret begins with `whsec_`.
3. Replay failed webhooks:
   - Once the endpoint is verified, click **Resend Failed Events** in the Stripe Dashboard.
   - The LCC payment service is strictly idempotent (`PaymentStatus.SUCCEEDED` check) and will safely transition consultations without duplicate billing.

---

### Playbook 4: WebRTC / Coturn TURN Relay Outage
**Symptoms:** Video room connects locally, but remote video shows `"Waiting for Peer to Join Video Stream"` when users are behind symmetric NAT or corporate firewalls.

**Immediate Actions:**
1. Check coturn listening sockets:
   ```bash
   netstat -tulpn | grep 3478
   ```
2. Inspect coturn logs:
   ```bash
   docker logs --tail 100 lcc_coturn_prod
   ```
3. Test TURN credential generation:
   - Run `scripts/verify_production_config.py --env production`.
   - Verify `TURN_SERVER_URL`, `TURN_USERNAME`, and `TURN_CREDENTIAL` are loaded into `settings`.
4. If coturn host IP changed, update DNS A-record for `turn.legalcasecompanion.in`.

---

### Playbook 5: Background Worker / Scheduler Failure
**Symptoms:** Document processing jobs, text extraction, and deadline scans cease updating. `background_jobs` table shows accumulating `PENDING` status.

**Immediate Actions:**
1. Check process status:
   ```bash
   docker logs --tail 50 lcc_worker_prod
   docker logs --tail 50 lcc_scheduler_prod
   ```
2. Check for duplicate scheduler instances (ensure only ONE scheduler process is active to prevent stampeding scan jobs).
3. Restart worker:
   ```bash
   docker restart lcc_worker_prod
   docker restart lcc_scheduler_prod
   ```
4. The scheduler loop will trigger `STALE_JOB_RECOVERY` within 5 minutes, reclaiming expired lease locks.

---

### Playbook 6: Private S3 Storage Outage
**Symptoms:** Presigned upload/download URL generation fails with `ClientError: EndpointConnectionError` or `AccessDenied`.

**Immediate Actions:**
1. Verify AWS IAM credentials (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`).
2. Verify AWS S3 bucket status in `ap-south-1` via AWS Status Dashboard.
3. Verify bucket CORS policy allows `PUT` from `https://app.legalcasecompanion.in`.
4. Ensure bucket policy enforces `s3:x-amz-server-side-encryption: AES256`.

---

## 3. Post-Incident Review (PIR) Template

```markdown
# Post-Incident Review: [Incident Title]
- **Date / Time:** YYYY-MM-DD HH:MM UTC
- **Duration:** XX minutes
- **Severity:** SEV-X
- **Impacted Services:** [Backend / Video / Payments / Documents]
- **Root Cause:** [Detailed technical summary of trigger and failure mode]
- **Mitigation & Fix:** [Immediate remediation steps executed]
- **Preventative Actions:** [Action items to prevent recurrence, assigned to owners]
```
