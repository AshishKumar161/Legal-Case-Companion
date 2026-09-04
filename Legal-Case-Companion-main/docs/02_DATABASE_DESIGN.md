STATUS: DRAFT (Domain Model is mostly FINAL, pending specific product decisions)

AUTHORITY: DERIVED FROM PROJECT SOURCE OF TRUTH

SOURCE DOCUMENTS:
- docs/00_PROJECT_CONTEXT.md
- docs/01_SYSTEM_ARCHITECTURE.md
- docs/04_AUTHORIZATION_SECURITY.md

IMPLEMENTATION STATUS: NOT STARTED

RULE:
NO DATABASE ENTITY OR FIELD MAY BE INVENTED WITHOUT TRACEABLE JUSTIFICATION

# Database Design & Domain Model

## 1. DATABASE OBJECTIVES
The database serves as the authoritative persistent data store for the Legal Case Companion. Its objectives are to:
- Securely store persistent application data.
- Enforce strict relational integrity and consistency.
- Clearly define data ownership to support the authorization layer.
- Support strict authorization boundaries (e.g., Client/Lawyer case isolation).
- Provide immutable auditability for sensitive operations.
- Support atomic transactional operations (e.g., booking and payment).

## 2. DATABASE TECHNOLOGY
FINAL:
- Database: PostgreSQL
- ORM: SQLAlchemy
- Migrations: Alembic
- Primary Keys: UUIDv7 (Application-generated)
- Timestamps: `TIMESTAMPTZ` (Database-authoritative where possible)
- Soft Deletion: Used for core business entities, disabled for financial/security/audit logs.

## 3. FINAL ENTITY INVENTORY (CORE DOMAIN)
1. **User**: Central identity and authentication.
2. **ClientProfile**: Client-specific domain data.
3. **LawyerProfile**: Lawyer-specific professional data.
4. **LawyerVerification**: Verification history and state.
5. **Case**: The core legal matter.
6. **CaseParticipant**: The authoritative relationship granting users access to a Case.
7. **Document**: Document metadata and storage state.
8. **Consultation**: Booking and scheduling domain.
9. **Payment**: Financial transaction state.
10. **AuditEvent**: Append-only security and access history.
11. **RefreshTokenSession**: Active session state for rotating refresh tokens.
12. **CaseTimelineEvent**: Append-only business history of a case visible to users.

### REJECTED ENTITIES
- **DocumentAccess**: Rejected. Authorization is correctly derived from `CaseParticipant`. Explicit per-document grants add unnecessary complexity and risk of desync.
- **DocumentVersion**: Rejected. V1 requirements do not justify complex versioning. If a replacement file is uploaded, a new `Document` record is created to preserve historical integrity.
- **LawyerAvailability**, **Notification**, **AIConversation/Message**, **PasswordResetToken**: Marked as PROPOSED/LATER PHASE. Not part of the initial core relational schema until their specific modules are architected.

## 4. ENTITY DEFINITIONS & SCHEMA

### 1. User
- **id**: UUID (PK)
- **email**: VARCHAR (Unique, Not Null)
- **phone**: VARCHAR (Unique, Nullable)
- **password_hash**: VARCHAR (Not Null, Argon2id)
- **role**: ENUM (CLIENT, LAWYER, ADMIN)
- **account_status**: ENUM (ACTIVE, SUSPENDED)
- **created_at**: TIMESTAMPTZ (Not Null)
- **updated_at**: TIMESTAMPTZ (Not Null)
- **deleted_at**: TIMESTAMPTZ (Nullable) - Soft delete.
*Constraints: Unique email, unique phone.*

### 2. ClientProfile
- **id**: UUID (PK)
- **user_id**: UUID (FK -> User.id, Unique, Not Null)
- **full_name**: VARCHAR (Not Null)
- **location**: VARCHAR (Nullable)
- **created_at**: TIMESTAMPTZ
- **updated_at**: TIMESTAMPTZ
- **deleted_at**: TIMESTAMPTZ (Nullable) - Soft delete.
*Ownership: Belongs to User. (0..1 relationship).*

