# Baseline Status Report: Legal Case Companion (LCC)

**Date**: September 10, 2026  
**Auditor**: Antigravity Engineering (Automated Baseline Audit)  
**Target Repository**: Legal Case Companion (`c:\Users\akuma\OneDrive\Desktop\lcc\Legal-Case-Companion-main\Legal-Case-Companion-main`)  
**Git Commit**: `098e227` (`feat: add bidirectional case document sharing, live consultation room drawer, branding assets, and desktop launcher`)  
**Operating Environment**: Windows 11 (Node v25.5.0, npm 11.8.0, Python 3.12.10)

---

## 1. Executive Summary & Baseline Quality Gate

This baseline establishes the exact structural, syntactical, type safety, linting, test collection, and build health of the Legal Case Companion repository prior to any refactoring.

| Validation Check | Target Scope | Command Executed | Result | Failures / Blockers |
| :--- | :--- | :--- | :--- | :--- |
| **Python Syntax Check** | `app/`, `tests/`, `scripts/`, `migrations/` | `python -m compileall -q app tests scripts migrations` | **PASSED** | 0 syntax errors across all Python files |
| **Pytest Test Collection** | Entire `tests/` directory | `pytest --collect-only` | **PASSED** | **749 tests collected in 3.19s**, 0 collection errors |
| **Backend Lint Check** | Entire repository | `ruff check .` | **FAILED (Scripts only)** | 9 errors in `scripts/load_test_phase_10.py` (B023); **0 errors** in `app/` and `tests/` |
| **Backend Type Check** | `app/` (core application) | `mypy app` | **FAILED** | **48 type errors across 13 source files** (230 files checked) |
| **Frontend TypeScript Check** | `frontend/` (`@/*`) | `npx tsc --noEmit` | **PASSED** | **0 type errors** across 152 frontend files |
| **Frontend Lint Check** | `frontend/` (`eslint`) | `npm run lint` | **FAILED** | **3 errors** (`prefer-const`), 32 warnings |
| **Frontend Production Build** | Next.js 16.3.4 (App Router) | `npm run build` | **PASSED** | **36 routes successfully compiled & optimized** |
| **Database Migration Integrity** | Alembic migration graph | `alembic heads` | **PASSED** | Single linear head `w1a2b3c4d5e6` (53 revisions) |

---

## 2. Detailed Verification Results & Recorded Failures

### 2.1 Python Syntax Compilation (`compileall`)
- **Status**: PASSED (Exit Code: 0)
- **Scope**: 230 `app` files, 162 `tests` files, 19 `scripts` files, 54 `migrations` files.
- **Outcome**: Zero syntax errors. All Python files parse into valid Python 3.12 bytecode.

---

### 2.2 Pytest Test Collection (`pytest --collect-only`)
- **Status**: PASSED (Exit Code: 0)
- **Duration**: 3.19 seconds
- **Test Inventory**:
  - **749 tests collected** across 12 test suites:
    * `tests/unit/`: 18 test modules (app health, metrics, background jobs, embedding, monetary lifecycle, reconciliation engine, recording lifecycle, refund reliability, etc.)
    * `tests/integration/`: 26 test modules (auth, session isolation, document security, websocket signaling, video sessions, payments, evidence locker)
    * `tests/e2e/`: End-to-end full system user journey flows
    * `tests/evaluation/`: AI legal retrieval and prompt regression suites
    * `tests/pilot/`: Controlled pilot verification harness
    * `tests/public_readiness/`: Launch gate verification
    * `tests/reliability/`: Outbox, idempotent scheduling, connection retries
    * `tests/security/`: Red team, BOLA/IDOR, log scrubbing, tamper defense
    * `tests/performance/`: Latency, indexing, and throughput benchmarks
- **Configuration Note**:
  `configfile: pytest.ini (WARNING: ignoring pytest config in pyproject.toml!)`
  Pytest flags that `pytest.ini` takes precedence over `[tool.pytest.ini_options]` in `pyproject.toml`.

---

### 2.3 Backend Linting (`ruff check .`)
- **Status**: FAILED (Exit Code: 1)
- **Errors**: 9 errors, all isolated to `scripts/load_test_phase_10.py`.
- **`app/` and `tests/` Status**: **PASSED (0 errors)**.

