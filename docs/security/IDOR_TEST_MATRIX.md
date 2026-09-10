# Phase 5 Object Ownership & IDOR Test Matrix

## Objective
Verify authoritative server-side boundary enforcement against Insecure Direct Object References (IDOR) across every domain entity identifier in Legal Case Companion.

---

## IDOR Test Scenarios Matrix

| Identifier Type | Target Entity | Test Scenario | Threat Actor | Expected Result | Enforcement Mechanism | Test Implementation |
| :--- | :--- | :--- | :--- | :---: | :--- | :--- |
| `user_id` | `User` profile / lifecycle | User A requests User B's profile modification or suspension | User B (Client/Lawyer) | **403 Forbidden** | Role check (`RequireRole([UserRole.ADMIN])`) and user identity match | `tests/integration/test_admin_security.py` |
| `case_id` | `Case` matter workspace | User A requests Case B metadata, activity, or documents | Unassociated User | **404 Not Found** (Existence Masking) | `authorize_case_access()` filters against active `CaseParticipant` table | `tests/security/test_authorization_and_bola_red_team.py` |
| `consultation_id` | `Consultation` session | Client A attempts to access Consultation B between Client B and Lawyer B | Unassociated Client | **403 Forbidden** | `_authorize_consultation_access()` verifies caller is participant or admin | `tests/integration/test_consultations_complete.py` |
| `document_id` | `Document` file download | User A attempts to generate presigned download URL for Document B in Case B | Unassociated User | **404 Not Found** / **403 Forbidden** | Verifies document belongs to case AND user is active case participant | `tests/security/test_document_and_storage_red_team.py` |
| `evidence_id` | `Evidence` item & custody log | Lawyer A attempts to read Evidence B belonging to Client B's private case | Unassociated Lawyer | **403 / 404** | Evaluates active case participation and explicit advocate access grants | `tests/security/test_evidence_authorization_and_idor.py` |
| `bundle_id` | `EvidenceBundle` export | User A attempts to download compiled court evidence bundle for Case B | Unassociated User | **403 Forbidden** | Checks case participant role and non-collaborator exclusion | `tests/integration/test_bundles.py` |
| `appointment_id` / `slot_id` | Lawyer Availability Slot | Client A attempts to delete or update Lawyer B's calendar slot | Client / Other Lawyer | **403 Forbidden** | `profile_service` verifies lawyer profile owner identity | `tests/integration/test_lawyer_operational_dashboard.py` |
| `lawyer_id` | `LawyerProfile` settings | Lawyer A attempts to modify Lawyer B's consultation fee or practice areas | Other Lawyer | **403 Forbidden** | Profile service checks `profile.user_id == current_user.id` | `tests/security/test_authorization_and_bola_red_team.py` |
| `verification_id` | `LawyerVerification` | Lawyer A attempts to start review or approve Lawyer B's verification | Non-Admin Lawyer | **403 Forbidden** | `RequireRole([UserRole.ADMIN])` and self-approval prohibition check | `tests/security/test_phase_5_api_security_audit.py` |
| `payment_id` | `Payment` intent | User A attempts to confirm or alter Payment Intent B created by User B | Unassociated User | **403 Forbidden** | `payment_service` asserts `payment.client_id == current_user.client_profile.id` | `tests/security/test_authorization_and_bola_red_team.py` |
| `transaction_identifier` | `CommercialTransaction` receipt | Client B attempts to fetch tax invoice receipt for Transaction A | Unassociated Client | **403 Forbidden** | Server checks `current_user.id in (txn.payer_user_id, txn.payee_user_id) or admin` | `tests/security/test_phase_5_api_security_audit.py` |
| `refund_id` | `CommercialRefund` | Client A attempts to approve or trigger refund on Transaction B | Non-Admin Client | **403 Forbidden** | Strict admin authorization required for manual refund issuance | `tests/unit/test_refund_reliability.py` |
| `review_id` | `AIReview` benchmark record | Client A attempts to action or approve AI review record | Non-Operator Client | **403 Forbidden** | `RequireOperatorPermission(OperationalPermission.COMPLIANCE_OPERATIONS)` | `tests/security/test_background_and_admin_red_team.py` |
| `meeting_id` / `room_id` | `VideoMeeting` session | User A attempts to connect WebSocket to meeting room of Consultation B | Unassociated User | **WS 1008 Policy Violation** | WebRTC signaling validates cryptographically signed room token | `tests/integration/test_native_video_and_recording_pipeline.py` |
| `recording_id` | `VideoRecording` asset | User A attempts to generate playback ticket for recording of Consultation B | Unassociated User | **403 Forbidden** | `video_recording_service` enforces participant authorization before ticket creation | `tests/integration/test_native_video_and_recording_pipeline.py` |
| `notification_id` | `Notification` record | User A attempts to read or mark as read Notification B sent to User B | Other User | **404 Not Found** (Scoped Query) | Scoped SQL filter: `Notification.user_id == current_user.id` | `tests/security/test_background_and_admin_red_team.py` |

---

## Key Principles Enforced
1. **Never authorize solely on entity identifier existence**: The system always validates the relationship graph (Caller → Tenant/Profile → Matter/Case → Asset).
2. **Existence Masking (404 instead of 403)**: For sensitive tenant assets (cases, documents, notifications), the API returns 404 to unassociated callers to prevent ID enumeration attacks.
3. **Pessimistic State Transitions**: All state transitions (`UNDER_REVIEW`, `PAID`, `REFUNDED`, `IN_PROGRESS`) lock rows pessimistically (`with_for_update()`) and validate permitted status paths.