### 3. LawyerProfile
- **id**: UUID (PK)
- **user_id**: UUID (FK -> User.id, Unique, Not Null)
- **full_name**: VARCHAR (Not Null)
- **bio**: TEXT (Nullable)
- **location**: VARCHAR (Nullable)
- **consultation_fee**: NUMERIC (Nullable)
- **practice_areas**: ARRAY/JSONB (Nullable)
- **created_at**: TIMESTAMPTZ
- **updated_at**: TIMESTAMPTZ
- **deleted_at**: TIMESTAMPTZ (Nullable) - Soft delete.
*Ownership: Belongs to User. (0..1 relationship).*

### 4. LawyerVerification
- **id**: UUID (PK)
- **lawyer_profile_id**: UUID (FK -> LawyerProfile.id, Not Null)
- **enrollment_number**: VARCHAR (Not Null)
- **state_bar_council**: VARCHAR (Not Null)
- **status**: ENUM (PENDING, UNDER_REVIEW, APPROVED, REJECTED)
- **reviewed_by**: UUID (FK -> User.id, Nullable)
- **reviewed_at**: TIMESTAMPTZ (Nullable)
- **created_at**: TIMESTAMPTZ
- **updated_at**: TIMESTAMPTZ
*Lifecycle: Each verification attempt is a historical record (1:N from LawyerProfile). Completed decisions are immutable.*

### 5. Case
- **id**: UUID (PK)
- **title**: VARCHAR (Not Null)
- **description**: TEXT (Not Null)
- **status**: ENUM (OPEN, IN_PROGRESS, CLOSED, CANCELLED)
- **created_at**: TIMESTAMPTZ
- **updated_at**: TIMESTAMPTZ
- **deleted_at**: TIMESTAMPTZ (Nullable) - Soft delete.
*Ownership: Case ownership is derived strictly from `CaseParticipant`. Do not use a separate client_id field.*

### 6. CaseParticipant
- **id**: UUID (PK)
- **case_id**: UUID (FK -> Case.id, Not Null)
- **user_id**: UUID (FK -> User.id, Not Null)
- **participant_role**: ENUM (OWNER, LAWYER, VIEWER)
- **status**: ENUM (ACTIVE, INACTIVE)
- **joined_at**: TIMESTAMPTZ (Not Null)
- **ended_at**: TIMESTAMPTZ (Nullable)
- **created_at**: TIMESTAMPTZ
- **updated_at**: TIMESTAMPTZ
*Constraints: `UNIQUE(case_id, user_id)`. Active membership uniqueness enforced via constraint/partial index.*
*Purpose: Authoritative mapping for case membership and authorization.*

### 7. Document
- **id**: UUID (PK)
- **case_id**: UUID (FK -> Case.id, Not Null)
- **uploaded_by**: UUID (FK -> User.id, Not Null)
- **filename**: VARCHAR (Not Null)
- **storage_key**: VARCHAR (Unique, Not Null)
- **mime_type**: VARCHAR (Not Null)
- **file_size**: INTEGER (Not Null)
- **security_status**: ENUM (QUARANTINED, VALIDATING, SCANNING, SAFE, REJECTED)
- **created_at**: TIMESTAMPTZ
- **updated_at**: TIMESTAMPTZ
- **deleted_at**: TIMESTAMPTZ (Nullable) - Soft delete.
*Lifecycle: One file = one row. Do not overwrite stored documents. New uploads = new rows.*

### 8. Consultation
- **id**: UUID (PK)
- **client_id**: UUID (FK -> ClientProfile.id, Not Null)
- **lawyer_id**: UUID (FK -> LawyerProfile.id, Not Null)
- **case_id**: UUID (FK -> Case.id, Nullable)
- **scheduled_at**: TIMESTAMPTZ (Not Null)
- **duration_minutes**: INTEGER (Not Null)
- **fee_amount**: NUMERIC (Not Null)
- **currency**: VARCHAR (Not Null)
- **status**: ENUM (REQUESTED, ACCEPTED, PAID, SCHEDULED, IN_PROGRESS, COMPLETED, CANCELLED, REJECTED, NO_SHOW)
- **completed_at**: TIMESTAMPTZ (Nullable)
- **rejection_reason**: VARCHAR (Nullable)
- **created_at**: TIMESTAMPTZ
- **updated_at**: TIMESTAMPTZ
- **deleted_at**: TIMESTAMPTZ (Nullable) - Soft delete.

