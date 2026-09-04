# 39 — SUPPORT INTELLIGENCE & USER FEEDBACK OPERATIONS

## 1. Zero-Trust Support Boundaries (Part G)

Customer support personnel holding the `USER_SUPPORT` operational permission assist pilot participants under strict architectural constraints:

> [!CAUTION]
> **NO EVIDENCE ACCESS FOR SUPPORT**:
> Support personnel cannot read, download, or view confidential case filings, evidence attachments, or consultation recordings.
> 
> Support tickets store only bounded operational metadata (account status, booking IDs, error messages).

---

## 2. Support Case Lifecycle & SLAs

Support tickets follow a rigid progression:
`OPEN` $\to$ `IN_PROGRESS` $\to$ `RESOLVED` $\to$ `CLOSED`

| Severity | Target First Response | Target Resolution | Permitted Resolution Codes |
| :--- | :--- | :--- | :--- |
| **SEV-1 (Critical)** | **$< 15\text{ min}$** | **$< 2\text{ hours}$** | `RESOLVED_HOTFIX_DEPLOYED`, `RESOLVED_CIRCUIT_BREAKER_RESET` |
| **SEV-2 (High)** | **$< 30\text{ min}$** | **$< 4\text{ hours}$** | `RESOLVED_CONFIG_CHANGED`, `RESOLVED_RETRY_TRIGGERED` |
| **SEV-3 (Medium)** | **$< 2\text{ hours}$** | **$< 24\text{ hours}$** | `RESOLVED_EXPLAINED`, `RESOLVED_USER_GUIDED` |
| **SEV-4 (Low)** | **$< 8\text{ hours}$** | **$< 48\text{ hours}$** | `USER_ABANDONED`, `DUPLICATE`, `RESOLVED_FEATURE_PLANNED` |

### Escalation Hierarchy:
- **Tier 1 (Customer Support)**: Account access, billing questions, browser compatibility.
- **Tier 2 (Platform Engineering)**: Video signaling failures, ClamAV upload stalls, webhook retries.
- **Tier 3 (Compliance & Legal)**: Bar Council enrollment disputes, statutory data subject requests.

---

## 3. Structured User Feedback System (Part H)

Pilot feedback submitted via `POST /api/v1/feedback` is categorized and sanitized:

### Feedback Taxonomy:
- `BUG`: Software defect or UI malfunction.
- `USABILITY`: Confusing layout, unclear legal jargon, difficult navigation.
- `FEATURE_REQUEST`: New capability requested by advocate or client.
- `LEGAL_RISK`: Potential advocate-client privilege concern or court procedure mismatch.
- `SECURITY_CONCERN`: Suspected vulnerability or unexpected permission prompt.
- `AI_QUALITY`: Grounding inaccuracy or unhelpful research summary.
- `OPERATIONAL`: Slow advocate response time or payment processing delay.

### Input Sanitization:
- URLs are stripped of query parameters to prevent token leaks.
- Feedback descriptions are defanged before any downstream AI model consumption.
