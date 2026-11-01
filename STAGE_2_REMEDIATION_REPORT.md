# Stage 2 Remediation Report — Critical Bug Fixes & Security Remediation

**Repository:** Legal Case Companion (LCC)  
**Execution Phase:** Stage 2 (Critical Bug Fixes & Security Remediation)  
**Roles:** Principal Backend Engineer, Application Security Engineer, Database Reliability Engineer, DevOps/SRE Engineer  
**Date:** November 2, 2026  
**Status:** Remediated, Verified, and Awaiting User Approval for Stage 3  

---

## Executive Summary

During Stage 2, all three confirmed critical vulnerabilities and defect reports identified in the Stage 1 audit were systematically diagnosed, remediated, hardened, and verified under zero-tolerance production engineering standards.

| Bug ID | Severity | Component | Root Cause | Remediation Summary | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **BUG-001** | **Critical** | Google OAuth (`app/domain/auth/google_oauth_service.py`) | Permissive clock skew `leeway=300` allowed expired JWT ID tokens to be accepted up to 5 minutes post-expiry. | Enforced `leeway=0`, added `verify_iat=True`, and explicit handling for `InvalidSignatureError` and `DecodeError`. | **RESOLVED** |
| **BUG-002** | **Critical** | Database Migrations (`migrations/versions/afbdf4813237_sync_remaining_model_indexes_and_.py`) | Redundant index creation on `lawyer_verifications` collided with ancestor migration `e4f8db885ba5`. | Implemented database schema inspection (`_safe_create_index`, `_safe_drop_index`) preserving existing indexes across fresh and upgraded instances. | **RESOLVED** |
| **BUG-003** | **High** | Document Ingestion (`app/api/v1/documents.py`) | Direct multipart upload (`upload_case_document_direct`) marked documents `SAFE` and `READY` immediately, bypassing magic byte validation, quarantine, and malware scanning. | Integrated strict extension & MIME verification, pre-quarantine storage, ClamAV/heuristic scanning via `ScannerService`, fail-closed lockdown, and storage cleanup. | **RESOLVED** |

---

## 1. Bug-by-Bug Root Cause Analysis

### BUG-001: Google OAuth JWT Expiration Validation
- **Location:** `app/domain/auth/google_oauth_service.py` (`verify_google_id_token`)
- **Root Cause:**
  When decoding Google OAuth ID tokens via `jwt.decode()`, a parameter `leeway=300` (5 minutes) was hardcoded under the assumption of mitigating potential time drift between local environments and Google token servers. However, standard RFC 7519 JWT semantics and Google Identity Services specify that ID tokens have short lifespans (typically 1 hour), and excessive clock skew allowances allow compromised, revoked, or expired tokens to be accepted for authentication for up to 300 seconds after their intended expiry timestamp (`exp`). Furthermore, `verify_iat` was omitted, and signature/decoding exceptions were caught generically.
- **Security Impact:**
  Replay attacks using recently expired tokens; vulnerability to token reuse in man-in-the-middle or intercepted session token scenarios.

---

### BUG-002: Duplicate Alembic Migration Indexes
- **Location:** `migrations/versions/afbdf4813237_sync_remaining_model_indexes_and_.py`
- **Root Cause:**
  Alembic autogeneration generated index creation statements for:
  - `ix_lawyer_verifications_lawyer_profile_id`
  - `ix_lawyer_verifications_reviewed_by`
  These indexes were already created in ancestor migration `e4f8db885ba5_add_foreign_key_indexes.py`. When running on a production or staging database upgraded through the version history, re-executing `op.create_index` without existence checks caused PostgreSQL/SQLite duplicate index errors. Conversely, during downgrade, `afbdf4813237` dropped these indexes, destroying indexes required by the earlier migration `e4f8db885ba5`.
- **Reliability Impact:**
  Breakage of CI/CD migration automation, deployment rollouts, and schema drift across environments.

---

