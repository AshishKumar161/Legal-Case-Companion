# Production Release Checklist

**Date:** 2026-09-10  
**Phase:** Phase 12: Production Readiness & Hardening  

---

## Phase A: Pre-Deployment Verification

Before triggering production deployment, the Release Engineer must sign off on each item:

- [ ] **1. Code Quality & Static Gates**:
  - `python -m compileall -q app tests scripts migrations` -> 0 syntax errors
  - `ruff check app tests scripts migrations` -> 0 errors
  - `mypy app` -> 0 errors across all source files
  - `frontend: npx tsc --noEmit` -> 0 TypeScript errors
  - `frontend: npm run lint` -> 0 ESLint errors, 0 warnings
- [ ] **2. Automated Test Suite**:
  - `pytest` -> All 848 tests passing (100% green)
  - `pytest tests/security/` -> All 129 security & red-team tests passing
- [ ] **3. Linear Database Migrations**:
  - `alembic heads` -> Confirmed exactly 1 single linear head revision
  - Schema migrations verified to be backward-compatible (safe for canary rollback)
- [ ] **4. Backup & Snapshot Verification**:
  - Automated or manual pre-deployment database snapshot taken
  - `python scripts/verify_backup_restore.py` verified operational
- [ ] **5. Production Secrets & Configuration Pre-Flight**:
  - `python scripts/verify_production_config.py --env production` -> PASSED
  - Confirmed all secrets (`JWT_PRIVATE_KEY`, `STRIPE_API_KEY`, etc.) populated in production Secret Manager
  - Verified no `.env`, `.pem`, or credentials accidentally committed to git
- [ ] **6. Software Supply Chain & Release Artifacts**:
  - `python scripts/generate_sbom.py` -> `sbom-backend.json` and `sbom-frontend.json` generated
  - `python scripts/generate_release_manifest.py` -> `release-manifest.json` updated with commit SHA

---

## Phase B: Deployment Execution

Execute deployment following the deterministic deployment sequence:

- [ ] **1. Execute Database Migration**:
  - Run `alembic upgrade head`
  - Verify migration exit code is 0
- [ ] **2. Deploy Backend & Worker Services**:
  - Deploy new immutable container image for API, Worker, and Scheduler
  - Verify container status is `running`
- [ ] **3. Poll Health & Readiness Probes**:
  - Probe `GET /api/v1/health/live` -> Expect HTTP 200 `{"status": "alive"}`
  - Probe `GET /api/v1/health/ready` -> Expect HTTP 200 `{"status": "ready", "database": "connected"}`
- [ ] **4. Deploy Frontend Application**:
  - Deploy new frontend container image / build
  - Probe `GET /` -> Expect HTTP 200
- [ ] **5. Ingress Traffic Switch**:
  - Route user traffic to new deployment instances

---

## Phase C: Post-Deployment Smoke Verification

Immediately following deployment, run the automated zero-destructive smoke verification:

- [ ] **1. Run Production Smoke Suite**:
  ```bash
  python scripts/production_smoke_test.py --url https://api.legalcasecompanion.in
  ```
  Verify all 7 automated steps pass:
  - Step 1: Liveness check (`/api/v1/health/live`)
  - Step 2: Readiness check (`/api/v1/health/ready`)
  - Step 3: Health details and zero credential exposure (`/api/v1/health/details`)
  - Step 4: Synthetic client user registration and JWT authentication
  - Step 5: Authenticated legal case creation
  - Step 6: Staged evidence presigned upload URL generation
  - Step 7: Single-use WebSocket realtime ticket issuance
- [ ] **2. Monitor Application Logs & Metrics (First 30 Minutes)**:
  - Check error rate: HTTP 5xx responses must be < 0.1%
  - Check worker queues: `background_jobs_dead_letter == 0`
  - Check database connection pool utilization

---

## Phase D: Rollback Criteria

If any of the following occur, abort deployment and initiate immediate rollback per [docs/release/ROLLBACK_PROCEDURE.md](file:///c:/Users/akuma/OneDrive/Desktop/lcc/Legal-Case-Companion-main/docs/release/ROLLBACK_PROCEDURE.md):
- Database migration fails or throws unrecoverable SQL exceptions.
- Readiness probe fails (`/api/v1/health/ready` returns 503 for > 60 seconds).
- Post-deployment smoke test suite fails any step.
- Error rate exceeds 1% of total requests during the initial 15-minute observation window.
