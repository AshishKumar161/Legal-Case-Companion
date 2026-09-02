# Legal Case Companion (LCC) - Production Operations Runbook

## 1. System Architecture & Process Topology

Legal Case Companion is structured as a hardened **modular monolith** backend in Python / FastAPI with PostgreSQL, private AWS S3 storage, real-time WebRTC video signaling, ClamAV antivirus scanning, and coturn NAT traversal.

```text
                                  +---------------------------------------+
                                  |         Internet Clients / Web        |
                                  +---------------------------------------+
                                                      |
                                                      v HTTPS (Port 443)
                                  +---------------------------------------+
                                  |     Next.js Frontend Container        |
                                  |     (Multi-stage node:20-alpine)      |
                                  +---------------------------------------+
                                                      |
                                                      v Internal / Rewrites
                                  +---------------------------------------+
                                  |     FastAPI Web API (uvicorn)         |
                                  |  - CorrelationId & Metrics Middleware |
                                  |  - RBAC & BOLA Enforced API Endpoints |
                                  |  - WebRTC WebSocket Signaling (/ws)   |
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
                                           |
                    TCP Stream (Port 3310) |               UDP/TCP (3478 / 5349)
                                           v                               v
                            +----------------------+      +----------------------+
                            | ClamAV / ClamD       |      | CoTURN STUN / TURN   |
                            | (Fail-Closed Daemon) |      | (WebRTC NAT Relay)   |
                            +----------------------+      +----------------------+
```

---

## 2. Environment Variables & Secret Configuration

Production environments must set all required environment variables securely without fallback to dev keys:

| Variable | Description | Production Requirement |
|---|---|---|
| `ENVIRONMENT` | Deployment environment | Must be `production` |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+psycopg://user:pass@host:5432/dbname` |
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
| `CLAMAV_HOST` | ClamAV TCP daemon hostname | e.g. `clamav` or internal IP |
| `CLAMAV_PORT` | ClamAV TCP daemon port | `3310` |
| `TURN_SERVER_URL` | Coturn STUN/TURN server URL | `turn:turn.legalcasecompanion.in:3478` |
| `TURN_USERNAME` | Turn username | Configured TURN user |
| `TURN_CREDENTIAL` | Turn password / static auth secret | Secure random string |
| `STRIPE_API_KEY` | Stripe secret key | Secret string |
| `STRIPE_WEBHOOK_SECRET`| Stripe webhook verification | Secret string |
| `EMAIL_PROVIDER` | Email provider engine | `sendgrid`, `ses`, or `smtp` (not `console`) |
| `FRONTEND_URL` | Client application domain | `https://app.legalcasecompanion.in` |
| `BACKEND_CORS_ORIGINS`| Authorized CORS origins | JSON list of trusted domains (never `*`) |

---

## 3. Operational Configuration Diagnostics

Before deploying or promoting application versions, execute the non-destructive diagnostics CLI:

```bash
python scripts/verify_production_config.py --env production
```
This utility validates that:
1. All Ed25519 cryptographic keys and CSRF tokens are present and PEM-formatted.
2. The database is reachable and tests connection latency.
3. ClamAV TCP daemon is accepting connections on port 3310.
4. TURN credentials and server URLs are configured.
5. Stripe API keys and webhook signing secrets are formatted correctly.
6. Zero secrets or passwords are printed to console logs.

---

## 4. Database Schema Migrations (Alembic)

Schema management is strictly controlled via Alembic. **`Base.metadata.create_all()` is disabled in production**.

### Current Revision Head
The active production revision head is:
```text
f1a2b3c4d5e6 (head)
```

### Pre-Deployment Migration Command
In automated deployment workflows (e.g. Render `preDeployCommand`):
```bash
alembic upgrade head
```

### Rollback Limitations & Procedure
To downgrade 1 revision in staging/emergency:
```bash
alembic downgrade -1
```
*Note: Dropping columns or migrating enum types in PostgreSQL with active connections requires lock timeouts (`DB_STATEMENT_TIMEOUT_MS`). Destructive rollbacks with data loss are restricted.*

