# Legal Case Companion — Production Security Hardening Architecture

**Document Reference**: `docs/20_SECURITY_HARDENING.md`  
**Phase**: Phase XVI — Production Security Hardening, Privacy, Data Protection & Deployment Readiness  
**Target System**: Legal Case Companion (LCC)  
**Security Posture**: Fail-Closed, Least Privilege, Defense-in-Depth, Zero Hardcoded Secrets

---

## 1. Executive Summary & Security Principles

This document formalizes the production security architecture for Legal Case Companion (LCC). The architecture is engineered around the principle:

> **SECURITY MUST NOT DEPEND ON DEFAULT CONFIGURATION. SECURITY MUST FAIL CLOSED. SECRETS MUST NEVER BE COMMITTED OR LOGGED.**

Every request moves through a unified, defense-in-depth pipeline:
```text
User / Browser
      ↓
HTTPS / TLS 1.3
      ↓
Hardened HTTP Headers (HSTS Preload, COOP, CORP, Strict CSP)
      ↓
Double-Submit CSRF & Explicit Origin Validation
      ↓
Tab-Isolated Session Authentication (Ed25519 Asymmetric JWT)
      ↓
Authoritative Role & Resource Authorization Boundary (IDOR Defense)
      ↓
Input & File Magic Byte / Archive Bomb Validation
      ↓
Secure Domain Services (Fail-Closed Scanner, Private S3, PostgreSQL)
      ↓
Transactional Outbox & Durable Background Jobs
      ↓
Redacted Structured Logging & Bounded Metric Observability
```

---

## 2. Cryptographic Architecture & Key Management

### 2.1 Asymmetric Token Architecture (Ed25519 / EdDSA)
- **Primary Algorithm**: `EdDSA` (Edwards-curve Digital Signature Algorithm over Curve25519).
- **Key Separation**:
  - The **private key** (`JWT_PRIVATE_KEY`) is stored strictly in server-side secret management (AWS Secrets Manager, HashiCorp Vault, or environment runtime). It is NEVER exposed to the frontend, database, or client logs.
  - The **public key** (`JWT_PUBLIC_KEY`) is used strictly for verification.
- **Algorithm Pinning & Rejection of `alg=none`**:
  - In `app/core/security.py`, `verify_access_token` inspects the unverified JWT header before cryptographic evaluation.
  - Any token with `alg != "EdDSA"` (including `none`, `HS256`, `RS256`) is explicitly rejected with `InvalidTokenError`.
- **Claim Enforcement**:
  - `iss`: `"legal-case-companion"` (Strictly validated)
  - `aud`: `"legal-case-companion"` (Strictly validated)
  - `type`: `"access"` (Prevents token-type confusion attacks)
  - `exp`: 15 minutes (Short-lived access lifetime)

### 2.2 Zero-Downtime Key Rotation Runbook
To rotate the JWT signing keys in production without invalidating all active sessions:

1. **Step 1: Generate New Ed25519 Key Pair**:
   ```bash
   python -c "from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey; from cryptography.hazmat.primitives import serialization; k=Ed25519PrivateKey.generate(); print('NEW_PRIVATE_KEY:'); print(k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()); print('NEW_PUBLIC_KEY:'); print(k.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode())"
   ```
2. **Step 2: Stage Key Rotation Configuration**:
   - Set `JWT_PREVIOUS_PUBLIC_KEY` = Current `JWT_PUBLIC_KEY`.
   - Set `JWT_PUBLIC_KEY` = New public key.
   - Set `JWT_PRIVATE_KEY` = New private key.
3. **Step 3: Deploy Backend Instances**:
   - Newly issued access tokens will be signed with the new private key.
   - Existing valid tokens in flight will successfully verify against `JWT_PREVIOUS_PUBLIC_KEY`.
4. **Step 4: Decommission Prior Public Key**:
   - After `ACCESS_TOKEN_EXPIRE_MINUTES` (15 minutes), all previous access tokens have expired naturally.
   - Remove `JWT_PREVIOUS_PUBLIC_KEY` from the environment.

### 2.3 Password Security (Argon2id)
- **Algorithm**: Argon2id via `argon2-cffi`.
- **Parameters**: Default recommended memory, iterations, and parallelism parameters providing state-of-the-art resistance to GPU/ASIC cracking.
- **Complexity**: Enforced minimum 8 characters with digit and upper/lower complexity requirements.
- **Token Invalidation**: Password changes immediately revoke all active `RefreshTokenSession` records for the user.

---

## 3. Web Application Security Controls

### 3.1 Security Headers Matrix
Implemented in `SecurityHeadersMiddleware` (FastAPI backend) and `next.config.ts` (Next.js frontend):

