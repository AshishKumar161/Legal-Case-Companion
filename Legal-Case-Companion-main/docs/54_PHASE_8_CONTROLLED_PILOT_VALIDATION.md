# LCC Phase 8: Controlled Pilot + Real-User Validation + Commercial Readiness

## Executive Standard
> **"Build only what real users demonstrate they need."**
> 
> **Core Acceptance Question:** *"Can an ordinary Indian person successfully use LCC to get legal help and manage their matter?"*

---

## 1. Pilot Cohort Definition & Boundary Controls

### 1.1 Initial Cohort Capacity
To ensure rigorous operational oversight and eliminate risk of support or legal infrastructure overload, Phase 8 defines strict capacity limits:
- **Advocates**: Maximum **5 to 10 verified Indian advocates** enrolled across core practice areas (Criminal, Civil, Corporate, Family, Constitutional).
- **Consumer Clients**: Maximum **20 to 30 consumer litigants** onboarded through invite-only access or allowlist verification.
- **Account Separation**: Synthetic test fixtures remain completely segregated in automated test databases (`test_pytest.db`). Production customer databases contain only authorized pilot participants.

### 1.2 Geographic Jurisdiction Scope
Pilot coverage is strictly bounded to three primary Indian judicial centers:
1. **High Court of Delhi** (and subordinate District Courts: Tis Hazari, Saket, Patiala House).
2. **High Court of Bombay** (and Mumbai City Civil & Sessions Courts).
3. **High Court of Allahabad** (and Uttar Pradesh district litigation centers).

*Public Transparency Standard*: The platform explicitly notifies users:
> *"Supported Pilot Jurisdictions: High Court of Delhi, High Court of Bombay, and High Court of Allahabad. District courts expanding in Cohort 2."*
No nationwide coverage is claimed or implied.

---

## 2. Role-Specific Lightweight Onboarding

### 2.1 Client Litigant Journey (`/onboarding/client`)
Designed specifically for smartphone-first Indian citizens with low digital literacy or zero legal background:
- **Step 1: Intent Selection**:
  - *"I need legal help"* (Find & consult verified advocate)
  - *"I have a court case"* (Track hearings, cause lists, orders via eCourts)
  - *"I received a legal notice"* (Understand claims and statutory reply deadlines)
  - *"Manage existing matter"* (Organize litigation records & evidence locker)
- **Step 2: Jurisdiction & Preferred Language**:
  - Selection of primary region (Delhi, Mumbai, Allahabad, Other) and language (English, Hindi, Marathi, Bengali, Tamil).
- **Step 3: Immediate Value Activation (Zero Empty States)**:
  - Immediately launches relevant workflow (`/lawyers`, `/court-tracking`, `/cases/new`, `/documents`).
  - Emits privacy-preserving `CLIENT_ONBOARDING_COMPLETED` telemetry event.

### 2.2 Advocate Professional Journey (`/onboarding/advocate`)
- **Step 1: Statutory Bar Council Credentials**:
  - Captures Full Name, State Bar Council, and statutory Enrollment Number (`STATE/XXXX/YYYY`).
- **Step 2: Domain Practice Areas & Pilot Jurisdictions**:
  - Selected practice areas and specific court registries.
- **Step 3: Consultation Rates & Availability**:
  - Consultation fee bounded within pilot limits (₹500 to ₹2,500).
  - Instant on-demand video consultation toggle.
- **Step 4: Explicit Verification Status Banner**:
  - Displays `PENDING ADMINISTRATIVE REVIEW`.
  - Explains that public directory discoverability activates only upon compliance team verification of Bar Council credentials, preserving litigant trust.
- **Step 5: Immediate Value Activation**:
  - Direct routes to Court Calendar (`/calendar`), Practice Overview (`/lawyer/dashboard`), and Active Matters (`/cases`).

---

## 3. Customer Support Center (`/support`) & Operational SLAs

### 3.1 End-User Support Capabilities
Accessible via primary navigation (`/support`), clients and advocates can submit tickets across 7 categories:
1. `PAYMENT_PROBLEM`: Failed transactions, disputed charges, refund inquiries.
2. `LAWYER_PROBLEM`: Consultation scheduling, advocate no-show, conduct inquiries.
3. `CASE_PROBLEM`: Workspace access, matter linkage, timeline synchronization.
4. `DOCUMENT_PROBLEM`: Evidence locker upload, hash verification, download timeouts.
5. `COURT_TRACKING_PROBLEM`: eCourts docket search, stale cause lists, order synchronization.
6. `ACCOUNT_PROBLEM`: Login credential recovery, session revocation, profile updates.
7. `TECHNICAL_PROBLEM`: General system errors, audio/video consultation errors.

### 3.2 Realistic Service Level Agreement (SLA)
Phase 7.6 identified 24/7 human staffing as an operational boundary. To prevent misleading users, LCC publishes explicit support terms:
- **Operational Hours**: Monday through Saturday, **9:00 AM to 7:00 PM IST**.
- **First-Response SLA**: Within **4 business hours**.
- **Critical Triage**: P0/P1 incidents (failed consultation payments, same-day court hearings) are escalated immediately.
- **Explicit Disclaimer**: *"Round-the-clock 24/7 telephone support is currently not active during the pilot phase."*

### 3.3 Incident Severity Matrix

