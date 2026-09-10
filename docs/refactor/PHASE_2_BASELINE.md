# Phase 2 Baseline Quality Report: Legal Case Companion (LCC)

**Date**: September 10, 2026  
**Auditor**: Antigravity Engineering  
**Scope**: Pre-repair baseline recording of all known static-analysis, type-safety, and code-quality defects.

---

## 1. Baseline Summary

| Validation Check | Target Scope | Initial Status | Target Status |
| :--- | :--- | :---: | :---: |
| **Python Syntax** | `app/`, `tests/`, `scripts/`, `migrations/` | **PASSED** (0 errors) | **PASSED** |
| **Pytest Collection** | Entire test suite (`tests/`) | **PASSED** (749 tests collected in 4.66s) | **PASSED** |
| **Backend Lint** | `app/`, `tests/` | **PASSED** (0 errors) | **PASSED** |
| **Scripts Lint** | `scripts/load_test_phase_10.py` | **FAILED** (9 errors, B023) | **PASSED** (0 errors) |
| **Backend Mypy** | `app/` (230 source files) | **FAILED** (48 errors across 13 files) | **PASSED** (0 errors) |
| **Frontend TypeScript**| `frontend/` (`@/*`) | **PASSED** (0 type errors across 152 files) | **PASSED** (0 errors) |
| **Frontend ESLint** | `frontend/` | **FAILED** (3 errors, 31 warnings) | **PASSED** (0 errors) |
| **Frontend Build** | Next.js 16.3.4 (App Router) | **PASSED** (36 routes compiled) | **PASSED** (36 routes) |

---

## 2. Detailed Initial Defect Inventory

### 2.1 Backend Mypy Errors (48 errors in 13 files)

1. **`app/services/cohort_governance_service.py` (3 errors)**
   - Line 115: `Unsupported operand types for > ("int" and "object") [operator]`
   - Line 243: `Generator has incompatible item type "int"; expected "bool" [misc]`
   - Line 246: `"Case" has no attribute "category" [attr-defined]`

2. **`app/services/workflow_telemetry_service.py` (3 errors)**
   - Line 266: `Unsupported left operand type for / ("object") [operator]`
   - Line 267: `Unsupported operand types for / ("object" and "int") [operator]`
   - Line 268: `Unsupported operand types for < ("int" and "object") [operator]`

3. **`app/services/support_service.py` (1 error)**
   - Line 246: `Generator has incompatible item type "int"; expected "bool" [misc]`

4. **`app/services/case_attention_service.py` (2 errors)**
   - Line 248: `Value of type "dict[str, str] | None" is not indexable [index]`
   - Line 249: `Value of type "dict[str, str] | None" is not indexable [index]`

5. **`app/services/reminder_service.py` (5 errors)**
   - Line 187: `"Consultation" has no attribute "client_user_id"; maybe "client_id"? [attr-defined]`
   - Line 189: `"Consultation" has no attribute "client_user_id"; maybe "client_id"? [attr-defined]`
   - Line 191: `"Consultation" has no attribute "lawyer_name" [attr-defined]`
   - Line 205: `"Consultation" has no attribute "client_user_id"; maybe "client_id"? [attr-defined]`
   - Line 212: `"Consultation" has no attribute "client_name" [attr-defined]`

6. **`app/services/lawyer_dashboard_service.py` (9 errors)**
   - Line 195: `Item "None" of "datetime | None" has no attribute "replace" [union-attr]`
   - Line 195: `Item "None" of "datetime | None" has no attribute "tzinfo" [union-attr]`
   - Line 196: `Unsupported operand types for > ("datetime" and "None") [operator]`
   - Line 202: `Argument "scheduled_at" to "TodayAgendaItem" has incompatible type "datetime | Any | None"; expected "datetime" [arg-type]`
   - Line 203: `Item "None" of "datetime | Any | None" has no attribute "strftime" [union-attr]`
   - Line 277: `Item "None" of "datetime | None" has no attribute "replace" [union-attr]`
   - Line 277: `Item "None" of "datetime | None" has no attribute "tzinfo" [union-attr]`
   - Line 278: `No overload variant of "__sub__" of "datetime" matches argument type "None" [operator]`
   - Line 287: `Item "None" of "datetime | Any | None" has no attribute "strftime" [union-attr]`
   - Line 593: `Argument "is_urgent" to "TodayAgendaItem" has incompatible type "datetime | bool | None"; expected "bool" [arg-type]`

