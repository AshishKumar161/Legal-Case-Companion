# Phase 9: Observability, Audit Logging & Health Architecture

## 1. Observability Architecture Overview

The Legal Case Companion (LCC) platform employs a unified observability model across three pillars:
1. **Distributed Tracing & Correlation**: End-to-end request tracing via `X-Request-ID` and Python context variables (`correlation_id_ctx`).
2. **Structured Logging & Privacy Scrubbing**: JSON-formatted logs with automatic redaction of bearer tokens, passwords, credit card numbers, and raw case document text.
3. **Metrics & Telemetry**: Prometheus metric registry (`app/core/metrics.py`) tracking request latencies, failure counters, worker queues, outbox states, and WebRTC telemetry.

---

## 2. Correlation ID Propagation Lifecycle

Every transaction is assigned a globally unique UUIDv7 correlation ID that propagates across distributed boundaries:

```
[Browser Client]
  │  (Header: X-Request-ID: <UUIDv7>)
  ▼
[CorrelationIdMiddleware]
  │  1. Sanitizes ID (prevents log injection)
  │  2. Sets contextvar `correlation_id_ctx`
  │  3. Injects into `request.state.correlation_id`
  ▼
[FastAPI Domain Routes & Services]
  │  Accesses `correlation_id_ctx.get()`
  ├──► [Database: AuditEvent] (Stores in `metadata.correlation_id`)
  ├──► [Outbox: OutboxEvent] (Stores in `headers.correlation_id`)
  └──► [Job: BackgroundJob] (Stores in `payload._correlation_id`)
  ▼
[Background Worker / Downstream Dispatcher]
  │  Restores correlation context from job/event payload
  └──► [External Provider Call] (Injects into headers / idempotency keys)
  ▼
[HTTP Response]
  └── Injects `X-Request-ID` header back to browser
```

### Verification
Validated by `test_correlation_id_propagation_to_audit` in `tests/integration/test_phase_9_cross_system_reliability.py`.

---

## 3. Privacy-Preserving Log Scrubber

The logger incorporates `SensitiveDataFilter` to prevent confidential legal data, passwords, and tokens from leaking into logs:

- **Tokens & Secrets Redacted**:
  - `Bearer [a-zA-Z0-9_\-\.]{20,}` → `Bearer [REDACTED_TOKEN]`
  - `password=...`, `client_secret=...` → `[REDACTED_SECRET]`
  - Presigned S3 query parameters (`X-Amz-Signature=...`) → `[REDACTED_SIGNATURE]`
- **PII Scrubbing**:
  - Aadhaar numbers (`\d{4}\s\d{4}\s\d{4}`) masked.
  - PAN cards (`[A-Z]{5}[0-9]{4}[A-Z]`) masked.
  - Credit card numbers (`\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}`) masked.

---

## 4. Authoritative Audit Logging (`AuditEvent`)

Audit logging is enforced on every security, operational, and commercial mutation:

| Field | Description | Example |
|---|---|---|
| `id` | Unique UUIDv7 audit identifier | `01a08c50-7000-8000-9000-000000000001` |
| `actor_user_id` | User initiating the action (or `None` for system jobs) | `01a08c3f-26c5-7a91-90e5-b6c5f567593c` |
| `action` | Business action identifier | `PAYMENT_SUCCEEDED`, `CONSULTATION_CANCELLED` |
| `event_type` | Categorical event classification | `CONSULTATION_MUTATION`, `AUTH_EVENT` |
| `entity_type` | Subject resource type | `CONSULTATION`, `PAYMENT`, `CASE` |
| `entity_id` | Subject resource UUID | `01a08c40-a739-7953-a5db-8f7a0007b99b` |
| `timestamp` | UTC timestamp of event | `2026-09-10T16:57:22.491982Z` |
| `metadata_` | Safe contextual payload & correlation ID | `{"correlation_id": "...", "amount": 2000.0}` |

Audit logs are strictly **append-only**. No update or delete endpoints exist for the `audit_events` table.

---

## 5. System Health & Readiness Architecture

The platform separates **Liveness** from **Readiness** to prevent cascading restarts in orchestrators (Kubernetes / Docker Swarm):

### 5.1 Liveness Probe (`GET /health`)
- **Purpose**: Confirms the FastAPI process is responsive and event loop is not deadlocked.
- **Dependencies**: None. Returns HTTP 200 immediately.
- **Failure Action**: Orchestrator restarts container.

### 5.2 Readiness Probe (`GET /health/readiness`)
- **Purpose**: Determines whether the service can actively serve production user traffic.
- **Subsystem Checks**:
  1. **PostgreSQL**: Executes `SELECT 1` with a 2-second timeout.
  2. **Redis**: Pings active Redis connection pool.
  3. **Storage Provider**: Confirms MinIO/S3 bucket accessibility.
- **Failure Behavior**: Returns HTTP 503 with JSON breakdown of failing subsystems. Orchestrator temporarily stops routing traffic to the instance without restarting the process.

---

## 6. Graceful Application Shutdown

In `app/main.py`, lifecycle handlers ensure no in-flight work is lost during deployments or container termination:
1. **Stop Ingress**: Readiness probe begins returning 503; HTTP server stops accepting new connections.
2. **Worker Grace Period**: Background job workers finish their active batch (up to 30s grace).
3. **Signaling Disconnect**: WebRTC signaling manager dispatches room shutdown notifications to connected peers.
4. **Pool Teardown**: Database engine connections (`engine.dispose()`) and Redis connection pools are safely closed.
