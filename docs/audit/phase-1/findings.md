# LCC PHASE 1 — SECURITY AUDIT FINDINGS

---

## SEC-FIND-01: [HIGH] Lawyer Self-Registration Without Immediate Bar Council Verification Gate Permits Direct Access to Advocate-Restricted Endpoints

- Finding ID: `SEC-FIND-01`
- Severity: `HIGH`
- Status: `[VERIFIED]`

Location:
- `app/domain/users/user_service.py`
  - function: `register_user`
  - lines: 56–82
- `app/api/v1/auth.py`
  - function: `register`
  - line: 216
- `docs/audit/phase-1/lawyer-verification-gate-matrix.json` (61 endpoints evaluated)

Evidence:
During public self-registration via `POST /api/v1/auth/register`, the client submits `UserCreate` with `role: str`. The server validates that the role is not `ADMIN`, but permits `role="LAWYER"`. The user record is created immediately with `role = UserRole.LAWYER` and `account_status = AccountStatus.ACTIVE` (lines 66-68 of `app/domain/users/user_service.py`).
While public advocate discovery (`app/domain/users/profile_service.py:204`) correctly enforces `LawyerVerification.status == VerificationStatus.APPROVED`, an exhaustive trace of all 61 advocate-relevant endpoints reveals that 41 endpoints guard functionality solely using `RequireRole([UserRole.LAWYER])` without verifying whether the advocate's Bar Council credentials have been vetted or approved by an administrator.

Attack / Failure Scenario:
An untrusted user self-registers with `{"email": "attacker@example.com", "password": "Password123", "full_name": "Attacker", "role": "LAWYER"}`. The user immediately receives a valid Ed25519 JWT access token containing `"role": "LAWYER"`. The attacker can immediately call lawyer-restricted endpoints—such as inspecting pending AI human review responses (`GET /api/v1/ai-reviews/pending`), drafting BSA Section 63 evidentiary certificates, or participating in lawyer-only workflow queues—prior to submitting any valid Bar Council enrollment certificate or undergoing review.

Impact:
Privilege escalation from unverified self-registered user to active legal practitioner tier, potentially compromising confidentiality of pending AI evaluations or legal workflows.

Existing Mitigation:
Consultation booking and public directory listings require `VerificationStatus.APPROVED`.

Why Existing Mitigation Is Not Sufficient:
Existing checks gate public client-facing exposure but fail to guard internal advocate-tier endpoints (41 endpoints) against unverified users holding `UserRole.LAWYER`.

Recommended Remediation Direction:
1. Initialize self-registered lawyer accounts with a distinct unverified status, or set role to `CLIENT` until verification is approved.
2. Introduce an explicit dependency `require_verified_lawyer` that checks `LawyerVerification.status == VerificationStatus.APPROVED` on all advocate endpoints.

Tests Covering This:
- `tests/test_multi_tab_auth_isolation.py`
- `tests/integration/test_kyc_verification_flow.py`

---

## SEC-FIND-02: [HIGH] Missing Database Migrations for 4 Tables Tracking Authentication & Session Models

- Finding ID: `SEC-FIND-02`
- Severity: `HIGH`
- Status: `[VERIFIED PRODUCTION DEPLOYMENT RISK]`

Location:
- `app/models/auth.py` (models: `EmailVerificationToken`, `PasswordResetToken`)
  - lines: 40, 65
- `app/models/consultation.py` (association table: `consultation_documents`)
- `app/models/message.py` (model: `DirectMessage`)
  - line: 12
- `migrations/versions/` (54 migration files)

Evidence:
Direct comparison of SQLAlchemy `Base.metadata.tables` (84 tables) against the 54 Alembic migration version files in `migrations/versions/` (80 net active tables) demonstrates that exactly 4 tables have never had `op.create_table` operations generated in any Alembic migration:
1. `email_verification_tokens`
2. `password_reset_tokens`
3. `consultation_documents`
4. `direct_messages`

