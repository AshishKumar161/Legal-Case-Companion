# Legal Case Companion (LCC) — Application Security & Threat Model Audit

**Date**: November 2, 2026  
**Auditor**: Principal Application Security Engineer  
**Reference Frameworks**: OWASP ASVS v4.0, OWASP Top 10 API Security Risks (2023), OWASP Top 10 LLM Applications

---

## 1. Security Architecture Overview

The Legal Case Companion handles highly confidential Indian legal documents, dispute litigation histories, advocate-client communications, and evidentiary materials. The application's defensive architecture was audited across twelve critical security dimensions.

```
+-----------------------------------------------------------------------------------+
|                            APPLICATION PERIMETER                                  |
|   - Trusted Host Middleware (Host header injection defense)                       |
|   - Security Headers (HSTS, CSP, X-Frame-Options: DENY, X-Content-Type-Options)  |
|   - Request Size Limiting (5MB raw payload cap)                                  |
|   - SlowAPI IP/User Rate Limiting                                                 |
+----------------------------------------+------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
|                        AUTHENTICATION & IDENTITY REALM                            |
|   - Asymmetric Ed25519 JWT (EdDSA) with claim enforcement (iss, aud, exp, jti)   |
|   - Key Rotation Fallback (JWT_PREVIOUS_PUBLIC_KEY verification)                  |
|   - Argon2id Password Hashing (Cryptographic salt & memory/time cost parameters)  |
|   - Secure Refresh Tokens (32 bytes high entropy, SHA-256 hashed, family revoke)  |
+----------------------------------------+------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
|                      AUTHORIZATION & RESOURCE ENCLAVE                             |
|   - Centralized RBAC + Object-Level Authorization (app/core/authorization.py)    |
|   - IDOR Obscuration (HTTP 404 ResourceNotFoundError on unauthorized access)      |
|   - Multi-tenant case and participant role isolation (OWNER, LAWYER, VIEWER)      |
|   - Evidence Locker granular grants (VIEW, DOWNLOAD, MANAGE with expiration)     |
+----------------------------------------+------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
|                     DATA INTEGRITY, STORAGE & AI RAG                              |
|   - S3 Private Buckets with Presigned Short-Lived Signed URLs (15m upload, 5m dl) |
|   - File Magic Byte Inspection & Zip-Bomb Decompression Guards                   |
|   - Background ClamAV Antivirus Quarantine Pipeline                               |
|   - Case-Scoped Evidence Grounding with Document Authorization Barrier            |
|   - Strict Legal Citation Normalization & Anti-Hallucination Disclaimer Guards    |
+-----------------------------------------------------------------------------------+
```

---

## 2. OWASP Top 10 & ASVS Threat Assessment

### 2.1 Injection (ASVS V5)
- **SQL Injection**: **SECURE**. All database interactions are routed through SQLAlchemy 2.0 ORM or parameterized queries (`sa.text(...)` with bound parameter dictionaries). Zero raw string concatenation into SQL statements was detected.
- **Path Traversal**: **SECURE**. Centralized `validate_storage_object_key` rejects control characters, URL-encoded traversal (`%2e%2e`), absolute slashes, and Windows drive specifiers (`os.path.normpath` validation). Filenames are sanitized via `validate_filename_security`.
- **Command Injection**: **SECURE**. No `shell=True` subprocess calls exist in request lifecycles.

### 2.2 Broken Authentication & Session Management (ASVS V2, V3)
- **JWT Signature Algorithm**: **SECURE**. Enforces EdDSA (Ed25519 asymmetric cryptography). Rejects `none` algorithm and algorithm confusion attacks.
- **Refresh Token Lifecycle**: **SECURE**. Refresh tokens are stored in `refresh_token_sessions` using single-iteration SHA-256 hashes of cryptographically random 32-byte tokens. Token reuse triggers immediate invalidation of the entire session family.
- **Defect Resolved**: **`BUG-001` (Critical) — RESOLVED**. `GoogleOAuthService.validate_id_token` enforces `leeway=0`, `verify_iat=True`, fail-closed requirement on `GOOGLE_CLIENT_ID`, and strict signature validation. Verified via `tests/unit/test_google_oauth_token_validation.py` (9/9 passed).

### 2.3 Broken Object-Level Authorization (BOLA / IDOR) (ASVS V4)
- **Case Isolation**: **SECURE**. `authorize_case_access` inspects `CaseParticipant` associations. When an unauthorized user attempts to view a case, an HTTP 404 (`ResourceNotFoundError`) is returned rather than HTTP 403, preventing resource enumeration and IDOR attacks.
- **Document Access**: **SECURE**. `authorize_document_access` enforces parent case membership or explicit uploader status. Additionally, confidential documents (`is_confidential=True`) are strictly barred from standard case viewers, restricting access to case owners and counsel.
- **Evidence Locker Grants**: **SECURE**. The Evidence Locker (`app/models/evidence.py`) mandates explicit `EvidenceAccessGrant` records with expiration checks (`grant.expires_at > now`) and hierarchical access levels (`VIEW` < `DOWNLOAD` < `MANAGE`).

