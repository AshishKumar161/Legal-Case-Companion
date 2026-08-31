# Legal Case Companion (LCC) - Production Operations Runbook

## 1. System Architecture & Process Topology

Legal Case Companion is structured as a hardened **modular monolith** backend in Python / FastAPI with PostgreSQL and private AWS S3 storage.

```text
                                  +---------------------------------------+
                                  |         Internet Clients / Web        |
                                  +---------------------------------------+
                                                      |
                                                      v HTTPS (Port 443)
                                  +---------------------------------------+
                                  |     FastAPI Web API (uvicorn)         |
                                  |  - CorrelationId & Metrics Middleware |
                                  |  - RBAC & BOLA Enforced API Endpoints |
                                  +---------------------------------------+
                                           |                     |
                        Job Enqueue / Reads|                     | S3 Presigned URLs
                                           v                     v
+-------------------------------+  +-------------------+  +-------------------------+
|  Job Worker Loop Process      |  | PostgreSQL DB     |  | AWS S3 Private Bucket   |
|  (python -m app.worker)       |->| - background_jobs |  | (lcc-secure-documents)  |
|  - Concurrent claim locking   |  | - cases / docs    |  +-------------------------+
|  - Safe error categorization  |  | - auth / audit    |
+-------------------------------+  +-------------------+
                                           ^
                                           | Scheduled Scans (Hourly / 5-min)
+-------------------------------+          |
|  Job Scheduler Process        |----------+
|  (python -m app.scheduler)    |
|  - Deadline & task scans      |
|  - Stale job recovery         |
+-------------------------------+
```

---

## 2. Environment Variables & Secret Configuration

Production environments must set all required environment variables securely without fallback to dev keys:

| Variable | Description | Production Requirement |
|---|---|---|
| `ENVIRONMENT` | Deployment environment | Must be `production` |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://user:pass@host:5432/dbname` |
| `DB_POOL_SIZE` | SQLAlchemy connection pool size | Recommended `20` |
| `DB_MAX_OVERFLOW` | Maximum pool overflow | Recommended `10` |
| `DB_STATEMENT_TIMEOUT_MS` | PostgreSQL query execution timeout | Default `30000` (30s) |
| `JWT_PRIVATE_KEY` | Ed25519 PEM Private Key | PKCS#8 format (never committed) |
| `JWT_PUBLIC_KEY` | Ed25519 PEM Public Key | SubjectPublicKeyInfo format |
| `CSRF_SECRET_KEY` | CSRF signing key | 32+ random characters |
| `AWS_S3_BUCKET_NAME` | Private S3 bucket name | `lcc-secure-documents` |
| `AWS_REGION` | AWS region | `ap-south-1` |
| `AWS_ACCESS_KEY_ID` | IAM user with S3 read/write | Restricted IAM policy |
| `AWS_SECRET_ACCESS_KEY`| IAM secret | Restricted IAM policy |
| `AWS_WEBHOOK_SECRET` | HMAC secret for malware scanning | Secret string |
| `STRIPE_API_KEY` | Stripe secret key | Secret string |
| `STRIPE_WEBHOOK_SECRET`| Stripe webhook verification | Secret string |
| `EMAIL_PROVIDER` | Email provider engine | `sendgrid` or `ses` (not `console`) |
| `SENDGRID_API_KEY` | SendGrid API key | Secret string |
| `OPENAI_API_KEY` | OpenAI API key for embeddings/LLM | Secret string |
| `LOG_LEVEL` | Application logging level | `INFO` |

---

## 3. Database Migration & Deployment Runbook

### Pre-Deployment Migrations
In production (Render, Docker, or Kubernetes), migrations are executed before starting web traffic:
```bash
alembic upgrade head
```

### Migration Integrity Verification
Confirm that the migration graph has exactly one head:
```bash
alembic heads
# Expected Output: 9c0d1e2f3a4b (head)
```

### Rollback Strategy
If a deployment fails, roll back to the previous revision:
```bash
alembic downgrade -1
```

---

## 4. PostgreSQL Backup & Disaster Recovery (DR)

### Daily Automated Backups
Run `pg_dump` with custom compressed format:
```bash
pg_dump -Fc -v --no-owner --no-privileges -d "$DATABASE_URL" -f "lcc_backup_$(date +%Y%m%d_%H%M%S).dump"
```

### Point-in-Time Recovery (PITR) / Restore Procedure
1. Provision target database instance.
2. Restore database schema and data:
```bash
pg_restore -v --clean --if-exists --no-owner -d "$NEW_DATABASE_URL" lcc_backup_20260830.dump
```
3. Run migration verification:
```bash
alembic current
```
4. Verify readiness probe:
```bash
curl -I https://api.legalcasecompanion.in/health/ready
```

---

## 5. Background Jobs, Worker & Scheduler Operations

### Running Standalone Worker
In a dedicated container or background worker service:
```bash
python -m app.worker 2.0 10
```
- Polls `background_jobs` table every 2.0s claiming up to 10 jobs atomically using `SELECT ... FOR UPDATE SKIP LOCKED`.
- Responds gracefully to `SIGINT` / `SIGTERM` signals.

### Running Standalone Scheduler
In a dedicated scheduler container:
```bash
python -m app.scheduler 60.0
```
- Idempotently enqueues periodic deadline scans, task overdue scans, and stale job recoveries.

### Stale Job Recovery
If an unmanaged worker crash occurs, the scheduler's `STALE_JOB_RECOVERY` job reclaims jobs locked for longer than lease expiry and resets them to `RETRYING` or `FAILED`.

---

## 6. Observability, Metrics & Security

### Health & Readiness Probes
- `GET /health/live` or `GET /health`: Liveness probe (returns 200 OK if process is running).
- `GET /health/ready` or `GET /ready`: Readiness probe (executes `SELECT 1` on DB connection pool).

### Operational Metrics
Admin-authenticated endpoint:
```http
GET /api/v1/admin/metrics
Authorization: Bearer <ADMIN_JWT>
```
Returns:
- Server uptime in seconds.
- Total HTTP request count and status code breakdown (2xx, 4xx, 5xx).
- Request latency percentiles (Average, P95).
- AI retrieval and LLM operation counts.

### Security Incident Response (Token Revocation)
If user credentials or refresh tokens are compromised:
1. Invoke Admin User Suspension:
```http
POST /api/v1/admin/users/{user_id}/suspend
```
2. This immediately revokes all active session refresh tokens and blocks access token renewal.

---

## 7. Production Readiness Checklist

- [x] **Configuration**: All secrets externalized and validated in `Settings`.
- [x] **Database Migrations**: Single linear chain with 1 head (`9c0d1e2f3a4b`).
- [x] **Security Headers**: HSTS, nosniff, DENY framing, strict CSP, Referrer-Policy, Permissions-Policy.
- [x] **Authentication**: Ed25519 JWT access tokens + rotating opaque refresh tokens + Argon2id.
- [x] **Authorization**: Resource-level BOLA/IDOR protection on all case resources.
- [x] **Private Storage**: Private S3 buckets with time-limited presigned URLs.
- [x] **Background Execution**: Persistent `background_jobs` queue with concurrency-safe locking and bounded retries.
- [x] **Observability**: Correlation IDs on all logs/errors + `GET /api/v1/admin/metrics`.
- [x] **Health Probes**: Liveness and readiness endpoints mounted at root and API v1.
- [x] **Regression Baseline**: 264+ automated tests passing with 0 warnings and 0 failures.