Classification & Deployment Risk Analysis:
- ORM model exists? YES (all 4 models are defined in SQLAlchemy Base.metadata).
- Migration creates table? NO (absent across all 54 migration revisions).
- Migration history contains table? NO.
- Production database bootstrap creates table? NO. In production, `app/main.py` lines 78-83 only executes `create_all` if `ENVIRONMENT in ("development", "test") and settings.DATABASE_URL.startswith("sqlite")`. Production environments use PostgreSQL managed strictly through Alembic.
- Startup creates tables automatically in prod? NO.
- Tests create tables independently? YES (`tests/conftest.py` calls `Base.metadata.create_all(bind=engine)` in SQLite in-memory, completely masking this defect during CI/CD test runs).
- Deployment migration path creates table? NO (`alembic upgrade head` fails to create these tables).
- Verdict: **VERIFIED PRODUCTION DEPLOYMENT RISK**.

Attack / Failure Scenario:
When the platform is deployed to production using standard database migration scripts (`alembic upgrade head`), the database schema will lack the `email_verification_tokens` and `password_reset_tokens` tables. Any user attempting to reset their password (`POST /api/v1/auth/forgot-password`) or confirm email verification (`POST /api/v1/auth/email/verify/otp`) will encounter a fatal 500 Internal Server Error due to missing relational tables (`relation "password_reset_tokens" does not exist`). Similarly, attaching documents to consultations or sending direct messages will fail with relation errors.

Impact:
Complete outage and denial of service for critical authentication lifecycle operations (account recovery, email OTP verification, direct messaging, and consultation attachments) on any freshly provisioned staging or production environment.

Existing Mitigation:
The local test suite uses SQLite in-memory databases with `Base.metadata.create_all()`, which masks the absence of Alembic migrations during unit testing.

Why Existing Mitigation Is Not Sufficient:
`Base.metadata.create_all()` is never executed in production environments; Alembic is the authoritative deployment mechanism.

Recommended Remediation Direction:
Generate a new Alembic migration revision creating these 4 missing tables with all foreign keys, unique constraints, and indices before Phase 2.

Tests Covering This:
- `tests/integration/test_account_recovery_and_identity_verification.py` (executed via SQLite in-memory mocks)

---

## SEC-FIND-03: [MEDIUM] In-Memory OAuth State Single-Use Replay Store Does Not Synchronize Across Distributed Workers

- Finding ID: `SEC-FIND-03`
- Severity: `MEDIUM`
- Status: `[VERIFIED]`

Location:
- `app/core/oauth_security.py`
  - variable: `_consumed_oauth_states`
  - function: `verify_oauth_state`
  - lines: 138, 175–185

Evidence:
Single-use replay defense for Google OAuth state tokens is implemented using an in-process Python dictionary:
```python
_consumed_oauth_states: dict[str, float] = {}
```
During verification in `verify_oauth_state()`, the function checks `if jti in _consumed_oauth_states:` and records the timestamp in memory.

Attack / Failure Scenario:
In a clustered or multi-worker production deployment (e.g. Uvicorn with `--workers 4`, or multiple container replicas behind an AWS ALB or Kubernetes ingress), an in-memory dictionary is isolated to the single OS process. If a state token is consumed on Worker 1, Worker 2 has no record of the token's `jti`. An adversary who intercepts an authorization code and state token could attempt replay against Worker 2 within the 10-minute expiry window.

Impact:
Potential OAuth state replay or fixation vulnerability in multi-instance production environments.

Existing Mitigation:
OAuth state tokens are cryptographically signed with Ed25519, expire after 10 minutes, bind a random 32-byte nonce, and the Google authorization code itself can only be exchanged once with Google.

Why Existing Mitigation Is Not Sufficient:
While Google's token endpoint will reject an already exchanged authorization code, the state validation layer in LCC fails to provide clustered idempotency guarantees independently.

Recommended Remediation Direction:
Store consumed state `jti` identifiers in Redis with a 600-second TTL (matching the state token expiry), falling back to in-memory only in single-worker test environments.

Tests Covering This:
- `tests/integration/test_api_matrix.py`
- `tests/security/test_oauth_security.py`

---

## SEC-FIND-04: [MEDIUM] Missing Global `Cache-Control: no-store` / `Pragma: no-cache` Security Headers Across Sensitive REST API and Auth Endpoints

