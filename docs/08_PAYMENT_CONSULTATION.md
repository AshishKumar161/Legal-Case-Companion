STATUS: IMPLEMENTED (BACKEND V3)

AUTHORITY: DERIVED FROM PROJECT SOURCE OF TRUTH

SOURCE DOCUMENTS:
- docs/00_PROJECT_CONTEXT.md
- docs/01_SYSTEM_ARCHITECTURE.md
- docs/02_DATABASE_DESIGN.md
- docs/03_API_SPECIFICATION.md
- docs/04_AUTHORIZATION_SECURITY.md
- docs/05_BACKEND_MODULES.md
- docs/06_AI_INTEGRATION.md
- docs/07_FILE_DOCUMENT_SYSTEM.md

IMPLEMENTATION STATUS: IMPLEMENTED (Backend V3 Core Workflow)

RULE:
PAYMENT AND CONSULTATION LOGIC MUST NOT INVENT BUSINESS RULES

# Payment and Consultation Specification

## 1. PURPOSE
This document defines the technical architecture surrounding the core professional interaction flow of the platform:
Client → Lawyer → Consultation → Payment where applicable → Ongoing case interaction.
It ensures that scheduling, professional engagement, and financial transactions are handled securely, consistently, and without inventing unauthorized business rules.

## 2. CONSULTATION LIFECYCLE & STATE MACHINE
The consultation lifecycle is enforced by `ConsultationService` and governed by the following state machine:

```text
REQUESTED
   ├── Lawyer Accept  → ACCEPTED
   ├── Lawyer Reject  → REJECTED
   └── Client Cancel  → CANCELLED

ACCEPTED
   ├── Payment Intent & Webhook Confirmation → PAID
   ├── Schedule / Reschedule                 → SCHEDULED
   └── Cancel                                → CANCELLED

PAID
   ├── Lawyer Confirm / Schedule             → SCHEDULED
   └── Cancel                                → CANCELLED

SCHEDULED
   ├── Start Session                         → IN_PROGRESS
   ├── Complete Session                      → COMPLETED
   └── Cancel                                → CANCELLED

COMPLETED, CANCELLED, REJECTED (Terminal States)
```

## 3. CONSULTATION ACTORS
- **CLIENT**: Discovers lawyers, requests consultations, makes payments, and attends consultations.
- **LAWYER**: Sets availability, accepts/rejects/conducts consultations, and establishes case relationships.
- **ADMIN**: Resolves disputes, reviews lawyer verifications, and handles platform-level interventions.
- **SYSTEM**: Processes asynchronous tasks (Stripe webhooks, audit events, case timeline events).
- **PAYMENT PROVIDER**: External service (Stripe / Mock) handling secure financial transactions.

## 4. CONSULTATION FLOW
Implemented flow:
1. Client searches/filters lawyers (`GET /api/v1/lawyers`).
2. Client views lawyer public profile (`GET /api/v1/lawyers/{user_id}`).
3. Client requests consultation (`POST /api/v1/consultations` or `POST /api/v1/cases/{case_id}/consultations`).
4. Lawyer accepts (`POST /api/v1/consultations/{id}/accept`) or rejects (`POST /api/v1/consultations/{id}/reject`).
5. For paid consultations: Client initiates payment (`POST /api/v1/consultations/{id}/payments`), completed via Stripe webhook (`POST /api/v1/payments/webhooks/stripe`).
6. Consultation scheduled (`POST /api/v1/consultations/{id}/schedule` or `/confirm`).
7. Consultation conducted and completed (`POST /api/v1/consultations/{id}/complete`), timestamping `completed_at`.

## 5. APPOINTMENT FLOW
Conceptual scheduling flow:
Lawyer availability → Selected time → Appointment request → Appointment confirmation → Consultation occurrence.

The following business rules remain UNDEFINED:
- slot duration
- cancellation window
- timezone rules
- maximum bookings
- rescheduling limits
STATUS: DECISION REQUIRED.

## 6. LAWYER AVAILABILITY
Consultation scheduling must fundamentally rely on lawyer availability information. The architecture requires that bookings cannot bypass availability constraints unless overridden by an explicit administrative or lawyer action.
(Availability constraints map to the `LawyerProfile` or related scheduling entities as defined in `docs/02_DATABASE_DESIGN.md`).

