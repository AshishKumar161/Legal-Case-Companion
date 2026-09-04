# 29 — SRE SLOS, METRICS & PRODUCTION ALERTING CATALOG

## 1. Objective & Philosophy

This document defines the production Service Level Indicators (SLIs), Service Level Objectives (SLOs), error-budget consumption formulas, and actionable alert definitions for the Legal Case Companion (LCC) platform.

**Core SRE Directive**: Alert only on actionable, user-impacting conditions. Avoid alert fatigue by prohibiting informational alerts from paging operators.

---

## 2. Service Level Objectives (SLOs) Matrix

| Domain | Service Level Indicator (SLI) | Target SLO | Measurement Window | Action on Breach |
| :--- | :--- | :--- | :--- | :--- |
| **API Availability** | $\frac{\text{Successful Requests } (<500)}{\text{Total Requests}}$ | $\ge 99.90\%$ | Rolling 30 days & Process Lifetime | Deploy freeze, SRE incident trigger |
| **API Latency** | 95th Percentile (p95) HTTP request duration | $< 500\text{ ms}$ | Rolling 24 hours | Profile slow query logs, scale backend workers |
| **Authentication** | $\frac{\text{Successful Token Operations}}{\text{Total Auth Operations}}$ | $\ge 99.95\%$ | Rolling 7 days | SecOps investigation for brute force/replay |
| **Evidence Activation**| Time from staged upload completion to virus-clean activation | $< 10.0\text{ s}$ (p95) | Rolling 24 hours | Check ClamAV daemon saturation |
| **Background Jobs** | $\frac{\text{Jobs Completed Without Permanent Failure}}{\text{Total Enqueued Jobs}}$ | $\ge 99.50\%$ | Rolling 7 days | Dead-letter queue inspection |
| **WebSocket Realtime**| Connection establishment success rate | $\ge 99.00\%$ | Rolling 24 hours | Check Redis pub/sub broker latency |
| **AI Safety Grounding**| Rate of answers backed by verified document citations | $\ge 98.00\%$ | Rolling 7 days | Prompt tuning, retrieval threshold adjustments |
| **Database Durability** | Daily automated snapshot and restore drill verification | $100\%$ | Daily | Immediate SEV-1 blocker |

---

## 3. Error Budget Consumption Formulas

For an availability target of $99.90\%$, the platform's allowed failure budget is $0.10\%$ ($1$ in $1,000$ requests):

$$\text{Allowed Error Count} = \text{Total Requests} \times 0.001$$

$$\text{Error Budget Consumed (\%)} = \left( \frac{\text{Count of HTTP 5xx Errors}}{\text{Allowed Error Count}} \right) \times 100$$

$$\text{Error Budget Remaining (\%)} = \max(100.0 - \text{Error Budget Consumed}, 0.0)$$

### Operational Burn Rate Policy
- **$< 50\%$ Consumed**: Normal release velocity.
- **$50\% - 80\%$ Consumed**: Feature velocity throttled; priority shifted to bug fixes and reliability hardening.
- **$\ge 100\%$ Consumed (Exhausted)**: **RELEASE FREEZE**. No non-emergency production deployments permitted until availability recovers.

---

## 4. Production Alerting Catalog

Each alert is evaluated in real time via `GET /api/v1/pilot/alerts` and the background health evaluator:

