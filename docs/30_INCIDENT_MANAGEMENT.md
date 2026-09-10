# 30 — PRODUCTION INCIDENT MANAGEMENT STANDARD

## 1. Incident Lifecycle & State Machine

Every production anomaly, degradation, security event, or data integrity issue must be tracked through the formal incident lifecycle:

```text
       ┌──────────┐
       │ DETECTED │
       └────┬─────┘
            │
            ├──────────────────────────────────────────┐
            ▼                                          │
    ┌──────────────┐                                   │
    │ ACKNOWLEDGED │                                   │
    └───────┬──────┘                                   │
            │                                          │
            ▼                                          ▼
    ┌───────────────┐                            ┌──────────┐
    │ INVESTIGATING │◄───────────────────────────┤  CLOSED  │ (Re-opened)
    └───────┬───────┘                            └────▲─────┘
            │                                         │
            ├──────────────────────────┐              │
            ▼                          ▼              │
      ┌───────────┐             ┌────────────┐        │
      │ MITIGATED │────────────►│  RESOLVED  ├────────┘
      └─────┬─────┘             └────────────┘
            │                          ▲
            └──────────────────────────┘
```

### State Machine Transition Invariants
1. **No Skip-To-Resolution**: An incident in `DETECTED` cannot transition directly to `RESOLVED` without acknowledgment or active investigation.
2. **Mandatory Documentation**: Transition to `RESOLVED` strictly requires `root_cause`, `mitigation`, or `resolution` notes.
3. **Audit Immutability**: Every transition appends an `IncidentTimelineEvent` and logs a non-repudiable `AuditEvent`.

---

## 2. Severity Classification Matrix

| Severity | Definition | Response SLA | Target Mitigation SLA | Incident Roles Activated |
| :--- | :--- | :--- | :--- | :--- |
| **SEV-1 (Critical)** | Platform outage, database unavailable, active data breach, cryptographic key compromise, evidence tampering detected. | **Immediate (15 min)** | **$< 2$ hours** | Incident Commander, Tech Lead, Comms Lead, SecOps Lead |
| **SEV-2 (High)** | Core workflow impaired (e.g. consultations failing, video room unreachable, auth failure spike, malware detected). | **30 min** | **$< 4$ hours** | Incident Commander, Tech Lead |
| **SEV-3 (Medium)** | Non-critical component degraded (e.g. background job latency, pilot allowlist sync delay, lawyer search filter slow). | **2 hours** | **$< 24$ hours** | On-call Engineer |
| **SEV-4 (Low)** | Minor cosmetic or non-blocking operational discrepancy, single user edge-case. | **Next Business Day** | Next Sprint | Assigned Engineer |

---

## 3. Incident Commander (IC) Playbook

1. **Acknowledge & Triage**:
   ```bash
   curl -X POST https://api.legalcasecompanion.in/api/v1/incidents/INC-20260904-0001/transition \
     -H "Authorization: Bearer <IC_TOKEN>" \
     -d '{"new_status": "ACKNOWLEDGED", "notes": "Incident acknowledged by SRE on-call; initiating bridge."}'
   ```
2. **Containment & Mitigation**:
   - If security breach/abuse $\to$ revoke offending user sessions, freeze account, apply IP throttling.
   - If service degradation $\to$ toggle `PILOT_GLOBAL_READ_ONLY=True` or disable specific features via `PILOT_DISABLED_FEATURES`.
3. **Resolution**:
   Record root cause, mitigation steps, and verify system recovery before marking `RESOLVED`.

---

## 4. Blameless Postmortem Policy & Template

All `SEV-1` and `SEV-2` incidents mandate a formal blameless postmortem published within 48 hours of closure.

```markdown
# INCIDENT POSTMORTEM: [INC-ID] - [Incident Summary]

## Executive Summary
- **Date / Time**: [YYYY-MM-DD HH:MM UTC]
- **Duration**: [X hours, Y minutes]
- **Severity**: [SEV-1 / SEV-2]
- **Impact**: [User impact summary]
- **Incident Commander**: [Name/Role]

## Timeline (UTC)
- `HH:MM`: Detected by [Automated Alert / User]
- `HH:MM`: Acknowledged by on-call engineer
- `HH:MM`: Root cause identified
- `HH:MM`: Mitigation applied
- `HH:MM`: Incident resolved and telemetry normalized

## Root Cause Analysis (5 Whys)
1. Why did the outage occur?
2. Why did that component fail?
3. Why was it not caught before production?
4. Why did the safeguard fail?
5. Why was the architecture vulnerable?

## Corrective & Preventative Actions
| Action Item | Type | Owner | Target Date |
| :--- | :--- | :--- | :--- |
| Add integration test for edge-case | Preventative | Engineer A | 2026-09-10 |
| Improve alert threshold | Detection | SRE Lead | 2026-09-08 |
```

---

## 5. Linkage with Support Cases & AI Human Reviews

1. **Support Case Linkage**: When customer support identifies an ongoing outage affecting multiple users, the support case is linked to the primary incident via `POST /api/v1/support/cases/{id}` (`linked_incident_id`), ensuring all affected users receive unified status updates upon incident resolution.
2. **AI Defect Linkage**: Severe AI hallucination or prompt injection incidents reported in `/api/v1/ai/reviews` link to a tracking `ProductionIncident`, triggering prompt defanging updates or model fallback procedures.