#### Recorded Ruff Violations:
| File | Line | Code | Description |
| :--- | :--- | :--- | :--- |
| `scripts/load_test_phase_10.py` | 102 | `B023` | Function definition does not bind loop variable `method` |
| `scripts/load_test_phase_10.py` | 103 | `B023` | Function definition does not bind loop variable `url` |
| `scripts/load_test_phase_10.py` | 103 | `B023` | Function definition does not bind loop variable `h` |
| `scripts/load_test_phase_10.py` | 104 | `B023` | Function definition does not bind loop variable `method` |
| `scripts/load_test_phase_10.py` | 105 | `B023` | Function definition does not bind loop variable `url` |
| `scripts/load_test_phase_10.py` | 105 | `B023` | Function definition does not bind loop variable `h` |
| `scripts/load_test_phase_10.py` | 105 | `B023` | Function definition does not bind loop variable `body` |
| `scripts/load_test_phase_10.py` | 107 | `B023` | Function definition does not bind loop variable `url` |
| `scripts/load_test_phase_10.py` | 107 | `B023` | Function definition does not bind loop variable `h` |

*Root Cause*: An inline closure worker inside `run_concurrent_requests` in `load_test_phase_10.py` closes over iteration variables instead of binding them via default arguments (`def send(m=method, u=url, ...):`).

---

### 2.4 Backend Static Type Analysis (`mypy app`)
- **Status**: FAILED (Exit Code: 1)
- **Scope**: Checked 230 source files in `app/`.
- **Total Errors**: **48 errors in 13 files**.