### Alert 1: Sustained HTTP 5xx Error Spike (`ALERT-HTTP-5XX-SPIKE`)
- **Condition**: 5xx error rate $> 0.50\%$ over $\ge 50$ requests within rolling window.
- **Severity**: `SEV-1 CRITICAL` (if $> 5\%$) / `SEV-2 HIGH` (if $> 0.5\%$).
- **Trigger**: Server exceptions, unhandled middleware crashes, or database query timeouts.
- **Escalation**: On-call Platform SRE $\to$ Backend Engineering Lead.
- **Runbook**: [24_PRODUCTION_DEPLOYMENT_RUNBOOK.md](file:///c:/Users/akuma/OneDrive/Desktop/lcc/Legal-Case-Companion-main/Legal-Case-Companion-main/docs/24_PRODUCTION_DEPLOYMENT_RUNBOOK.md).

### Alert 2: Evidence Locker Cryptographic Tampering (`ALERT-EVIDENCE-TAMPERING`)
- **Condition**: `tamper_events_total > 0`.
- **Severity**: `SEV-1 CRITICAL`.
- **Trigger**: S3 object payload byte SHA-256 mismatch against immutable custody record.
- **Escalation**: Immediate page to SecOps Lead and Legal Compliance Officer.
- **Immediate Action**: Execute security freeze on affected evidence ID; extract S3 access audit logs.
- **Runbook**: [23_INCIDENT_RESPONSE.md](file:///c:/Users/akuma/OneDrive/Desktop/lcc/Legal-Case-Companion-main/Legal-Case-Companion-main/docs/23_INCIDENT_RESPONSE.md).

### Alert 3: Authentication Anomaly / Stuffing Spike (`ALERT-AUTH-ATTACK-SPIKE`)
- **Condition**: Total authentication failure count $\ge 30$ in rolling sample.
- **Severity**: `SEV-2 HIGH`.
- **Trigger**: Credential stuffing, brute-force attempts, or widespread refresh-token family reuse.
- **Escalation**: SecOps Incident Responder.
- **Immediate Action**: Inspect IP distribution in structured access logs; apply IP rate-limiting rules.
- **Runbook**: [23_INCIDENT_RESPONSE.md](file:///c:/Users/akuma/OneDrive/Desktop/lcc/Legal-Case-Companion-main/Legal-Case-Companion-main/docs/23_INCIDENT_RESPONSE.md).

### Alert 4: Background Worker Dead-Letter Backlog (`ALERT-DLQ-BACKLOG`)
- **Condition**: Exhausted background jobs in `DEAD_LETTER` status $\ge 5$.
- **Severity**: `SEV-3 MEDIUM`.
- **Trigger**: Downstream API outage (OpenAI, Stripe, SendGrid), persistent database deadlock.
- **Escalation**: Application Engineering On-Call.
- **Immediate Action**: Inspect job stack traces via `/api/v1/admin/jobs?status=DEAD_LETTER`.
- **Runbook**: [24_PRODUCTION_DEPLOYMENT_RUNBOOK.md](file:///c:/Users/akuma/OneDrive/Desktop/lcc/Legal-Case-Companion-main/Legal-Case-Companion-main/docs/24_PRODUCTION_DEPLOYMENT_RUNBOOK.md).

### Alert 5: Dependency Outage / Circuit Breaker (`ALERT-DEPENDENCY-FAILURE`)
- **Condition**: Cumulative dependency failure events $\ge 10$.
- **Severity**: `SEV-2 HIGH`.
- **Trigger**: Redis disconnection, S3 timeout, ClamAV daemon crash, LiveKit SFU failure.
- **Escalation**: Platform SRE.
- **Immediate Action**: Check container health via `docker compose ps` and backing service network latency.
- **Runbook**: [24_PRODUCTION_DEPLOYMENT_RUNBOOK.md](file:///c:/Users/akuma/OneDrive/Desktop/lcc/Legal-Case-Companion-main/Legal-Case-Companion-main/docs/24_PRODUCTION_DEPLOYMENT_RUNBOOK.md).

---

## 5. Statistical Validity & Sample Confidence Limits (Part E)

In controlled low-volume pilot environments, reporting $100\%$ availability over 5 requests is statistically meaningless. LCC enforces explicit statistical confidence constraints:

1. **Threshold Requirement**: Sample sizes $N < 30$ requests trigger the flag:
   ```json
   "confidence_limitation": "INSUFFICIENT_SAMPLE_SIZE"
   ```
2. **Definitive Claims Restricted**: No SLO is certified as definitively met for public release until sample size $N \ge 30$ with error budget consumption $< 20\%$.
3. **WebRTC Failure Decomposition (Part K)**:
   Realtime failures are separated into distinct telemetry buckets:
   - `webrtc_signaling_failure`
   - `webrtc_ice_failure`
   - `webrtc_turn_relay_failure`
   - `webrtc_device_permission_denied`
   - `webrtc_user_abandonment`