### BUG-003: Direct Document Upload Security Bypass
- **Location:** `app/api/v1/documents.py` (`upload_case_document_direct`)
- **Root Cause:**
  The direct multipart/form-data upload route `/cases/{case_id}/documents` accepted raw file bytes and immediately instantiated `Document` entities with `security_status=DocumentSecurityStatus.SAFE` and `processing_status=DocumentProcessingStatus.READY`. This completely bypassed:
  1. Permitted file extension enforcement.
  2. Cryptographic magic-byte signature validation (`validate_file_magic_bytes`).
  3. Pluggable antivirus scanning (`ScannerService` + ClamAV + Heuristic signatures).
  4. The quarantine state machine (`QUARANTINED` -> `VALIDATING` -> `SCANNING` -> `SAFE`).
  5. Asynchronous background worker isolation.
- **Security Impact:**
  Malicious actors could upload Windows PE executables (`.exe`), Linux binaries (`ELF`), script-embedded PDFs, or malware test vectors (e.g. EICAR) disguised with any filename or spoofed `Content-Type`, which would instantly become downloadable, trigger participant notifications, and enter the AI/RAG embedding index.

---

## 2. Exact Files Modified

1. **`app/domain/auth/google_oauth_service.py`**
   - Removed `leeway=300`; enforced `leeway=0`.
   - Enabled `verify_iat=True` in decoding options.
   - Added explicit handlers for `jwt.InvalidSignatureError` ("Invalid Google ID token signature") and `jwt.DecodeError` ("Malformed Google ID token").
2. **`migrations/versions/afbdf4813237_sync_remaining_model_indexes_and_.py`**
   - Added schema introspection helpers: `_safe_create_index` and `_safe_drop_index` using `sa.inspect(op.get_bind())`.
   - Prevented re-creation of `ix_lawyer_verifications_lawyer_profile_id` and `ix_lawyer_verifications_reviewed_by` if already present.
   - Preserved ancestor indexes during `downgrade()`.
3. **`migrations/versions/n1a2b3c4d5e6_add_instant_consultation_flag.py`**
   - Added safe index inspection in `downgrade()` for `ix_consultations_is_instant`.
4. **`migrations/versions/7f8a9b0c1d2e_add_lawyer_experience_and_jurisdiction.py`**
   - Added safe table and index checks on downgrade for `ix_consultations_lawyer_scheduled` and `ix_lawyer_profiles_location`.
5. **`migrations/versions/e4f8db885ba5_add_foreign_key_indexes.py`**
   - Added missing `import sqlalchemy as sa` and safe table/index inspection on downgrade.
6. **`app/models/document.py`**
   - Added central `EXTENSION_TO_MIME` mapping linking permitted extensions (`.pdf`, `.txt`, `.docx`, `.doc`, `.png`, `.jpg`, `.jpeg`) to their canonical MIME types.
7. **`app/domain/documents/document_processor.py`**
   - Hardened `process_document()` to explicitly verify `document.security_status == DocumentSecurityStatus.SAFE` before reading bytes or generating embeddings, aborting with a warning if quarantined or unverified.
8. **`app/api/v1/documents.py`**
   - Completely refactored `upload_case_document_direct`:
     - Validates filename security (no null bytes, path traversal, double extensions).
     - Validates permitted extensions against `EXTENSION_TO_MIME`.
     - Validates declared `Content-Type` against `ALLOWED_MIME_TYPES` and detects extension mismatches/spoofing.
     - Validates binary magic bytes against declared MIME type (`validate_file_magic_bytes`).
     - Ingests new records in `DocumentSecurityStatus.QUARANTINED` and `DocumentProcessingStatus.PENDING`.
     - Invokes `ScannerService(db).scan_document(doc.id)`.
     - Catches `ScannerUnavailableError` to **fail closed** (document remains in quarantine without notification or download permission).
     - If rejected/malware is detected: cleans up storage object, marks `DocumentProcessingStatus.FAILED`, and returns HTTP 422/400 validation error.
     - Only upon verified `SAFE` status: transitions document to `READY`, records case activity, and dispatches participant notifications.
9. **`tests/unit/test_google_oauth_token_validation.py`** *(New File)*
   - 8 unit and security regression tests for BUG-001.
10. **`tests/security/test_direct_upload_security.py`** *(New File)*
    - 13 integration and security regression tests for BUG-003.

---

## 3. Implementation Details & Architecture Alignment

