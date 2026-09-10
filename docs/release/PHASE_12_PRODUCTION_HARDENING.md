# Phase 12: Production Hardening, Secrets & Observability Specification

**Date:** 2026-09-10  
**Phase:** Phase 12: Production Readiness & Hardening  

---

## 1. Production Environment Variable Classification

All environment variables used by Legal Case Companion (LCC) are formally categorized below. Production startup enforces strict fail-fast validation to prevent running with insecure development placeholders.

| Variable Name | Classification | Required in Prod? | Default Value | Used By | Failure Behavior |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `ENVIRONMENT` | PUBLIC | **YES** | `development` | Core Config, Lifespan | Defaults to dev; enables prod security when `production`. |
| `DATABASE_URL` | SECRET | **YES** | *None* | SQLAlchemy Engine, Alembic | Startup crashes immediately if missing or invalid. |
| `JWT_PRIVATE_KEY` | SECRET | **YES** | *None* | Ed25519 Token Signing | Startup crashes immediately if missing/placeholder. |
| `JWT_PUBLIC_KEY` | SECRET | **YES** | *None* | Ed25519 Token Verification | Startup crashes immediately if missing/placeholder. |
| `CSRF_SECRET_KEY` | SECRET | **YES** | *None* | CSRF Double-Submit Protection| Startup crashes immediately if missing/placeholder. |
| `POSTGRES_PASSWORD` | SECRET | **YES** | *None* | Docker Compose, Postgres | Compose fails fast with `${POSTGRES_PASSWORD:?}`. |
| `STRIPE_API_KEY` | SECRET | **YES** | *None* | Payment Provider | Startup diagnostics fail; checkout attempts blocked. |
| `STRIPE_WEBHOOK_SECRET` | SECRET | **YES** | *None* | Payment Webhooks | Webhook verification rejects requests with 401/400. |
| `OPENAI_API_KEY` | SECRET | **YES** | *None* | AI Provider, Statutory Search | AI queries fail-closed with clear error message. |
| `AWS_ACCESS_KEY_ID` | SECRET | **YES** | *None* | S3 Storage Provider | S3 presigned URL generation fails fast. |
| `AWS_SECRET_ACCESS_KEY`| SECRET | **YES** | *None* | S3 Storage Provider | S3 presigned URL generation fails fast. |
| `AWS_S3_BUCKET_NAME` | SENSITIVE | **YES** | `lcc-secure-documents` | S3 Storage Provider | Startup validation rejects unconfigured bucket. |
| `AWS_REGION` | INTERNAL | **YES** | `ap-south-1` | S3 Storage Provider | Defaults to AWS Mumbai region. |
| `REDIS_URL` | INTERNAL | OPTIONAL | `redis://localhost:6379/0`| Presence, Session Invalidation| Gracefully degrades to in-memory fallback. |
| `CLAMAV_HOST` | INTERNAL | OPTIONAL | `None` | Antivirus Daemon | Gracefully falls back to heuristic signature scanner. |
| `CLAMAV_PORT` | INTERNAL | OPTIONAL | `3310` | Antivirus Daemon | Standard ClamD daemon port. |
| `LIVEKIT_URL` | SENSITIVE | OPTIONAL | `None` | Video Consultation SFU | Falls back to WebRTC peer-to-peer / TURN relay. |
| `LIVEKIT_API_KEY` | SECRET | OPTIONAL | `None` | Video Consultation SFU | Room token issuance fails if URL set without keys. |
| `LIVEKIT_API_SECRET` | SECRET | OPTIONAL | `None` | Video Consultation SFU | Room token issuance fails if URL set without keys. |
| `TURN_SERVER_URL` | SENSITIVE | OPTIONAL | `None` | WebRTC NAT Traversal | Warning issued; direct P2P connection attempted. |
| `FRONTEND_URL` | PUBLIC | **YES** | `http://localhost:3000` | CORS, Cookie Domain, Emails | Required for strict CORS origin checking. |
| `BACKEND_CORS_ORIGINS` | SENSITIVE | **YES** | `["http://localhost:3000"]` | CORS Middleware | Wildcard `*` strictly forbidden in production. |
| `LOG_LEVEL` | PUBLIC | OPTIONAL | `INFO` | Structured Logger | Controls log verbosity (DEBUG, INFO, WARNING, ERROR). |

