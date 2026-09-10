# Legal Case Companion (LCC) — Production Release Checklist (6.0)

This checklist defines the required release gates, pre-flight verification, deployment sequence, and post-release validation for Legal Case Companion releases.

---

## 1. Pre-Flight Verification Gates (Local / CI)

- [x] **Branch Isolation**: Active development performed on feature branch (e.g. `feat/production-launch-6.0`).
- [x] **Full Pytest Suite**: All automated tests pass:
  ```powershell
  .\.venv\Scripts\pytest.exe
  ```
  *Target: 333+ passed, 0 failed, 1 skipped.*
- [x] **Deployment Smoke Suite**:
  ```powershell
  .\.venv\Scripts\pytest.exe tests/e2e/test_production_smoke_suite.py -v
  ```
- [x] **Database Migration & Recovery Rehearsal**:
  ```powershell
  .\.venv\Scripts\pytest.exe tests/integration/test_migration_and_recovery_rehearsal.py -v
  ```
- [x] **Frontend Code Standards**:
  ```powershell
  cd frontend ; npm run lint
  ```
  *Target: 0 errors.*
- [x] **Production Bundle Build**:
  ```powershell
  cd frontend ; npm run build
  ```
  *Target: 12/12 routes static/dynamically rendered, 0 TypeScript errors.*
- [x] **Secrets Scan**:
  - Verify zero committed private keys, JWT secrets, AWS tokens, or Stripe keys in git diff.
  - Verify `app/core/config.py` raises explicit configuration errors if production secrets are missing.

---

## 2. Deployment Sequence (Staging / Production)

1. **Pre-Deploy Migration Run**:
   - Render automatically executes `alembic upgrade head` before booting new containers.
   - Verify `alembic heads` shows linear schema head.
2. **Container Launch**:
   - Web service (`lcc-backend`) starts with Gunicorn / Uvicorn workers.
   - Worker service (`lcc-worker`) starts with `python -m app.services.job_worker`.
3. **Health Probes Verification**:
   - `GET /api/v1/health/live` returns HTTP 200 `{"status": "alive"}`.
   - `GET /api/v1/health/ready` returns HTTP 200 `{"status": "ready", "database": "connected"}`.

---

## 3. Post-Deployment Smoke Verification

1. Authenticate with controlled pilot client credentials at `/login`.
2. Inspect Matter Workspace at `/cases/[caseId]`.
3. Confirm evidence documents load from secure S3 presigned URLs.
4. Execute test Copilot query and verify grounded response.
5. Verify Background Worker heartbeat via Admin Console `/admin/dashboard`.
6. Submit test Pilot Feedback and verify sanitized recording.

---

## 4. Release Abort / Rollback Criteria

Trigger immediate rollback to last known stable release if:
- Health check `/api/v1/health/ready` fails after container deployment.
- Error rate exceeds $1\%$ of requests in the first 15 minutes post-deploy.
- BOLA authorization failure detected in security logs.