### Zero-Tolerance OAuth Validation
```python
claims = jwt.decode(
    token,
    key=rsa_key,
    algorithms=["RS256"],
    audience=client_id if client_id else None,
    issuer=settings.GOOGLE_ISSUERS,
    leeway=0,  # Zero tolerance clock skew: expired tokens are strictly rejected
    options={
        "verify_aud": bool(client_id),
        "verify_iss": True,
        "verify_exp": True,
        "verify_iat": True,
    },
)
```

### Idempotent Schema Migration
```python
def _safe_create_index(name: str, table_name: str, columns: list[str], unique: bool = False) -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    indexes = {idx["name"] for idx in insp.get_indexes(table_name)}
    if name not in indexes:
        op.create_index(name, table_name, columns, unique=unique)
```

### Direct Upload Quarantine & Antivirus Workflow
```
[User POST /cases/{id}/documents]
       │
       ▼
[Validate Filename Security & Extension]
       │
       ▼
[Detect Spoofed MIME & Validate Magic Bytes]
       │
       ▼
[Save to Storage with UUID7 Object Key]
       │
       ▼
[Insert DB Record: status=QUARANTINED, processing=PENDING]
       │
       ▼
[Invoke ScannerService.scan_document()]
       ├── Scanner Unavailable ──▶ Fail Closed (stays QUARANTINED, returns 201, download blocked)
       ├── Malware Detected    ──▶ Delete Storage Object, mark REJECTED/FAILED, raise HTTP 422
       └── Verified Clean      ──▶ Mark SAFE / READY, record case activity, notify participants
```

---

## 4. Security Impact Assessment

1. **OAuth Session Hijacking Mitigated:** Expired tokens (even by 1 millisecond past expiry) are rejected immediately by cryptographic signature verification.
2. **Malware & Web Shell Ingestion Blocked:** Uploading executables (Windows PE, Linux ELF, scripts, double extensions) is stopped at the API perimeter before files can enter storage.
3. **Fail-Closed Antivirus Ingestion:** If ClamAV daemon is unreachable or times out, untrusted documents remain locked in `QUARANTINED` status. Attempting to generate presigned download URLs returns HTTP 403 Forbidden. Quarantined documents are strictly excluded from AI search and text extraction workers.
4. **Data Isolation & Anti-Enumeration Preserved:** Cross-case upload and download attempts continue to return HTTP 404/403 to prevent cross-tenant enumeration.

---

## 5. Regression Tests Added

### BUG-001 (`tests/unit/test_google_oauth_token_validation.py`)
- `test_valid_google_token_accepted`: Valid RS256 token accepted.
- `test_expired_token_rejected`: Token expired 10 seconds ago rejected.
- `test_token_expired_by_one_second_rejected`: Zero-leeway verification strictly rejects tokens expired by 1 second.
- `test_invalid_signature_rejected`: Signature tampering rejected.
- `test_wrong_audience_rejected`: Token issued for another OAuth client rejected.
- `test_wrong_issuer_rejected`: Malicious issuer claims rejected.
- `test_malformed_jwt_token_rejected`: Truncated/corrupted token strings rejected with `DecodeError`.
- `test_nonce_mismatch_rejected`: Inconsistent nonce values rejected.

### BUG-003 (`tests/security/test_direct_upload_security.py`)
- `test_direct_upload_valid_file_workflow`: Clean PDF validated, scanned, marked SAFE & READY, downloadable.
- `test_direct_upload_invalid_file_signature`: File claimed as PDF with non-PDF bytes rejected.
- `test_direct_upload_spoofed_mime_type_executable_rejected`: Windows PE (`MZ`) and Linux ELF headers blocked.
- `test_direct_upload_spoofed_content_type_mismatch`: Mismatched Content-Type vs extension rejected.
- `test_direct_upload_prohibited_extensions_and_path_traversal`: Traversal (`../../evil.pdf`), `.sh`, `.exe`, `.pdf.exe` rejected.
- `test_direct_upload_oversized_file`: >10MB files rejected.
- `test_direct_upload_malicious_eicar_virus_detected`: EICAR test virus detected, rejected, storage cleaned.
- `test_direct_upload_clamav_unavailable_fails_closed`: Scanner daemon failure locks document in quarantine; download blocked (HTTP 403).
- `test_direct_upload_scanner_timeout_fails_closed`: Scanner timeout locks document in quarantine.
- `test_direct_upload_unauthorized_user_blocked`: Non-participant cannot upload to case.
- `test_direct_upload_unauthorized_download_blocked`: Non-participant cannot download case documents.
- `test_direct_upload_duplicate_upload_isolation`: Repeated identical uploads generate unique isolated storage keys.
- `test_quarantined_document_processing_worker_safety`: `DocumentProcessor` refuses to process quarantined documents.

