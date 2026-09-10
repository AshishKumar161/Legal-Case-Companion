# Observability, Logging & Alerting Specification (Phase XV)

## 1. Structured Logging Specification

In production (`ENVIRONMENT=production`), all application log output is formatted as machine-readable single-line JSON on `stdout`.

### JSON Log Schema
```json
{
  "timestamp": "2026-09-04T02:30:00Z",
  "level": "INFO",
  "logger": "app.services.evidence_service",
  "service": "lcc-backend",
  "environment": "production",
  "correlation_id": "0191bd76-943b-7a38-89c0-547e14d4ef9a",
  "user_id": "0191bd76-943b-7a38-89c0-547e14d4ef9b",
  "duration_ms": 42.5,
  "action": "EVIDENCE_ACTIVATION",
  "message": "Evidence 'Master Services Agreement' successfully scanned and activated.",
  "error_code": null,
  "exception": null
}
```

### Sensitive Data Scrubbing
The `SensitiveDataScrubberFilter` automatically redacts sensitive tokens, passwords, and private URLs before writing to stdout:
- Passwords $\rightarrow$ `***REDACTED***`
- Bearer tokens $\rightarrow$ `Bearer ***REDACTED***`
- Refresh tokens $\rightarrow$ `***REDACTED***`
- Access tokens $\rightarrow$ `***REDACTED***`
- AWS S3 Presigned URL signatures $\rightarrow$ `X-Amz-Signature=***REDACTED***`

---

## 2. Correlation ID Propagation

Every HTTP request is stamped with a unique correlation identifier (`X-Request-ID`):
1. **Client Ingestion**: If supplied by caller, sanitized to prevent header injection. If absent, a new UUIDv7 identifier is generated.
2. **Context Variable**: Bound to `correlation_id_ctx` using Python `contextvars.ContextVar`.
3. **Log Injection**: Filtered into all logging output automatically.
4. **Asynchronous Background Tasks**: Propagated inside `job.payload["_correlation_id"]` and `outbox.headers["correlation_id"]` to trace operations across worker process boundaries.
5. **Response Header**: Echoed in HTTP response header `X-Request-ID`.

---

## 3. Operational Metrics Dictionary

Metrics are tracked with **strictly bounded cardinality** to prevent memory exhaustion in time-series collectors:

| Metric Name | Type | Labels | Description |
|---|:---:|---|---|
| `http_requests_total` | Counter | `method`, `path` | Total HTTP request volume per endpoint |
| `http_status_total` | Counter | `status_code` | Distribution of HTTP status codes (2xx, 4xx, 5xx) |
| `http_latency_ms` | Histogram | - | Average and P95 latency across recent request samples |
| `auth_failures_total` | Counter | `reason` | Authentication failure count (`INVALID_CREDENTIALS`, `EXPIRED_TOKEN`) |
| `authorization_denials_total` | Counter | `resource_type` | Access denials (`case`, `evidence`, `consultation`, `admin`) |
| `evidence_operations_total` | Counter | `operation`, `outcome` | Evidence vault actions (`UPLOAD_INIT`, `ACTIVATION`, `SHARE`, `VERIFY`) |
| `evidence_tamper_alerts_total` | Counter | - | High-severity count of detected cryptographic hash mismatches |
| `queue_jobs_total` | Counter | `job_type`, `status` | Background job execution count (`SUCCEEDED`, `RETRYING`, `DEAD_LETTER`) |
| `dependency_failures_total` | Counter | `dependency_name` | Outage count (`DATABASE`, `REDIS`, `MALWARE_SCANNER`, `STORAGE`) |
| `outbox_events_total` | Counter | `event_type`, `status` | Outbox events (`PUBLISHED`, `RETRYING`, `DEAD_LETTER`) |

> [!CAUTION]
> **Cardinality Rule**: Never use dynamic UUIDs (`user_id`, `case_id`, `evidence_id`) as Prometheus/metrics labels. Labels must use predefined, finite enum sets.

---

## 4. Health Check Endpoints

| Endpoint | Target Probe | Timeout | Description |
|---|---|:---:|---|
| **`GET /health/live`** | Orchestrator Liveness | None | Confirms Python process is responsive. Never fails on external dependency outages. |
| **`GET /health/ready`** | Load Balancer Readiness | 3s | Confirms database connectivity before routing inbound traffic. Returns `503` if DB down. |
| **`GET /health/details`** | Ops Deep Monitoring | 5s | Reports granular connection state for PostgreSQL, Redis, S3, ClamAV, and queue depths. |

---

## 5. Security & Reliability Alerting Thresholds

| Severity | Alert Condition | Window | Action |
|:---:|---|:---:|---|
| **P1 — CRITICAL** | `evidence_tamper_alerts_total > 0` | Immediate | On-call security page; immediately freeze affected evidence item |
| **P1 — CRITICAL** | `database_status == disconnected` | 1 minute | Page on-call; check PostgreSQL container / cluster status |
| **P1 — CRITICAL** | `dead_letter_jobs > 5` | 5 minutes | Alert DevOps; inspect dead-letter error logs |
| **P2 — WARNING** | `http_5xx_error_rate > 1%` | 5 minutes | Investigate recent deployments or upstream dependency latency |
| **P2 — WARNING** | `redis_status == degraded` | 3 minutes | Verify Redis service; notify realtime team |
| **P3 — INFO** | `auth_failures_total > 50` | 10 minutes | Check for brute force or client token refresh misconfiguration |