---

## 5. Background Worker & Scheduler Operations

### Running Standalone Worker
```bash
python -m app.worker 2.0 10
```
- Polls `background_jobs` table every 2.0s claiming up to 10 jobs atomically using `SELECT ... FOR UPDATE SKIP LOCKED`.
- Responds gracefully to `SIGINT` / `SIGTERM` signals.

### Running Standalone Scheduler
In a dedicated scheduler container (strictly 1 instance):
```bash
python -m app.scheduler 60.0
```
- Idempotently enqueues periodic deadline scans, task overdue scans, and stale job recoveries.

---

## 6. Antivirus & Document Malware Scanning (ClamAV)

1. **Daemon Connectivity**: ClamD TCP daemon on port 3310 (`clamav:3310`).
2. **Fail-Closed Assurance**:
   - If the ClamAV daemon is unreachable, the scanner raises `ScannerUnavailableError`.
   - The document remains in `DocumentSecurityStatus.QUARANTINED` with processing error `"Malware scanner service is temporarily unavailable. Document remains quarantined."`.
   - Documents are **never** permitted to transition to `SAFE` without byte-level verification.
3. **Recovery**: When ClamD recovers, the scheduler loop re-enqueues quarantined documents for verification.

---

## 7. WebRTC & Video Room Signaling (Coturn)

1. **WebSocket Signaling Endpoint**:
   `GET /api/v1/consultations/{id}/video/ws?token=...`
2. **Authentication**:
   HMAC-SHA256 signed access token (2-hour TTL).
3. **STUN/TURN Relay (Coturn)**:
   - Config file: `coturn/turnserver.conf`.
   - Ports: 3478 (UDP/TCP), 5349 (TLS).
   - Dynamic ICE servers populated in `VideoMeetingService.create_meeting_room`.

---

## 8. Observability & Health Probes

### Health Probes
- `GET /health/live`, `GET /liveness`: Liveness probe (returns 200 OK if process is alive).
- `GET /health/ready`, `GET /readiness`: Readiness probe (executes `SELECT 1` on DB connection pool).

### Operational Metrics
Admin-authenticated endpoint:
```http
GET /api/v1/admin/metrics
Authorization: Bearer <ADMIN_JWT>
```
- URL paths are automatically sanitized with `{id}` masking to prevent UUID leakage and bounded cardinality.

---

## 9. Production Readiness Checklist

- [x] **Configuration**: All secrets externalized, classified, and verified via `scripts/verify_production_config.py`.
- [x] **Database Migrations**: Single linear Alembic chain with head `f1a2b3c4d5e6`.
- [x] **Security Headers**: HSTS, nosniff, DENY framing, strict CSP, Referrer-Policy, Permissions-Policy.
- [x] **Authentication**: Ed25519 JWT access tokens + rotating opaque refresh tokens + Argon2id.
- [x] **Authorization**: Strict BOLA/IDOR protection and `CaseParticipant` guards.
- [x] **Private Storage**: Private S3 buckets with AES256 server-side encryption and presigned URLs.
- [x] **Malware Scanning**: Pluggable `HeuristicSignatureScanner` + `ClamAVScanner` with strict fail-closed behavior.
- [x] **Video Signaling**: Real-time authenticated WebSocket signaling + configured Coturn TURN relay.
- [x] **Payments & Webhooks**: Stripe integration with HMAC-SHA256 verification and replay idempotency.
- [x] **Rate Limiting**: Applied to booking, payment intent, and video join token endpoints.
- [x] **Background Execution**: Persistent `background_jobs` queue with graceful worker and scheduler shutdown.
- [x] **Observability**: Sanitized low-cardinality metrics + separate `/liveness` and `/readiness` probes.
- [x] **CI/CD Pipeline**: GitHub Actions CI workflow covering tests, migrations, frontend build, and Docker images.
- [x] **Incident Response**: Emergency playbooks in `docs/INCIDENT_RESPONSE.md`.