## 7. PAYMENT ARCHITECTURE (BACKEND V4)
The payment architecture strictly enforces that the backend is the absolute authority for application-level payment state.
Operational flow:
1. Client requests payment creation (`POST /api/v1/consultations/{consultation_id}/payments`).
2. Backend verifies client ownership, consultation validity, and payable status (`REQUESTED`, `ACCEPTED`).
3. Backend determines the fee amount from `consultation.fee_amount` and currency from `consultation.currency`. Client-submitted amounts are rejected.
4. Idempotency: If an active payment (`CREATED`, `PENDING`) already exists for the consultation, the existing payment intent is returned without creating duplicates.
5. Provider integration creates `PaymentIntent` via `StripePaymentProvider` (production) or `MockPaymentProvider` (development/test).
6. Payment recorded with status `CREATED`.
7. External payment provider sends webhook (`POST /api/v1/payments/webhooks/stripe`) with cryptographic `Stripe-Signature`.
8. Backend verifies webhook signature, tracks webhook lifecycle, and transitions payment status to `SUCCEEDED` (or `FAILED`).
9. On success, consultation status transitions to `PAID`, and `PAYMENT_CONFIRMED` case timeline event is recorded.
10. Webhook duplicate deliveries are handled idempotently (`already_processed`).

The system MUST NOT trust only the frontend payment result to confirm a booking.

## 8. PAYMENT PROVIDER
- Provider: Stripe (`StripePaymentProvider`) with mock fallback (`MockPaymentProvider`).
- Webhook endpoint: `/api/v1/payments/webhooks/stripe` protected with `Stripe-Signature` cryptographic header.

## 9. PAYMENT DATA & SCHEMA
- **id**: UUID (PK, UUIDv7)
- **consultation_id**: UUID (FK -> Consultation.id, RESTRICT)
- **payer_user_id**: UUID (FK -> User.id, RESTRICT)
- **amount**: Numeric (Server authoritative)
- **currency**: String (e.g., "INR")
- **status**: Enum (`CREATED`, `PENDING`, `SUCCEEDED`, `FAILED`, `REFUNDED`)
- **provider**: String ("stripe" / "mock")
- **provider_payment_id**: String (Unique, Indexed)
- **created_at**, **updated_at**: DateTime with timezone.

## 10. PAYMENT CREDENTIALS & PRIVACY
- System never accepts, stores, or logs sensitive credentials (card numbers, CVVs, API secrets, webhook secret tokens).
- Public/client payment response models expose only safe fields: `id`, `consultation_id`, `payer_user_id`, `amount`, `currency`, `status`, `provider`, `created_at`.

## 11. PAYMENT VERIFICATION & AUDIT LOGGING
Standardized audit events emitted during financial workflows:
- `PAYMENT_CREATED`: Emitted upon payment intent initialization.
- `PAYMENT_SUCCEEDED`: Emitted upon verified successful webhook processing.
- `PAYMENT_FAILED`: Emitted upon verified failed payment webhook.
- `WEBHOOK_RECEIVED`: Emitted upon incoming provider webhook.
- `WEBHOOK_PROCESSED`: Emitted upon completed webhook execution.
The backend MUST NOT trust:
- frontend success flags.
- client-submitted payment status.
- client-submitted transaction completion claims.

## 12. WEBHOOKS / CALLBACKS
Payment provider callbacks/webhooks are necessary for asynchronous payment confirmation.
The architecture must account for:
- asynchronous payment confirmation (user closes browser before redirect).
- duplicate webhook delivery (idempotency required).
- out-of-order events (e.g., `payment.failed` arriving after `payment.success`).
- invalid events (forged requests).
- replay concerns.
- signature verification (cryptographic validation of payload).

Exact webhook design and schemas: DECISION REQUIRED.

## 13. IDEMPOTENCY
CRITICAL: Payment and booking operations must avoid creating duplicate records when the same request is retried (e.g., due to network timeouts).
Idempotency must be implemented for:
- payment creation (avoid double charging).
- booking creation (avoid double booking a slot).
- payment confirmation.
- webhook processing.

## 14. PAYMENT STATES
Exact payment states are not defined in the source documents.
STATUS: DECISION REQUIRED.
Conceptually, the system needs to distinguish:
- payment initiated
- payment confirmed (success)
- payment failed
- payment uncertain (pending/processing)

