STATUS: DRAFT

AUTHORITY: DERIVED FROM PROJECT SOURCE OF TRUTH

SOURCE DOCUMENTS:
- docs/00_PROJECT_CONTEXT.md
- docs/01_SYSTEM_ARCHITECTURE.md
- docs/02_DATABASE_DESIGN.md
- docs/03_API_SPECIFICATION.md

IMPLEMENTATION STATUS: NOT STARTED

RULE:
SECURITY REQUIREMENTS MUST NOT BE INVENTED

# Authorization and Security Specification

## 1. SECURITY BOUNDARIES
Clearly distinguish:
- **Authentication**: Who is the user?
- **Authorization**: What may the user access/do?
- **Audit**: What happened and who performed it?
- **UUID**: How is the resource identified?
- **Encryption**: How is sensitive information protected in transit/at rest?

Never treat one mechanism as a replacement for another.

## 2. AUTHENTICATION MODEL
FINAL:
- Use JWT access tokens with server-controlled opaque refresh-token sessions.
- Password authentication must use **Argon2id**. Plaintext passwords must never be stored.
- Passwords, access tokens, refresh tokens, signing keys, API keys, and secrets must never be logged.
- Exact Argon2id tuning parameters will be benchmarked during implementation (configurable via environment).

## 3. ACCESS TOKEN ARCHITECTURE
FINAL:
- **Format**: JWT.
- **Signing Algorithm**: EdDSA. (RS256 was rejected because EdDSA provides equivalent/better security with much smaller keys and faster verification, assuming robust Python library support like `authlib` or `PyJWT`).
- **Lifetime**: 15 minutes. (A 15-minute TTL provides an optimal balance between security and user experience. It limits the exposure window of stolen access tokens while preventing excessive token-refresh overhead).
- **Minimal Claims**: `sub`, `role`, `iss`, `aud`, `iat`, `exp`, `jti`.
- **Prohibited Data**: Do not store case lists, document permissions, mutable authorization state, large user profiles, or sensitive legal information inside the JWT.
- **Principle**: JWT proves identity. JWT does not by itself prove access to a resource.

## 4. REFRESH TOKEN ARCHITECTURE
FINAL:
- **Format**: Opaque cryptographically random refresh token.
- **Storage**: Store only a secure hash/representation of the refresh token in the database. Raw tokens must not be stored in plaintext.
- **Lifetime**: Absolute lifetime of 30 days, with an inactivity expiration of 7 days. A refresh token/session expires when either condition is reached.
- **Browser Storage**: `HttpOnly` + `Secure` + `SameSite` cookie. Do NOT store refresh tokens in `localStorage` because `localStorage` is completely accessible to JavaScript and vulnerable to Cross-Site Scripting (XSS) attacks.
- **Metadata**: Maintain server-side metadata (session ID, user ID, token family ID, hash, created_at, expires_at, last_used_at, revoked_at, device metadata, IP metadata).
- **Rotation**: Strict refresh-token rotation on every use.
- **Reuse Detection**: If a used/revoked token is presented, treat as theft, revoke the affected token family/session, and record a security event.
- **Logout Single-session**: Revoke that session/token family.
- **Logout All-devices**: Revoke all active refresh sessions for the user.

## 5. CSRF STRATEGY
FINAL:
- Since refresh tokens are stored in cookies, CSRF protection is mandatory for the refresh endpoint.
- **Primary Mechanism**: Double-submit cookie pattern. The backend issues a cryptographically random anti-CSRF token in a non-HttpOnly cookie, which the frontend must read and include in a custom HTTP header (e.g., `X-CSRF-Token`) during the refresh request.
- **Defense-in-Depth**: Strict `Origin` and `Referer` validation must be enforced on the backend.

## 6. DEVICE / SESSION MANAGEMENT
FINAL:
- The session data model is associated with: session ID, user ID, token family ID, created_at, last_used_at, expires_at, revoked_at, device metadata, and IP metadata.
- Users can view active sessions, revoke a specific session, or revoke all sessions.
- Sensitive raw token material is never exposed in these views.

## 7. ACCOUNT STATE, LIFECYCLE & MFA
FINAL:
- **States**: ACTIVE, SUSPENDED, SOFT_DELETED.
- **Revocation**: When suspended or soft-deleted, revoke all refresh-token sessions, prevent creation of new sessions, and reject authorization for protected resources.
- **Soft Deletion Cascade**: Soft deletion MUST NOT cascade-delete cases, documents, consultations, audit records, or legal history.
- **MFA Policy**: 
  - ADMIN: Mandatory MFA or equivalent step-up authentication.
  - LAWYER: Optional/strongly recommended MFA.
  - CLIENT: No mandatory MFA initially.
- **Step-up Authentication**: Required for sensitive operations (changing password, changing security settings, privileged administrative functions).

## 8. AUTHORIZATION MODEL & ROLES
FINAL:
- **Roles**: CLIENT, LAWYER, ADMIN. Role-based authorization provides coarse-grained access. It does NOT replace resource-level authorization.
- **Resource Authorization**: Use RBAC + resource-level authorization. Check actual relationship between actor, resource, case, participant, document, etc.
- **UUIDs**: Knowing the UUID of a resource must never be sufficient for access.