### 9. Payment
- **id**: UUID (PK)
- **consultation_id**: UUID (FK -> Consultation.id, Not Null)
- **payer_user_id**: UUID (FK -> User.id, Not Null)
- **amount**: NUMERIC (Not Null)
- **currency**: VARCHAR (Not Null)
- **status**: ENUM (CREATED, PENDING, SUCCEEDED, FAILED, REFUNDED)
- **provider**: VARCHAR (Not Null)
- **provider_payment_id**: VARCHAR (Unique, Nullable)
- **created_at**: TIMESTAMPTZ
- **updated_at**: TIMESTAMPTZ
*Lifecycle: Immutable financial record. No soft deletion allowed. Status transitions are controlled.*

### 10. AuditEvent
- **id**: UUID (PK)
- **actor_user_id**: UUID (FK -> User.id, Nullable)
- **event_type**: VARCHAR (Not Null)
- **entity_type**: VARCHAR (Not Null)
- **entity_id**: UUID (Nullable)
- **action**: VARCHAR (Not Null)
- **timestamp**: TIMESTAMPTZ (Not Null)
- **metadata**: JSONB (Nullable)
*Lifecycle: Append-only, completely immutable. No UPDATE, NO DELETE, NO soft delete. Never store secrets.*

### 11. RefreshTokenSession
- **id**: UUID (PK)
- **user_id**: UUID (FK -> User.id, Not Null)
- **token_family_id**: UUID (Not Null)
- **token_hash**: VARCHAR (Not Null)
- **created_at**: TIMESTAMPTZ (Not Null)
- **last_used_at**: TIMESTAMPTZ (Not Null)
- **expires_at**: TIMESTAMPTZ (Not Null)
- **revoked_at**: TIMESTAMPTZ (Nullable)
- **device_metadata**: VARCHAR (Nullable)
- **ip_metadata**: VARCHAR (Nullable)
*Lifecycle: Mutable through controlled session lifecycle operations (not append-only). Not soft-deleted.*

### 12. CaseTimelineEvent
- **id**: UUID (PK)
- **case_id**: UUID (FK -> Case.id, Not Null)
- **actor_user_id**: UUID (FK -> User.id, Nullable)
- **event_type**: VARCHAR (Not Null)
- **description**: TEXT (Not Null)
- **event_metadata**: JSON (Nullable)
- **created_at**: TIMESTAMPTZ
- **updated_at**: TIMESTAMPTZ
*Lifecycle: Append-only business history of a case visible to authorized users.*

### 13. CaseTask
- **id**: UUID (PK)
- **case_id**: UUID (FK -> Case.id, Not Null)
- **title**: VARCHAR (Not Null)
- **description**: TEXT (Nullable)
- **status**: ENUM (PENDING, IN_PROGRESS, COMPLETED, CANCELLED)
- **priority**: ENUM (LOW, MEDIUM, HIGH, URGENT)
- **due_date**: TIMESTAMPTZ (Nullable)
- **owner_user_id**: UUID (FK -> User.id, Nullable)
- **created_by_user_id**: UUID (FK -> User.id, Nullable)
- **completed_at**: TIMESTAMPTZ (Nullable)
- **created_at**: TIMESTAMPTZ
- **updated_at**: TIMESTAMPTZ
- **deleted_at**: TIMESTAMPTZ (Nullable) - Soft delete.
*Lifecycle: Task items assigned to case participants with deadline tracking.*

### 14. CaseNote
- **id**: UUID (PK)
- **case_id**: UUID (FK -> Case.id, Not Null)
- **author_user_id**: UUID (FK -> User.id, Not Null)
- **title**: VARCHAR (Nullable)
- **content**: TEXT (Not Null)
- **is_private**: BOOLEAN (Not Null, default False)
- **created_at**: TIMESTAMPTZ
- **updated_at**: TIMESTAMPTZ
- **deleted_at**: TIMESTAMPTZ (Nullable) - Soft delete.
*Lifecycle: Matter notes with author-level privacy boundaries.*

