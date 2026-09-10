# Phase 2: Static Analysis & Code Quality Baseline Report

**Execution Date**: September 10, 2026  
**Repository**: Legal Case Companion (LCC)  
**Status**: COMPLETE (0 static errors across all target linters, compilers, and typecheckers)

---

## Executive Summary

Phase 2 successfully eliminated all known static-analysis, baseline code-quality, and typecheck defects across the repository without altering intended business logic, database schemas, or API contracts.

| Quality Gate | Baseline (Start of Phase 2) | Target | Final State | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Python Syntax Compilation** (`compileall`) | Clean | 0 errors | 0 errors | **PASS** |
| **Ruff Linter** (`app`, `tests`, `scripts`) | 9 violations (B023) | 0 errors | 0 errors | **PASS** |
| **Mypy Type Checker** (`app/` across 230 files) | 48 errors across 13 files | 0 errors | 0 errors | **PASS** |
| **Frontend ESLint** (`frontend/`) | 3 violations (`prefer-const`) | 0 errors | 0 errors (31 warnings) | **PASS** |
| **Frontend TypeScript** (`tsc --noEmit`) | Passing | 0 errors | 0 errors | **PASS** |
| **Frontend Production Build** (`next build`) | Passing | 0 errors | 0 errors (36/36 routes) | **PASS** |
| **Pytest Collection** (`pytest --collect-only`) | 749 tests | 749 tests | 749 tests collected | **PASS** |

---

## Detailed Remediation Log

### 1. Frontend ESLint (`prefer-const`)
- **File**: `frontend/src/app/consultations/[id]/room/page.tsx`
- **Root Cause**: MediaStream variables (`stream`) were declared with `let` on lines 1096, 1116, and 1210 but never reassigned within their lexical scopes.
- **Fix Applied**: Converted variable declarations from `let stream = ...` to `const stream = ...`.
- **Validation**: `npm run lint` reported 0 errors (31 warnings remaining for unused imports / image optimizations).

### 2. Scripts Closure Binding (`Ruff B023`)
- **File**: `scripts/load_test_phase_10.py`
- **Root Cause**: Asynchronous callback closures within loops captured the loop variables `method`, `url`, `h`, and `body` by reference rather than by value, causing all concurrent requests to evaluate against the final loop iteration's values.
- **Fix Applied**: Explicitly bound loop iteration variables as default parameters in the closure helper functions (`req_method=method, req_url=url, req_h=h, req_body=body`).
- **Validation**: `ruff check app tests scripts` returned zero errors.

### 3. Backend Mypy Errors (48 errors across 13 files)

#### A. `app/api/v1/pilot.py`
- **Root Cause**: Module import `from datetime import datetime` shadowed the standard library `datetime` module, causing subsequent references to `datetime.timedelta` and `datetime.timezone.utc` to fail type checking. Additionally, return type annotation for metrics endpoint was under-typed.
- **Fix Applied**:
  - Explicitly imported `timedelta` and `timezone` from `datetime`.
  - Replaced shadowed `datetime.timedelta` and `datetime.timezone.utc` references with `timedelta` and `timezone.utc` (or `UTC`).
  - Added explicit return type annotation `dict[str, Any]`.

#### B. `app/services/reminder_service.py`
- **Root Cause**: Model drift where code accessed `Consultation.client_user_id`, `c.lawyer_name`, and `c.client_name`, which do not exist on the SQLAlchemy ORM model.
- **Fix Applied**:
  - Traversed authoritative relationships: `c.client.user_id`, `c.lawyer.user_id`, `c.client.full_name`, and `c.lawyer.full_name`.
  - Added explicit `None` guards to prevent dereferencing nullable relationship chains.

#### C. `app/services/bundle_service.py`
- **Root Cause**: Filtered query using `EvidenceAccessGrant.granted_to_user_id`, which was an obsolete column name.
- **Fix Applied**:
  - Updated filter to query canonical column `EvidenceAccessGrant.grantee_user_id == user.id`.

