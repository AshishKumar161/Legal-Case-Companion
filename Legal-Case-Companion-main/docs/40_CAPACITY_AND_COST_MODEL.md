# 40 — CAPACITY VALIDATION & COST OBSERVABILITY MODEL

## 1. Capacity Limits & Operating Envelopes (Part M)

LCC defines three distinct operating envelopes based on measured load behavior in staging:

| Metric / Dimension | Safe Operating Envelope (Green) | Degradation Threshold (Amber) | Emergency Threshold (Red) | Scaling Action |
| :--- | :--- | :--- | :--- | :--- |
| **Concurrent HTTP Req/sec**| $\le 250\text{ rps}$ | $250 - 500\text{ rps}$ | $> 500\text{ rps}$ | Auto-scale backend container replicas |
| **PostgreSQL Active Conns** | $\le 40$ | $40 - 75$ | $> 75$ (Max: 100) | Enable PgBouncer transaction pooling |
| **Redis Memory Utilization**| $\le 400\text{ MB}$ | $400 - 800\text{ MB}$ | $> 800\text{ MB}$ (Max: 1GB) | Flush expired ephemeral keys; scale node |
| **Background Queue Depth** | $\le 20\text{ jobs}$ | $20 - 100\text{ jobs}$ | $> 100\text{ jobs}$ | Spin up secondary Celery worker worker pool |
| **ClamAV CPU Saturation** | $\le 60\%$ | $60\% - 85\%$ | $> 85\%$ | Scale ClamAV daemon container instances |
| **LiveKit Concurrent Rooms**| $\le 30$ | $30 - 75$ | $> 75$ | Expand LiveKit SFU node cluster |
| **AI Request Latency (p95)** | $\le 2,500\text{ ms}$ | $2,500 - 5,000\text{ ms}$ | $> 5,000\text{ ms}$ | Circuit breaker to fallback provider |

---

## 2. Infrastructure Cost Observability Model (Part N)

The system exposes live approximate cost estimations via `GET /api/v1/pilot/costs`.

### Unit Cost Assumptions (USD):
- **HTTP API Request**: $\$0.000002$ per request.
- **Evidence Storage & Scan**: $\$0.0050$ per uploaded file (ClamAV compute + S3 PUT).
- **AI Query Completion**: $\$0.0150$ per query (input context chunks + model generation).
- **LiveKit WebRTC Video Hour**: $\$0.0400$ per consultation hour (bandwidth + TURN relay).

### Approximate Infrastructure Cost Per Legal Workflow:
- **Matter Creation & Setup**: $\$0.0015$
- **Evidence Upload & Virus Scan**: $\$0.0055$ per exhibit
- **AI-Grounded Case Fact Extraction**: $\$0.0200$ per 5-document matter
- **45-Minute Consultation (Audio/Video + Recording)**: $\$0.0350$
- **Entire Client Onboarding to Resolution Lifecycle**: $\approx \$0.15 - \$0.30$ per case