### 15. Notification
- **id**: UUID (PK)
- **user_id**: UUID (FK -> User.id, Not Null)
- **type**: ENUM (CASE_CREATED, CASE_STATUS_CHANGED, PARTICIPANT_ADDED, LAWYER_ASSIGNED, TASK_ASSIGNED, TASK_DUE_SOON, TASK_COMPLETED, CONSULTATION_REQUESTED, CONSULTATION_ACCEPTED, CONSULTATION_REJECTED, CONSULTATION_SCHEDULED, CONSULTATION_CANCELLED, CONSULTATION_COMPLETED, PAYMENT_CREATED, PAYMENT_SUCCEEDED, PAYMENT_FAILED, PAYMENT_REFUNDED)
- **title**: VARCHAR(255) (Not Null)
- **message**: VARCHAR(1000) (Not Null)
- **case_id**: UUID (FK -> Case.id, Nullable)
- **consultation_id**: UUID (FK -> Consultation.id, Nullable)
- **task_id**: UUID (FK -> CaseTask.id, Nullable)
- **metadata**: JSON (Nullable)
- **is_read**: BOOLEAN (Not Null, default False)
- **read_at**: TIMESTAMPTZ (Nullable)
- **created_at**: TIMESTAMPTZ
- **updated_at**: TIMESTAMPTZ
- **deleted_at**: TIMESTAMPTZ (Nullable) - Soft delete.
*Lifecycle: In-app user notifications generated by domain events.*

### 16. VideoMeeting
- **id**: UUID (PK)
- **consultation_id**: UUID (FK -> Consultation.id, Not Null, Unique)
- **room_id**: VARCHAR(255) (Not Null, Unique)
- **provider**: VARCHAR(50) (Not Null, default 'internal_webrtc')
- **status**: ENUM (SCHEDULED, ACTIVE, COMPLETED, CANCELLED)
- **host_user_id**: UUID (FK -> User.id, Nullable)
- **started_at**: TIMESTAMPTZ (Nullable)
- **ended_at**: TIMESTAMPTZ (Nullable)
- **created_at**: TIMESTAMPTZ
- **updated_at**: TIMESTAMPTZ
*Lifecycle: Manages live meeting room metadata and provider session mapping.*

### 17. VideoRecordingConsent
- **id**: UUID (PK)
- **consultation_id**: UUID (FK -> Consultation.id, Not Null)
- **user_id**: UUID (FK -> User.id, Not Null)
- **consented**: BOOLEAN (Not Null, default False)
- **consented_at**: TIMESTAMPTZ (Nullable)
- **created_at**: TIMESTAMPTZ
- **updated_at**: TIMESTAMPTZ
- Unique Constraint: `(consultation_id, user_id)`
*Lifecycle: Enforces dual-consent legal requirements for consultation recordings.*

### 18. VideoRecording
- **id**: UUID (PK)
- **consultation_id**: UUID (FK -> Consultation.id, Not Null)
- **case_id**: UUID (FK -> Case.id, Nullable)
- **recording_type**: VARCHAR(50) (Not Null, default 'browser_media_recorder')
- **status**: ENUM (PENDING, RECORDING, UPLOADING, AVAILABLE, FAILED, DELETED)
- **started_at**: TIMESTAMPTZ (Nullable)
- **ended_at**: TIMESTAMPTZ (Nullable)
- **duration_seconds**: INTEGER (Nullable)
- **file_size_bytes**: BIGINT (Nullable)
- **mime_type**: VARCHAR(100) (Not Null, default 'video/webm')
- **checksum_sha256**: VARCHAR(64) (Nullable)
- **storage_path**: VARCHAR(500) (Not Null)
- **created_at**: TIMESTAMPTZ
- **updated_at**: TIMESTAMPTZ
- **deleted_at**: TIMESTAMPTZ (Nullable) - Soft delete.
*Lifecycle: Stores consultation recording metadata with cryptographic integrity verification.*

