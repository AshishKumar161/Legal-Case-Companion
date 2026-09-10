# 33 — SUPPORT OPERATIONS & BOUNDARY POLICIES

## 1. Core Principle: Zero-Trust Support Boundaries

Customer support personnel holding the `USER_SUPPORT` operational permission must troubleshoot platform issues under strict least-privilege boundaries:

> [!IMPORTANT]
> **NO ARBITRARY EVIDENCE ACCESS**:
> Support personnel **CANNOT** read, view, or download confidential client legal documents, evidence files, or consultation notes merely to troubleshoot an account.
> 
> Access to confidential evidence requires an explicit, time-limited `EvidenceAccessGrant` issued directly by the case owner or legal process.

---

## 2. Permitted vs Prohibited Support Actions

| Category | Permitted Support Actions (`USER_SUPPORT`) | Strictly Prohibited Actions |
| :--- | :--- | :--- |
| **User Accounts** | View user email, account status, registration date, verification status; trigger verification email resend. | View plain passwords, alter account credentials directly, bypass MFA. |
| **Cases & Matters** | View case title, case status, participant list (names/roles), creation timestamp. | Read private case facts, inspect confidential case notes, modify claims. |
| **Evidence Locker** | Inspect filename, file size, virus scan status (`CLEAN`, `QUARANTINED`), upload timestamp. | Generate presigned download URL, view file contents, delete evidence files. |
| **Consultations** | View scheduled consultation time, participant IDs, payment status, meeting room ID. | Access video call recordings, view advocate's private consultation notes. |
| **Payments** | View Stripe payment ID, amount, timestamp, status (`SUCCEEDED`, `FAILED`). | View raw card details, trigger unauthorized refunds without billing approval. |

---

## 3. Operational Support Playbooks

### Playbook 1: User Account Lockout / Password Reset Assistance
1. Verify user identity via registered phone number or secondary identification.
2. Trigger password reset link dispatch via `/api/v1/auth/forgot-password`.
3. Support never asks for or receives temporary passwords.

### Playbook 2: Bar Council Verification Escalation
1. Lawyer status is `PENDING` or `REJECTED`.
2. Inspect Bar Council ID certificate upload status.
3. If legible and verified against state bar council directory, escalate to Compliance Officer holding `USER_MANAGEMENT` permission for approval via `/api/v1/admin/verifications/{id}/approve`.

### Playbook 3: Video Consultation Disconnection / TURN Traversal
1. Litigant reports "Cannot connect to video call".
2. Check `GET /api/v1/pilot/status` for WebRTC TURN relay health.
3. Advise client to switch off corporate VPN/firewall blocking UDP traffic on port 3478.
4. If room was canceled due to system error, escalate to Billing Operator for credit/reschedule.

### Playbook 4: Evidence Upload Stalled in Quarantine
1. Client reports "Document uploaded but cannot share with lawyer".
2. Check document status: If `QUARANTINED`, ClamAV scan is either in progress or rejected.
3. If ClamAV failed closed, SRE verifies daemon connectivity. Document automatically reactivates upon clean scan completion.
