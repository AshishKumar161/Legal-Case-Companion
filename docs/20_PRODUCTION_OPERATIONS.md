# Legal Case Companion (LCC) — Production Operations Manual (6.0)

This operational manual governs the deployment architecture, configuration standards, observability mechanisms, and background worker operations for Legal Case Companion in production.

---

## 1. Production Architecture Topology

```
                              [ Cloudflare / CDN ]
                                       │
                                       ▼
                       [ Render Web Service (FastAPI) ]
                       - HTTPS Terminated (ap-south-1 / Singapore)
                       - SecurityHeadersMiddleware (HSTS, CSP, X-Frame)
                       - CorrelationIdMiddleware (Tracing)
                       - PayloadLimit (15MB document bound)
                                       │
                 ┌─────────────────────┴─────────────────────┐
                 │                                           │
                 ▼                                           ▼
       [ PostgreSQL (Render) ]                     [ Background Workers ]
       - pgvector Extension                        - Idempotent Queue Processing
       - Pool: 20 conns, 10 overflow               - Stale Lease Recovery
       - Auto Point-in-Time Backups                - Deadline & Reminder Scanners
                 │
                 ▼
       [ AWS S3 (ap-south-1) ]
       - Bucket: lcc-secure-documents
       - SSE-S3 Encryption
       - Private Access (Zero Public ACLs)
       - Presigned URLs with 15-min TTL
```

---

## 2. Environment Configuration Matrix

| Variable | Staging | Production | Description / Policy |
| :--- | :--- | :--- | :--- |
| `ENVIRONMENT` | `staging` | `production` | Enables strict production secret checks in `Settings`. |
| `DEBUG` | `False` | `False` | Enforces no debug stack traces or interactive debuggers. |
| `JWT_PRIVATE_KEY` / `PUBLIC_KEY` | Real Ed25519 PEM | Real Ed25519 PEM | Strict asymmetric EdDSA signing keys (no dev fallback). |
| `CSRF_SECRET_KEY` | Cryptographic secret | Cryptographic secret | Minimum 32-byte secret for double-submit cookie verification. |
| `DATABASE_URL` | `postgresql://.../lcc_staging` | `postgresql://.../lcc_prod` | Dedicated PostgreSQL instance with pooling & pgvector. |
| `AWS_S3_BUCKET_NAME` | `lcc-docs-staging` | `lcc-secure-documents` | Isolated document storage buckets. |
| `AWS_WEBHOOK_SECRET` | Webhook signing key | Webhook signing key | Authenticates AWS malware scanning event callbacks. |
| `STRIPE_API_KEY` / `SECRET` | `sk_test_...` | `sk_live_...` | Payment and consultation booking checkout webhooks. |
| `EMAIL_PROVIDER` | `sendgrid` (or sandbox) | `sendgrid` (or `ses`) | Production email dispatch with domain verification. |
| `OPENAI_API_KEY` | Dedicated Org Key | Production Org Key | Bound LLM inference & text embeddings (`text-embedding-3-small`). |

---

## 3. Observability & Operational Dashboard

Production telemetry is accessible via `/api/v1/admin/metrics` and `/api/v1/admin/jobs/stats`:

### Key Operational Questions & Metrics:
1. **Is the API healthy?**
   - Probe: `GET /api/v1/health/live` (Process state).
   - Probe: `GET /api/v1/health/ready` (Verifies database connectivity).
2. **Are background workers healthy?**
   - Endpoint: `GET /api/v1/admin/jobs/stats`.
   - Alert condition: `RUNNING` jobs with expired leases $> 5\text{ minutes}$ (stale lease recovery triggers automatically).
3. **Are documents processing safely?**
   - Statuses tracked: `QUARANTINED` $\to$ `SAFE` $\to$ `READY`.
   - Alert condition: Document status = `FAILED` exceeding $2\%$ of daily upload volume.
4. **Is AI responding within boundaries?**
   - Monitored via `ai_response_audits` table (`grounding_score`, `citation_accuracy`, `latency_ms`).
   - Alert condition: Average p95 latency $> 8\text{ seconds}$ or grounding score drop below $0.85$.
5. **Are payments working?**
   - Webhook endpoint: `/api/v1/webhooks/stripe`.
   - Idempotency key tracking via `payments` table prevents duplicate charging.

---

## 4. AI Context Bounding & Cost Governance

To prevent uncontrolled token consumption or runaway API spend:
- **Maximum Query Length**: Hard bounded at $2,000$ characters.
- **Retrieved Chunks Bound**: Maximum 5 document chunks per query (`top_k=5`).
- **Prompt Injection Defense**: Multi-pattern regex scanner drops override attempts before LLM dispatch.
- **Rate Limits**: Scoped per user via `slowapi` (`10/min` on conversation creation, `15/min` on messages).