- Finding ID: `SEC-FIND-04`
- Severity: `MEDIUM`
- Status: `[VERIFIED]`

Location:
- `app/middleware/security.py`
  - class: `SecurityHeadersMiddleware`
  - lines: 5–53
- `app/api/v1/auth.py`
- `app/api/v1/cases.py`
- `app/api/v1/evidence.py`

Evidence:
Inspection of `SecurityHeadersMiddleware` confirms comprehensive enforcement of HSTS, X-Content-Type-Options, X-Frame-Options, Content-Security-Policy (with frame-ancestors 'none'), Referrer-Policy, Cross-Origin-Opener-Policy, Cross-Origin-Resource-Policy, and Permissions-Policy (`geolocation=(), microphone=(), camera=(), payment=()`).
However, neither `SecurityHeadersMiddleware` nor endpoint handlers set `Cache-Control: no-store, no-cache, must-revalidate` or `Pragma: no-cache` headers on REST responses (with the sole exception of byte-range video streaming in `app/api/v1/recordings.py`).

Attack / Failure Scenario:
When users access sensitive endpoints such as `/api/v1/auth/me`, `/api/v1/cases/*`, `/api/v1/evidence/*`, or `/api/v1/consultations/*` via intermediate caching proxies, corporate forward proxies, or shared terminal web browsers, responses may be cached on local disks or shared proxy stores. An attacker with local access to the client machine or inspectable proxy logs could recover highly sensitive PII, case facts, or legal evidence documents.

Impact:
Sensitive data leakage and legal confidentiality breach via intermediate cache or browser history storage.

Existing Mitigation:
Responses are transmitted exclusively over TLS (enforced by HSTS).

Why Existing Mitigation Is Not Sufficient:
TLS secures transport in transit, but does not prevent client-side browser caching or proxy storage of decrypted response payloads.

Recommended Remediation Direction:
Add default `Cache-Control: no-store, max-age=0` and `Pragma: no-cache` headers in `SecurityHeadersMiddleware` for all paths under `/api/v1/`, permitting explicit overrides only on static/public assets or media streams.

Tests Covering This:
- `tests/e2e/test_production_deployment_readiness.py`

---

## SEC-FIND-05: [MEDIUM] Test Payment Simulation Route (`/api/v1/consultations/{consultation_id}/pay-test`) Exists in Production Route Tree

- Finding ID: `SEC-FIND-05`
- Severity: `MEDIUM`
- Status: `[VERIFIED]`

Location:
- `app/api/v1/consultations.py`
  - function: `process_test_payment`
  - lines: 770–786

Evidence:
The endpoint `POST /api/v1/consultations/{consultation_id}/pay-test` allows authenticated users with `UserRole.CLIENT` or `UserRole.ADMIN` to simulate successful payment, instantly transitioning consultation status to `PAID` and provisioning video meeting rooms without communicating with Stripe or Razorpay.

Attack / Failure Scenario:
The endpoint includes an environment check:
```python
if not settings.ENABLE_TEST_PAYMENTS or settings.ENVIRONMENT in ("production", "staging"):
    raise HTTPException(status_code=403, detail="Simulated test payments are strictly disabled in this environment.")
```
If an operator accidentally sets `ENABLE_TEST_PAYMENTS=true` or misconfigures `ENVIRONMENT=development` in a publicly accessible pre-production or staging cluster, any client can book consultations and bypass real payment gateways entirely.

Impact:
Financial loss through unpaid consultation provisioning and lawyer calendar reservation.

Existing Mitigation:
The explicit guard blocks execution when `ENVIRONMENT in ("production", "staging")` or `ENABLE_TEST_PAYMENTS` is false.

Why Existing Mitigation Is Not Sufficient:
Dead test code embedded in production route trees creates reliance on runtime flags rather than architectural isolation.

Recommended Remediation Direction:
Move test payment endpoints to a dedicated test-only router (e.g. `app/api/testing/`) that is never mounted when building production distributions.

Tests Covering This:
- `tests/test_instant_consultation_flow.py`