#### Catalog of Recorded Mypy Errors:
```
app/api/v1/calendar.py:89: error: Argument 1 to "filter" of "Query" has incompatible type "bool"; expected "ColumnElement[bool]..." [arg-type]
app/api/v1/calendar.py:210: error: Argument 1 to "filter" of "Query" has incompatible type "bool"; expected "ColumnElement[bool]..." [arg-type]
app/api/v1/calendar.py:337: error: Item "None" of "datetime | None" has no attribute "replace" [union-attr]
app/api/v1/calendar.py:337: error: Item "None" of "datetime | None" has no attribute "tzinfo" [union-attr]
app/api/v1/calendar.py:338: error: Item "None" of "datetime | Any | None" has no attribute "strftime" [union-attr]
app/api/v1/calendar.py:339: error: Item "None" of "datetime | Any | None" has no attribute "strftime" [union-attr]
app/api/v1/calendar.py:340: error: Item "None" of "datetime | Any | None" has no attribute "strftime" [union-attr]
app/api/v1/calendar.py:342: error: Unsupported left operand type for - ("None") [operator]
app/api/v1/calendar.py:342: error: Unsupported operand types for <= ("datetime" and "None") [operator]
app/api/v1/calendar.py:350: error: Argument "scheduled_at" to "CalendarEventItem" has incompatible type "datetime | Any | None"; expected "datetime" [arg-type]

app/api/v1/pilot.py:420: error: "type[datetime]" has no attribute "timedelta" [attr-defined]
app/api/v1/pilot.py:525: error: "type[datetime]" has no attribute "timedelta" [attr-defined]
app/api/v1/pilot.py:608: error: Incompatible return value type (got "dict[str, Any]", expected "list[dict[str, Any]]") [return-value]
app/api/v1/pilot.py:627: error: "type[datetime]" has no attribute "datetime" [attr-defined]
app/api/v1/pilot.py:627: error: "type[datetime]" has no attribute "timezone" [attr-defined]

app/api/v1/verification.py:305: error: Argument "rejection_category" to "reject_verification" of "LawyerVerificationService" has incompatible type "str | None"; expected "str" [arg-type]
app/api/v1/verification.py:306: error: Argument "reason" to "reject_verification" of "LawyerVerificationService" has incompatible type "str | None"; expected "str" [arg-type]

app/services/bundle_service.py:135: error: "type[EvidenceAccessGrant]" has no attribute "granted_to_user_id" [attr-defined]

app/services/case_attention_service.py:248: error: Value of type "dict[str, str] | None" is not indexable [index]
app/services/case_attention_service.py:249: error: Value of type "dict[str, str] | None" is not indexable [index]

app/services/cohort_governance_service.py:115: error: Unsupported operand types for > ("int" and "object") [operator]
app/services/cohort_governance_service.py:243: error: Generator has incompatible item type "int"; expected "bool" [misc]
app/services/cohort_governance_service.py:246: error: "Case" has no attribute "category" [attr-defined]

app/services/evidence_service.py:71: error: Item "None" of "ClientProfile | None" has no attribute "full_name" [union-attr]
app/services/evidence_service.py:72: error: Item "None" of "ClientProfile | None" has no attribute "full_name" [union-attr]
app/services/evidence_service.py:73: error: Item "None" of "LawyerProfile | None" has no attribute "full_name" [union-attr]
app/services/evidence_service.py:74: error: Item "None" of "LawyerProfile | None" has no attribute "full_name" [union-attr]

app/services/job_worker.py:504: error: "VideoMeetingService" has no attribute "cleanup_stale_meetings" [attr-defined]

app/services/lawyer_dashboard_service.py:195: error: Item "None" of "datetime | None" has no attribute "replace" [union-attr]
app/services/lawyer_dashboard_service.py:195: error: Item "None" of "datetime | None" has no attribute "tzinfo" [union-attr]
app/services/lawyer_dashboard_service.py:196: error: Unsupported operand types for > ("datetime" and "None") [operator]
app/services/lawyer_dashboard_service.py:202: error: Argument "scheduled_at" to "TodayAgendaItem" has incompatible type "datetime | Any | None"; expected "datetime" [arg-type]
app/services/lawyer_dashboard_service.py:203: error: Item "None" of "datetime | Any | None" has no attribute "strftime" [union-attr]
app/services/lawyer_dashboard_service.py:277: error: Item "None" of "datetime | None" has no attribute "replace" [union-attr]
app/services/lawyer_dashboard_service.py:277: error: Item "None" of "datetime | None" has no attribute "tzinfo" [union-attr]
app/services/lawyer_dashboard_service.py:278: error: No overload variant of "__sub__" of "datetime" matches argument type "None" [operator]
app/services/lawyer_dashboard_service.py:287: error: Item "None" of "datetime | Any | None" has no attribute "strftime" [union-attr]
app/services/lawyer_dashboard_service.py:593: error: Argument "is_urgent" to "TodayAgendaItem" has incompatible type "datetime | bool | None"; expected "bool" [arg-type]

app/services/profile_service.py:241: error: "LawyerProfile" has no attribute "match_reasons" [attr-defined]

app/services/reminder_service.py:187: error: "Consultation" has no attribute "client_user_id"; maybe "client_id"? [attr-defined]
app/services/reminder_service.py:189: error: "Consultation" has no attribute "client_user_id"; maybe "client_id"? [attr-defined]
app/services/reminder_service.py:191: error: "Consultation" has no attribute "lawyer_name" [attr-defined]
app/services/reminder_service.py:205: error: "Consultation" has no attribute "client_user_id"; maybe "client_id"? [attr-defined]
app/services/reminder_service.py:212: error: "Consultation" has no attribute "client_name" [attr-defined]

app/services/support_service.py:246: error: Generator has incompatible item type "int"; expected "bool" [misc]

app/services/workflow_telemetry_service.py:266: error: Unsupported left operand type for / ("object") [operator]
app/services/workflow_telemetry_service.py:267: error: Unsupported operand types for / ("object" and "int") [operator]
app/services/workflow_telemetry_service.py:268: error: Unsupported operand types for < ("int" and "object") [operator]
```

#### Root-Cause Breakdown of Type Errors:
1. **Name & Namespace Import Errors** (`app/api/v1/pilot.py`):
   `from datetime import datetime` was imported, but code calls `datetime.timedelta(...)`, `datetime.datetime.now(...)`, and `datetime.timezone.utc`.
2. **Schema & Model Drift**:
   - `EvidenceAccessGrant` model defines user reference as `user_id` or `grantee_user_id`, while `bundle_service.py:135` queries `granted_to_user_id`.
   - `Consultation` model has `client_id` (FK to `client_profiles.id`), but `reminder_service.py` references `c.client_user_id`, `c.lawyer_name`, and `c.client_name` directly on the model instance instead of navigating through relationships (`c.client.user_id`, `c.lawyer.user.full_name`).
   - `Case` model does not have a `category` attribute in `cohort_governance_service.py`.
3. **Missing Service Method**:
   `app/services/job_worker.py:504` dispatches `STALE_MEETING_CLEANUP` to `VideoMeetingService.cleanup_stale_meetings(...)`, which was omitted from `VideoMeetingService`.
