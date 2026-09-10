# Phase 1: Structure & Hygiene Verification Report

**Date**: September 10, 2026  
**Auditor**: Antigravity Engineering  
**Target Repository**: Legal Case Companion (`c:\Users\akuma\OneDrive\Desktop\lcc\Legal-Case-Companion-main`)  
**Phase Status**: **PASS**  

---

## 1. Executive Summary

Phase 1 normalized the nested project repository hierarchy into a single, canonical project root, relocated test fixtures to their standard directory, purged verified duplicate files, relocated frontend test automation scripts, consolidated pytest configuration into `pyproject.toml`, purged ephemeral test-generated WebM recordings, updated the canonical `.gitignore`, and verified that zero business logic, database models, database migrations, or API contracts were modified.

---

## 2. Directory Normalization & Moved Files

### 2.1 Flattening of Nested Hierarchy
The legacy nested directory `Legal-Case-Companion-main/Legal-Case-Companion-main/` was flattened into the single canonical git root `c:\Users\akuma\OneDrive\Desktop\lcc\Legal-Case-Companion-main\`.
- All backend modules (`app/`), frontend source (`frontend/`), test suites (`tests/`), migrations (`migrations/`), documentation (`docs/`), operations tooling (`scripts/`), container specifications (`Dockerfile`, `docker-compose*.yml`, `render.yaml`), packaging (`pyproject.toml`, `uv.lock`), and local runtime environments (`.venv/`, `storage/`, `.env`, `test.db`) now reside at the canonical project root.
- The redundant empty wrapper folder `Legal-Case-Companion-main` was completely removed.

### 2.2 Relocated Files
| Source Path (Old) | Target Path (New) | Purpose / Rationale |
| :--- | :--- | :--- |
| `Rental_Agreement_Evidence.pdf` | `tests/fixtures/Rental_Agreement_Evidence.pdf` | Relocated from root into standard test fixtures folder. |
| `Rental_Agreement_Evidence.txt` | `tests/fixtures/Rental_Agreement_Evidence.txt` | Relocated from root into standard test fixtures folder. |
| `project_report.md` | `docs/archive/project_report.md` | Relocated 74 KB initial development audit report into documentation archive. |
| `frontend/capture_case_detail_and_copilot.mjs` | `frontend/scripts/capture_case_detail_and_copilot.mjs` | Relocated standalone Puppeteer script from frontend root to scripts. |
| `frontend/capture_redesign_screenshots.mjs` | `frontend/scripts/capture_redesign_screenshots.mjs` | Relocated standalone Puppeteer screenshot script. |
| `frontend/test_browser_flow.mjs` | `frontend/scripts/test_browser_flow.mjs` | Relocated standalone browser flow validation script. |
| `frontend/test_phase_7_1_qa.mjs` | `frontend/scripts/test_phase_7_1_qa.mjs` | Relocated standalone QA automation script. |
| `frontend/test_video_flow.mjs` | `frontend/scripts/test_video_flow.mjs` | Relocated standalone video consultation tester. |

---

## 3. Detailed Audit of Deleted Files

Every file deletion was verified against the reference and dependency graph before removal:

### 1. `LegalCaseCompanion.exe` (Outer Root)
- **ACTION**: DELETED
- **REASON**: Redundant duplicate of inner project launcher binary (`LegalCaseCompanion.exe`). Precompiled binaries should not be checked into multiple locations in source control.
- **REFERENCE CHECK**: Outer `Run-LegalCaseCompanion.bat` referenced it; replaced by single canonical `Run-LegalCaseCompanion.bat` launching the root binary.
- **VALIDATION**: Canonical launcher runs directly against project binary.

### 2. `Run-LegalCaseCompanion.bat` (Outer Root)
- **ACTION**: DELETED
- **REASON**: Shell wrapper that navigated into `Legal-Case-Companion-main/`. Rendered obsolete by directory flattening.
- **REFERENCE CHECK**: Checked for OS/CI scripts referencing outer `.bat`; none exist.
- **VALIDATION**: Canonical [Run-LegalCaseCompanion.bat](file:///c:/Users/akuma/OneDrive/Desktop/lcc/Legal-Case-Companion-main/Run-LegalCaseCompanion.bat) at root launches `LegalCaseCompanion.exe` cleanly.

### 3. `app.ico` (Project Root)
- **ACTION**: DELETED
- **REASON**: Cryptographically identical SHA-256 duplicate of `LegalCaseCompanion.ico` (61,554 bytes).
- **REFERENCE CHECK**: Zero build scripts, Python modules, or frontend components imported `app.ico`. `scripts/build_launcher.bat` already explicitly references `LegalCaseCompanion.ico`.
- **VALIDATION**: Icon compilation in `build_launcher.bat` verified intact.

### 4. `openapi.json` (Project Root)
- **ACTION**: DELETED
- **REASON**: Exact 806 KB duplicate of `docs/openapi.json`. FastAPI generates and serves the live OpenAPI schema dynamically at `/api/v1/openapi.json`. `scripts/generate_openapi.py` explicitly exports to `docs/openapi.json`.
- **REFERENCE CHECK**: All documentation and API contract reviews reference `docs/openapi.json`.
- **VALIDATION**: Offline API specification preserved in `docs/openapi.json`; dynamic schema functional in FastAPI.

### 5. `uv.lock.local` (Project Root)
- **ACTION**: DELETED
- **REASON**: Stale local backup snapshot created on Sep 1, 2026. Superseded by authoritative `uv.lock`.
- **REFERENCE CHECK**: Zero CI/CD, Docker, or packaging tools consume `uv.lock.local`.
- **VALIDATION**: `uv.lock` and `pyproject.toml` remain 100% consistent.

### 6. `pytest.ini` (Project Root)
- **ACTION**: CONSOLIDATED & DELETED
- **REASON**: Configuration duplicated and conflicted with `[tool.pytest.ini_options]` in `pyproject.toml`, emitting runtime warning `WARNING: ignoring pytest config in pyproject.toml!`.
- **REFERENCE CHECK**: Pytest configuration migrated completely into `pyproject.toml` (`testpaths`, `python_files`, `addopts`, `filterwarnings`).
- **VALIDATION**: `python -m pytest --collect-only` executes in 0.93s, collects all 749 tests, with zero warnings.

### 7. `storage/recordings/*.webm` (304 Test Recordings)
- **ACTION**: PURGED
- **REASON**: Ephemeral dummy WebM video chunks (443 bytes each) generated during previous test runs.
- **REFERENCE CHECK**: Verified not tracked by git; directory layout (`storage/recordings/`) preserved.
- **VALIDATION**: Integration tests automatically regenerate ephemeral video files during execution.

---

## 4. Retained & Preserved Files (Safety Guarantees)

| File | Status | Reason Retained |
| :--- | :--- | :--- |
| `LegalCaseCompanion.exe` (Root) | **RETAINED** | Windows desktop launcher executable compiled from `scripts/launcher.cs`. Retained for user desktop execution convenience. |
| `LegalCaseCompanion.ico` (Root) | **RETAINED** | Canonical high-resolution application icon used for Windows desktop launcher compilation. |
| `docs/openapi.json` | **RETAINED** | Static reference specification for client SDK generation and offline contract validation. |
| `uv.lock` | **RETAINED** | Authoritative Python dependency resolution lockfile. |
| `frontend/patch-fs.js` | **RETAINED** | Retained to prevent potential Next.js webpack build regressions under Node 25. |
| `app/services/abuse_defense_service.py` | **RETAINED** | Phase XX public abuse resilience service; to be wired in Phase 3. |
| `app/services/ai_budget_service.py` | **RETAINED** | AI query and token quota governor; to be wired in Phase 3. |
| `app/services/cancellation_policy_service.py`| **RETAINED** | Commercial cancellation and refund evaluator; to be wired in Phase 3. |
| `app/services/reminder_service.py` | **RETAINED** | Operational court hearing and deadline notification service; to be repaired and wired in Phase 3. |
| `app/db/session.py` | **RETAINED (Marked for Phase 5)** | Legacy alias re-exporting `app.db.database`. Retained until Phase 5 dead code pruning. |
| `frontend/src/components/ActionCenter/*` | **RETAINED** | Complete UI components retained for dashboard integration in Phase 5. |

---

## 5. Configuration & Reference Updates

1. **`pyproject.toml`**:
   - Added canonical `[tool.pytest.ini_options]`:
     ```toml
     [tool.pytest.ini_options]
     asyncio_mode = "auto"
     testpaths = ["tests"]
     python_files = ["test_*.py"]
     addopts = "-v --tb=short"
     filterwarnings = [
         "ignore:.*'HTTP_422_UNPROCESSABLE_ENTITY' is deprecated.*:starlette.exceptions.StarletteDeprecationWarning",
         "ignore:.*Setting per-request cookies.*:DeprecationWarning",
     ]
     ```
2. **`frontend/eslint.config.mjs`**:
   - Added `"scripts/**"` to `globalIgnores` so moved automation scripts do not trigger application linting errors.
3. **`.gitignore`**:
   - Consolidated into canonical root `.gitignore`.
   - Explicitly covers `.venv/`, `node_modules/`, `storage/recordings/`, `*.db`, `test.db`, `__pycache__/`, `*.tsbuildinfo`, while preserving `.env.example` and `.env.prod.example`.
4. **Documentation Links**:
   - Updated hardcoded file links in `walkthrough.md`, `docs/29_SRE_SLOS_AND_ALERTING.md`, `docs/32_AI_PRODUCTION_SAFETY.md`, `docs/37_PRODUCT_METRICS.md`, and `docs/42_PUBLIC_LAUNCH_GATES.md` from `Legal-Case-Companion-main/Legal-Case-Companion-main` to `Legal-Case-Companion-main`.

---

## 6. Post-Normalization Verification Results

| Check | Target Scope | Command | Result | Metrics |
| :--- | :--- | :--- | :---: | :--- |
| **Python Syntax** | All Python modules | `python -m compileall -q app tests scripts migrations` | **PASSED** | 0 syntax errors |
| **Pytest Collection** | Test suite | `python -m pytest --collect-only` | **PASSED** | **749 tests collected in 0.93s** (0 warnings) |
| **Targeted Unit Test** | Health & App | `python -m pytest tests/unit/test_app.py` | **PASSED** | **7/7 passed in 4.72s** |
| **Backend Lint** | App & Tests | `python -m ruff check app tests` | **PASSED** | **All checks passed! (0 errors)** |
| **Frontend TypeScript**| Next.js Client | `npx tsc --noEmit` | **PASSED** | **0 type errors** |
| **Frontend Build** | Next.js Production | `npm run build` | **PASSED** | **36 routes compiled & optimized** |
| **Git Tree Cleanliness**| Repository Root | `git status -s` | **PASSED** | Clean renames, zero orphan files |

---

## 7. Remaining Structural & Baseline Issues for Next Phases

1. **48 Backend Mypy Type Errors**: Scheduled for repair in Phase 2.
2. **3 Frontend ESLint Violations (`prefer-const`)**: Scheduled for repair in Phase 2.
3. **9 Ruff Closure Variable Binding Warnings in `scripts/load_test_phase_10.py`**: Scheduled for repair in Phase 2.
4. **Missing Method `VideoMeetingService.cleanup_stale_meetings`**: Scheduled for implementation and unit test greening in Phase 3.
5. **Unhooked Defensive Services**: Scheduled for integration in Phase 3.