---

## SEC-FIND-06: [LOW] Rate Limiter Storage Falls Back to In-Memory (`memory://`) Without Redis

- Finding ID: `SEC-FIND-06`
- Severity: `LOW`
- Status: `[VERIFIED]`

Location:
- `app/api/v1/auth.py`
  - lines: 53–58

Evidence:
The rate limiter storage URI is declared as:
```python
_rate_limit_storage_uri = (
    settings.REDIS_URL
    if settings.REDIS_URL and settings.ENVIRONMENT.lower() == "production"
    else "memory://"
)
limiter = Limiter(key_func=get_remote_address, storage_uri=_rate_limit_storage_uri)
```

Attack / Failure Scenario:
If `REDIS_URL` is not provided in environment configuration, SlowAPI defaults to process-local memory. Across N worker processes, an attacker can make N times the nominal threshold of login or registration attempts before triggering an HTTP 429 response.

Impact:
Weakened brute-force resistance across multi-process deployments lacking Redis.

Existing Mitigation:
Individual endpoints have strict per-minute limits (e.g. login: 15/min, forgot-password: 5/min, verify-otp: 10/min).

Why Existing Mitigation Is Not Sufficient:
In-memory buckets cannot track IP request volume across concurrent worker processes.

Recommended Remediation Direction:
Raise a configuration error on application startup in production if `REDIS_URL` is absent.

Tests Covering This:
- `tests/e2e/test_database_backup_restore.py`

---

## SEC-FIND-07: [LOW] Unauthenticated State Modification Permitted on Court Case Synchronization (`POST /api/v1/court-cases/{id_or_cnr}/sync`)

- Finding ID: `SEC-FIND-07`
- Severity: `LOW`
- Status: `[VERIFIED]`

Location:
- `app/api/v1/court_cases.py`
  - function: `sync_court_case`
  - lines: 299–320

Evidence:
The endpoint `POST /api/v1/court-cases/{id_or_cnr}/sync` accepts `current_user: User | None = Depends(get_optional_current_user)` rather than `Depends(get_current_user)`.
Inside the handler:
```python
case = _find_court_case(db, id_or_cnr)
case.last_synchronized_at = datetime.now(UTC)
case.sync_status = "SYNCED"
db.commit()
```
The database record is modified and committed on behalf of an unauthenticated caller.

Attack / Failure Scenario:
An anonymous client or bot can iterate through known CNR numbers or case IDs, submitting POST requests to update `last_synchronized_at` and mutate `sync_status` to `"SYNCED"`.

Impact:
Unauthorized database write and timestamp contamination.

Existing Mitigation:
Endpoint is rate limited via `@limiter.limit("20/minute")` per IP, and `_find_court_case` prevents arbitrary writes outside existing case records.

Why Existing Mitigation Is Not Sufficient:
State-modifying operations (POST) should never accept unauthenticated requests unless explicitly designed as public webhooks or onboarding forms.

Recommended Remediation Direction:
Require authentication (`current_user: User = Depends(get_current_user)`) or restrict to users following the matter.

Tests Covering This:
- `tests/integration/test_court_cases_api.py`

---

## SEC-FIND-08: [INFO] OpenID Connect Clock Skew Leeway Set to 300 Seconds

- Finding ID: `SEC-FIND-08`
- Severity: `INFO`
- Status: `[VERIFIED]`

Location:
- `app/domain/auth/google_oauth_service.py`
  - function: `validate_id_token`
  - line: 167

Evidence:
`leeway=300` is passed to `jwt.decode()` during Google ID token validation.

Attack / Failure Scenario:
A 5-minute leeway window is relatively generous. While it safely prevents clock drift false rejections with Google identity servers, it slightly extends the acceptance window for recently expired tokens.

Impact:
Negligible operational impact because tokens are consumed immediately upon callback.

Existing Mitigation:
Tokens are validated over TLS and matched against expected nonces.

Recommended Remediation Direction:
Consider reducing leeway to 60 seconds once production NTP time synchronization is confirmed.

Tests Covering This:
- `tests/integration/test_api_matrix.py`
