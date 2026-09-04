# Legal Case Companion — Production Rollback Runbook

**Document Reference**: LCC-DOC-027  
**Classification**: Emergency Operational Procedure  
**Effective Version**: 1.0.0 (`prod-2026.09.04`)

---

## 1. Rollback Decision Framework & Triggers

A production rollback is an emergency operational procedure executed when a new release violates core service-level objectives or exhibits critical defects that cannot be hotfixed safely within 15 minutes.

### Automatic Rollback Triggers

| Trigger Condition | Threshold | Monitoring Signal |
| :--- | :--- | :--- |
| **API Error Rate Spike** | $> 0.5\%$ HTTP 5xx responses for $> 3$ consecutive minutes | Prometheus / CloudWatch HTTP metrics |
| **Authentication Outage** | $> 1\%$ token validation or login failures | `/auth/login` endpoint error counter |
| **Latency Degradation** | API p95 latency $> 2500\text{ ms}$ sustained for $> 5$ minutes | `/health/ready` probe response time |
| **Data Integrity Fault** | Corrupted hash verification or spurious `TAMPER_DETECTED` events | Evidence service custody error logs |
| **Worker Crash Loop** | Workers exiting with non-zero status repeatedly | Docker container restart counter |
| **Database Pool Exhaustion** | 100% database pool utilization with queue timeouts | PostgreSQL active connection gauge |

---

## 2. Safe Rollback Principles & Schema Compatibility

### The Golden Rule of Database Backward Compatibility
> **All database schema migrations must be backward-compatible with the immediately preceding application version.**

1. **Additive Changes First**: New columns must be nullable or have safe defaults. Dropping columns or renaming columns must occur in a phased, multi-release cycle (Expand $\to$ Migrate $\to$ Contract).
2. **Container-Only Rollbacks**: Because schemas are backward compatible, **99% of rollbacks should rollback application containers ONLY**, leaving the database at the upgraded schema. This avoids data loss of any records created during the new deployment window.

---

## 3. Step-by-Step Rollback Execution

### Step 1: Declare Incident & Notify Stakeholders
1. Announce deployment rollback in the incident bridge.
2. Freeze all non-essential administrative actions.

### Step 2: Rollback Application Containers
```bash
# 1. Inspect current running services
docker-compose -f docker-compose.prod.yml ps

# 2. Point container tags to the previous stable release (e.g., v0.9.9)
export RELEASE_TAG=v0.9.9
export RELEASE_ID=prod-2026.08.28

# 3. Gracefully recreate backend and frontend containers
docker-compose -f docker-compose.prod.yml up -d --no-deps backend worker scheduler frontend

# 4. Verify containers are healthy
docker-compose -f docker-compose.prod.yml ps
```

### Step 3: Database Downgrade (ONLY if explicitly mandated by schema corruption)
> [!CAUTION]
> Downgrading the database schema should ONLY be performed if the migration itself caused data corruption or database lockup. Any records created during the new deployment window that depend on new columns will be modified or lost.

```bash
# 1. Identify previous migration revision
alembic current
alembic history -i

# 2. Revert to target previous revision (e.g., j1a2b3c4d5e6)
alembic downgrade <target_revision_hash>

# 3. Confirm target linear head
alembic current
```

### Step 4: Emergency Full Database Restore (Disaster Recovery Scenario)
If the database suffered catastrophic corruption:
```bash
# 1. Stop write traffic by putting API in maintenance mode
docker-compose -f docker-compose.prod.yml stop backend worker scheduler

# 2. Restore pre-deployment snapshot
dropdb -h localhost -U lcc_admin legal_db
createdb -h localhost -U lcc_admin legal_db
pg_restore -h localhost -U lcc_admin -d legal_db -v backup_predeploy.dump

# 3. Restart application stack
docker-compose -f docker-compose.prod.yml up -d
```

---

## 4. Post-Rollback Validation Checklist

After executing rollback steps:
- [ ] `/api/v1/health/live` returns 200 OK.
- [ ] `/api/v1/health/ready` returns 200 OK with `database: connected` and latency $< 100\text{ ms}$.
- [ ] `/api/v1/health/details` reports previous stable `APP_VERSION` and `RELEASE_ID`.
- [ ] Run synthetic smoke test: `python scripts/production_smoke_test.py`.
- [ ] Verify test login and case access succeed without errors.
- [ ] Confirm error rates and latency return to baseline within 5 minutes.

---

## 5. Post-Mortem & Root-Cause Analysis (RCA)

Within 24 hours of any rollback:
1. Preserve container logs, database logs, and diagnostic telemetry from the failed release window.
2. Conduct blameless Root-Cause Analysis (RCA) meeting with engineering, product, and operations leads.
3. Formulate preventive test cases to cover the specific failure mode in `tests/e2e/` or `tests/security/`.
4. Document findings and publish post-mortem report to `docs/rca/`.
