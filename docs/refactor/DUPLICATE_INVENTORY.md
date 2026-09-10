# Duplicate & Redundancy Inventory: Legal Case Companion (LCC)

**Auditor**: Antigravity Engineering  
**Scope**: Cryptographic hash duplicates, duplicate implementations, duplicate configs, OpenAPI drift, and candidate deletion analysis.

---

## 1. Identical Duplicate Files (SHA-256 Match)

| SHA-256 Hash | Duplicate File Paths | File Size | Description |
| :--- | :--- | :--- | :--- |
| `de9b7654f15a6b0c...` | 1. `LegalCaseCompanion.exe` (Root)<br>2. `Legal-Case-Companion-main/LegalCaseCompanion.exe` (Nested) | 77,824 B | Windows C# Desktop launcher binary compiled from `scripts/launcher.cs`. Committed in two separate directories. |
| `987ae8a6fd61726a...` | 1. `LegalCaseCompanion.ico`<br>2. `app.ico` | 61,554 B | High-resolution application icon. Exactly identical content under two different names in project root. |
| `87a324fd9de4d0b1...` | 1. `openapi.json` (Root)<br>2. `docs/openapi.json` | 806,524 B | Static snapshot of FastAPI OpenAPI specification. Exactly identical 806 KB file duplicated in docs. |
| `866552b553655106...` | 1. `frontend/public/lcc-logo.png`<br>2. `frontend/public/logo.png` | 16,929 B | Platform branding logo in frontend public assets. Identical image committed under two filenames. |
| `b846031c238b97d1...` | 1. `storage/recordings/01a07569.../recording_test.webm`<br>2. `storage/recordings/01a0756d.../recording_test.webm`<br>3. `storage/recordings/01a0769d.../recording_test.webm` | 443 B | Dummy WebM recording files generated during video recording unit tests. |
| `f9c02460a5e840d2...` | 55 identical files in `storage/recordings/consultations/*/*.webm` | 443 B | Ephemeral dummy video chunks created by test fixtures. |

---

## 2. Near-Duplicates & Alternative Implementations

### 2.1 Desktop Launcher Scripts
- **Outer File**: `Run-LegalCaseCompanion.bat` (348 bytes)
  - Checks if `LegalCaseCompanion.exe` is in current folder; if not, checks `Legal-Case-Companion-main\LegalCaseCompanion.exe`.
- **Inner File**: `Legal-Case-Companion-main/Run-LegalCaseCompanion.bat` (206 bytes)
  - Checks only current folder.
- *Analysis*: The outer batch file is a wrapper created because the repository has an outer container folder.

### 2.2 Storage Providers (`app/core/storage.py`)
- `LocalStorageProvider`: Writes uploads to local disk folder (`storage/`).
- `S3StorageProvider`: Streams uploads to AWS S3 bucket with KMS encryption.
- `MockStorageProvider`: In-memory byte store for unit test suites.
- *Analysis*: Clean strategy pattern implementation. Keep all three, governed by `STORAGE_PROVIDER` setting.

### 2.3 Video Meeting Providers (`app/services/video_meeting_service.py`)
- `InternalWebRTCMeetingProvider`: P2P WebRTC with STUN/TURN (RFC 5766 CoTURN HMAC credentials).
- `LiveKitMeetingProvider`: SFU WebRTC meeting token generator for production scale.
- `MockVideoMeetingProvider`: Mock provider for test harnesses.
- *Analysis*: Essential tiered fallback architecture. Production requires `LiveKitMeetingProvider`, local testing uses `InternalWebRTCMeetingProvider`.

### 2.4 Recording Storage Providers (`app/services/recording_storage.py`)
- `LocalRecordingStorageProvider`
- `S3RecordingStorageProvider`
- `MockRecordingStorageProvider`
- *Analysis*: Duplicates logic from `app/core/storage.py`. Candidate for consolidation into a single unified storage abstraction.

### 2.5 Email Providers (`app/services/email_service.py`)
- `SendGridEmailService`
- `ConsoleEmailService`
- `MockEmailService`
- *Analysis*: Standard provider pattern. Governed by `EMAIL_PROVIDER`.

---

## 3. Duplicate Configuration

### 3.1 `pytest.ini` vs `pyproject.toml`
- **Issue**:
  - `pyproject.toml` contains `[tool.pytest.ini_options]` (`asyncio_mode = "auto"`, `testpaths = ["tests"]`).
  - `pytest.ini` defines `[pytest]` with additional `addopts = -v --tb=short` and `filterwarnings`.
  - Pytest prints warning on every invocation: `configfile: pytest.ini (WARNING: ignoring pytest config in pyproject.toml!)`.
- **Action**: Merge `addopts` and `filterwarnings` into `pyproject.toml`, deprecating `pytest.ini`.

### 3.2 Environment Templates
- `.env.example`: 4,949 bytes (Comprehensive development template with comments).
- `.env.prod.example`: 3,907 bytes (Hardened production deployment template for Render/AWS).
- `.env`: 1,923 bytes (Active local developer environment configuration).
- *Status*: Valid separation of development vs production configuration profiles.

### 3.3 Lockfiles
- `uv.lock` (600,066 bytes): Authoritative current dependency resolution lockfile.
- `uv.lock.local` (505,155 bytes): Stale local backup snapshot committed on Sep 1, 2026.
- *Status*: `uv.lock.local` is an orphaned legacy file.

---

## 4. Duplicate OpenAPI Specifications

- **Location 1**: `openapi.json` in project root (806,524 bytes).
- **Location 2**: `docs/openapi.json` (806,524 bytes) — **Exact duplicate**.
- **Location 3**: Live dynamically generated schema at `GET /api/v1/openapi.json`.
- *Issue*: Static JSON files drift as routes and schemas evolve. Committing two identical 800 KB JSON files causes repository bloat.
- *Recommendation*: Keep `docs/openapi.json` as documentation reference; delete root `openapi.json` or generate dynamically in CI.

