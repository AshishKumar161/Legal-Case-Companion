# Production Deployment Guide

**Date:** 2026-09-10  
**Phase:** Phase 12: Production Readiness & Hardening  

---

## 1. Deterministic Deployment Sequence

Production deployments must execute in a strictly controlled, linear sequence to ensure zero downtime and prevent schema inconsistency:

```
┌────────────────────────────────────────────────────────┐
│ 1. Build & Push Verified Container Images (Immutable)  │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│ 2. Execute Linear Database Migrations (alembic upgrade)│
└──────────────────────────┬─────────────────────────────┘
                           │ (Must complete successfully before booting new pods)
                           ▼
┌────────────────────────────────────────────────────────┐
│ 3. Start Backend & Worker Pods (Pre-Traffic)           │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│ 4. Poll Readiness Probes (/api/v1/health/ready)        │
└──────────────────────────┬─────────────────────────────┘
                           │ (Instances verify DB connectivity before receiving traffic)
                           ▼
┌────────────────────────────────────────────────────────┐
│ 5. Switch Ingress / Reverse Proxy Traffic (Zero Downtime)
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│ 6. Run Post-Deployment Smoke Suite (7-Step Validation) │
└────────────────────────────────────────────────────────┘
```

> [!IMPORTANT]
> **Zero Startup Auto-Migrations in Production:**  
> Application pods must **never** execute `Base.metadata.create_all()` or run Alembic migrations on runtime startup. In `app/main.py`, automatic table creation is strictly conditioned on `ENVIRONMENT in ("development", "test") and DATABASE_URL.startswith("sqlite")`. Production migrations run solely as an audited pre-deploy job (`preDeployCommand: "alembic upgrade head"` on Render, or dedicated migration runner in Docker/Kubernetes).

---

## 2. Worker & Scheduler Deployment Topology

### Background Job Worker (`python -m app.worker`)
- **Process Model:** Dedicated worker process with independent lifecycle from the API server.
- **Job Claiming:** Uses database row-level locking (`SELECT ... FOR UPDATE SKIP LOCKED`) to claim pending jobs. Multiple worker instances can run concurrently without race conditions or duplicate execution.
- **Job Leases:** Each claimed job receives a 5-minute lease (`locked_until`). If a worker container crashes, the lease expires and the job is automatically picked up by an active worker.
- **Graceful Shutdown:** Handles `SIGTERM` and `SIGINT` by finishing the active job before exiting.

### Background Job Scheduler (`python -m app.scheduler`)
- **Process Model:** Runs as a **singleton service** (replicas = 1) to periodically scan and schedule recurring maintenance tasks (stale meeting cleanup, expired session pruning, outbox dispatch).
- **Idempotent Dispatch:** Scheduled jobs are enqueued as deduplicated records in the `background_jobs` table. Even in the event of an accidental dual-scheduler startup, idempotent job deduplication prevents duplicate processing.

---

## 3. Step-by-Step Deployment Instructions

### Option A: Cloud PaaS (Render)
1. Verify configuration:
   ```bash
   python scripts/verify_production_config.py --env production
   ```
2. Link repository to Render and deploy using blueprint `render.yaml`.
3. Render automatically provisions:
   - `lcc-backend` (web service with pre-deploy `alembic upgrade head`)
   - `lcc-worker` (background worker service)
   - `lcc-scheduler` (background scheduler service)
   - `lcc-frontend` (Next.js web service)
   - `lcc-db` (managed PostgreSQL instance)
4. Inject production secrets in the Render Dashboard (`JWT_PRIVATE_KEY`, `STRIPE_API_KEY`, etc.).

### Option B: Self-Hosted Docker Compose (`docker-compose.prod.yml`)
1. Create a secure `.env.production` file on the deployment host:
   ```bash
   ENVIRONMENT=production
   POSTGRES_USER=lcc_admin
   POSTGRES_PASSWORD=<GENERATE_SECURE_PASSWORD>
   POSTGRES_DB=legal_db
   JWT_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n..."
   JWT_PUBLIC_KEY="-----BEGIN PUBLIC KEY-----\n..."
   CSRF_SECRET_KEY=<SECURE_64_CHAR_HEX>
   STRIPE_API_KEY=sk_live_...
   STRIPE_WEBHOOK_SECRET=whsec_...
   OPENAI_API_KEY=sk-proj-...
   AWS_ACCESS_KEY_ID=AKIA...
   AWS_SECRET_ACCESS_KEY=...
   AWS_S3_BUCKET_NAME=lcc-prod-documents
   FRONTEND_URL=https://app.legalcasecompanion.in
   BACKEND_CORS_ORIGINS=["https://app.legalcasecompanion.in"]
   ```
2. Pre-run database migrations:
   ```bash
   docker compose -f docker-compose.prod.yml --env-file .env.production run --rm backend alembic upgrade head
   ```
3. Start all services in detached mode:
   ```bash
   docker compose -f docker-compose.prod.yml --env-file .env.production up -d
   ```
4. Verify readiness:
   ```bash
   curl -f http://localhost:8000/api/v1/health/ready
   curl -f http://localhost:3000/
   ```
5. Run smoke validation:
   ```bash
   python scripts/production_smoke_test.py --url http://localhost:8000
   ```
