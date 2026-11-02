# Legal Case Companion (LCC) — DevOps, Infrastructure & Reliability Audit

**Date**: November 2, 2026  
**Auditor**: Principal DevOps / SRE Engineer  
**Scope**: Docker containerization, CI/CD pipelines, Render cloud deployment, secret management, and operational reliability.

---

## 1. Containerization & Docker Audit

### 1.1 Backend Dockerfile (`Dockerfile`)
- **Multi-Stage Architecture**: **Implemented**.
  - `Stage 1 (builder)`: Based on `python:3.11-slim`, installs `build-essential`, `libpq-dev`, creates virtual environment in `/opt/venv`, and installs dependencies via `pip install .`.
  - `Stage 2 (runner)`: Based on `python:3.11-slim`, installs runtime `libpq5` and `curl`, copies `/opt/venv`, copies application code, sets ownership to non-root `appuser:appuser`, and runs as `USER appuser`.
- **Strengths**:
  - Compiles C-extensions in builder stage without carrying compilation toolchains into production.
  - Enforces non-root execution (`USER appuser`, UID/GID created via `groupadd -r` and `useradd -r`).
  - Contains container healthcheck: `curl -f http://localhost:8000/api/v1/health/live || exit 1`.
- **Opportunities for Hardening**:
  - In `Dockerfile` line 17, `RUN mkdir -p app && touch app/__init__.py` is used to cache dependency installation. Because our project now uses a standard package structure, copying `pyproject.toml` and installing dependencies with uv or wheels directly minimizes layer recreation.
  - Ensure `.dockerignore` excludes `.venv/`, `tests/`, `docs/`, `frontend/`, `storage/`, and node modules from the build context.

### 1.2 Docker Compose (`docker-compose.yml` & `docker-compose.prod.yml`)
- **Development Compose (`docker-compose.yml`)**:
  - Provides PostgreSQL 15 (`postgres:15-alpine`) and Redis 7 (`redis:7-alpine`) with health checks and persistent volumes.
- **Production Compose (`docker-compose.prod.yml`)**:
  - Full micro-service simulation: PostgreSQL, Redis, ClamAV antivirus daemon (`clamav/clamav:1.4.1`), Coturn TURN server (`coturn/coturn:4.6.2-alpine`), Backend API, Background Worker (`app.worker`), Scheduler (`app.scheduler`), and Next.js Frontend.
  - Security options enabled across services: `security_opt: [no-new-privileges:true]`.
  - Resource constraints declared (`cpus`, `memory` limits).
  - Health check dependencies correctly ordered (`backend` depends on `postgres: condition: service_healthy`, `redis: condition: service_healthy`).

---

## 2. CI/CD Workflow Audit (`.github/workflows/ci.yml`)

The repository maintains an automated GitHub Actions pipeline structured into four sequential jobs:

```
[backend-ci]  ───┐
                 ├──▶ [docker-build-ci] ──▶ [release-artifacts-ci]
[frontend-ci] ───┘
```

### 2.1 Backend CI Quality Gates
1. **Repository Checkout & Setup**: Uses `actions/checkout@v4`, `astral-sh/setup-uv@v5`, and `actions/setup-python@v5` (Python 3.12).
2. **Lock Consistency**: `uv lock --check` verifies lockfile reproducibility.
3. **Bytecode Compilation**: `python -m compileall app tests scripts migrations` validates syntax.
4. **Code Quality**: `ruff check .` and `mypy app` enforce formatting and static typing.
5. **Secret Scanner**: `python scripts/ci_secret_scanner.py` inspects git commits for credentials.
6. **Migration Lifecycle**: `alembic upgrade head` and `python scripts/test_migrations_lifecycle.py` verify upgrade/downgrade safety.
7. **OpenAPI Parity**: `python scripts/verify_openapi_contract.py` guarantees client contract synchronization.
8. **Test Execution**: Runs complete unit and integration suites with PostgreSQL and Redis service containers.

### 2.2 CI/CD Pipeline Gates Verification & Status
1. **OpenAPI Parity (`BUG-004`)**: **RESOLVED & VERIFIED**.
   - `docs/openapi.json` synchronized via `scripts/generate_openapi.py` to match the 337 live API paths and 396 operations (including canonical Legal AI Advisor, Payout Recovery, and KYC Verification endpoints).
   - Gate test `python scripts/verify_openapi_contract.py` passes with exit code 0.
   - Regression test `tests/integration/test_openapi_contract_parity.py` added to guard contract alignment.