## 9. CLIENT/LAWYER CASE ISOLATION
FINAL:
- **CLIENT**: Access to own profile, own cases, authorized case documents, own consultations, own payments, own notifications.
- **LAWYER**: Access to own profile, assigned/authorized cases, assigned case documents, assigned consultations, only permitted client/case info, own notifications.
- **ADMIN**: Explicit administrative scope. No unrestricted access by implication. All privileged operations must be auditable.

## 10. NOTIFICATION AUTHORIZATION & BOLA DEFENSE
FINAL:
- **Isolation**: Notifications are strictly private to `user_id`.
- **BOLA Protection**: Any attempt by User A to view, mark read/unread, or delete User B's notification MUST return `404 Not Found` (never 403) to prevent ID enumeration.
- **Payload Privacy**: Notification messages and metadata must never leak passwords, plain auth tokens, API keys, full credit card numbers, or full confidential case documents.
- **Soft Delete**: Notifications deleted by users are soft-deleted via `deleted_at` and excluded from listing/unread count calculations.

## 11. DOCUMENT UPLOAD SECURITY
FINAL:
- **S3 Bucket**: PRIVATE. Never expose raw public S3 objects.
- **Flow**: Upload → quarantine → validate → malware scan → mark safe → store/enable access → allow downstream AI processing.
- **Restrictions**: 
  - Maximum file size: 10MB.
  - Allowed MIME types/extensions: PDF, PNG, JPEG, strictly enforced.
  - Filename normalization: System-generated random filenames/UUIDs.
- **Validation**: A document MUST NOT enter the AI/RAG pipeline before security validation and malware scanning succeeds. If a scan fails, the document must be permanently quarantined/deleted and an error returned.
- **Presigned URLs**: Must only be issued AFTER authorization and safety validation succeeds. S3 object keys are not authorization.

## 11. RATE LIMITING & BRUTE FORCE
FINAL:
- Configurable via environment variables. Initial production limits:
  - Registration: 3 req/min.
  - Login / Refresh: 5 req/min. Temporary 15-minute block on 5 consecutive failures.
  - Password reset/request & confirm: 3 req/min.
  - Public APIs: 60 req/min.
  - Sensitive authenticated APIs: 300 req/min.
  - Admin/security-sensitive APIs: 30 req/min.
- Includes IP-based and account-identifier-based controls.
- Returns `429 Too Many Requests`.

## 12. SECRETS MANAGEMENT
FINAL:
- Secrets must be managed using environment/deployment secret configuration (e.g., Render secret configuration).
- Do not commit secrets. Document secret rotation.

## 13. AUDIT LOGGING & SECURITY EVENTS
FINAL:
- Maintain append-only audit/security events for: login success, login failure, refresh success, refresh-token reuse, logout, logout-all, password change, password reset, account suspension, account restoration, MFA changes, privileged admin action, document access, security-sensitive payment events.
- Never store plaintext passwords, raw refresh tokens, raw access tokens, or secret keys in the audit log.
- Row-level audit fields do not replace append-only audit logs.

## 14. AI SECURITY
FINAL:
- All uploaded/retrieved legal documents are UNTRUSTED CONTENT.
- Documents may contain malicious instructions (prompt injection). Never treat document text as system instructions.
- Enforce authorization before retrieval and before sending context to the AI system.
- Prevent cross-user and cross-case retrieval.
- AI access must occur only through the authorized backend application flow.

## 15. GOOGLE OAUTH 2.0 & OPENID CONNECT (OIDC)
FINAL:
- **Protocol**: Standard OAuth 2.0 / OpenID Connect Authorization-Code Flow with server-side token exchange and cryptographic ID token validation.
- **Provider Role**: Google acts strictly as an Identity Provider (IdP). LCC remains the application session authority; Google tokens are never used as or substituted for LCC session tokens.
- **State & CSRF Protection**: Authorization initiation generates a 10-minute Ed25519-signed state JWT containing a cryptographically random `nonce`, `return_url`, `purpose`, and `jti`.
- **Open-Redirect Defense**: Return URLs are strictly validated to permit only relative paths (`/cases/*`, `/dashboard`) or allowlisted origins (`GOOGLE_ALLOWED_REDIRECT_ORIGINS`). Attacker-supplied redirects fall back to `/dashboard`.
- **Cryptographic Verification**: Google ID tokens are validated against Google's public JWKS (`https://www.googleapis.com/oauth2/v3/certs`) via RS256, verifying `iss` (`accounts.google.com`), `aud` (`GOOGLE_CLIENT_ID`), `exp`, `sub`, and `email_verified == True`.
- **Identity Model**: External identities are tracked in `user_external_identities` with a unique constraint on `(provider, provider_subject)`. Email alone is never used as the permanent identity key.
- **Account Linking & Role Integrity**: Verified Google emails link to existing accounts safely. New accounts default strictly to `UserRole.CLIENT`. OAuth callbacks cannot self-assign `ADMIN` or verified `LAWYER` status.
- **Audit Logging**: Logs `GOOGLE_LOGIN_SUCCESS`, `GOOGLE_LOGIN_FAILED`, `GOOGLE_IDENTITY_CREATED`, `GOOGLE_IDENTITY_LINKED`, `GOOGLE_IDENTITY_UNLINKED` without logging provider secrets or tokens.

## 16. UNDEFINED / DECISION REQUIRED
None. The core authentication, external identity, and security architecture is FINAL.

