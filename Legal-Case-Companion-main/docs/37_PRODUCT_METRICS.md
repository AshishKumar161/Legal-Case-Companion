# 37 — PRODUCT FUNNEL & WORKFLOW TELEMETRY SPECIFICATION

## 1. Privacy-Conscious Telemetry Architecture (Part T)

Legal Case Companion (LCC) measures product usability and funnel progression without becoming a secondary repository of privileged legal communications or sensitive personal data.

### Strict Data Minimization Invariants
- **No Document Contents**: Telemetry payloads strictly prohibit raw document excerpts, contract terms, or evidence bytes.
- **No Private Case Notes**: Private notes, consultation chat transcripts, and advocate trial strategies are completely excluded from analytics.
- **No Secrets or Credentials**: Passwords, bearer tokens, and presigned URLs are stripped by `_sanitize_metadata` in [app/services/workflow_telemetry_service.py](file:///c:/Users/akuma/OneDrive/Desktop/lcc/Legal-Case-Companion-main/Legal-Case-Companion-main/app/services/workflow_telemetry_service.py).
- **Bounded Metadata**: Payloads contain only coarse-grained categories, execution durations, error codes, and entity UUIDs.

---

## 2. Core Funnel Progression Maps (Part C)

### 2.1 Litigant / Client Journey Funnel
```text
[ USER_REGISTERED ]
       │
       ▼
[ ONBOARDING_COMPLETED ]
       │
       ▼
[ CASE_CREATED ]
       │
       ▼
[ LAWYER_SEARCHED ]
       │
       ▼
[ CONSULTATION_REQUESTED ]
       │
       ▼
[ CONSULTATION_COMPLETED ]
       │
       ▼
[ EVIDENCE_UPLOADED ]
       │
       ▼
[ COPILOT_QUERIED ]
```

### 2.2 Advocate / Lawyer Journey Funnel
```text
[ LAWYER_REGISTERED ]
       │
       ▼
[ LAWYER_VERIFICATION_SUBMITTED ]
       │
       ▼
[ LAWYER_VERIFICATION_COMPLETED ]
       │
       ▼
[ LAWYER_AVAILABILITY_CONFIGURED ]
       │
       ▼
[ CONSULTATION_ACCEPTED ]
       │
       ▼
[ CONSULTATION_COMPLETED ]
       │
       ▼
[ EVIDENCE_REVIEWED ]
```

---

## 3. Workflow Execution Telemetry (Part D)

Every critical workflow execution emits structured lifecycle telemetry:

| Workflow Slug | Measured Transition | Success Criteria | Expected Failures | Unexpected Failures |
| :--- | :--- | :--- | :--- | :--- |
| `REGISTRATION` | Account signup | `201 Created` | Capacity reached, unlisted email | Internal DB crash |
| `CASE_CREATION` | Matter initialization | `201 Created` with UUID | Missing required title | DB constraint violation |
| `CONSULTATION_BOOKING`| Slot reservation & payment | Status `SCHEDULED` | Advocate busy, slot taken | Payment provider timeout |
| `VIDEO_INITIATION` | WebRTC room join | Session active, token issued | Unsupported browser | SFU disconnection |
| `EVIDENCE_UPLOAD` | File upload & quarantine | File staged in S3 | Disallowed extension, file too large | S3 bucket timeout |
| `EVIDENCE_ACTIVATION`| ClamAV virus scan | Status `ACTIVE` with hash | Malware detected (`QUARANTINED`) | ClamAV daemon crash |
| `AI_RETRIEVAL` | Vector chunk search | $\ge 1$ chunk retrieved | 0 matching chunks (safe refusal) | Embedding service error |

---

## 4. Querying Funnel & Operational Metrics

Operators holding `ADMIN` privileges inspect real-time funnel conversion via:
```bash
curl -X GET https://api.legalcasecompanion.in/api/v1/pilot/funnel \
  -H "Authorization: Bearer <ADMIN_TOKEN>"
```

### Response Schema:
```json
{
  "client_funnel": {
    "registered": 75,
    "first_case_created": 62,
    "lawyer_searched": 54,
    "consultation_requested": 48,
    "consultation_completed": 45,
    "evidence_uploaded": 40,
    "ai_interaction": 38
  },
  "lawyer_funnel": {
    "registered": 30,
    "verification_submitted": 28,
    "availability_configured": 26,
    "consultation_accepted": 25,
    "consultation_completed": 25,
    "evidence_reviewed": 22
  },
  "sample_confidence": "HIGH"
}
```

---

## 5. Phase XX Regional Language & Commercial Metrics (Part P)

Phase XX expands product telemetry with privacy-preserving aggregates:

### 5.1 Language Adoption Tracking
- Tracks distribution across `en-IN` and `hi-IN` active client sessions.
- Measures dictionary fallback frequencies (`MetricsCollector.record_localization_fallback`) to detect unlocalized keys in regional production flows.

### 5.2 Commercial & Financial Aggregates
- **Gross Merchandise Value (GMV)**: Cumulative client consultation bookings.
- **Platform Facilitation Revenue**: 10.0% facilitation fee.
- **Statutory GST Accrual**: 18.0% Goods and Services Tax recorded under SAC 9982.
- **Refund Ratio**: Tracks proportion of rescheduled or disputed consultations.

### 5.3 Public Abuse Telemetry
- Aggregated counts of blocked disposable domains (`MetricsCollector.record_abuse_anomaly`).
- Throttled consultation request velocity events.
