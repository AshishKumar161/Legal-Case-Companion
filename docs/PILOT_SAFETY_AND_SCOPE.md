# Legal Case Companion (LCC) — Pilot Safety & Scope Framework

## Executive Summary
This document establishes the operational parameters, risk mitigations, cohort boundaries, and safety protocols for conducting the controlled real-world pilot of **Legal Case Companion (LCC)**.

---

## 1. Pilot Cohort Definition & Access Control
The pilot is restricted strictly to an invite-only cohort:
- **Client Participants**: 20–30 invited clients undergoing real or supervised legal consultations.
- **Lawyer Participants**: 5–10 practicing Advocates verified by State Bar Councils with active bar enrollment IDs.
- **Platform Supervisors**: Designated administrative accounts with audit log monitoring access.
- **Registration Safeguard**: Public self-registration as `ADMIN` is strictly forbidden and rejected at the API boundary (`403 Forbidden`).

---

## 2. Pending Business & Legal Policies

As established by product leadership, arbitrary rules are **not** hard-coded into the codebase. Clear configuration boundaries exist in `app/core/config.py`:

| Policy Area | Configuration Parameter | Pilot Default Value | Status |
| :--- | :--- | :--- | :--- |
| **Document Retention** | `DOCUMENT_RETENTION_DAYS` | `None` (Unenforced) | `PENDING BUSINESS/LEGAL POLICY` |
| **Cancellation & Refunds** | `CANCELLATION_REFUND_POLICY_MODE` | `"PENDING_BUSINESS_DECISION"` | `PENDING BUSINESS/LEGAL POLICY` |

### Policy Integration Hooks:
- **Document Retention**: Automated pruning workers will remain inactive until an explicit retention duration (e.g., 365 days, 7 years, or indefinite with client consent) is legally approved.
- **Cancellation & Refunds**: The cancellation service records all cancellation requests with actor tracking and audit trails without automated fund clawbacks until legal terms of service (e.g., full refund >24h, 50% refund <24h) are ratified.

---

## 3. Security & Data Integrity Protections

The pilot environment operates under strict security invariants validated by automated integration test harnesses:

1. **BOLA / IDOR Defense**:
   - Access to cases, documents, consultations, notes, and video rooms is validated against active tenancy. Unauthorized requests fail closed with `404 Not Found` (revealing no existence indicators).
2. **Document & Malware Security**:
   - Files are stored in private S3 buckets partitioned by case and document UUID (`cases/{case_id}/documents/{doc_id}`).
   - Magic bytes are strictly verified against declared MIME types to prevent content spoofing.
   - Anti-malware scanning operates under a **fail-closed** guarantee: if ClamAV daemon is unreachable, documents remain `QUARANTINED` and cannot be accessed.
3. **WebRTC Video Privacy**:
   - Video room tokens are cryptographically signed using HMAC-SHA256 with user ID, room ID, and expiration timestamps.
   - Room admission enforces early-join (15 mins prior) and late-grace (120 mins post) boundaries.
4. **Authoritative Financial State Transitions**:
   - Payment states transition exclusively via verified Stripe webhook signatures (`payment_intent.succeeded`).
   - Webhook processing is strictly idempotent, preventing double-crediting or duplicate consultation state transitions.

---

## 4. Operational Incident Escalation Matrix

| Severity | Incident Description | Escalation Path | Mitigation Action |
| :--- | :--- | :--- | :--- |
| **SEV-1 (Critical)** | Unauthorized data access, BOLA bypass, or active malware bypass | Engineering Lead & Security Officer | Immediate IP rate-limiting, session revocation, document quarantine freeze |
| **SEV-2 (High)** | Video signaling outage, payment webhook desync, or ClamAV offline | On-call DevOps & Backend Engineer | Restart Coturn/ClamAV containers, execute payment reconciliation playbook |
| **SEV-3 (Medium)** | Email notification delivery delays or minor UI glitches | Product Team | Review SMTP relay logs, queue retry worker |

---

## 5. Scope Boundary Confirmation: AI Subsystem Freeze

In accordance with Phase VIII directives:
- **Zero changes** were made to LLM prompts, reasoning pipelines, RAG retrieval thresholds, legal authority vector indices, or embedding models.
- The AI subsystem remains entirely isolated behind its operational boundary and was not modified.
