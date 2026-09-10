# Legal Case Companion (LCC) — Pilot Incident Response & Disaster Recovery (6.0)

This playbook establishes the protocol for responding to, containing, communicating, and recovering from technical and operational incidents during production and pilot rollouts.

---

## 1. Incident Severity Definitions

| Level | Definition | Response SLA | Examples |
| :--- | :--- | :--- | :--- |
| **P0** | Critical Outage / Data Loss / Security Breach | Immediate ($< 15\text{ min}$) | Database unreachable, cross-matter BOLA leak, credential exposure, complete API downtime. |
| **P1** | Core Workflow Degraded | $< 1\text{ hour}$ | Document upload/processing failing, Copilot failing globally, consultation checkout failing. |
| **P2** | Non-Critical Feature Impacted | $< 4\text{ hours}$ | Email notifications delayed, timeline generation delay, lawyer search filter error. |
| **P3** | Minor Friction / Visual Issue | $< 24\text{ hours}$ | UI styling defect, non-blocking label typo, minor mobile padding alignment. |

---

## 2. 7-Step Incident Response Protocol

```
[1. DETECT]   Alert trigger / Admin probe / User feedback
     │
[2. ASSESS]   Triage severity (P0-P3), identify affected tenant scope
     │
[3. CONTAIN]  Isolate failure (suspend affected service/route, revoke sessions if auth-related)
     │
[4. COMMUNICATE] Post status update to pilot participants (no sensitive legal details)
     │
[5. FIX]      Deploy hotfix or execute rollback to last known good release
     │
[6. VERIFY]   Run production smoke suite (`test_production_smoke_suite.py`)
     │
[7. DOCUMENT] Publish Post-Mortem within 24h documenting root cause & preventive controls
```

---

## 3. Disaster Recovery & Rollback Procedures

### Application Release Rollback
If a newly deployed image exhibits unforeseen errors:
1. In Render Dashboard: Select previous successful build from Deployments history $\to$ Click **Rollback to this deploy**.
2. Alternatively via Git:
   ```bash
   git revert <failing_commit_hash>
   git push origin main
   ```

### Database Point-in-Time Recovery (PITR)
1. Render Managed PostgreSQL performs continuous WAL archiving and automated daily snapshots.
2. In the event of catastrophic data corruption:
   - Provision recovery clone at timestamp $T - 5\text{ minutes}$.
   - Validate table constraints using `test_production_database_schema_and_constraints_integrity`.
   - Update `DATABASE_URL` in web and worker services.

### Storage / Document Recovery
- AWS S3 bucket `lcc-secure-documents` utilizes versioning and SSE-S3 encryption.
- Accidental deletions or corrupted document chunks can be restored via S3 Object Versioning.
