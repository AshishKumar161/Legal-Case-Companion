# 36 — CONTROLLED PILOT EXECUTION & COHORT PROGRESSION

## 1. Objective & Scope

This document establishes the operational playbook for executing the **Controlled Production Pilot** of Legal Case Companion (LCC). The objective is to validate real-world advocate and litigant workflows under strict, verifiable stage gates rather than relying solely on automated testing.

---

## 2. Multi-Stage Cohort Progression Model (Part Q)

| Stage | Cohort Name | Target Population | Entry Criteria | Exit Criteria | Rollback / Pause Trigger |
| :---: | :--- | :--- | :--- | :--- | :--- |
| **Stage 1** | **Internal & Partner Cohort** | 10 verified advocates, 25 litigants | Pre-screened partner firms in Delhi & NCR; manual allowlist enrollment. | 100% successful consultation test runs; 0 SEV-1/SEV-2 incidents over 7 days. | Any evidence tamper event or auth replay anomaly. |
| **Stage 2** | **Expanded Bar Cohort** | 50 verified advocates, 100 litigants | State Bar Council enrollment verification; active dispute cases. | 80% consultation completion rate; p95 latency $< 500\text{ ms}$; error budget $< 20\%$. | Sustained 5xx spike $> 0.5\%$; ClamAV quarantine backlog $> 5$. |
| **Stage 3** | **Maximum Pilot Capacity** | 100 advocates, 250 litigants | Formal cohort onboarding; regional language pilot testing. | All 6 Public-Launch Gates satisfied; DPA agreements signed. | Error budget consumed $\ge 80\%$; open regulatory inquiry. |
| **Stage 4** | **Public-Launch Review** | Open public onboarding | Full sign-off by Security Lead, SRE Lead, and External Legal Counsel. | Continuous 99.9% availability; automated reconciliation clean. | Automatic revert to Stage 2 upon emergency read-only trip. |

---

## 3. End-to-End User Lifecycle Audit (Part A)

### 3.1 Client Lifecycle Journey
1. **Invitation & Onboarding**: Litigant receives allowlist notification or referral link from enrolled advocate $\to$ registers at `/register` $\to$ verifies email $\to$ profile setup.
2. **Case Creation & Intelligence**: Creates matter $\to$ uploads initial case papers $\to$ system auto-indexes document pages $\to$ reviews chronology and risk factors.
3. **Lawyer Discovery & Booking**: Searches verified advocate directory $\to$ reviews practice areas $\to$ books available consultation slot $\to$ completes payment.
4. **Consultation & Collaboration**: Joins in-app WebRTC video meeting $\to$ provides dual recording consent $\to$ shares exhibits through Evidence Locker.
5. **Feedback & Account Closure**: Submits structured pilot feedback $\to$ optionally executes soft account deletion (`DELETE /auth/account`).

### 3.2 Advocate / Lawyer Lifecycle Journey
1. **Verification & Enrollment**: Submits Bar Council of India enrollment certificate $\to$ compliance operator verifies credentials against state bar directory.
2. **Practice & Availability**: Configures consultation fee, calendar availability slots, and jurisdiction badges.
3. **Matter Management**: Accepts consultation requests $\to$ reviews client evidence under granular access grants $\to$ conducts meeting.
4. **AI-Assisted Workflow**: Queries Copilot with grounded case context $\to$ drafts legal chronologies $\to$ verifies statutory citations before filing.

### 3.3 Operator Control Plane
1. **Allowlist & Governance**: Manages enrollment entries at `/api/v1/pilot/allowlist`.
2. **Support & Escalation**: Resolves client tickets under zero-trust boundaries (no arbitrary evidence access).
3. **Incident Containment**: Toggles `PILOT_GLOBAL_READ_ONLY` or `PILOT_DISABLED_FEATURES` when anomalies are detected.

---

## 4. Pilot Experimentation Framework (Part B)

Experiments are tracked in the database (`pilot_experiments`) and managed via `/api/v1/pilot/experiments`:
- **Hypothesis Formulation**: Every feature variation must define clear success and failure thresholds before rollout.
- **Cohort Scoping**: Experiments are applied only to specific cohorts (`DELHI_BAR_COHORT_A`, `NEW_CLIENTS`).
- **Terminal Decision**: At experiment conclusion, the operator records `GRADUATE_TO_DEFAULT`, `ITERATE`, or `ROLLBACK`.

---

## 5. Phase XX Staged Public Release Controls (Part AA)

To prevent premature exposure before formal external legal sign-off, Phase XX defines strict operational stages:

| Stage | Name | Target Population | Release Controls | Rollback Trigger |
| :--- | :--- | :--- | :--- | :--- |
| **Stage 2** | Controlled Expanded Pilot | 250 clients, 100 advocates | Allowlisted Bar cohorts, strict capacity limits | Error budget $> 20\%$, tamper alert |
| **Stage 3** | Large Verified Cohort | 1,000 clients, 250 advocates | Subject to external counsel sign-off; verified bar intake | Payment anomaly rate $> 1.0\%$ |
| **Stage 4** | Restricted Public Registration | 5,000 clients, 500 advocates | Daily registration caps, anti-bot CAPTCHA | Abuse registration spike $> 100$/hr |
| **Stage 5** | Broader Public Availability | Uncapped throttled | Normal self-registration under full observability | Sustained p95 latency $> 500$ms |
| **Stage 6** | Normal Production Operation | Public production | Standard SLO monitoring, continuous reconciliation | Trip circuit breaker |

Public registration must never advance directly from disabled to unrestricted without progressive staged evaluation.
