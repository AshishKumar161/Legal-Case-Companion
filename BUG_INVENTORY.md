# Legal Case Companion (LCC) — Prioritized Bug Inventory

**Date**: November 2, 2026  
**Auditor**: Principal Backend & Security Engineer  
**Audit Standard**: Confirmed defects backed by reproduction steps, source references, code-level remediations, and verified regression test suites.

---

## Executive Summary of Bug Resolution

| Bug ID | Severity | Component | Status | Verification Gate |
| :--- | :--- | :--- | :--- | :--- |
| **BUG-001** | **Critical** | Google OAuth JWT Verification | **RESOLVED & HARDENED** | `tests/unit/test_google_oauth_token_validation.py` (9/9 passed) |
| **BUG-002** | **Critical** | Database Migrations Lifecycle | **RESOLVED & HARDENED** | `scripts/test_migrations_lifecycle.py` (PostgreSQL + SQLite passed) |
| **BUG-003** | **High** | Document Security & Quarantine | **RESOLVED & HARDENED** | `tests/security/test_direct_upload_security.py` (16/16 passed) |
| **BUG-004** | **High** | OpenAPI Schema Contract Drift | **RESOLVED & HARDENED** | `scripts/verify_openapi_contract.py` (333 paths / 392 ops 100% match) |
| **BUG-005** | **Medium** | Pytest Configuration (`pythonpath`) | **RESOLVED & HARDENED** | `pyproject.toml` + clean `pytest -q` execution |
| **BUG-006** | **Medium** | Vector Retrieval Performance | **RESOLVED & HARDENED** | `scripts/benchmark_vector_retrieval.py` (3.75x speedup, 78.7% mem reduction) |
| **BUG-007** | **Low** | Webhook Config Disclosure | **RESOLVED & HARDENED** | `tests/security/test_webhook_security.py` (3/3 passed, safe 503/401 errors) |

---

## BUG-001: Excessive Clock Skew Leeway Allows Expired Google OAuth ID Tokens

- **Bug ID**: `BUG-001`
- **File and Function**: `app/domain/auth/google_oauth_service.py` -> `GoogleOAuthService.validate_id_token`
- **Severity**: **Critical**
- **Original Root Cause**:
  `jwt.decode(...)` specified `leeway=300` (5 minutes = 300 seconds), allowing expired Google OAuth tokens to be accepted up to 300 seconds post-expiry. Furthermore, if `GOOGLE_CLIENT_ID` was unconfigured, audience validation was bypassed.
- **Implemented Fix**:
  - Enforced fail-closed behavior: raises `ConfigurationError` immediately if `GOOGLE_CLIENT_ID` is missing when Google auth is active.
  - Enforced `verify_aud=True` and `audience=client_id` unconditionally.
  - Set clock skew tolerance to strict `leeway=0` and enabled `verify_iat=True`.
  - Sanitized logging and shielded internal exception details from leaking to clients.
- **Verification & Regression Tests**:
  - `tests/unit/test_google_oauth_token_validation.py` (9 passed)
  - `tests/integration/test_auth_stabilization.py` (13 passed)
- **Final Status**: **COMPLETED & VERIFIED**

---

## BUG-002: Duplicate Index Creation and Postgres Type Collisions in Alembic Migrations

- **Bug ID**: `BUG-002`
- **File and Function**: `migrations/versions/afbdf4813237_sync_remaining_model_indexes_and_.py` & related migration revisions
- **Severity**: **Critical**
- **Original Root Cause**:
  Revision `afbdf4813237` attempted to re-create indexes on `lawyer_verifications` that were already present in `e4f8db885ba5`. Furthermore, PostgreSQL-specific migration execution suffered from duplicate enum creation (`notificationtype`, `advocatedocumenttype`), boolean defaults specified as integer `0`, UUID foreign key type mismatches (`sa.CHAR(32)` vs `sa.Uuid()`), and VARCHAR-to-ENUM column casts in `25500e9a54c3`.
- **Implemented Fix**:
  - Fixed duplicate index creation with `_safe_create_index` and safe drops in `afbdf4813237`.
  - Configured PostgreSQL enum variants with `create_type=False` and `checkfirst=True` in `5c8a1b2e3f4d`, `u1a2b3c4d5e6`, and `w1a2b3c4d5e6`.
  - Corrected boolean defaults to `sa.false()` in `b2c3d4e5f6a1`, `c3d4e5f6a1b2`, `f1a2b3c4d5e6`, and `g1a2b3c4d5e6`.
  - Replaced incompatible `sa.CHAR(32)` foreign keys with `sa.Uuid()`.
  - Added clean transactional type conversion for 16 VARCHAR columns in `25500e9a54c3`.
  - Extended `scripts/test_migrations_lifecycle.py` to run both live PostgreSQL container testing and SQLite validation.
- **Verification & Regression Tests**:
  - `python scripts/test_migrations_lifecycle.py` (Exit code 0: Clean fresh upgrade -> downgrade past drift -> legacy data insertion -> re-upgrade to head -> data preserved).
- **Final Status**: **COMPLETED & VERIFIED**

---

## BUG-003: Direct Case Document Upload Bypasses Magic-Byte Signature Validation and Malware Quarantine

- **Bug ID**: `BUG-003`
- **File and Function**: `app/api/v1/documents.py` -> `upload_case_document`
- **Severity**: **High**
- **Original Root Cause**:
  Direct multipart upload accepted raw files and immediately marked them `SAFE` and `READY`, bypassing magic-byte validation, quarantine states, and ClamAV scanning. Quarantined documents lacked bounded retry and failure monitoring, and preview/chunk endpoints allowed unauthorized reading.