## 15. BOOKING CONSISTENCY
The architecture must ensure consistency between the Appointment, Payment, and Consultation.
Failure scenarios to reason about:
- **Payment succeeds BUT booking update fails**: The system must log the orphaned payment and alert admins, or automatically retry the booking update.
- **Booking created BUT payment fails**: The booking must eventually expire or be released back to availability.
- **Webhook arrives twice**: Idempotency must silently acknowledge the second webhook without altering state twice.
- **Webhook arrives late**: State transitions must respect a terminal state (don't fail a booking that was already manually confirmed).
- **External provider times out**: The system must place the booking in a pending state until verified.

## 16. TRANSACTION BOUNDARIES
Operations that may need database-level transactional consistency:
- creating a booking and blocking the availability slot simultaneously.
- recording a payment result and updating the related consultation status.
- associating a payment entity with a consultation entity.

## 17. PAYMENT FAILURE
When a payment fails (declined, provider unavailable, timeout, duplicate request, verification failure):
- The client-facing system must not claim payment success.
- The associated consultation must not proceed to a confirmed state.
- The user should be prompted to retry.

## 18. UNKNOWN PAYMENT STATE
If the payment provider returns an ambiguous or unavailable result:
- DO NOT assume failure.
- DO NOT assume success.
The system should represent the uncertainty internally (e.g., "Pending Verification") and determine the final state asynchronously via webhooks or background polling against the trusted provider API.

## 19. REFUNDS
The current project context does not explicitly define a refund policy.
STATUS: DECISION REQUIRED
The architecture does not currently invent refund windows, rules, cancellation percentages, or automatic refund behavior.

## 20. CANCELLATION
Consultation cancellation rules are not defined in the source context.
STATUS: DECISION REQUIRED
(Cancellation period, fees, refund policy, and no-show policy are unwritten).

## 21. RESCHEDULING
Consultation rescheduling rules are not explicitly defined.
STATUS: DECISION REQUIRED.

## 22. NO-SHOW
Behavior for client or lawyer no-shows is undefined.
STATUS: DECISION REQUIRED.

## 23. CONSULTATION ACCESS
Access to consultation information is strictly limited:
- the client involved in the consultation.
- the lawyer involved in the consultation.
- admin (only where explicitly authorized via admin workflows).
Universal access to consultations is forbidden.

## 24. CASE ASSOCIATION
The conceptual relationship is derived from the database design:
Client → Consultation → Lawyer.
Consultation → Case.
A consultation can lead to a case, or belong to an existing case. The exact cardinality (1:1, 1:N) aligns with `docs/02_DATABASE_DESIGN.md`.

## 25. CONSULTATION NOTES
Whether consultation notes are part of the current project requirements is undefined.
STATUS: DECISION REQUIRED.

## 26. VIDEO CONSULTATION
The project context mentions online/offline consultations.
Architectural boundary: Application → Consultation Service → External Video Provider.
Video Provider: DECISION REQUIRED.
(Meeting URL behavior, recording, transcription, and retention are NOT invented here).

## 27. PAYMENT WEBHOOK SECURITY
High-level security requirements for webhooks:
- verify provider authenticity (via whitelisted IPs if applicable).
- verify cryptographic signatures (e.g., HMAC-SHA256).
- prevent replay attacks (checking webhook event IDs).
- validate payload structure.
- reject forged callbacks immediately with a 400/401.
- make processing idempotent.
- record relevant audit information.

## 28. PAYMENT AUDITING
Actions requiring auditability:
- payment initiation
- payment confirmation
- payment failure
- webhook processing
- refund action (if eventually supported)
- admin intervention in payment state

## 29. PAYMENT LOGGING
System logs must NEVER contain:
- card numbers or CVVs.
- payment credentials.
- secret keys (API secrets).
- authentication tokens.
- sensitive legal information passed during the booking.

## 30. CONSULTATION NOTIFICATIONS
Notification rules (e.g., booking request, confirmation, payment result, appointment reminder, cancellation, consultation update) are not defined.
STATUS: DECISION REQUIRED.

## 31. EXTERNAL SERVICE FAILURE
When external providers (Payment, Video, Notification) fail, the system should isolate the failure. Unrelated application functionality (e.g., viewing past cases, uploading documents) must continue to function normally.

## 32. SECURITY BOUNDARIES
Trust boundaries:
`Client ↓ Backend (Authoritative) ↓ Payment Provider`
`Client ↓ Backend (Authoritative) ↓ Video Provider`
The backend strictly mediates these integrations and remains responsible for all application-level authorization and state changes.

## 33. PAYMENT API BOUNDARY
The API exposes application-level payment operations (e.g., `/consultations/{id}/pay`).
- It does NOT expose raw provider credentials to clients.
- It does NOT allow the client to directly `PUT` a payment status to `success` without backend validation.

## 34. PAYMENT / CONSULTATION DATA OWNERSHIP
- Client can access their own consultation/payment information.
- Lawyer can access consultation information where they are the assigned professional.
- Administrative access must be explicitly authorized.

## 35. PAYMENT DECISION REGISTER

| Decision | Status | Reason | Source | Impact |
|---|---|---|---|---|
| Payment Provider | PROPOSED: Stripe (DECISION REQUIRED) | India constraints | Docs | Integration logic |
| Payment States | DECISION REQUIRED | Not finalized | Docs | DB Schema / Logic |
| Webhook Strategy | DECISION REQUIRED | Not finalized | Docs | Async processing |
| Refund Policy | DECISION REQUIRED | Not finalized | Docs | Financial ops |
| Cancellation Policy | DECISION REQUIRED | Not finalized | Docs | Business ops |
| Rescheduling Policy | DECISION REQUIRED | Not finalized | Docs | Business ops |
| Currency / Pricing | DECISION REQUIRED | Not finalized | Docs | Business logic |
| Idempotency Design | DECISION REQUIRED | Not finalized | Docs | API / DB consistency |

## 36. CONSULTATION DECISION REGISTER

| Decision | Status | Reason | Source | Impact |
|---|---|---|---|---|
| Appointment vs Consult States | DECISION REQUIRED | Not finalized | Docs | Lifecycle logic |
| Scheduling Rules / Slots | DECISION REQUIRED | Not finalized | Docs | Booking UX |
| Lawyer Availability Model | DECISION REQUIRED | Not finalized | Docs | DB queries |
| Video Provider | DECISION REQUIRED | Not finalized | Docs | Third-party int. |
| No-Show Policy | DECISION REQUIRED | Not finalized | Docs | Business logic |
| Consultation Notes | DECISION REQUIRED | Not finalized | Docs | Feature scope |

## 37. TRACEABILITY

| Requirement | Source Document | Source Section | Status | Implementation Impact |
|---|---|---|---|---|
| Consultation booking | 00_PROJECT_CONTEXT.md | Known Product Flow | KNOWN | Core feature |
| Payment for consultation | 00_PROJECT_CONTEXT.md | Known Product Flow | KNOWN | Payment integration |
| Lawyer availability | 02_DATABASE_DESIGN.md | Entity Relationships | KNOWN | Scheduling logic |
| Payment backend authority | 04_AUTHORIZATION_SECURITY.md | 29. Payment Security | KNOWN | Verification logic |

## 38. FAILURE SCENARIO MATRIX

| Scenario | Possible Cause | Expected System Principle | State | Recovery Requirement | Status |
|---|---|---|---|---|---|
| Payment success but booking update fails | DB lock/crash | Eventual consistency | Orphaned | Manual/Auto reconciliation | DECISION REQUIRED |
| Payment failure | Insufficient funds | Do not confirm | Failed | Prompt retry | KNOWN |
| Unknown payment result | Timeout | Await provider truth | Pending | Webhook/Polling | KNOWN |
| Duplicate webhook | Network retry | Idempotency | Confirmed | Ignore safely | KNOWN |
| Forged webhook | Attacker | Reject invalid signature | Unchanged | Log security event | KNOWN |
| Provider timeout | Provider down | Isolate failure | Pending | Retry later | KNOWN |
| Booking conflict | Race condition | DB Constraints | Failed | Reject second booking | KNOWN |

## 39. SECURITY RISKS
- forged payment confirmation (client bypassing payment gateway).
- duplicate payment (lack of idempotency leading to double charges).
- duplicate booking (race conditions in scheduling).
- unauthorized consultation access (IDOR vulnerabilities).
- webhook replay (attackers re-sending old success webhooks).
- provider compromise (leaked API keys).
- sensitive payment data leakage (logging CVVs).
- payment/booking inconsistency (state mismatch).
- fraudulent cancellation/refund actions (bypassing admin checks).

## 40. UNDEFINED / DECISION REQUIRED
Unresolved payment and consultation decisions:
- Exact payment gateway provider (PROPOSED: Stripe).
- Formal payment and consultation lifecycle states.
- Exact schema and logic for idempotency keys.
- Refund, cancellation, rescheduling, and no-show policies.
- Pricing structure and currency limits.
- Lawyer availability slot intervals and timezone handling.
- Selection of the video consultation provider and associated features (recording, links).
- Consultation notification requirements.
- Exact retry mechanisms for handling inconsistent states (polling vs webhooks).