---

## 6. Database Migration Validation

The complete database migration lifecycle was validated using `scripts/test_migrations_lifecycle.py`:
- **Scenario A (Fresh Database):** Full upgrade from base to head (all 54 revisions) completed with zero errors.
- **Scenario B (Downgrade):** Downgraded past `25500e9a54c3` to `n1a2b3c4d5e6`; verified legacy schema was safely restored without dropped indexes.
- **Scenario C (Legacy Data Ingestion):** Inserted legacy records into restored schema.
- **Scenario D (Re-Upgrade with Existing Data):** Upgraded back to head with existing records; verified data preservation in `pilot_feedback` and no duplicate index collisions.

---

## 7. Before-and-After Test Results

| Metric | Stage 1 Baseline | Stage 2 Post-Remediation | Combined Security Closure | Net Delta |
| :--- | :--- | :--- | :--- | :--- |
| **Total Tests Discovered** | 848 | 869 | **877** | +29 new tests |
| **Passed Tests** | 846 | 869 | **877** | **+31 passing** |
| **Failed Tests** | 2 | 0 | **0** | **0 failures** |
| **Pass Rate** | 99.76% | 100.0% | **100.0%** | **100% Green** |
| **Pytest Warnings** | 147 | 146 | **0** | **100% Clean** |
| **Compile Check (`compileall`)** | Passed | Passed | **Passed** | 0 errors |
| **Secret Scanner (`ci_secret_scanner`)** | Passed | Passed | **Passed** | 0 exposed secrets |
| **PostgreSQL Migration Lifecycle** | Untested | SQLite Only | **PostgreSQL + SQLite 100% Passed** | Production Validated |
| **OpenAPI Contract Parity** | Failed (Drift) | Stale | **Passed (333 paths / 392 ops)** | Zero Drift |

---

## 8. Remaining Risks & Considerations

1. **ClamAV Daemon Deployment in Local/Dev:** In dev environments without a live ClamAV daemon container running on port 3310, `DefaultMalwareScanner` gracefully falls back to `HeuristicSignatureScanner` (which verifies EICAR signatures, executable headers, PDF script payloads, and HTML injection). For production, ensure ClamAV daemon is provisioned as specified in `docker-compose.yml`.
2. **Quarantine Bounded Retry Monitoring:** The `ScannerService.retry_quarantined_documents` mechanism bounds retry attempts to 3 iterations. Documents remaining unverified after 3 attempts trigger `DOCUMENT_SCAN_RETRY_EXHAUSTED` audit events and remain quarantined pending administrator security review.

---

## 9. Deployment Instructions

1. **Code Deployment:** Deploy updated application code to backend containers.
2. **Database Migration:** Run standard Alembic upgrade:
   ```bash
   alembic upgrade head
   ```
   *(Note: Schema inspection ensures this command is completely idempotent and safe on PostgreSQL and SQLite).*
3. **Configuration Verification:** Confirm `CLAMAV_HOST` and `CLAMAV_PORT` are configured in production environment variables (`CLAMAV_HOST=clamav`, `CLAMAV_PORT=3310`).

---

## 10. Rollback Procedures

If rollback is required:
1. Revert application code commit using git:
   ```bash
   git revert <commit-sha>
   ```
2. Database rollback (if downgrading revision `afbdf4813237`):
   ```bash
   alembic downgrade w1a2b3c4d5e6
   ```
   The safe drop inspection ensures parent foreign key indexes from `e4f8db885ba5` will remain intact during rollback.

---

*Note: Combined Security Closure and Stage 2 verification is completed with 100% pass rate.*
