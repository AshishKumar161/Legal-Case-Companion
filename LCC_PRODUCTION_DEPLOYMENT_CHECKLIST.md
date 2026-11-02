# Legal Case Companion (LCC) — Production Deployment Checklist

**Document ID:** `LCC-SRE-CHK-2026-01`  
**Classification:** Operational Runbook  
**Target Phase:** Pre-Production to Production Handoff  
**Mandatory Rule:** Do not deploy to production. Do not start automatic deployment. Every checkbox must be manually verified and signed off by the Lead SRE, Security Architect, and Database Administrator.

---

## 1. Cryptographic Secrets & Environment Configuration

- [ ] **Ed25519 Authentication Keys:**
  - High-entropy PEM-encoded Ed25519 private key configured in `JWT_PRIVATE_KEY` (Not present in code repository).
  - Corresponding public key configured in `JWT_PUBLIC_KEY`.
- [ ] **CSRF Protection:**
  - `CSRF_SECRET_KEY` populated with a unique 64-character random hex string.
- [ ] **Environment Mode:**
  - `ENVIRONMENT="production"` set explicitly.
  - `DEBUG=false` strictly enforced (checked by boot assertion).
- [ ] **CORS Isolation:**
  - `BACKEND_CORS_ORIGINS` strictly contains `["https://app.legalcasecompanion.in"]`.
  - Zero wildcard (`*`) origins permitted.
- [ ] **Cookie Security:**
  - Refresh token cookies configured with `Secure=True`, `HttpOnly=True`, `SameSite=Strict`.

---

## 2. Database & Data Migration Readiness

- [ ] **PostgreSQL Version & Extension:**
  - PostgreSQL 16.x or 18.x running with `pgvector >= 0.8.0`.
  - Extension verified via `SELECT extversion FROM pg_extension WHERE extname = 'vector';`.
- [ ] **Performance Configuration:**
  - `maintenance_work_mem >= 512MB` for HNSW index builds.
  - `shared_buffers = 2GB` (or 25% of system memory).
  - `random_page_cost = 1.1` for NVMe/SSD storage.
- [ ] **Database Connection Pooling:**
  - `DB_POOL_SIZE=25`, `DB_MAX_OVERFLOW=15`, `DB_POOL_TIMEOUT=30.0`.
  - `DB_STATEMENT_TIMEOUT_MS=15000` (15s query limit to prevent connection starvation).
- [ ] **Migration State Check:**
  - `alembic heads` shows exactly 1 clean head ([z3a4b5c6d7e8_enforce_payout_idempotency_not_null.py](file:///home/ashish/Desktop/lcc/migrations/versions/z3a4b5c6d7e8_enforce_payout_idempotency_not_null.py)).
  - Schema changes adhere to expand-and-contract pattern.
  - Rollback migration verified using [`tests/integration/test_payout_migration_backfill_and_rollback.py`](file:///home/ashish/Desktop/lcc/tests/integration/test_payout_migration_backfill_and_rollback.py).

---

## 3. Cloud Storage, KMS & Malware Security Guardrails

- [ ] **AWS S3 Bucket Governance:**
  - Dedicated buckets provisioned in `ap-south-1` (`lcc-prod-evidence-locker`, `lcc-prod-consultation-recordings`).
  - S3 Block Public Access enabled on all 4 settings (`BlockPublicAcls`, `IgnorePublicAcls`, `BlockPublicPolicy`, `RestrictPublicBuckets`).
  - S3 Object Versioning enabled for immutable legal audit trails.
- [ ] **KMS Customer Managed Key (CMK):**
  - CMK created with annual rotation enabled (`enable_key_rotation = true`).
  - Bucket policy requires SSE-KMS with CMK on all `PutObject` operations.
  - TLS 1.3 enforced via `aws:SecureTransport: true`.
- [ ] **ClamAV Antivirus Daemon:**
  - Dedicated `clamd` container active and responding on TCP `3310`.
  - `freshclam` service updating virus signatures every 2 hours.
  - Fail-closed operational policy verified: offline daemon forces incoming documents to remain quarantined.
- [ ] **Video Recording Policy:**
  - `VIDEO_RECORDING_ENABLED=false` strictly maintained across production settings until explicit legal and regulatory approval is granted.

---

## 4. Observability, Logging & Alerting Setup

- [ ] **Structured JSON Logging:**
  - `logging.py` configured with `JsonFormatter` in production.
  - Regex PII/credential scrubbing verified (Aadhaar, PAN, Cards, Tokens redacted).
- [ ] **Log Shipper:**
  - Fluent Bit / CloudWatch Agent configured to stream logs from container stdout.
- [ ] **Prometheus Metrics:**
  - Scrape target active at `GET /metrics` exporting OpenMetrics text format.
  - Latency quantiles (P50, P90, P95, P99) and status codes (2xx, 4xx, 5xx) tracking properly.
- [ ] **Prometheus Alerting Rules:**
  - `alert.rules.yml` loaded into Alertmanager.
  - Alert notifications routed to SRE on-call channel (Slack `#sre-alerts` / PagerDuty).
- [ ] **Grafana Operational Dashboard:**
  - `grafana_dashboard.json` imported with active telemetry panels.
- [ ] **OpenTelemetry Tracing:**
  - `OTEL_EXPORTER_OTLP_ENDPOINT` pointing to production OTLP collector.

---

## 5. Automated Backups & Disaster Recovery Verification

- [ ] **Automated Encrypted Backups:**
  - [`scripts/db_backup_encrypted.sh`](file:///home/ashish/Desktop/lcc/scripts/db_backup_encrypted.sh) scheduled via cron / Kubernetes CronJob every 6 hours.
  - AES-256 encryption active with strong offsite key.
  - SHA-256 checksums stored alongside encrypted backup files in S3 backup vault.
- [ ] **Restoration Verification Drill:**
  - Executed [`scripts/verify_pg_backup_restore.py`](file:///home/ashish/Desktop/lcc/scripts/verify_pg_backup_restore.py).
  - Confirmed 100% byte fidelity, schema integrity, and pgvector HNSW index preservation.
  - Drill completion time under 60 seconds (well within RTO <= 30 mins).

---

## 6. Pre-Flight Diagnostic Execution

Before approving production deployment, run the pre-flight verification CLI:

```bash
python scripts/verify_production_config.py --env production
```

**Required Output:** `Result: [PASSED] — Configuration satisfies environment readiness requirements.` with 0 critical issues.

---

## 7. Sign-off & Go/No-Go Decision Matrix

| Role | Name | Decision | Date | Signature / Auth Token |
| :--- | :--- | :--- | :--- | :--- |
| **Lead Platform / DevOps Engineer** | Ashish Kumar | **PENDING AUDIT** | `2026-11-03` | `[Awaiting Infrastructure Provisioning]` |
| **Site Reliability Engineer (SRE)** | On-Call Lead | **PENDING AUDIT** | `2026-11-03` | `[Awaiting Infrastructure Provisioning]` |
| **Cloud Security Architect** | SecOps Lead | **PENDING AUDIT** | `2026-11-03` | `[Awaiting Infrastructure Provisioning]` |
| **Principal Database Architect** | DBA Lead | **PENDING AUDIT** | `2026-11-03` | `[Awaiting Infrastructure Provisioning]` |

> [!CAUTION]
> If any critical checkbox is unchecked or any verification script fails, the deployment status remains **NO-GO**. Automatic deployment is strictly prohibited.