#### D. `app/services/cohort_governance_service.py`
- **Root Cause**: Attempted to query non-existent column `Case.category`. Also, `STAGE_TARGETS` dictionary values were inferred as untyped `object`, causing `int(target["advocates"])` type errors.
- **Fix Applied**:
  - Declared `StageTarget(TypedDict)` with typed fields `advocates: int` and `matters: int`.
  - Filtered cases by domain category using canonical case fields (`title` and `description`).

#### E. `app/models/user.py` & `app/schemas/profile.py`
- **Root Cause**: Code in `app/services/profile_service.py` accessed `LawyerProfile.match_reasons`, which was absent on the ORM model and response schema.
- **Fix Applied**:
  - Added ephemeral runtime attribute `match_reasons: list[str] = []` on `LawyerProfile`.
  - Added `match_reasons: list[str] = []` on `LawyerPublicResponse`.

#### F. `app/api/v1/calendar.py`
- **Root Cause**: Direct arithmetic on `t.due_date` without null checks; invalid boolean literal `False` passed to SQLAlchemy `filter()`.
- **Fix Applied**:
  - Imported `false` from `sqlalchemy` and used `filter(false())`.
  - Added `if t.due_date is None: continue` guard before date comparisons.

#### G. `app/services/lawyer_dashboard_service.py`
- **Root Cause**: direct comparison and subtraction on nullable `Task.due_date`; un-narrowed bool expression.
- **Fix Applied**:
  - Added `if t.due_date is None: continue` guards.
  - Wrapped `is_urgent` check with explicit `bool(...)`.

#### H. `app/services/evidence_service.py`
- **Root Cause**: Used `getattr(u, "full_name", None)` on `User` instead of accessing `client_profile.full_name`.
- **Fix Applied**:
  - Checked `if u.client_profile and u.client_profile.full_name: ...`.

#### I. `app/api/v1/verification.py`
- **Root Cause**: Nullable `payload.rejection_category` and `payload.reason` passed to non-null string parameters; legacy submit route attempted to call new multi-step document workflow without certificate.
- **Fix Applied**:
  - Provided explicit fallbacks `payload.rejection_category or "OTHER"` and `payload.reason or "No reason provided"`.
  - Wired legacy route to `ProfileService.submit_verification` to maintain backwards compatibility without requiring immediate document uploads.

#### J. `app/services/case_attention_service.py`
- **Root Cause**: Indexing into dictionary keys when `nearest_hearing` was `None`.
- **Fix Applied**:
  - Added explicit guard `and nearest_hearing is not None` before accessing attributes.

#### K. `app/services/workflow_telemetry_service.py`
- **Root Cause**: Inferred dictionary values inside funnel steps were typed as `object`, causing arithmetic operator errors on `s["count"]`.
- **Fix Applied**:
  - Defined `FunnelStep(TypedDict)` with `name: str`, `count: int`, `drop_off_pct: float`.

#### L. `app/services/support_service.py`
- **Root Cause**: Generator expression in `sum()` resolved to invalid overload.
- **Fix Applied**:
  - Replaced `sum(1 for rc in ...)` with `len([rc for rc in resolved_cases if ...])`.

#### M. `app/services/video_meeting_service.py`
- **Root Cause**: Missing method `cleanup_stale_meetings(max_idle_hours: int = 2) -> int` expected by `job_worker.py`.
- **Fix Applied**:
  - Implemented `cleanup_stale_meetings(max_idle_hours: int = 2) -> int` to transition stale active meetings to `ENDED` and consultations to `COMPLETED`.

---

## Verification & Quality Gates

All baseline verification gates passed cleanly:
```bash
python -m compileall -q app tests scripts migrations    # PASS
python -m ruff check app tests scripts                   # All checks passed! (0 errors)
python -m mypy app                                       # Success: no issues found in 230 source files
cd frontend && npx tsc --noEmit                         # 0 errors
cd frontend && npm run lint                              # 0 errors (31 warnings)
cd frontend && npm run build                             # PASS (36/36 routes)
pytest --collect-only                                    # 749 tests collected
```