## 5. RELATIONSHIP MODEL
- `User` → `ClientProfile` (0..1)
- `User` → `LawyerProfile` (0..1)
- `User` → `RefreshTokenSession` (1:N)
- `User` → `AuditEvent` (1:N)
- `User` → `CaseParticipant` (1:N)
- `User` → `Payment` as payer (1:N)
- `User` → `Notification` (1:N)
- `Case` → `CaseParticipant` (1:N)
- `Case` → `Document` (1:N)
- `Case` → `CaseTimelineEvent` (1:N)
- `Case` → `CaseTask` (1:N)
- `Case` → `CaseNote` (1:N)
- `Case` → `Consultation` (1:N)
- `Case` → `Notification` (1:N)
- `LawyerProfile` → `LawyerVerification` (1:N)
- `LawyerProfile` → `Consultation` (1:N)
- `ClientProfile` → `Consultation` (1:N)
- `Consultation` → `Payment` (1:N)
- `Consultation` → `Notification` (1:N)
- `CaseTask` → `Notification` (1:N)
- `Document` → `uploaded_by User`

## 6. OWNERSHIP SEMANTICS
- `User`: owns/controls their own account identity.
- `ClientProfile`: belongs to User.
- `LawyerProfile`: belongs to User.
- `Case`: owned/participated through `CaseParticipant`.
- `Document`: belongs to Case and explicitly records `uploaded_by` User.
- `Consultation`: relates authorized client + lawyer + case.
- `Payment`: belongs to the financial transaction and explicitly identifies `payer_user_id`.
- `AuditEvent`: belongs to the audit/security system.
- `CaseTimelineEvent`: belongs to a Case and records an actor.

## 7. AUTHORIZATION MATRIX

| Entity | Client | Lawyer | Admin |
|--------|--------|--------|-------|
| `User` | Own Identity | Own Identity | Scoped Admin Access |
| `Profile` | Own | Own | Scoped Admin Access |
| `Case` | Own/Authorized via CaseParticipant | Assigned via CaseParticipant | Scoped Admin Access |
| `Document` | Authorized Case Docs | Assigned Case Docs | Scoped Admin Access |
| `Consultation` | Participant | Participant | Scoped Admin Access |
| `Payment` | Own | Related context | Scoped Admin Access |

*Note: Admins have explicit scoped permissions and privileged access must be auditable. Admins do not receive automatic unrestricted access to legal documents.*

## 8. DATA INTEGRITY & RELATIONSHIPS

**Primary Keys**: All PKs are native `UUID` (generated as UUIDv7 by the application).
**Foreign Keys**: Default delete behavior is `ON DELETE RESTRICT` to prevent accidental cascading data loss.
**Soft Delete**: Core entities (`User`, `ClientProfile`, `LawyerProfile`, `Case`, `Document`, `Consultation`) use `deleted_at`.
**Unique Constraints**:
- `User.email`
- `User.phone`
- `ClientProfile.user_id`
- `LawyerProfile.user_id`
- `CaseParticipant.(case_id, user_id)`
- `Document.storage_key`
- `Payment.provider_payment_id` (Nullable Unique)

## 9. INDEXING STRATEGY
Indexes must be created to support frequent query paths and soft deletion filters:
- **User**: `email`, `phone`
- **ClientProfile**: `user_id`
- **LawyerProfile**: `user_id`
- **CaseParticipant**: `user_id`, `case_id`
- **Document**: `case_id`, `uploaded_by`
- **Consultation**: `client_id`, `lawyer_id`
- **Payment**: `provider_payment_id`, `payer_user_id`
- **RefreshTokenSession**: `token_family_id`, `user_id`
- **AuditEvent**: `actor_user_id`, `entity_id`
- **CaseTimelineEvent**: `case_id`
- **Partial Indexes**: Queries on soft-deletable tables should use partial indexes where `deleted_at IS NULL`. Active membership constraints may require partial unique indexing.

## 10. DECISION REGISTER

| Decision | Status | Reason |
|---|---|---|
| Core Entity Schema | FINAL | Core attributes and FKs are frozen |
| Case Ownership Model | FINAL | CaseParticipant handles case authorization |
| Payment Integrity | FINAL | Financial facts are immutable post-settlement |
| Document Immutability | FINAL | New uploads create new Document records |
| AuditEvent Immutability | FINAL | Append-only. No UPDATE, DELETE, or soft-delete. |

## 11. EVIDENCE LOCKER DOMAIN MODEL (PHASE XIV)

Phase XIV introduces the dedicated, high-security Evidence Locker schema:

### 1. `evidence`
Primary entity for legally sensitive evidence objects.
- `id`: UUID (PK, UUIDv7)
- `case_id`: UUID (FK cases.id, NOT NULL)
- `created_by_user_id`: UUID (FK users.id, NOT NULL)
- `current_version_id`: UUID (FK evidence_versions.id, Nullable)
- `title`: VARCHAR(255) (NOT NULL)
- `description`: VARCHAR(1000) (Nullable)
- `category`: Enum (FORENSIC, FINANCIAL, CONTRACTUAL, DIGITAL, TESTIMONIAL, REGULATORY, PHYSICAL_SCAN, MISCELLANEOUS)
- `status`: Enum (UPLOADING, QUARANTINED, ACTIVE, REVOKED, DELETION_PENDING, DELETED)
- `sensitivity`: Enum (STANDARD, CONFIDENTIAL, HIGHLY_CONFIDENTIAL, PRIVILEGED)
- `original_filename`: VARCHAR(255) (NOT NULL)
- `legal_hold`: BOOLEAN (Default FALSE)
- `legal_hold_reason`: VARCHAR(500) (Nullable)
- `retention_until`: TIMESTAMPTZ (Nullable)
- `created_at`, `updated_at`, `deleted_at`: TIMESTAMPTZ

### 2. `evidence_versions`
Immutable versions preserving cryptographic SHA-256 digests and storage pointers.
- `id`: UUID (PK, UUIDv7)
- `evidence_id`: UUID (FK evidence.id, ON DELETE CASCADE)
- `version_number`: INTEGER (NOT NULL)
- `uploaded_by_user_id`: UUID (FK users.id)
- `storage_key`: VARCHAR(512) (UNIQUE, NOT NULL)
- `original_filename`: VARCHAR(255) (NOT NULL)
- `content_type`: VARCHAR(100) (NOT NULL)
- `size_bytes`: BIGINT (NOT NULL)
- `sha256`: VARCHAR(64) (NOT NULL, SHA-256 hex digest)
- `scan_status`: Enum (PENDING, VALIDATING, SCANNING, PASSED, FAILED)
- `scan_details`: VARCHAR(500) (Nullable)
- `integrity_status`: Enum (UNVERIFIED, VERIFIED_MATCH, TAMPER_DETECTED)
- `last_verified_at`: TIMESTAMPTZ (Nullable)
- `created_at`, `updated_at`: TIMESTAMPTZ
- UniqueConstraint: `(evidence_id, version_number)`

### 3. `evidence_access_grants`
Controlled client/lawyer sharing grants with granular permissions and expiration.
- `id`: UUID (PK, UUIDv7)
- `evidence_id`: UUID (FK evidence.id, ON DELETE CASCADE)
- `grantee_user_id`: UUID (FK users.id, ON DELETE CASCADE)
- `granted_by_user_id`: UUID (FK users.id)
- `access_level`: Enum (VIEW, DOWNLOAD, MANAGE)
- `expires_at`: TIMESTAMPTZ (Nullable)
- `revoked_at`: TIMESTAMPTZ (Nullable)
- `revocation_reason`: VARCHAR(255) (Nullable)
- `created_at`, `updated_at`: TIMESTAMPTZ

### 4. `evidence_custody_events`
Immutable, chronological chain-of-custody audit ledger.
- `id`: UUID (PK, UUIDv7)
- `evidence_id`: UUID (FK evidence.id, ON DELETE CASCADE)
- `version_id`: UUID (FK evidence_versions.id, ON DELETE SET NULL)
- `actor_user_id`: UUID (FK users.id)
- `action`: Enum (UPLOADED, SCAN_PASSED, SCAN_FAILED, SHARED, ACCESS_REVOKED, VIEWED, DOWNLOADED, INTEGRITY_VERIFIED, INTEGRITY_FAILED, VERSION_CREATED, LEGAL_HOLD_APPLIED, LEGAL_HOLD_REMOVED, DELETION_REQUESTED, DELETED)
- `previous_event_id`: UUID (FK evidence_custody_events.id, Nullable - chronological backward reference)
- `timestamp`: TIMESTAMPTZ (Server-side default NOW())
- `metadata`: JSON (Nullable)