2. **PostgreSQL Migration Lifecycle (`BUG-002`)**: **RESOLVED & VERIFIED**.
   - Migrations `5c8a1b2e3f4d`, `7f8a9b0c1d2e`, `afbdf4813237`, `b2c3d4e5f6a1`, `c3d4e5f6a1b2`, `e4f8db885ba5`, `f1a2b3c4d5e6`, `g1a2b3c4d5e6`, `i1a2b3c4d5e6`, `l1a2b3c4d5e6`, `n1a2b3c4d5e6`, `u1a2b3c4d5e6`, `w1a2b3c4d5e6`, `25500e9a54c3`, plus forward corrective migrations `y1a2b3c4d5e6` (payout idempotency key & index) and `z1a2b3c4d5e6` (pgvector extension & HNSW cosine index) hardened with conditional DDL, duplicate index checks, postgresql-specific enum variants, boolean false defaults, and UUID foreign key consistency.
   - Verified on live PostgreSQL database (`127.0.0.1:5433`) and SQLite via `python scripts/test_migrations_lifecycle.py`: full clean upgrade to head, selective downgrade, legacy data preservation, and re-upgrade to head pass with 0 errors.
3. **Pytest Project Configuration (`BUG-005`)**: **RESOLVED & VERIFIED**.
   - `pyproject.toml` updated with `pythonpath = ["."]` under `[tool.pytest.ini_options]`.
   - Deprecation filter added for `slowapi` and starlette third-party coroutine/status code warnings without suppressing project warnings.
   - Direct execution `.venv/bin/python -m pytest` functions out-of-the-box from repo root with 0 warnings.
4. **Secret Scanner Zero-Leakage Gate**: **RESOLVED & VERIFIED**.
   - Working tree audit via `python scripts/ci_secret_scanner.py` inspects git history and untracked files across 950+ repository files with 0 secret detections.

---

## 3. Render Cloud Deployment Audit (`render.yaml`)

The deployment architecture is declared as Infrastructure-as-Code in `render.yaml`:
- **Web Service**: `lcc-backend` (FastAPI Docker runner, Singapore region).
- **Worker 1**: `lcc-worker` (`python -m app.worker`).
- **Worker 2**: `lcc-scheduler` (`python -m app.scheduler`).
- **Web Service 2**: `lcc-frontend` (Next.js Docker runner).
- **Database**: `lcc-db` (Managed PostgreSQL 15, Singapore region).

### 3.1 Deployment Findings & Hardening Recommendations
- **Migration Concurrency**:
  - `render.yaml` declares `preDeployCommand: "alembic upgrade head"` on the `lcc-backend` web service.
  - This is an optimal SRE pattern: migrations execute in an isolated pre-deploy step *before* any backend or worker container instances are rotated, preventing race conditions and schema locks between concurrent application replicas.
  - **Risk Remediated**: Migration duplicate index and PostgreSQL type incompatibilities (`BUG-002`) have been fully resolved. Pre-deploy execution `alembic upgrade head` runs cleanly and idempotently on both empty and existing databases.
- **Distributed Concurrency & Worker Coordination (`BUG-008`)**:
  - Process-local mutexes (`threading.Lock()`) replaced with PostgreSQL database row-level locking (`SELECT ... FOR UPDATE`) and database partial unique constraint `ix_payouts_idempotency_key`.
  - Payout operations across distributed `lcc-backend` replicas and `lcc-worker` processes cannot produce duplicate disbursements.
  - Automatic interrupted payout recovery (`POST /api/v1/commercial/payouts/recover`) enables self-healing on worker crashes or restarts.
- **Antivirus Production Health Probes (`BUG-010`)**:
  - Production ClamAV operational health endpoint `/api/v1/health/scanner` provides real-time readiness and liveness telemetry.
  - ClamAV socket timeout fails closed to quarantine; heuristic scanner prohibited from marking files SAFE in production.
- **Graceful Shutdown**:
  - Both `app/worker.py` and `app/scheduler.py` attach handlers for `SIGINT` and `SIGTERM`, completing the current batch before cleanly terminating (`running = False`).
- **Heartbeat & Liveness Probes**:
  - Both background services generate atomic JSON heartbeat files (`/tmp/lcc_worker_heartbeat.json`, `/tmp/lcc_scheduler_heartbeat.json`) with timestamps and process IDs for orchestrator health checks.

---

## 4. Environment & Secret Management

- **`.env.example`**: Comprehensive template defining required database, Redis, JWT keys, S3 storage, email, Stripe, and AI credentials.
- **Fail-Safe Startup**: `app/core/config.py` enforces that in `production` and `staging` environments:
  - SQLite is rejected; PostgreSQL with SSL is required.
  - Wildcard CORS is rejected.
  - Asymmetric Ed25519 keys (`JWT_PRIVATE_KEY` and `JWT_PUBLIC_KEY`) must be configured.
  - Webhook secrets (`STRIPE_WEBHOOK_SECRET`, `AWS_WEBHOOK_SECRET`) must be non-empty.
  - `CLAMAV_HOST` is strictly required in production; missing host triggers `ScannerUnavailableError` and fails closed.
