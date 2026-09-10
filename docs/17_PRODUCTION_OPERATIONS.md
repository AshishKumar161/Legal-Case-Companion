# Production Operations & Deployment Guide (Phase XV)

## 1. Operational Deployment Topology

Legal Case Companion (LCC) is designed as a modular monolith capable of independent multi-instance horizontal scaling:

```text
                                 [ Internet / Clients ]
                                           │
                                   [ Load Balancer ]
                                   (TLS Termination)
                                           │
                        ┌──────────────────┴──────────────────┐
                        │                                     │
               [ Web / API Node A ]                  [ Web / API Node B ]
               (FastAPI / Uvicorn)                   (FastAPI / Uvicorn)
                        │                                     │
                        └──────────────────┬──────────────────┘
                                           │
               ┌───────────────────────────┼───────────────────────────┐
               │                           │                           │
      [ PostgreSQL 15+ ]            [ Redis 7 Cluster ]         [ Private AWS S3 ]
      (Authoritative DB)           (Presence / Tickets / PubSub) (Encrypted Object Store)
               │                           │                           │
               └───────────────────────────┼───────────────────────────┘
                                           │
                        ┌──────────────────┴──────────────────┐
                        │                                     │
              [ Background Worker A ]               [ Background Worker B ]
              (app.worker / Leasing)                (app.worker / Leasing)
                        │                                     │
                        └──────────────────┬──────────────────┘
                                           │
                                  [ Job Scheduler ]
                                (app.scheduler - Single)
```

---

## 2. Background Workers & Queue Management

The execution model employs **PostgreSQL-backed row-level atomic locking** (`locked_by`, `locked_until`) with leasing to ensure at-most-once/at-least-once durable execution across multi-instance worker fleets:

- **Worker Deployment Command**:
  ```bash
  python -m app.worker [poll_interval_seconds]
  ```
  Default polling interval is `2.0` seconds with batch size `10`.
- **Worker Scaling**:
  Multiple worker processes (`lcc_worker_prod_1`, `lcc_worker_prod_2`) can run concurrently. They use `skip_locked=True` during batch claims to eliminate lock contention.
- **Graceful Shutdown**:
  Workers listen to `SIGTERM` and `SIGINT`. Upon signal reception, the active loop finishes processing its in-flight batch, releases leases, and terminates cleanly within container shutdown timeouts (30s).
- **Lease Expiry & Dead-Letter Handling**:
  If a worker crashes mid-job, its lease (`locked_until`) expires after 60 seconds. The `STALE_JOB_RECOVERY` routine re-queues expired jobs with exponential backoff. Jobs that exhaust `max_attempts` (default: 5) transition to `DEAD_LETTER` with complete stack traces preserved in `last_error`.

---

## 3. Database Connection Pool Configuration

The application uses SQLAlchemy with the Psycopg 3 binary driver. Recommended production connection pool settings:

```python
# Engine Settings (app/db/database.py)
pool_size = 20          # Base connections per API instance
max_overflow = 10       # Max surge connections during traffic spikes
pool_timeout = 30       # Seconds to wait for a connection before failing
pool_recycle = 1800     # Recycle connections every 30 minutes
pool_pre_ping = True    # Validates connection liveness before checkout
```

Worker processes use lower pool allocations (`pool_size = 5`, `max_overflow = 5`) to prevent starving web API threads.

---

## 4. Timeout Policies & Bounded Execution

| Subsystem | Operation | Timeout | Fallback / Behavior |
|---|---|:---:|---|
| **API Requests** | Inbound HTTP | 30s | Bounded by reverse proxy (Nginx/ALB) |
| **PostgreSQL** | Read / Write queries | 5s | Statement timeout; rolls back transaction |
| **Redis** | Ping / Token checks | 2s | In-memory fallback or graceful degradation |
| **AWS S3** | Object PUT / GET | 10s | Bounded retry with exponential backoff |
| **ClamAV** | File Byte Scanning | 10s | Fail-closed: marks `SCAN_FAILED`, never activates |
| **Worker Jobs** | Job Lease Execution | 60s | Stale job recovery reclaims lease |
| **WebSockets** | Handshake Ticket | 60s | Ephemeral single-use ticket expiry |

---

## 5. Database Migration Discipline

1. **Zero-Downtime Rule**: Schema changes must be backward-compatible with running API instances.
2. **Column Additions**: Must be nullable or have database-level server defaults (`server_default`).
3. **Index Creation**: Long-running table index creation in PostgreSQL must use `CONCURRENTLY` where supported.
4. **Pre-Deployment Execution**:
   ```bash
   alembic upgrade head
   ```
5. **Rollback Plan**:
   Every migration defines a corresponding `downgrade()` method. Verify schema reversibility in staging prior to production application.

---

## 6. Production Deployment Checklist

- [ ] Database backup snapshot taken before applying migrations.
- [ ] Environment variables verified against `.env.example`.
- [ ] `ENVIRONMENT=production` set (disables dev mocks, enforces HTTPS cookies).
- [ ] Database migrations executed (`alembic upgrade head`).
- [ ] Health checks reporting `ready`:
  ```bash
  curl -f http://localhost:8000/api/v1/health/ready
  ```
- [ ] Worker container launched and verified (`python -m app.worker`).
- [ ] Scheduler container launched (`python -m app.scheduler`).
- [ ] Redis cluster reachable and responsive.
- [ ] AWS S3 bucket permissions verified (`s3:GetObject`, `s3:PutObject`).
- [ ] ClamAV scanner container healthy and responding on port 3310.
- [ ] Structured JSON logging active with secret redaction verified.
