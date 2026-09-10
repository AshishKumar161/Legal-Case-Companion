# API Authorization & RBAC Matrix

## Overview
This matrix establishes the authoritative server-side access control baseline for every sensitive endpoint category across Legal Case Companion (LCC). All authorization checks are evaluated and enforced server-side via FastAPI dependencies and domain service boundaries.

---

## 1. Administrative & Governance Endpoints

| Endpoint | HTTP Method | Auth Required | Required Role / Permission | Object Ownership Rule | Expected Unauthorized Status | Automated Test Coverage |
| :--- | :---: | :---: | :--- | :--- | :---: | :--- |
| `/api/v1/admin/overview` | `GET` | Yes | `ADMIN` | Global platform scope | 403 Forbidden | `tests/integration/test_admin_security.py` |
| `/api/v1/admin/users` | `GET` | Yes | `ADMIN` | Global user directory | 403 Forbidden | `tests/integration/test_admin_security.py` |
| `/api/v1/admin/users/{user_id}/suspend` | `POST` | Yes | `ADMIN` | Target user account state | 403 Forbidden | `tests/integration/test_admin_security.py` |
| `/api/v1/admin/users/{user_id}/reactivate` | `POST` | Yes | `ADMIN` | Target user account state | 403 Forbidden | `tests/integration/test_admin_security.py` |
| `/api/v1/admin/operators/{user_id}/permissions` | `POST` / `DELETE` | Yes | Operator: `USER_MANAGEMENT` | Operator hierarchy | 403 Forbidden | `tests/security/test_background_and_admin_red_team.py` |
| `/api/v1/compliance/scorecard` | `GET` | Yes | Operator: `COMPLIANCE_OPERATIONS` | Internal governance | 401 / 403 | `tests/security/test_phase_5_api_security_audit.py` |
| `/api/v1/compliance/items` | `GET` | Yes | Operator: `COMPLIANCE_OPERATIONS` | Internal registry | 403 Forbidden | `tests/security/test_background_and_admin_red_team.py` |

---

## 2. Lawyer Verification Lifecycle Endpoints

| Endpoint | HTTP Method | Auth Required | Required Role / Permission | Object Ownership Rule | Expected Unauthorized Status | Automated Test Coverage |
| :--- | :---: | :---: | :--- | :--- | :---: | :--- |
| `/api/v1/verification/advocate/submit` | `POST` | Yes | `LAWYER` | Current advocate profile | 403 Forbidden | `tests/integration/test_advocate_verification_lifecycle.py` |
| `/api/v1/verification/advocate/status` | `GET` | Yes | `LAWYER` | Current advocate draft/dossier | 403 Forbidden | `tests/integration/test_advocate_verification_lifecycle.py` |
| `/api/v1/verification/admin/queue` | `GET` | Yes | `ADMIN` | Review queue access | 403 Forbidden | `tests/security/test_phase_5_api_security_audit.py` |
| `/api/v1/verification/{verification_id}` | `GET` | Yes | `ADMIN` or Owner `LAWYER` | Verification record owner | 403 / 404 | `tests/integration/test_advocate_verification_lifecycle.py` |
| `/api/v1/verification/admin/{id}/start-review` | `POST` | Yes | `ADMIN` | Self-review blocked | 403 Forbidden | `tests/security/test_phase_5_api_security_audit.py` |
| `/api/v1/verification/admin/{id}/approve` | `POST` | Yes | `ADMIN` | Self-approval blocked | 403 Forbidden | `tests/security/test_phase_5_api_security_audit.py` |
| `/api/v1/verification/admin/{id}/reject` | `POST` | Yes | `ADMIN` | Reviewer assignment | 403 Forbidden | `tests/security/test_phase_5_api_security_audit.py` |
| `/api/v1/verification/admin/{id}/revoke` | `POST` | Yes | `ADMIN` | Formal revocation | 403 Forbidden | `tests/integration/test_advocate_verification_lifecycle.py` |
| `/api/v1/verification/advocate/{lawyer_id}/badge` | `GET` | No | Public (BCI Rule 36) | Public verified registry | None (Public) | `tests/integration/test_advocate_verification_lifecycle.py` |

---

## 3. Case, Document & Evidence Endpoints