7. **`app/services/bundle_service.py` (1 error)**
   - Line 135: `"type[EvidenceAccessGrant]" has no attribute "granted_to_user_id" [attr-defined]`

8. **`app/api/v1/pilot.py` (5 errors)**
   - Line 420: `"type[datetime]" has no attribute "timedelta" [attr-defined]`
   - Line 525: `"type[datetime]" has no attribute "timedelta" [attr-defined]`
   - Line 608: `Incompatible return value type (got "dict[str, Any]", expected "list[dict[str, Any]]") [return-value]`
   - Line 627: `"type[datetime]" has no attribute "datetime" [attr-defined]`
   - Line 627: `"type[datetime]" has no attribute "timezone" [attr-defined]`

9. **`app/services/evidence_service.py` (4 errors)**
   - Line 71: `Item "None" of "ClientProfile | None" has no attribute "full_name" [union-attr]`
   - Line 72: `Item "None" of "ClientProfile | None" has no attribute "full_name" [union-attr]`
   - Line 73: `Item "None" of "LawyerProfile | None" has no attribute "full_name" [union-attr]`
   - Line 74: `Item "None" of "LawyerProfile | None" has no attribute "full_name" [union-attr]`

10. **`app/api/v1/verification.py` (2 errors)**
    - Line 305: `Argument "rejection_category" to "reject_verification" of "LawyerVerificationService" has incompatible type "str | None"; expected "str" [arg-type]`
    - Line 306: `Argument "reason" to "reject_verification" of "LawyerVerificationService" has incompatible type "str | None"; expected "str" [arg-type]`

11. **`app/api/v1/calendar.py` (9 errors)**
    - Line 89: `Argument 1 to "filter" of "Query" has incompatible type "bool" [arg-type]`
    - Line 210: `Argument 1 to "filter" of "Query" has incompatible type "bool" [arg-type]`
    - Line 337: `Item "None" of "datetime | None" has no attribute "replace" [union-attr]`
    - Line 337: `Item "None" of "datetime | None" has no attribute "tzinfo" [union-attr]`
    - Line 338: `Item "None" of "datetime | Any | None" has no attribute "strftime" [union-attr]`
    - Line 339: `Item "None" of "datetime | Any | None" has no attribute "strftime" [union-attr]`
    - Line 340: `Item "None" of "datetime | Any | None" has no attribute "strftime" [union-attr]`
    - Line 342: `Unsupported left operand type for - ("None") [operator]`
    - Line 342: `Unsupported operand types for <= ("datetime" and "None") [operator]`
    - Line 350: `Argument "scheduled_at" to "CalendarEventItem" has incompatible type "datetime | Any | None"; expected "datetime" [arg-type]`

12. **`app/services/profile_service.py` (1 error)**
    - Line 241: `"LawyerProfile" has no attribute "match_reasons" [attr-defined]`

13. **`app/services/job_worker.py` (1 error)**
    - Line 504: `"VideoMeetingService" has no attribute "cleanup_stale_meetings" [attr-defined]`

---

### 2.2 Scripts Ruff B023 Closure Binding Errors (9 errors in 1 file)

**`scripts/load_test_phase_10.py`**:
- Line 102: `B023 Function definition does not bind loop variable 'method'`
- Line 103: `B023 Function definition does not bind loop variable 'url'`
- Line 103: `B023 Function definition does not bind loop variable 'h'`
- Line 104: `B023 Function definition does not bind loop variable 'method'`
- Line 105: `B023 Function definition does not bind loop variable 'url'`
- Line 105: `B023 Function definition does not bind loop variable 'h'`
- Line 105: `B023 Function definition does not bind loop variable 'body'`
- Line 107: `B023 Function definition does not bind loop variable 'url'`
- Line 107: `B023 Function definition does not bind loop variable 'h'`

---

### 2.3 Frontend ESLint Violations (3 errors in 1 file)

**`frontend/src/app/consultations/[id]/room/page.tsx`**:
- Line 1096: `error 'stream' is never reassigned. Use 'const' instead (prefer-const)`
- Line 1116: `error 'stream' is never reassigned. Use 'const' instead (prefer-const)`
- Line 1210: `error 'stream' is never reassigned. Use 'const' instead (prefer-const)`
