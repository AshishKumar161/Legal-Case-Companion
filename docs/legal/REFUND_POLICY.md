# Legal Case Companion (LCC) - Deterministic Refund Policy

**Effective Date:** September 5, 2026  
**Applicable Service:** Consultation Bookings & Platform Facilitation Fees

---

## 1. Principles of Deterministic Refunds
LCC enforces deterministic, server-authoritative refund rules to ensure total financial transparency for litigants and fair treatment of practicing advocates. All refunds are reconciled against primary payment gateway transactions.

---

## 2. Refund Matrix & Eligibility

| Cancellation / Failure Reason | Timing Window | Refund Entitlement | Advocate Payout Status |
| :--- | :--- | :--- | :--- |
| **Client Voluntary Cancellation** | > 24 hours prior to session | **100% Full Refund** (Gross + GST) | Nullified / No Payout |
| **Client Late Cancellation** | < 24 hours prior to session | **50% Partial Refund** | 50% Advocate Retention Fee |
| **Advocate Cancellation** | Any time prior to session | **100% Full Refund** | Nullified / No Payout |
| **Advocate No-Show** | Advocate fails to join within 10 min | **100% Full Refund** + Priority Rebook | Zero Payout + Quality Flag |
| **Platform Technical Failure** | WebRTC video/audio loss > 5 min | **100% Full Refund** | Reviewed for Platform Reimbursement |
| **Duplicate Payment** | Within 48 hours of transaction | **100% Immediate Refund** | Adjusted against original invoice |

---

## 3. Double-Refund & Double-Payout Safeguards
Under Phase 10 server-authoritative financial rules:
1. Every refund creates an immutable `RefundRecord` linked to the primary `CommercialTransaction`.
2. Transactions in `REFUNDED` status are cryptographically locked; subsequent refund requests are rejected with `TRANSACTION_ALREADY_REFUNDED`.
3. If an advocate payout was already settled prior to a dispute, an `adjustment_required` flag is raised in the settlement ledger to deduct the amount from subsequent advocate disbursements.

---

## 4. Processing Timelines & Disbursement
* Approved refunds are initiated immediately via our payment provider (Razorpay / Cashfree).
* Funds typically reflect in the original payment method (UPI / Net Banking / Card) within **5 to 7 business days**, subject to banking network settlement cycles.
* Official refund receipts are issued with unique reference IDs for tracking with the issuing bank.