| Header | Backend API Value | Frontend Web Value | Security Purpose |
| :--- | :--- | :--- | :--- |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains; preload` | `max-age=31536000; includeSubDomains; preload` | Enforces HTTPS; prevents SSL stripping. |
| `X-Content-Type-Options` | `nosniff` | `nosniff` | Blocks MIME-type sniffing. |
| `X-Frame-Options` | `DENY` | `DENY` | Prevents clickjacking and framing. |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | `strict-origin-when-cross-origin` | Prevents URL credential/token leakage to external referrers. |
| `Cross-Origin-Opener-Policy` | `same-origin` | `same-origin` | Isolates browsing context from cross-origin popups. |
| `Cross-Origin-Resource-Policy` | `same-site` | `same-site` | Blocks cross-origin asset theft. |
| `Content-Security-Policy` | `default-src 'none'; frame-ancestors 'none'; sandbox` | Curated Next.js CSP (`default-src 'self' ...`) | Strictly blocks XSS, script injection, and clickjacking. |
| `Permissions-Policy` | `geolocation=(), microphone=(), camera=(), payment=()` | `camera=(self), microphone=(self), geolocation=()` | Limits hardware access (permits WebRTC video room consultation on frontend). |

### 3.2 CORS & CSRF Defense Architecture
- **CORS Configuration**:
  - `allow_origins=["*"]` is strictly forbidden when `allow_credentials=True`.
  - In production, `BACKEND_CORS_ORIGINS` is strictly validated against configured origins (e.g. `https://app.legalcasecompanion.in`).
  - Cross-origin requests from unlisted origins are rejected with HTTP 400/403.
- **Double-Submit CSRF**:
  - On login, Google SSO, and refresh, a cryptographically random 32-byte CSRF token is issued in a cookie (`SameSite=Strict`, `Secure=True` in production).
  - State-changing cookie-authenticated requests require the client to mirror this value in the `X-CSRF-Token` header.
  - The `Origin` / `Referer` headers are strictly validated against allowlisted origins.

---

## 4. File Ingestion & Execution Boundary Security

### 4.1 Content Signature & Magic Byte Validation
Every document upload undergoes cryptographic byte inspection before storage:
- Rejects executable binary headers: DOS/PE (`MZ`), ELF (`\x7fELF`), Java/Mach-O (`\xca\xfe\xba\xbe`, `\xfe\xed\xfa\xce`).
- Validates file content against declared MIME type (PDF, PNG, JPEG, DOCX).
- Rejects plain-text files containing embedded null bytes or non-text control characters.

### 4.2 Archive & Zip-Bomb Protection
In `app/core/file_validation.py`, `validate_archive_safety` protects all ZIP containers and DOCX/XLSX packages:
- **Max Uncompressed Size**: 200 MB maximum uncompressed output.
- **Max Compression Ratio**: 100:1 ratio limit (immediately aborts recursive/bomb archives like 42.zip).
- **Path Traversal Defense**: Rejects members containing `..`, leading `/` or `\`, or drive identifiers (`C:`).
- **Nested Archive Prohibition**: Rejects containers with embedded `.zip`, `.tar`, `.gz`, or `.rar` files.
- **Max File Count**: 1,000 files maximum inside an archive container.

### 4.3 Download & Inline Execution Isolation
- All file download URLs generated by `EvidenceService` specify:
  - `ResponseContentDisposition: attachment; filename="..."`
  - `ResponseContentType: <content_type>`
- Inline viewing (`get_view_url`) is strictly limited to verified, safe viewing formats (`application/pdf`, `image/png`, `image/jpeg`).
- Any HTML, SVG, XML, or script-bearing format is forcibly converted to `attachment` with `application/octet-stream` to prevent execution within the application's origin context.

---

## 5. Storage & Database Least-Privilege Policies

### 5.1 AWS S3 IAM Least-Privilege Policy
The backend API and workers operate under isolated IAM roles:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "LCCEvidencePrivateStorage",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject"
      ],
      "Resource": "arn:aws:s3:::lcc-secure-documents/*"
    },
    {
      "Sid": "LCCBucketMetadata",
      "Effect": "Allow",
      "Action": [
        "s3:ListBucket"
      ],
      "Resource": "arn:aws:s3:::lcc-secure-documents"
    }
  ]
}
```
- **S3 Public Access Block**: All 4 AWS Block Public Access settings are enabled on `lcc-secure-documents`.
- **Default Server-Side Encryption**: `AES256` or AWS KMS (`aws:kms`).

### 5.2 PostgreSQL Database Security
- Application runs under an unprivileged `lcc_app` user (NOT superuser).
- Statement timeout enforced at 30,000 ms (`DB_STATEMENT_TIMEOUT_MS=30000`).
- Pool sizing: `DB_POOL_SIZE=20`, `DB_MAX_OVERFLOW=10`, `DB_POOL_RECYCLE=1800`.
- SQLite is strictly blocked in `ENVIRONMENT=production`.

---

## 6. Rate Limiting & Abuse Defense

SlowAPI rate limits protect critical endpoints from brute-force and resource exhaustion:
- `POST /api/v1/auth/login`: 15 requests / minute
- `POST /api/v1/auth/register`: 5 requests / minute
- `POST /api/v1/auth/password/reset/request`: 5 requests / minute
- `POST /api/v1/auth/password/reset/confirm`: 5 requests / minute
- `DELETE /api/v1/auth/account`: 5 requests / minute
- `POST /api/v1/realtime/ws-ticket`: 30 requests / minute