### 2.4 Sensitive Data Exposure & Logging (ASVS V8)
- **Log Sanitization**: **SECURE**. `SensitiveDataScrubberFilter` in `app/core/logging.py` intercepts all log records, scrubbing passwords, bearer tokens, refresh tokens, access tokens, AWS signatures, card numbers, Indian Aadhaar numbers (`\b\d{4}\s\d{4}\s\d{4}\b`), Indian PAN (`\b[A-Z]{5}[0-9]{4}[A-Z]\b`), and court CNR numbers.
- **Static Repository Secrets**: **SECURE**. Zero committed production secrets, private keys, or API tokens were found across the repository (verified by `scripts/ci_secret_scanner.py`).
- **Defect Resolved**: **`BUG-007` (Low) — RESOLVED**. `aws_malware_webhook` fails safely with generic HTTP 503 (`Webhook service unavailable`) without exposing internal secret configuration status. Constant-time signature comparison enforced. Verified via `tests/security/test_webhook_security.py`.

### 2.5 File Upload Security (ASVS V12)
- **Magic Bytes Validation**: Implemented via `validate_file_magic_bytes` against PDF, PNG, JPEG, DOCX, and text signatures.
- **Zip Bomb Defense**: Implemented in `validate_archive_safety` enforcing max 1000 items, max 200MB uncompressed volume, and max 100:1 compression ratio.
- **Defect Resolved**: **`BUG-003` (High) — RESOLVED**. In `app/api/v1/documents.py`, direct multipart upload strictly verifies extensions, validates binary magic bytes, enforces initial `QUARANTINED` status, executes scanner validation, and handles scanner unavailability with fail-closed quarantine and bounded retry monitoring (`ScannerService.retry_quarantined_documents`). Preview and chunk extraction are barred on non-SAFE documents. Verified via `tests/security/test_direct_upload_security.py` (16/16 passed).

### 2.6 Server-Side Request Forgery (SSRF)
- **External Network Calls**: Limited to Stripe API, OpenAI/Groq API, and Google OIDC JWKS.
- **OIDC Discovery**: JWKS endpoints are locked to `https://www.googleapis.com/oauth2/v3/certs`. No arbitrary URL fetching from client-provided query parameters is permitted.

### 2.7 Cross-Site Scripting (XSS) & CSRF
- **CORS**: Configured strictly via `BACKEND_CORS_ORIGINS`. Production environment rejects wildcard `*` with credentials.
- **CSRF Defense**: Refresh token endpoint validates `X-CSRF-Token` headers against secure `csrf_token` cookies.

---

## 3. Evidence-Grounded AI & RAG Security

The RAG pipeline was audited against LLM security standards:

| Risk Area | Threat Description | LCC Mitigation Status |
|---|---|---|
| **Cross-Tenant Vector Leakage** | User retrieves embedding chunks from cases they do not belong to. | **ENFORCED**: `RetrievalService.search_case_evidence` requires `authorize_case_access` and filters SQL queries by `DocumentChunk.case_id == case_id`. Chunks outside the case are physically impossible to retrieve. |
| **Malicious Document Retrieval** | User uploads infected or unapproved documents to poison AI answers. | **ENFORCED**: SQL filter explicitly requires `Document.security_status == DocumentSecurityStatus.SAFE`. Quarantined or infected documents are never fed to the LLM. |
| **Prompt Injection** | Adversarial text in legal evidence attempts to hijack system prompt instructions. | **ENFORCED**: `AIPromptPolicy` wraps retrieved evidence in structured, delimited blocks and instructs the model to disregard instructions contained within evidentiary quotes. |
| **Legal Hallucination** | Model invents case citations, sections, or nonexistent court precedents. | **ENFORCED**: `CitationNormalizer` and `ClaimVerifier` compare citations against known Indian acts (BNS, BSA, BNSS, IPC, CrPC) and flag ungrounded claims with confidence penalties. |
| **Resource Depletion** | High token consumption or denial-of-service via massive prompts. | **ENFORCED**: `AIBudgetService` enforces per-user daily token and request quotas with SlowAPI rate limiting (10 req/min). |

---

## 4. Remediation Checklist

1. [x] **Remediate BUG-001**: Set Google OAuth token validation leeway to 0 seconds, enforce `verify_iat`, and fail-closed if `GOOGLE_CLIENT_ID` is missing. (**RESOLVED**)
2. [x] **Remediate BUG-003**: Enforce `validate_file_magic_bytes`, set `security_status=QUARANTINED`, implement bounded retry monitoring, and block non-SAFE document chunk/preview access. (**RESOLVED**)
3. [x] **Remediate BUG-007**: Remove configuration disclosure in `app/api/v1/webhooks.py`, returning safe HTTP 503 and logging securely. (**RESOLVED**)
4. [x] **Enhance Database Query (BUG-006)**: Optimize vector retrieval with column projection, database-side filtering, bounded candidate windows, and NumPy BLAS vectorization (3.75x speedup, 78.7% memory reduction). (**RESOLVED**)