- **Implemented Fix**:
  - Strict file extension validation against `EXTENSION_TO_MIME`.
  - Cryptographic magic-byte signature validation via `validate_file_magic_bytes`.
  - Ingestion initially in `DocumentSecurityStatus.QUARANTINED` and `DocumentProcessingStatus.PENDING`.
  - Synchronous scanner invocation with fail-closed behavior on scanner unavailability.
  - Implemented `ScannerService.retry_quarantined_documents` with attempt tracking, bounded retries (default 3), and failure monitoring (`DOCUMENT_SCAN_RETRY_EXHAUSTED` audit events).
  - Hardened `get_document_pages` and `get_document_chunks` to strictly reject non-SAFE documents with `AuthorizationError`.
  - Enforced confidentiality authorization restricting confidential documents from standard case viewers.
- **Verification & Regression Tests**:
  - `tests/security/test_direct_upload_security.py` (16 passed)
- **Final Status**: **COMPLETED & VERIFIED**

---

## BUG-004: OpenAPI Schema Contract Drift Breaks CI/CD Parity Gate

- **Bug ID**: `BUG-004`
- **File and Function**: `docs/openapi.json` vs `app/main.py`
- **Severity**: **High**
- **Original Root Cause**:
  Live API contained 333 paths and 392 operations due to newly added Legal AI Advisor endpoints (`/api/v1/advisor/chat`, `/api/v1/advisor/sessions`, etc.), while `docs/openapi.json` contained 329 paths and 388 operations.
- **Implemented Fix**:
  - Regenerated canonical `docs/openapi.json` using the official `scripts/generate_openapi.py` exporter.
  - Updated `scripts/verify_openapi_contract.py` baseline assertions to 333 paths / 392 operations.
  - Created automated regression test `tests/integration/test_openapi_contract_parity.py` with ephemeral test route filtering.
- **Verification & Regression Tests**:
  - `python scripts/verify_openapi_contract.py` (Exit code 0: 333 paths / 392 operations 100% matched).
  - `tests/integration/test_openapi_contract_parity.py` (Passed).
- **Final Status**: **COMPLETED & VERIFIED**

---

## BUG-005: Pytest Configuration Missing `pythonpath` Setting in `pyproject.toml`

- **Bug ID**: `BUG-005`
- **File and Function**: `pyproject.toml` -> `[tool.pytest.ini_options]`
- **Severity**: **Medium**
- **Original Root Cause**:
  `pyproject.toml` did not configure `pythonpath = ["."]`, causing `ModuleNotFoundError: No module named 'app'` when running pytest without manually exporting `PYTHONPATH=.`.
- **Implemented Fix**:
  - Configured `pythonpath = ["."]` in `pyproject.toml` under `[tool.pytest.ini_options]`.
  - Filtered third-party `slowapi` deprecation warning (`asyncio.iscoroutinefunction`).
- **Verification & Regression Tests**:
  - `env -u PYTHONPATH .venv/bin/python -m pytest tests/unit/test_google_oauth_token_validation.py` (Passed with 0 warnings).
- **Final Status**: **COMPLETED & VERIFIED**

---

## BUG-006: In-Memory Cosine Similarity Calculation in RAG Retrieval Causes Memory & CPU Scaling Bottleneck

- **Bug ID**: `BUG-006`
- **File and Function**: `app/domain/ai/retrieval_service.py` -> `RetrievalService.search_case_evidence`
- **Severity**: **Medium**
- **Original Root Cause**:
  All chunks for a case were fetched as full SQLAlchemy ORM objects into application memory, followed by pure Python loops computing cosine similarity on float arrays.
- **Implemented Fix**:
  - Replaced full ORM entity loading with column-level projected queries (`with_entities`), eliminating ORM instance overhead.
  - Implemented database-side filtering (`case_id`, `deleted_at IS NULL`, `security_status == SAFE`, `embedding IS NOT NULL`).
  - Added bounded candidate retrieval window (`LIMIT max_candidates`) preventing out-of-memory errors on large litigation matters.
  - Implemented high-performance vectorized cosine similarity via NumPy BLAS (`batch_cosine_similarity`), reducing vector calculation time by over 70%.
  - Authored benchmark script `scripts/benchmark_vector_retrieval.py` testing against live PostgreSQL database.
- **Verification & Regression Tests**:
  - `scripts/benchmark_vector_retrieval.py` (Latency reduced from 137.60ms to 36.64ms [3.75x speedup]; Memory reduced from 6533.92 KB to 1389.69 KB [78.7% reduction]; Score parity verified).
  - `tests/performance/test_retrieval_and_authority_benchmarks.py` (Passed).
- **Final Status**: **COMPLETED & VERIFIED**

---

## BUG-007: Webhook Secret Absence Discloses Internal Configuration State

- **Bug ID**: `BUG-007`
- **File and Function**: `app/api/v1/webhooks.py` -> `aws_malware_webhook`
- **Severity**: **Low**
- **Original Root Cause**:
  When `AWS_WEBHOOK_SECRET` was unconfigured, the endpoint returned HTTP 500 with `"Webhook secret not configured"`, leaking internal configuration variables to unauthenticated callers.
- **Implemented Fix**:
  - Log internal diagnostic error securely (`logger.error("AWS_WEBHOOK_SECRET is not configured...")`).
  - Return safe external error: HTTP 503 Service Unavailable (`{"detail": "Webhook service unavailable"}`).
  - Enforced constant-time header comparison with `secrets.compare_digest`.
  - Created dedicated security regression test suite `tests/security/test_webhook_security.py`.
- **Verification & Regression Tests**:
  - `tests/security/test_webhook_security.py` (3 passed).
- **Final Status**: **COMPLETED & VERIFIED**
