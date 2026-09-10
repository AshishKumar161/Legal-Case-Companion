# Production Rollback Procedure & Runbook

**Date:** 2026-09-10  
**Phase:** Phase 12: Production Readiness & Hardening  

---

## 1. Rollback Philosophy & Principles

1. **Target Recovery Time**: Rollback operations must restore stable service within **15 minutes (RTO <= 15m)**.
2. **Immutable Artifact Tags**: Releases are deployed as immutable container tags (e.g. `lcc-backend:prod-2026.09.04`). Rollback consists of pointing orchestrator services to the previously verified image tag.
3. **Expand-Contract Database Strategy**:
   - Database migrations must be forward- and backward-compatible.
   - New database columns must be nullable or possess defaults so that previous application container versions continue to function without error.
   - Column or table drops must occur only in a subsequent release after all application code ceases reading from them.

---

## 2. Decision Matrix: Rollback vs. Fix-Forward

| Scenario | Severity | Action | Recovery Target |
| :--- | :--- | :--- | :--- |
| **Readiness probe fails on boot** | CRITICAL | **Immediate Container Rollback** | < 5 Minutes |
| **Smoke test fails (e.g. login broken)** | CRITICAL | **Immediate Container Rollback** | < 5 Minutes |
| **Elevated 5xx error rate (> 1%)** | HIGH | **Container Rollback** | < 10 Minutes |
| **Database migration execution failure** | CRITICAL | **Migration Abort & Database Restore** | < 15 Minutes |
| **Minor cosmetic UI bug on non-critical page** | LOW | **Fix-Forward in Next Release** | Next Sprint / Patch |

---

## 3. Step-by-Step Rollback Procedures

### Procedure 1: Application Container Rollback (Render / PaaS)
1. Navigate to the Render Dashboard for `lcc-backend`, `lcc-worker`, `lcc-scheduler`, and `lcc-frontend`.
2. Open the **Deploys** tab.
3. Locate the previous successful release deploy (e.g. `Deploy #42 - Commit 098e227`).
4. Click **Rollback to this deploy**.
5. Render immediately stops the failing instances and switches traffic back to the prior container image.
6. Verify recovery:
   ```bash
   python scripts/production_smoke_test.py --url https://api.legalcasecompanion.in
   ```

### Procedure 2: Docker Compose Rollback (Self-Hosted)
1. Identify the previous stable release tag from `release-manifest.json` or image registry:
   ```bash
   PREV_TAG="prod-2026.08.28"
   ```
2. Update the image reference in `.env.production` or re-tag:
   ```bash
   docker tag "lcc-backend:${PREV_TAG}" "lcc-backend:latest"
   docker tag "lcc-frontend:${PREV_TAG}" "lcc-frontend:latest"
   ```
3. Restart containers with the previous image:
   ```bash
   docker compose -f docker-compose.prod.yml up -d backend worker scheduler frontend
   ```
4. Verify readiness:
   ```bash
   curl -f http://localhost:8000/api/v1/health/ready
   curl -f http://localhost:3000/
   ```

### Procedure 3: Database Migration Downgrade (When Safe)
> [!CAUTION]
> Only downgrade migrations if the migration script specifically implements a verified `downgrade()` function that does not discard existing customer data.

1. Check current migration state:
   ```bash
   alembic current
   ```
2. Revert to the specific previous revision:
   ```bash
   alembic downgrade -1
   ```
3. If the schema change was destructive or corrupted data, perform a point-in-time restore from the pre-deployment backup per [docs/release/DISASTER_RECOVERY.md](file:///c:/Users/akuma/OneDrive/Desktop/lcc/Legal-Case-Companion-main/docs/release/DISASTER_RECOVERY.md).

---

## 4. Post-Rollback Incident Procedures

1. **Notify Stakeholders**: Alert Platform Engineering and Operations leads in the incident Slack/Teams channel.
2. **Preserve Logs**: Export container logs from the failed deployment window before containers are recycled:
   ```bash
   docker logs lcc_backend_prod > /var/log/lcc_failed_deploy_$(date +%s).log
   ```
3. **Conduct Post-Mortem**: Document root cause, failure trigger, and preventive test coverage in a Phase Post-Mortem within 24 hours.