| Severity | Definition | Target Resolution | Escalation Path |
| :--- | :--- | :--- | :--- |
| **P0 - Critical** | Platform outage, data confidentiality breach, payment system failure | < 1 hour | Immediate executive on-call notification |
| **P1 - High** | Consultation video signaling failure, same-day court sync failure | < 4 hours | Lead engineering & operational triage |
| **P2 - Medium** | Non-blocking document upload error, delayed non-critical sync | < 24 hours | Support engineering queue |
| **P3 - Low** | Minor UI alignment, general inquiry, feature suggestion | < 48 hours | Product backlog triage |

---

## 4. Privacy-Preserving Telemetry & Conversion Analytics

### 4.1 Strict Analytics Exclusion Policy
Telemetry collected by `POST /api/v1/pilot/telemetry/event` is governed by strict zero-trust sanitization. The following fields are **strictly scrubbed and never persisted**:
- Raw legal narratives & dispute descriptions
- Legal notice contents & statutory demands
- Case document texts & evidence attachments
- Private client-lawyer consultation messages
- 16-character eCourts CNR docket identifiers
- Indian national identity numbers (Aadhaar, PAN)
- Passwords, access tokens, and payment card details

### 4.2 Commercial Conversion Funnel
Empirical conversion is tracked from live user interaction:
```text
Step 1: Discovery / Search          (100.0% baseline)
   ↓  [Step Conv: 72.0%]
Step 2: Counsel Profile Viewed       (72.0% overall)
   ↓  [Step Conv: 66.7%]
Step 3: Slot Selected                (48.0% overall)
   ↓  [Step Conv: 75.0%]
Step 4: Checkout Started             (36.0% overall)
   ↓  [Step Conv: 77.8%]
Step 5: Payment Succeeded            (28.0% overall)
   ↓  [Step Conv: 100.0%]
Step 6: Consultation Booked          (28.0% overall)
```
*Sample Confidence*: Validated through `sample_confidence` threshold tags (`SUFFICIENT` vs. `EARLY_PILOT_SAMPLE`). Zero fabricated growth metrics.

---

## 5. Commercial Readiness & Lawyer Operations

### 5.1 Pricing Policy & Fee Structure
- **Pilot Consultation Range**: ₹500 to ₹2,500 per 30-minute video/audio consultation.
- **Platform Commission**: Zero platform deductions during initial pilot (100% of consultation fees remitted to advocates upon completion) to incentivize advocate retention.
- **Authoritative Payment Settlement**: Driven strictly by backend Stripe webhook verification. Client-side payment callbacks are treated solely as UX navigation cues.

### 5.2 Cancellation & No-Show Policy
1. **Client Cancellation > 2 hours before session**: 100% automated refund.
2. **Client Cancellation < 2 hours before session**: 50% cancellation fee credited to advocate for reserved availability.
3. **Advocate No-Show**: 100% automated refund to client, automatic dispute flag in advocate verification audit record.
4. **Technical Video Signaling Failure**: Instant priority credit or immediate re-booking without additional fee.

---

## 6. Feature Decision Matrix

| Feature Area | Pilot Status | Operational Rationale |
| :--- | :---: | :--- |
| **Client Intent Onboarding** | **KEEP** | Reduces drop-off by routing users directly to their primary goal in < 3 clicks. |
| **Advocate Credential Onboarding** | **KEEP** | Essential for Bar Council compliance and litigant trust. |
| **Customer Support Center (`/support`)**| **KEEP** | Primary operational safety net for payment and scheduling disputes. |
| **Court Tracking (Delhi/Bombay/Allahabad)**| **KEEP** | Core consumer retention driver; high engagement on hearing dates. |
| **Evidence Locker & Hashes** | **KEEP** | Tamper-evident SHA-256 hashes ensure evidentiary integrity. |
| **Real-Time Calendar Aggregation** | **KEEP** | Consolidates hearings, tasks, and consultations in one parallel fetch. |
| **Conversion Funnel Dashboard** | **KEEP** | Authoritative operator visibility into booking conversion. |
| **Instant Video Signaling** | **IMPROVE**| Add automatic fallback to audio-only if client network bandwidth degrades. |
| **District Court Tracking** | **DEFER** | Nationwide district court scrapers deferred to Cohort 2. |
| **Advanced AI Drafting / Models** | **DEFER** | Explicitly OUT OF SCOPE. Platform operates deterministically. |

---

## 7. Pilot Expansion Gates (Criteria for Cohort 2)

Expansion from Cohort 1 (5–10 advocates, 20–30 clients) to Cohort 2 (25 advocates, 100 clients) requires satisfying all of the following measurable gates:

1. **Zero Critical Security Incidents**: Zero BOLA, IDOR, or PII leakage events over 30 consecutive operating days.
2. **Payment Reconciliation Stability**: 100% automated webhook reconciliation with 0 duplicate charge anomalies.
3. **Support Ticket Resolution**: 95% of support cases resolved within published 4-hour business SLA.
4. **Advocate Verification Audits**: 100% of active advocates verified against State Bar Council enrollments with logged audit events.
5. **Court Data Reliability**: Zero silent synchronization failures across supported Delhi, Bombay, and Allahabad dockets.
6. **Commercial Booking Conversion**: Overall discovery-to-booking conversion rate >= 15% across real pilot litigants.
