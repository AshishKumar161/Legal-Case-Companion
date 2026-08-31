# Production Deployment Plan

## 1. Overview
The Legal Case Companion backend is a modular monolith built on FastAPI, utilizing PostgreSQL for state, and AWS S3 for secure document storage. 

This document outlines the infrastructure and deployment architecture for a real-world, secure SaaS environment. We assume a **Render + AWS** hybrid architecture, combining the ease of PaaS for compute with the robustness of AWS for storage.

## 2. Infrastructure Architecture

### 2.1 Compute (Render Web Service)
- **Framework:** FastAPI running on Uvicorn with multiple workers (`uvicorn app.main:app --workers 4 --host 0.0.0.0 --port $PORT`).
- **Scaling:** Render auto-scaling enabled (scale on CPU/Memory thresholds).
- **Environment:** Dockerized environment or native Python environment using `uv`.
- **Health Checks:** Native `/health` and `/ready` endpoints configured in the deployment platform to ensure traffic is only routed to healthy instances.

### 2.2 Database (Render Managed PostgreSQL)
- **Engine:** PostgreSQL 15+.
- **Network Security:** Database is deployed within the Render Private Network, inaccessible from the public internet.
- **Connection Pooling:** SQLAlchemy `pool_size` and `max_overflow` tuned, or PgBouncer utilized if connection limits are reached.
- **Backups:** Automated daily backups with Point-in-Time Recovery (PITR) enabled.

### 2.3 Storage (AWS S3)
- **Bucket Configuration:** Private bucket. "Block Public Access" turned ON globally.
- **Access Control:** No bucket policies allowing public read.
- **Integration:** The backend uses IAM credentials (via Environment Variables) with a strict policy allowing only `s3:PutObject`, `s3:GetObject`, and `s3:DeleteObject` on `arn:aws:s3:::lcc-secure-documents/*`.
- **Malware Scanning:** Future integration will trigger an AWS Lambda function on `s3:ObjectCreated:Put` to scan for malware, updating the backend via a secure webhook.

## 3. Security Configuration

### 3.1 Secrets Management
- Secrets (`JWT_PRIVATE_KEY`, `JWT_PUBLIC_KEY`, `DATABASE_URL`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`) are stored in Render's Native Environment Variables.
- No secrets are ever committed to the repository (enforced via `.gitignore`).

### 3.2 Key Management
- Ed25519 asymmetric keys are used for JWT signing.
- Keys must be rotated every 180 days. A blue-green deployment with a grace period is required for zero-downtime rotation.

### 3.3 HTTPS & Domain
- **TLS:** Render provides automatic managed TLS/SSL via Let's Encrypt.
- **HSTS:** Strict-Transport-Security headers enabled.
- **Routing:** Custom domain configured (e.g., `api.legalcasecompanion.com`).

## 4. CI/CD Pipeline (GitHub Actions)

### 4.1 Continuous Integration (CI)
On every Pull Request to `main`:
1. Checkout code.
2. Install `uv`.
3. Run `ruff check`.
4. Run `mypy .`.
5. Spin up ephemeral PostgreSQL via Docker service.
6. Run `pytest` against PostgreSQL.
7. Block merge on any failures.

### 4.2 Continuous Deployment (CD)
On merge to `main`:
1. Trigger Render Deployment via Webhook.
2. Render build script builds the Docker image (`docker build`).
3. **Database Migration Safety (Pre-deploy):** `alembic upgrade head`. 
   - *Rule 1:* This runs *before* new code handles traffic.
   - *Rule 2:* Migrations must never contain destructive downgrades.
   - *Rule 3:* Migrations adding `NOT NULL` columns must supply default values or be multi-step to avoid locking.
   - *Rule 4:* `ALTER TYPE` (Enum changes) must be wrapped in `COMMIT` on PostgreSQL if outside a transaction block.
4. Start Command: Container boot `uvicorn app.main:app`.
5. Verify health via `/api/v1/health/ready` before traffic is routed.

## 5. Recovery & Monitoring
- **Logging:** Structured JSON logs sent to stdout, captured by Render, and exported to a centralized logging provider (e.g., Datadog or AWS CloudWatch).
- **Error Tracking:** Integration with Sentry for real-time exception tracking.
- **Disaster Recovery:** Documented Runbook for restoring the PostgreSQL DB from Render backups.