| Endpoint | HTTP Method | Auth Required | Required Role / Permission | Object Ownership Rule | Expected Unauthorized Status | Automated Test Coverage |
| :--- | :---: | :---: | :--- | :--- | :---: | :--- |
| `/api/v1/cases` | `GET` | Yes | Authenticated (`CLIENT`, `LAWYER`, `ADMIN`) | Filtered to active participant cases | 401 Unauthorized | `tests/security/test_authorization_and_bola_red_team.py` |
| `/api/v1/cases` | `POST` | Yes | `CLIENT`, `LAWYER`, `ADMIN` | Creator becomes case owner | 401 Unauthorized | `tests/integration/test_cases.py` |
| `/api/v1/cases/{case_id}` | `GET` | Yes | Active Participant / `ADMIN` | 404 Masking for non-participants | 404 Not Found | `tests/security/test_authorization_and_bola_red_team.py` |
| `/api/v1/cases/{case_id}` | `PATCH` | Yes | Case Owner / Counsel / `ADMIN` | Non-collaborator mutation rejected | 403 Forbidden | `tests/security/test_authorization_and_bola_red_team.py` |
| `/api/v1/cases/{case_id}/documents` | `POST` | Yes | Active Participant / `ADMIN` | Closed case upload blocked | 403 / 422 | `tests/security/test_document_and_storage_red_team.py` |
| `/api/v1/cases/{case_id}/documents/{document_id}/download-url` | `GET` | Yes | Active Participant / `ADMIN` | Document membership verification | 403 / 404 | `tests/security/test_document_and_storage_red_team.py` |
| `/api/v1/cases/{case_id}/evidence` | `GET` / `POST` | Yes | Active Participant / `ADMIN` | Custody log provenance | 403 Forbidden | `tests/security/test_evidence_authorization_and_idor.py` |
| `/api/v1/cases/{case_id}/bundles` | `GET` / `POST` | Yes | Case Owner / Counsel / `ADMIN` | Evidence compilation boundary | 403 Forbidden | `tests/integration/test_bundles.py` |

---

## 4. Consultations & Real-Time Media Endpoints

| Endpoint | HTTP Method | Auth Required | Required Role / Permission | Object Ownership Rule | Expected Unauthorized Status | Automated Test Coverage |
| :--- | :---: | :---: | :--- | :--- | :---: | :--- |
| `/api/v1/consultations/request` | `POST` | Yes | `CLIENT` | Client profile required | 403 Forbidden | `tests/test_instant_consultation_flow.py` |
| `/api/v1/consultations/{id}` | `GET` | Yes | Participant (`CLIENT`, `LAWYER`) or `ADMIN` | Third-party isolation | 403 Forbidden | `tests/integration/test_consultations_complete.py` |
| `/api/v1/consultations/{id}/accept` | `POST` | Yes | Assigned `LAWYER` | Reassigned lawyer blocked | 403 Forbidden | `tests/test_instant_consultation_flow.py` |
| `/api/v1/consultations/{id}/pay-test` | `POST` | Yes | `CLIENT` / `ADMIN` (Dev/Test Only) | Gated in staging/production | 403 Forbidden | `tests/security/test_phase_5_api_security_audit.py` |
| `/api/v1/consultations/{id}/video/room` | `GET` | Yes | Consultation Participant | Room provisioned only when PAID | 403 Forbidden | `tests/integration/test_native_video_and_recording_pipeline.py` |
| `/api/v1/consultations/{id}/video/ws` | `WS` | Yes | Cryptographic Video Token | Room & consultation context binding | WS Policy Violation (1008) | `tests/integration/test_native_video_and_recording_pipeline.py` |
| `/api/v1/consultations/ws/incoming-calls` | `WS` | Yes | Verified `LAWYER` (Single-Use Ticket) | Active lawyer profile required | WS Policy Violation (1008) | `tests/integration/test_presence_and_realtime_calls.py` |
| `/api/v1/recordings/{id}/playback-ticket` | `POST` | Yes | Consultation Participant | Ephemeral 60s ticket | 403 Forbidden | `tests/integration/test_native_video_and_recording_pipeline.py` |

---

## 5. Commercial, Payments & Invoices

| Endpoint | HTTP Method | Auth Required | Required Role / Permission | Object Ownership Rule | Expected Unauthorized Status | Automated Test Coverage |
| :--- | :---: | :---: | :--- | :--- | :---: | :--- |
| `/api/v1/commercial/transactions/{id}` | `GET` | Yes | Payer, Payee, or `ADMIN` | Third party cannot read details | 403 Forbidden | `tests/pilot/test_phase_10_commercial_operations.py` |
| `/api/v1/commercial/invoices/{id}/receipt` | `GET` | Yes | Payer, Payee, or `ADMIN` | Third party cannot generate receipt | 403 Forbidden | `tests/security/test_phase_5_api_security_audit.py` |
| `/api/v1/commercial/payouts/process` | `POST` | Yes | `ADMIN` | Formal escrow release | 403 Forbidden | `tests/pilot/test_phase_10_commercial_operations.py` |
| `/api/v1/commercial/settlement/reconciliation` | `GET` | Yes | `ADMIN` | Platform ledger | 403 Forbidden | `tests/pilot/test_phase_10_commercial_operations.py` |
| `/api/v1/webhooks/stripe` | `POST` | No (Signature Verified) | Valid HMAC Webhook Signature | Idempotent event ID deduplication | 400 / 401 | `tests/security/test_phase_7_6_production_security.py` |

---

## 6. Calendar & Unified Projections

| Endpoint | HTTP Method | Auth Required | Required Role / Permission | Object Ownership Rule | Expected Unauthorized Status | Automated Test Coverage |
| :--- | :---: | :---: | :--- | :--- | :---: | :--- |
| `/api/v1/calendar/events` | `GET` | Yes | Authenticated User | Scoped strictly to caller's cases & tasks | 401 Unauthorized | `tests/security/test_phase_5_api_security_audit.py` |
| `/api/v1/attention/cases` | `GET` | Yes | Authenticated User | Scoped strictly to caller's cases | 401 Unauthorized | `tests/integration/test_lawyer_operational_dashboard.py` |