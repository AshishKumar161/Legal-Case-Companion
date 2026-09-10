# Legal Case Companion — Privacy Architecture & Data Map

**Document Reference**: `docs/21_PRIVACY_DATA_MAP.md`  
**Phase**: Phase XVI — Production Security Hardening, Privacy, Data Protection & Deployment Readiness  
**Target System**: Legal Case Companion (LCC)  
**Jurisdiction Context**: India (Digital Personal Data Protection Act, 2023 Alignment)

---

## 1. Important Legal Disclaimer

> [!IMPORTANT]
> **Technical Controls vs. Legal Compliance**: This document outlines technical privacy controls, data flows, minimization mechanisms, and technical retention safeguards. The existence of these engineering controls does **NOT** constitute formal legal certification or a regulatory compliance guarantee under the Digital Personal Data Protection Act, 2023 (DPDP Act), GDPR, HIPAA, or ISO/IEC 27701. Formal compliance requires ongoing legal advisory, statutory notices, consent management interfaces, and regulatory auditing.

---

## 2. Personal Identifiable Information (PII) Inventory

| Data Asset / Model | Stored Fields | Business Purpose | Storage Engine | Access Boundary | Default Retention | Deletion / Anonymization Mechanism |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **User Identity** (`users`) | `id`, `email`, `password_hash`, `role`, `account_status`, `deleted_at` | Authentication, authorization, session anchoring | PostgreSQL (`users` table) | Authenticated user (`/users/me`), Admins | Indefinite until deletion request | Soft-deleted (`deleted_at`), email replaced with `deleted_<id>@anonymized.local` |
| **Client Profile** (`client_profiles`) | `full_name`, `phone_number`, `address`, `city`, `state`, `postal_code` | Lawyer consultation contact, case representation | PostgreSQL (`client_profiles`) | Profile owner, authorized case lawyers | Lifecycle of active user account | Cleared on account deletion; names anonymized |
| **Lawyer Profile** (`lawyer_profiles`) | `full_name`, `phone_number`, `bar_number`, `state_bar_council`, `practice_areas`, `court_jurisdictions` | Client discoverability, legal mandate verification | PostgreSQL (`lawyer_profiles`) | Public marketplace, authenticated clients | Maintained during Bar verification | Anonymized on account deletion |
| **Lawyer Verification** (`lawyer_verifications`) | `enrollment_number`, `id_document_url`, `verification_status` | Statutory validation of Bar Council credentials | PostgreSQL / Private S3 | Admins, assigned compliance reviewer | 7 years (Advocates Act / Limitation Act) | Retained for statutory compliance audit |
| **Legal Cases** (`cases`) | `title`, `description`, `status` | Case management & legal collaboration | PostgreSQL (`cases`) | Assigned participants (Client, Lawyer) | Minimum 7 years from case closure | Soft deletion only; legal chain preserved |
| **Evidence Metadata** (`evidence`, `evidence_versions`) | `title`, `description`, `original_filename`, `sha256`, `storage_key`, `content_type` | Court filings, client-lawyer evidence exchange | PostgreSQL | Authorized case members with grants | Indefinite or policy-controlled (`DOCUMENT_RETENTION_DAYS`) | Technical deletion forbidden while under `is_legal_hold` |
| **Physical Evidence Files** | Binary document contents | Storage of legal proof, affidavits, contracts | AWS S3 (`lcc-secure-documents`) | Download authorized participants (presigned 60s URLs) | Aligned with metadata | Versioned; private S3 deletion upon expired retention |
| **Consultation Records** (`consultations`) | `client_id`, `lawyer_id`, `scheduled_at`, `fee`, `status` | Scheduling, legal consultation billing | PostgreSQL | Client, Lawyer, Admin | 7 years (financial audit & tax reporting) | Retained for tax / financial record-keeping |
| **Payments** (`payments`) | `amount`, `currency`, `status`, `payment_intent_id` | Fee collection & disbursement | PostgreSQL | Client, Lawyer, Platform billing | 7 years (Companies Act, GST statutory audit) | Immutable financial transaction log |
| **Consultation Recordings** (`video_recordings`) | `room_name`, `storage_path`, `checksum_sha256` | Record of client-lawyer consultation advice | Local disk / Private S3 | Both consenting participants | Configurable; user revocable | Physical file wiped on deletion |
| **AI Conversations** (`ai_conversations`) | `user_id`, `query`, `response`, `citations` | Client legal guidance & case summarization | PostgreSQL | Conversation owner only | 90 days default | Deleted upon user request or session clearing |
| **Audit Logs** (`audit_events`, `evidence_custody_events`) | `actor_user_id`, `action`, `metadata`, `ip_metadata`, `timestamp` | Chain of custody, security forensics, anti-tamper | PostgreSQL (append-only) | Platform security officers, court subpoena | Permanent (non-deletable) | Retained as required for legal evidence admissibility |

