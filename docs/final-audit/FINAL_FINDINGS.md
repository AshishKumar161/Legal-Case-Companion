# Phase 13: Final Findings & Remediation Register

**Date:** 2026-09-11  
**Auditor:** Independent Full-System Audit (Phase 13)  
**Status:** ALL DEFECTS RESOLVED  

---

## 1. Findings Summary Table

| Finding ID | Severity | Component | Classification | Status |
| :--- | :--- | :--- | :--- | :--- |
| **FINDING-P13-01** | HIGH | Backend Dependencies (`pyproject.toml`) | Defect | **FIXED** |
| **FINDING-P13-02** | HIGH | Frontend Dependencies (`js-yaml`) | Vulnerability | **FIXED** |
| **FINDING-P13-03** | MEDIUM | Unit Test Foreign Keys (`test_monetary_lifecycle.py`) | Defect | **FIXED** |
| **FINDING-P13-04** | LOW | Docker Build Context (`.dockerignore`) | Hardening | **FIXED** |
| **FINDING-P13-05** | MEDIUM | Concurrency Idempotency (`VideoMeetingService`) | Defect | **FIXED** |
| **FINDING-P13-06** | INFO | Managed Database Backup Environment | Operational Note | **ACCEPTED RISK** |

---

## 2. Detailed Findings & Remediations

### FINDING-P13-01: Runtime Production Dependency Missing from Core Dependencies
- **Severity:** HIGH
- **Component:** `pyproject.toml`
- **File:** `pyproject.toml`
- **Issue:** `httpx` was listed solely under `[project.optional-dependencies] dev` rather than `[project.dependencies]`.
- **Root Cause:** In dev environments, `httpx` is installed for pytest/testclient; however, production services `GoogleOAuthService` (`app/domain/auth/google_oauth_service.py`) and `EmailService` (`app/domain/notifications/email_service.py`) import `httpx` directly.
- **Production Impact:** When built in production containers using `pip install .` without `--extra dev`, any invocation of Google OAuth login or email sending would throw `ModuleNotFoundError: No module named 'httpx'`.
- **Remediation:** Moved `"httpx>=0.27.0"` into `project.dependencies` and removed it from `project.optional-dependencies.dev`.
- **Verification:** Verified with `scratch/audit_backend_dependencies.py`, Python `compileall`, and Docker dependency checks.

---

### FINDING-P13-02: Transitive Dependency Vulnerability in Frontend Tree
- **Severity:** HIGH
- **Component:** Frontend Dependencies (`js-yaml`)
- **File:** `frontend/package-lock.json`
- **Issue:** `npm audit` reported high-severity vulnerability GHSA-2883-xcg3-v3hh in `js-yaml` (`<= 4.3.1`), used transitively by `@eslint/eslintrc`.
- **Production Impact:** Potential ReDoS / CPU starvation during ESLint execution or config loading.
- **Remediation:** Executed `npm audit fix` in `frontend/`, upgrading the transitive package cleanly.
- **Verification:** `npm audit --audit-level=high` reports **0 vulnerabilities**. Verified `npm run lint` passes with 0 errors and 0 warnings.

---

### FINDING-P13-03: Foreign Key Constraint Failure in Monetary Lifecycle Unit Tests
- **Severity:** MEDIUM
- **Component:** Unit Test Suite
- **File:** `tests/unit/test_monetary_lifecycle.py`
- **Issue:** `test_commercial_transaction_financial_separation` and `test_reconciliation_exact_decimal_balance` attempted to insert `CommercialTransaction` rows referencing mock/unpersisted `User` and `Consultation` UUIDs. When executed in an environment enforcing SQLite/Postgres foreign keys, the tests failed with `sqlite3.IntegrityError: FOREIGN KEY constraint failed`.
- **Root Cause:** Test fixtures lacked persisted parent records for `client_profiles`, `lawyer_profiles`, and `consultations`.
- **Remediation:** Updated both test cases to persist valid `User`, `ClientProfile`, `LawyerProfile`, and `Consultation` records before executing commercial transactions.
- **Verification:** Re-ran `tests/unit/test_monetary_lifecycle.py` with 100% pass (3/3 passed).

---

### FINDING-P13-04: Incomplete Local Database Exclusion in Docker Ignore
- **Severity:** LOW
- **Component:** Container Build Context
- **File:** `.dockerignore`
- **Issue:** Root `.dockerignore` specified `test_*.db` but omitted `test.db` and generic `*.sqlite*` patterns, creating a risk that local SQLite databases might be copied into Docker image layers.
- **Remediation:** Added `test.db`, `*.db`, `*.sqlite*`, and `storage/recordings/` to root `.dockerignore`.
- **Verification:** Verified `.dockerignore` excludes all database and local recording artifacts.

---

### FINDING-P13-05: Concurrency Conflict Handling in Meeting Provisioning
- **Severity:** MEDIUM
- **Component:** Video Consultation Domain
- **File:** `app/domain/consultations/video_meeting_service.py`
- **Issue:** When two consultation participants (client and lawyer) initiated a meeting at the exact same millisecond with identical consultation room parameters, simultaneous session insertion could lead to a duplicate key or transaction conflict if not wrapped in idempotency rollback recovery.
- **Remediation:** Ensured meeting session provisioning handles concurrency races by rolling back active session on conflict and re-querying the pre-existing provisioned meeting record.
- **Verification:** Verified with `tests/reliability/test_concurrency_and_failover.py` and unit reliability tests (100% pass).

---

### FINDING-P13-06: Local Backup Validation vs. Managed RDS Architecture
- **Severity:** INFORMATIONAL / ACCEPTED RISK
- **Component:** Backup & Recovery
- **Description:** Local test suites and CI run automated backup/restore verification against SQLite (`sqlite3.backup()` API), whereas production operates on managed PostgreSQL (e.g., AWS RDS Aurora) using WAL archiving and daily automated snapshots.
- **Mitigation & Operational Safety:** `scripts/verify_backup_restore.py` verifies 100% of all 83 schema tables and constraints. Production deployment and disaster recovery procedures are documented in `docs/release/DISASTER_RECOVERY.md` and `docs/release/PRODUCTION_DEPLOYMENT.md`.

---

## 3. Findings Conclusion

All identified defects have been remediated, and the associated regression tests pass with zero errors.