---

## 2. Secrets Management & Hygiene Policies

1. **Zero Source Control Leakage**:
   - `.env`, `.env.*`, `*.pem`, `*.key`, and credentials are fully ignored in `.gitignore` and `.dockerignore`.
   - Production secrets are injected dynamically via cloud secret stores (e.g. AWS Secrets Manager, Render Environment Groups, Kubernetes Secrets).
2. **Zero Insecure Defaults**:
   - Production startup explicitly rejects strings containing `replace`, `changeme`, `secret`, `dummy`, `test`, or `<set-in-environment>`.
   - `scripts/verify_production_config.py` runs before deployment to ensure all keys meet cryptographic requirements without printing secret values.
3. **Log Scrubbing**:
   - `SensitiveDataFilter` scrubs all access tokens, bearer tokens, passwords, private keys, credit cards, and presigned URLs from application logs.

---

## 3. Health & Readiness Probe Semantics

The application provides clearly segregated probes in `app/api/v1/health.py`:

- **Liveness Probe (`/health/live`, `/health`, `/liveness`)**:
  - Purpose: Indicates whether the application process and event loop are responsive.
  - Invariant: **Never checks external services or databases**. Prevents cascading container crash loops and restarts during transient external dependency outages.
  - Return: HTTP 200 `{"status": "alive", "service": "lcc-backend"}`.
- **Readiness Probe (`/health/ready`, `/readiness`)**:
  - Purpose: Indicates whether the application instance can safely receive and process incoming client requests.
  - Invariant: Executes a lightweight database ping (`SELECT 1`).
  - Return: HTTP 200 `{"status": "ready", "database": "connected"}` if operational; HTTP 503 `{"status": "not_ready"}` if database is unreachable.
- **Comprehensive Details Probe (`/health/details`)**:
  - Purpose: Deep operational monitoring of PostgreSQL, Redis, Storage, ClamAV, and Background Job queues.
  - Invariant: Sanitized output; never exposes internal connection strings or credentials.

---

## 4. Security Headers & TLS Configuration

Production HTTP responses enforce high-grade security headers via `SecurityHeadersMiddleware`:
- `Content-Security-Policy`: Restricts scripts, styles, frames (`frame-ancestors 'none'`), and object sources.
- `Strict-Transport-Security` (HSTS): `max-age=31536000; includeSubDomains; preload` ensures all browser traffic uses TLS 1.3/1.2.
- `X-Content-Type-Options`: `nosniff` prevents MIME-type sniffing.
- `X-Frame-Options`: `DENY` prevents clickjacking.
- `Referrer-Policy`: `strict-origin-when-cross-origin` protects sensitive URL paths.
- `Permissions-Policy`: Restricts browser camera/microphone access to legitimate consultation domains.

---

## 5. Resource Limits & Denial-of-Service Defense

1. **Payload Size Limits**: `RequestSizeLimitMiddleware` limits incoming HTTP request bodies to 5MB (`5_242_880 bytes`). Large evidence uploads bypass API servers via presigned S3 URLs directly to object storage.
2. **Rate Limiting**: `slowapi` enforces per-IP and per-user limits on sensitive endpoints (e.g. 5 requests/minute on login/registration, 20 requests/minute on AI search).
3. **Container Resource Limits**: Configured in `docker-compose.prod.yml`:
   - Backend: 2.0 CPUs, 2048 MB memory
   - Worker: 2.0 CPUs, 2048 MB memory
   - Scheduler: 1.0 CPUs, 1024 MB memory
   - Postgres: 2.0 CPUs, 2048 MB memory
   - Redis: 1.0 CPUs, 1024 MB memory
   - Frontend: 1.5 CPUs, 1536 MB memory
