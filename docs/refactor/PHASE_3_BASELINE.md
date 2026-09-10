# Phase 3: Service Integration & Background Worker Baseline

**Execution Date**: September 10, 2026  
**Repository**: Legal Case Companion (LCC)  
**Status**: BASELINE ESTABLISHED

---

## 1. Quality Gates Status at Baseline

| Check | Baseline Command | Result / Metrics | Status |
| :--- | :--- | :--- | :--- |
| **Python Syntax Compilation** | `python -m compileall -q app tests scripts migrations` | 0 syntax errors | **PASS** |
| **Ruff Linter** | `ruff check app tests scripts` | 0 errors | **PASS** |
| **Mypy Static Type Analysis** | `mypy app` | 0 errors across 230 source files | **PASS** |
| **Frontend TypeScript** | `cd frontend && npx tsc --noEmit` | 0 type errors | **PASS** |
| **Frontend ESLint** | `cd frontend && npm run lint` | 0 errors (31 warnings) | **PASS** |
| **Frontend Production Build** | `cd frontend && npm run build` | 36/36 routes generated successfully | **PASS** |
| **Pytest Collection** | `pytest --collect-only` | 749 tests collected | **PASS** |
| **Full Pytest Suite** | `pytest` | 742 passed, 7 failed (99.07% pass rate) | **7 FAILURES** |

---

## 2. Current Known Failures (7 Tests)

### Failure 1: `tests/public_readiness/test_phase_xx_public_readiness.py::test_advocate_verification_and_discovery_ranking`
- **Error**: `TypeError: LawyerVerificationService.submit_verification() got an unexpected keyword argument 'enrollment_number'`
- **Affected Service**: `LawyerVerificationService`
- **Root Cause**: `LawyerVerificationService.submit_verification` signature was modified to expect `(user, payload: AdvocateVerificationSubmitRequest)` without backwards-compatible keyword arguments for `(user, enrollment_number, state_bar_council, ...)`.
- **Expected Behavior**: `submit_verification` should support both parameter styles (`payload` or `enrollment_number`/`state_bar_council` keyword arguments) transparently.

### Failure 2: `tests/test_instant_consultation_flow.py::test_full_flow`
- **Error**: `AssertionError: Pay-test failed: 422 == 200: {"error":{"code":"VALIDATION_ERROR","message":"Cannot create payment for consultation in IN_PROGRESS state"}}`
- **Affected Services**: `ConsultationService`, `PaymentService`
- **Root Cause**: Instant consultations default to `CONFIRMED` or `IN_PROGRESS` immediately on creation, but payment simulation endpoint rejects consultations not in `PENDING` / initial payable state.
- **Expected Behavior**: Payment processing lifecycle should align with instant consultation state machine rules.

### Failure 3: `tests/integration/test_presence_and_realtime_calls.py::test_presence_heartbeat_and_authoritative_status`
- **Error**: `assert data2["is_available"] is False` (evaluates `True is False`)
- **Affected Services**: `PresenceService` / `ProfileService`
- **Root Cause**: Stale presence calculation or availability toggle does not reconcile active status changes when the lawyer disconnects or toggles off.
- **Expected Behavior**: Lawyer availability should reflect real-time heartbeat and presence status authoritatively.

### Failures 4-6: `tests/integration/test_consultation_room_time_access.py`
- **Failing Tests**:
  - `test_room_access_status_blocked_before_window`
  - `test_room_access_lawyer_can_join_early`
  - `test_room_access_when_lawyer_online`
- **Affected Services**: `ConsultationService`, `VideoMeetingService`
- **Root Cause**: Access window calculation before consultation scheduled start time is either out of sync or time zone offset calculation disagrees with scheduled datetime representation.
- **Expected Behavior**: Strict time-gated access (early join grace period for advocate, blocking litigant before scheduled window).

### Failure 7: `tests/integration/test_consultation_lifecycle_production.py::test_concurrency_and_double_start_protection`
- **Error**: State machine / double-start protection failure under concurrent start requests.
- **Affected Service**: `ConsultationService`
- **Root Cause**: Concurrency guard on transitioning consultation from `CONFIRMED` to `IN_PROGRESS` or double room creation.
- **Expected Behavior**: Second simultaneous start attempt must be rejected or idempotently return the existing active room session.

---

## 3. Phase 3 Scope & Service Hookup Targets

| Service | File Path | Current Status | Target in Phase 3 |
| :--- | :--- | :--- | :--- |
| **`VideoMeetingService.cleanup_stale_meetings`** | `app/services/video_meeting_service.py` | Stale meeting cleanup method drafted in Phase 2 | Ensure robust integration with LiveKit provider session closure, transaction safety, idempotency, and unit/integration tests |
| **`job_worker.py`** | `app/services/job_worker.py` | Runs background maintenance jobs | Complete audit of all registered job types, parameter mappings, idempotency keys, and error recovery |
| **`AbuseDefenseService`** | `app/services/abuse_defense_service.py` | Implemented but unhooked | Wire into registration, consultation booking, and user creation workflows |
| **`AIBudgetService`** | `app/services/ai_budget_service.py` | Implemented but unhooked | Wire into AI chat, assistant, and research endpoints before expensive LLM execution |
| **`CancellationPolicyService`** | `app/services/cancellation_policy_service.py` | Implemented but unhooked | Wire into consultation cancellation and refund workflows |
| **`ReminderService`** | `app/services/reminder_service.py` | Implemented but unhooked from scheduler | Register in `JobScheduler` periodic maintenance scans for hearings and task deadlines |
