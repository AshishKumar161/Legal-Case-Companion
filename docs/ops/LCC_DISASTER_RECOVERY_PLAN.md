# Legal Case Companion (LCC) — Disaster Recovery & Business Continuity Plan

**Document ID:** `LCC-SRE-DRP-2026-01`  
**Classification:** Confidential — SRE & Security Operations  
**Scope:** Core Database, Evidence Locker, Redis Presence, and Application Services  
**Target Recovery Metrics:**
- **Recovery Time Objective (RTO):** $\le 30\text{ minutes}$ (Maximum tolerable outage duration).
- **Recovery Point Objective (RPO):** $\le 15\text{ minutes}$ (Maximum tolerable data loss window).

---

## 1. Incident Command Structure & Roles

During a severe platform outage or disaster event, the following incident response team is activated:

| Role | Primary Responsibility | Contact Protocol |
| :--- | :--- | :--- |
| **Incident Commander (IC)** | Directs recovery operations, coordinates technical teams, and communicates with executive stakeholders. | PagerDuty Priority 1 / Bridge |
| **Lead SRE / Platform Lead** | Executes infrastructure failover, DNS routing, and container orchestration. | SRE On-Call War Room |
| **PostgreSQL Database Architect** | Manages database restore, PITR recovery, WAL replay, and schema validation. | Database Ops Escalation |
| **Cloud Security Officer (CSO)** | Inspects compromise vectors, rotates cryptographic secrets, and ensures evidence chain-of-custody. | Security Operations Center |
| **Legal Compliance Officer** | Audits regulatory reporting requirements under the DPDP Act and Bar Council rules. | Legal Advisory Bridge |

---

## 2. Disaster Recovery Scenarios & Procedures

### Scenario A: Primary Database Failure or Hardware Loss
**Symptom:** Backend health checks fail with HTTP 503 (`Database unreachable`), continuous connection drops.  
**RTO:** 15 minutes | **RPO:** <= 5 minutes (via automated RDS replica promotion or WAL replay).

#### Step-by-Step Restoration Procedure:
1. **Declare Outage & Engage War Room:**
   - Incident Commander posts notification in `#sre-incidents` and pages on-call engineers.
2. **Promote Standby Hot Replica (If Managed Cloud):**
   ```bash
   aws rds failover-db-cluster --db-cluster-identifier lcc-prod-pg16-cluster
   ```
3. **If Cold Restore from Encrypted Backup is Required:**
   - Fetch the latest verified encrypted dump from the private backup S3 vault:
     ```bash
     aws s3 cp s3://lcc-prod-db-backups/backups/latest/legal_db_latest.dump.enc /tmp/recovery.dump.enc
     ```
   - Decrypt the dump using AES-256-CBC:
     ```bash
     openssl enc -d -aes-256-cbc -pbkdf2 -iter 100000 \
       -in /tmp/recovery.dump.enc \
       -out /tmp/recovery.dump \
       -k "${BACKUP_ENCRYPTION_KEY}"
     ```
   - Verify SHA-256 checksum against committed `.sha256` manifest:
     ```bash
     sha256sum /tmp/recovery.dump.enc
     ```
   - Restore into fresh PostgreSQL target with pgvector enabled:
     ```bash
     pg_restore -h "${NEW_DB_HOST}" -p 5432 -U lcc_admin -d legal_db -v -c /tmp/recovery.dump
     ```
   - Run verification drill script:
     ```bash
     python scripts/verify_pg_backup_restore.py --db-url "${NEW_DATABASE_URL}"
     ```
4. **Traffic Re-routing:**
   - Update `DATABASE_URL` in container orchestration (`render.yaml` or AWS Secrets Manager).
   - Trigger rolling deployment of `lcc-backend` and `lcc-worker`.

---

### Scenario B: AWS Region Outage (`ap-south-1` Failure)
**Symptom:** Total loss of Mumbai region connectivity, S3 buckets, and container hosts.  
**RTO:** 30 minutes | **RPO:** <= 15 minutes.