4. **Nullable / Optional Handling**:
   In `calendar.py` and `lawyer_dashboard_service.py`, `scheduled_at` is typed `datetime | None` in SQLAlchemy models, but accessed directly without `if item.scheduled_at is not None:` guards.

---

### 2.5 Frontend TypeScript Check (`npx tsc --noEmit`)
- **Status**: **PASSED (Exit Code: 0)**
- **Scope**: All TypeScript and TSX files in `frontend/src` and configuration files.
- **Outcome**: Clean compilation with zero errors. All types, interfaces, React 19 hooks, and Next.js 16 app router contracts align.

---

### 2.6 Frontend Linting (`npm run lint` -> `eslint`)
- **Status**: FAILED (Exit Code: 1)
- **Summary**: 35 problems (3 errors, 32 warnings).

#### Recorded ESLint Errors:
| File | Line | Rule | Details |
| :--- | :--- | :--- | :--- |
| `frontend/src/app/consultations/[id]/room/page.tsx` | 1096 | `prefer-const` | `'stream' is never reassigned. Use 'const' instead.` |
| `frontend/src/app/consultations/[id]/room/page.tsx` | 1116 | `prefer-const` | `'stream' is never reassigned. Use 'const' instead.` |
| `frontend/src/app/consultations/[id]/room/page.tsx` | 1210 | `prefer-const` | `'stream' is never reassigned. Use 'const' instead.` |

*Warnings Summary (32 total)*:
- 25 unused variables (`@typescript-eslint/no-unused-vars`) across `dashboard/page.tsx`, `documents/page.tsx`, `lawyers/[lawyerId]/page.tsx`, `calendar/page.tsx`, etc.
- 7 unoptimized `<img>` tags (`@next/next/no-img-element`) in auth and shell templates.

---

### 2.7 Frontend Production Build (`npm run build`)
- **Status**: **PASSED (Exit Code: 0)**
- **Framework**: Next.js 16.3.4 (Webpack)
- **Output**: 36 routes generated and validated:
  - 30 static pages (`/`, `/admin/*`, `/calendar`, `/cases`, `/cases/new`, `/consultations`, `/dashboard`, `/documents`, `/lawyers`, `/login`, `/messages`, `/onboarding/*`, `/profile`, `/register`, etc.)
  - 6 dynamic server-rendered routes (`/cases/[caseId]`, `/cases/[caseId]/bundles`, `/cases/[caseId]/evidence`, `/cases/[caseId]/evidence/[evidenceId]`, `/cases/[caseId]/timeline`, `/consultations/[id]/room`, `/lawyers/[lawyerId]`)

---

### 2.8 Runtime Test Suite Execution Sample
- `tests/unit/test_app.py`: **7/7 passed (100%)**
- `tests/integration/test_video_session_reliability.py`: **4 passed, 1 failed**:
  * `test_stale_meeting_cleanup`: `AttributeError: 'VideoMeetingService' object has no attribute 'cleanup_stale_meetings'`
- `tests/unit/test_background_maintenance_jobs.py`: **5 passed, 1 failed**:
  * `test_stale_meeting_cleanup_job`: `JobStatus.RETRYING == JobStatus.SUCCEEDED` due to `AttributeError: 'VideoMeetingService' object has no attribute 'cleanup_stale_meetings'`

---

## 3. Environment & Configuration State

1. **Python Virtual Environment**:
   - Location: `.venv` in inner project directory.
   - All runtime dependencies (`fastapi`, `sqlalchemy`, `alembic`, `pydantic`, `cryptography`, `argon2-cffi`, `redis`, `boto3`, `stripe`, `numpy`, `requests`, etc.) and dev dependencies (`pytest`, `mypy`, `ruff`, `black`, `isort`, `httpx`) are installed and functional.
2. **Database Engine**:
   - Local development uses SQLite (`test.db` / `sqlite:///./test.db`).
   - Production configuration uses PostgreSQL (`postgresql+psycopg://...`).
   - Alembic tracks 53 sequential revisions up to `w1a2b3c4d5e6`.
3. **Secret Security**:
   - `.env.example` and `.env.prod.example` serve as sanitized documentation templates.
   - Working `.env` file is excluded via `.gitignore` and `.dockerignore`.
   - Zero production secrets are committed or displayed in this report.
