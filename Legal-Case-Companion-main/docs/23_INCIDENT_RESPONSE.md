# Legal Case Companion — Security Incident Response & Forensics Playbook

**Document Reference**: `docs/23_INCIDENT_RESPONSE.md`  
**Phase**: Phase XVI — Production Security Hardening, Privacy, Data Protection & Deployment Readiness  
**Target System**: Legal Case Companion (LCC)  
**Security Posture**: Fail-Closed, Forensic Preservation, Rapid Containment

---

## 1. Incident Severity Classification

| Level | Severity | Description | Response Target | Example Scenarios |
| :--- | :--- | :--- | :--- | :--- |
| **P1** | **Critical** | Core cryptographic compromise, active evidence tampering, data exfiltration | **Immediate (< 15 mins)** | JWT private key leak, unauthorized DB dump, S3 bucket public exposure |
| **P2** | **High** | Targeted account takeover, malware bypass, worker queue compromise | **< 1 hour** | High-privilege lawyer account compromise, ClamAV bypass attempt |
| **P3** | **Medium** | Rate limit evasion, suspicious authentication volume, dead-letter spike | **< 4 hours** | Distributed brute-force login attempts, outbox worker failure |
| **P4** | **Low** | Non-exploitable vulnerability, informational scan warning | **< 24 hours** | Low-severity dependency notice, minor typo in public documentation |

---

## 2. Standard Incident Response Lifecycle

Every incident progresses through 8 structured phases:
```text
1. Detect   → Metric alert, deep health probe, log alert, user report
2. Contain  → Network isolation, credential revocation, session termination
3. Preserve → Snapshot database, archive custody records, export audit logs
4. Rotate   → Issue new Ed25519 keys, rotate DB/S3/Redis credentials
5. Revoke   → Invalidate active refresh tokens, blacklist compromised tokens
6. Recover  → Point-in-time recovery (PITR), restore from encrypted backups
7. Validate → Execute automated regression & health probes
8. Report   → Post-mortem documentation, regulatory notice (if applicable)
```

---

## 3. Dedicated Incident Playbooks

### Playbook A: JWT Private Signing Key Compromise (Severity: P1)
1. **Immediate Containment**:
   - Generate a new Ed25519 key pair immediately.
   - Deploy new key pair to all backend instances.
   - Do **NOT** set `JWT_PREVIOUS_PUBLIC_KEY` in an emergency compromise scenario; force immediate re-authentication.
2. **Session Invalidation**:
   - Execute bulk session revocation across the database:
     ```sql
     UPDATE refresh_token_sessions SET revoked_at = NOW() WHERE revoked_at IS NULL;
     ```
   - Clear all active Redis presence and WebSocket ticket keys:
     ```bash
     redis-cli -u $REDIS_URL "KEYS" "lcc:ticket:*" | xargs redis-cli -u $REDIS_URL "DEL"
     ```
3. **Forensic Analysis**:
   - Inspect access logs for tokens with abnormal `iat` timestamps or unexpected IP sources.
4. **Validation**: Verify that old tokens return `401 Unauthorized` (`InvalidSignatureError`).

---

### Playbook B: AWS S3 Credential / Storage Compromise (Severity: P1)
1. **Immediate Containment**:
   - Deactivate the compromised IAM access key in AWS IAM Console immediately.
   - Verify `Block Public Access` remains `ENABLED` on `lcc-secure-documents`.
2. **Credential Rotation**:
   - Create a new IAM access key pair with least-privilege policy.
   - Update `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` in the production secret manager.
   - Redeploy the backend API and background worker containers.
3. **Evidence Integrity Audit**:
   - Dispatch the background reconciliation job:
     ```bash
     python -c "from app.services.evidence_service import EvidenceService; from app.db.session import SessionLocal; db=SessionLocal(); EvidenceService(db).reconcile_orphaned_evidence()"
     ```
   - Check `evidence_versions` for any unverified or tampered files (`status = TAMPER_DETECTED`).

---

### Playbook C: Evidence Tampering / Integrity Mismatch (Severity: P1)
1. **Detection**:
   - Raised by background integrity audits or on-download SHA-256 verification mismatch.
2. **Forensic Preservation (CRITICAL)**:
   - **DO NOT OVERWRITE OR DELETE THE COMPROMISED FILE**.
   - Query and export the complete chain of custody for the affected `evidence_id`:
     ```sql
     SELECT * FROM evidence_custody_events WHERE evidence_id = '<affected_uuid>' ORDER BY timestamp ASC;
     ```
   - Record the expected `sha256` vs. the actual computed byte hash.
3. **Quarantine**:
   - Update evidence metadata status to `TAMPER_DETECTED`.
   - Revoke all active `evidence_access_grants` for the affected file.
   - Apply a technical `is_legal_hold = TRUE` retention lock to ensure forensic artifacts cannot be altered or purged.
4. **Notification**: Notify the case owner, assigned lawyer, and platform security lead.

---

### Playbook D: Malware Ingestion Incident (Severity: P2)
1. **Detection**:
   - ClamAV scan returns `FOUND` or ClamAV daemon is unreachable during staged upload.
2. **Fail-Closed Execution**:
   - File status transitions to `QUARANTINED` in `evidence_versions`.
   - Physical file remains locked in isolated staging storage; it is NEVER moved to active evidence storage.
   - The file is never made available for download or view.
3. **Custody Logging**:
   - An immutable `SCAN_FAILED` custody event is recorded with malware signature metadata.
4. **Cleanup**:
   - Abandoned or quarantined upload objects are purged by the scheduled cleanup job after 48 hours.

---

### Playbook E: Account Takeover & Session Theft (Severity: P2)
1. **Immediate Containment**:
   - Revoke all active sessions for the targeted user:
     ```python
     auth_service.revoke_user_sessions(user_id)
     ```
   - Reset the account password, invalidating existing hashes.
2. **Evidence Access Audit**:
   - Inspect `evidence_custody_events` for any `DOWNLOADED` or `VIEWED` actions initiated by the compromised account during the compromise window.
3. **Communication**:
   - Notify the affected user via verified secondary email or phone.