---

## 5. Candidate Action Matrix (KEEP / MERGE / MOVE / DELETE)

| Candidate File / Target | Proposed Action | Classification | Safe to Delete? | Justification & Prerequisites |
| :--- | :---: | :--- | :---: | :--- |
| `LegalCaseCompanion.exe` (Root) | **DELETE** | Redundant Binary | **SAFE** | Duplicate copy exists in project root. Pre-compiled binaries should ideally be distributed via GitHub Releases, not checked into source control. |
| `LegalCaseCompanion.exe` (Inner) | **MOVE** | Binary Artifact | **CONDITIONAL** | Should be moved to build releases or generated on-demand via `scripts/build_launcher.bat`. Safe if build script is verified. |
| `Run-LegalCaseCompanion.bat` (Root) | **DELETE** | Outer Wrapper | **SAFE** | Shell wrapper for outer directory structure. Once project hierarchy is flattened, this is obsolete. |
| `app.ico` | **DELETE** | Redundant Asset | **SAFE** | Identical SHA-256 to `LegalCaseCompanion.ico`. All references can use `LegalCaseCompanion.ico`. |
| `openapi.json` (Root) | **DELETE** | Duplicate Artifact | **SAFE** | Exact duplicate of `docs/openapi.json`. Application serves live OpenAPI dynamically from FastAPI. |
| `docs/openapi.json` | **KEEP** | Documentation Spec | **SAFE TO KEEP** | Useful for offline client SDK generators and API contract audits. |
| `frontend/public/logo.png` | **DELETE** | Duplicate Asset | **SAFE** | Identical SHA-256 to `frontend/public/lcc-logo.png`. Update any imports referencing `logo.png` to `lcc-logo.png`. |
| `uv.lock.local` | **DELETE** | Stale Lockfile | **SAFE** | Superseded by authoritative `uv.lock`. Zero tools consume `uv.lock.local`. |
| `Rental_Agreement_Evidence.pdf` | **MOVE** | Root Fixture | **UNSAFE TO DELETE** | Referenced by `tests/integration/test_document_security_and_websocket_signaling.py` and `tests/pilot/test_phase_xix_pilot_execution.py`. **Must MOVE to `tests/fixtures/` and update test path references first.** |
| `Rental_Agreement_Evidence.txt` | **MOVE** | Root Fixture | **UNSAFE TO DELETE** | Same as above. Referenced by integration test suites. |
| `project_report.md` (Outer root) | **MOVE** | Stale Documentation | **SAFE TO MOVE** | 74 KB audit report from earlier development cycle. Move to `docs/archive/` or delete once historical findings are preserved. |
| `app/db/session.py` | **DELETE** | Legacy Alias | **SAFE** | Pure re-export (`__all__ = ["SessionLocal", "engine", "get_db"]`). Zero callers in `app/` or `tests/`. Everyone uses `app.db.database`. |
| `pytest.ini` | **MERGE** | Duplicate Config | **SAFE AFTER MERGE** | Safe to delete only after migrating `addopts` and `filterwarnings` into `pyproject.toml`. |
| `storage/recordings/*.webm` | **DELETE** | Ephemeral Test Data | **SAFE** | 304 test webm files (443 bytes each) left behind by test runs. Git ignored, but taking up local storage. |
| `test.db` | **DELETE / RESET**| Ephemeral Local DB | **SAFE** | 2.2 MB SQLite database. Recreated automatically on boot by `lifespan` handler. |
| `scripts/load_test_phase_10.py` | **KEEP & FIX** | Utility Script | **DO NOT DELETE** | Load testing harness with 9 ruff closure warnings (`B023`). Fix closure variables. |
| `frontend/*.mjs` test scripts | **MOVE** | Standalone Test Scripts | **SAFE TO MOVE** | 5 Puppeteer scripts cluttering `frontend/` root. Move to `frontend/scripts/` or `tests/e2e/`. |
| `frontend/patch-fs.js` | **EVALUATE** | Build Monkey-Patch | **UNSAFE UNTIL TESTED**| Node.js patch script. Must verify if Next.js 16 webpack build succeeds without it. |
| `ActionCenter.tsx` | **MERGE** | Unused Component | **DO NOT DELETE** | Functional UI component for dashboard action items. Integrate into `/dashboard/page.tsx`. |
| `MatterBriefCard.tsx` | **MERGE** | Unused Component | **DO NOT DELETE** | Functional intake briefing card. Integrate into `/cases/[caseId]/page.tsx`. |
| `MatterParticipantsPanel.tsx`| **MERGE** | Unused Component | **DO NOT DELETE** | Case participants sidebar. Integrate into case collaboration view. |
| `MatterRequestsBoard.tsx` | **MERGE** | Unused Component | **DO NOT DELETE** | Kanban board for client document requests. Integrate into `/documents` or `/cases`. |
| `IntelligenceCenter.tsx` | **MERGE** | Unused Component | **DO NOT DELETE** | Case intelligence viewer. Integrate into case copilot tab. |

---

## 6. Safety Protocol for Candidate Deletion Phase

Prior to executing any file deletions in subsequent refactoring phases, the following safety gates must be passed:

1. **Grep Pre-Flight**: Run recursive pattern search for the exact filename, relative import, and symbol across `app/`, `frontend/`, `tests/`, `scripts/`, `docs/`, `Dockerfile`, and `render.yaml`.
2. **Atomic Git Commit**: Perform file removals in dedicated, single-purpose commits separate from functional code changes.
3. **Full Test Suite Run**: Run `pytest` and `npm run build` after each removal batch to guarantee zero regressions.