---

## 3. Data Minimization Principles

LCC enforces data minimization across all API surfaces:
1. **Response Schemas (Allowlisting)**:
   - All endpoints utilize Pydantic response models with explicit fields.
   - Database ORM objects are NEVER serialized directly to JSON.
   - Internal credentials, `password_hash`, AWS storage paths, and full audit logs are strictly excluded from client-facing responses.
2. **AI Query Minimization**:
   - Only document chunks matching cosine similarity thresholds are forwarded to external LLMs.
   - Whole case histories, user email addresses, and phone numbers are never injected into AI prompts.
3. **Presence & WebSocket Minimization**:
   - Presence tracking utilizes hashed user identifiers (`user_id`), broadcasting strictly `ONLINE` / `OFFLINE` status without IP addresses, browser versions, or GPS locations.

---

## 4. Safe Account Deletion Architecture

When an account deletion is requested via `DELETE /api/v1/auth/account`:
1. **Authentication Requirement**: If the account has a password set, the user must supply valid password credentials.
2. **Session Revocation**: All active `RefreshTokenSession` records are immediately revoked (`revoked_at = now()`).
3. **PII Anonymization**:
   - `user.email` is rewritten to `deleted_<user_id>@anonymized.local`.
   - `user.account_status` transitions to `DEACTIVATED`.
   - Associated `ClientProfile` and `LawyerProfile` details (phone number, physical address, full name) are blanked or rewritten to `Anonymized User`.
4. **Preservation of Legal & Financial Integrity**:
   - Cases, evidence filings, and consultation records are **NOT** destructively deleted; they are preserved with anonymized actor references to prevent invalidating ongoing court proceedings or legal holds.
   - Financial transactions and audit logs are retained to satisfy statutory audit obligations under Indian law.
5. **Immutable Audit Trail**: An `ACCOUNT_DELETED` audit event is written to the immutable append-only audit log.

---

## 5. Third-Party Data Flow & Sub-Processor Inventory

| Third-Party Provider | Data Disclosed | Purpose | Transfer Mechanism | Failure Mode |
| :--- | :--- | :--- | :--- | :--- |
| **AWS (Amazon Web Services)** | Encrypted document bytes, S3 keys | Private Evidence storage | TLS 1.3 / AWS IAM SigV4 | Fail-closed (storage unavailable) |
| **OpenAI** | Sanitized query + retrieved text snippets | AI legal reasoning & summarization | HTTPS REST API / TLS 1.3 | Returns generic uncertainty warning |
| **Stripe** | Payment amount, currency, tokenized card ID | Fee payment processing | TLS 1.3 / Server-side SDK | Transaction fails safely |
| **Google OAuth / OIDC** | User Google ID (`sub`), verified email, name | Single Sign-On (SSO) | TLS 1.3 OpenID Connect | Disallows login; falls back to email/password |
| **ClamAV (Internal Container)** | Raw file streams | Antivirus / malware scanning | TCP socket stream (private Docker network) | Fail-closed (Evidence quarantined) |
| **Coturn (Internal Container)** | Ephemeral WebRTC audio/video packets | P2P consultation media relay | Encrypted SRTP / DTLS | Consultation falls back to direct mesh |

---

## 6. Technical Alignment with India DPDP Act, 2023

1. **Lawful Processing & Purpose Limitation**: Data is collected exclusively for facilitating legal representation and case collaboration.
2. **Notice & Consent**: Consultation video recordings require explicit bidirectional consent from both Client and Lawyer before recording commences.
3. **Data Principal Rights**:
   - **Right to Access & Correction**: Implemented via profile management endpoints (`GET /users/me`, `PUT /users/me`).
   - **Right to Erasure**: Implemented via `DELETE /api/v1/auth/account` with statutory retention exceptions.
   - **Grievance Redressal**: Audit logs track all data access and administrative modifications.