#### Step-by-Step Procedure:
1. **Activate Secondary Standby Region (`ap-south-2` Hyderabad):**
   - Apply Terraform in secondary region:
     ```bash
     cd deploy/aws && terraform apply -var="aws_region=ap-south-2" -var="environment=prod-dr"
     ```
2. **Promote Replicated S3 Evidence Vault:**
   - Cross-Region Replication (CRR) automatically replicates S3 objects between `ap-south-1` and `ap-south-2`.
   - Update `AWS_S3_BUCKET_NAME` to `lcc-prod-evidence-locker-dr`.
3. **Update Global DNS Ingress (Cloudflare):**
   - Shift traffic via Cloudflare DNS failover pool from Primary ALB to Secondary DR ALB.
4. **Verify Health:**
   - Run [`scripts/verify_production_config.py --env production`](file:///home/ashish/Desktop/lcc/scripts/verify_production_config.py).

---

### Scenario C: Evidence Locker Ransomware / Accidental Deletion
**Symptom:** Document files missing or returning 404 in storage provider.  
**RTO:** 20 minutes | **RPO:** 0 minutes (Zero data loss).

#### Step-by-Step Procedure:
1. **S3 Object Versioning Protection:**
   - The S3 Evidence Locker bucket (`lcc-prod-evidence-locker`) enforces S3 Object Versioning and S3 Object Lock.
   - Accidental `DeleteObject` calls only create a soft *Delete Marker*.
2. **Undelete Operation (Bulk Delete Marker Removal):**
   ```python
   import boto3
   s3 = boto3.client('s3')
   bucket = 'lcc-prod-evidence-locker'
   paginator = s3.get_paginator('list_object_versions')
   for page in paginator.paginate(Bucket=bucket):
       for marker in page.get('DeleteMarkers', []):
           s3.delete_object(Bucket=bucket, Key=marker['Key'], VersionId=marker['VersionId'])
   ```
3. **Forensic Integrity Verification:**
   - Compare SHA-256 hashes of restored files against database records (`documents.sha256_checksum`).

---

### Scenario D: Compromised JWT Private Key or Secret Leak
**Symptom:** Authentication token forged or secret discovered in unauthorized access logs.  
**RTO:** 10 minutes | **RPO:** Immediate session revocation.

#### Step-by-Step Procedure:
1. **Generate New Ed25519 Keypair:**
   ```bash
   python -c "from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey; from cryptography.hazmat.primitives import serialization; k=Ed25519PrivateKey.generate(); print(k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()); print(k.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode())"
   ```
2. **Deploy Dual-Verification Grace Period:**
   - Set `JWT_PRIVATE_KEY` to the new key.
   - Configure verification to accept tokens signed with either old or new public key for 15 minutes (access token TTL).
3. **Purge Refresh Tokens:**
   - Flush active refresh sessions from Redis:
     ```bash
     redis-cli -u "${REDIS_URL}" EVAL "return redis.call('del', unpack(redis.call('keys', 'lcc:refresh:*')))" 0
     ```
   - Users are forced to re-authenticate cleanly via MFA/password.

---

## 3. Disaster Recovery Drill Schedule

To maintain continuous readiness, the following drills are scheduled and documented:

| Frequency | Drill Type | Scope & Acceptance Criteria |
| :--- | :--- | :--- |
| **Weekly (Automated)** | **Automated DB Restore Test** | `verify_pg_backup_restore.py` executes dump, AES-256 decryption, and schema checks. Must complete in < 60s. |
| **Monthly** | **S3 Versioning Undelete Test** | Tests object recovery from delete markers in staging evidence bucket. |
| **Quarterly** | **Simulated Database Failover** | Managed database cluster failover drill during low-traffic maintenance window. Target RTO < 10 mins. |
| **Biannually** | **Full Secret Rotation Drill** | Rotation of JWT keys, CSRF secrets, Turn credentials, and database passwords in staging. |
