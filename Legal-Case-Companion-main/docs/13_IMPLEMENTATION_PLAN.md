STATUS: DRAFT
AUTHORITY: IMPLEMENTATION ROADMAP
SOURCE DOCUMENTS:
- docs/00_PROJECT_CONTEXT.md
- docs/01_SYSTEM_ARCHITECTURE.md
- docs/02_DATABASE_DESIGN.md
- docs/03_API_SPECIFICATION.md
- docs/04_AUTHORIZATION_SECURITY.md
- docs/05_BACKEND_MODULES.md
- docs/06_AI_INTEGRATION.md
- docs/07_FILE_DOCUMENT_SYSTEM.md
- docs/08_PAYMENT_CONSULTATION.md
- docs/09_INFRASTRUCTURE_DEPLOYMENT.md
- docs/10_TESTING_STRATEGY.md
- docs/11_ENVIRONMENT_CONFIGURATION.md
- docs/12_ENGINEERING_RULES.md
- docs/00_DECISION_REGISTER.md

IMPLEMENTATION STATUS: NOT STARTED

RULE:
IMPLEMENT ONLY DOCUMENTED REQUIREMENTS. DO NOT STRUCTURE AS "BUILD EVERYTHING -> TEST EVERYTHING". USE "IMPLEMENT PHASE -> TEST/VERIFY -> APPROVE PHASE -> CONTINUE".

# Implementation Roadmap Specification

## 1. PURPOSE
Provides the ordered roadmap and sequence for engineering implementation.

## 2. IMPLEMENTATION PRINCIPLES
- Implement phase -> test/verify -> approve phase -> continue.
- Build foundations before dependent features.
- Authentication must exist before protected APIs.
- Authorization must exist before sensitive resource APIs.
- Database foundation must exist before repository/database-dependent modules.
- Document authorization must exist before document access.
- Payment infrastructure must exist before payment flows.
- AI infrastructure must exist before RAG/AI features.

## 3. IMPLEMENTATION PHASES

### PHASE 1: PROJECT BOOTSTRAP & DEVELOPMENT FOUNDATION
- **Status**: IMPLEMENTED
- **Objective**: Establish the core backend project structure, environment configuration, and infrastructure scaffolding.
- **Files Created**: `pyproject.toml`, `.env.example`, `app/main.py`, `app/core/config.py`, `app/core/logging.py`, `app/core/exceptions.py`, `app/middleware/correlation_id.py`, `app/db/database.py`, `app/models/base.py`, `alembic.ini`, `migrations/env.py`, `pytest.ini`, `tests/unit/test_app.py`
- **Validation**: Python environment execution initially failed locally, but has been completely resolved by leveraging `uv` via `.uv_dir/uv.exe`.
- **Known Limitations**: None.

### PHASE 2: DATABASE FOUNDATION
- **Status**: IMPLEMENTED
- **Objective**: Setup PostgreSQL database connection, SQLAlchemy ORM, and Alembic migrations.
- **Prerequisites**: Phase 1.
- **Implementation Work**: Configured database connection pool. Setup Alembic. Defined base ORM models (implementing UUIDv7 primary keys, TIMESTAMPTZ created_at/updated_at with PostgreSQL triggers, soft-delete). Created 12 core entity models (`User`, `ClientProfile`, `LawyerProfile`, `LawyerVerification`, `Case`, `CaseParticipant`, `Document`, `Consultation`, `Payment`, `AuditEvent`, `RefreshTokenSession`, `CaseTimelineEvent`).
- **Validation/Tests**: Alembic migration commands execute successfully against local SQLite and are structurally verified for PostgreSQL. Enum recreation and constraints successfully mapped.
- **Completion Criteria**: ORM models are mapped. Migrations are tested and validated for upgrade/downgrade.
- **Dependencies**: Database infrastructure.

### PHASE 3: AUTHENTICATION
- **Objective**: Implement JWT-based authentication with refresh tokens.
- **Prerequisites**: Phase 2.
- **Implementation Work**: Implement user registration and login endpoints. Implement JWT access tokens (EdDSA, 15m TTL), opaque refresh tokens (HttpOnly cookies, 30d TTL), and strict refresh-token rotation. Implement double-submit CSRF protection and strict rate limiting. Secure password hashing using Argon2id.
- **Validation/Tests**: Unit tests for JWT logic. API tests for login, registration, unauthorized access.
- **Completion Criteria**: Users can securely register, login, receive tokens, and access an authenticated test endpoint.
- **Dependencies**: Database (User entity).

### PHASE 4: AUTHORIZATION
- **Objective**: Implement resource-based and role-based access control.
- **Prerequisites**: Phase 3.
- **Implementation Work**: Implement RBAC middleware (Admin vs Client vs Lawyer). Implement resource ownership validation (e.g., Case ownership, CaseParticipants).
- **Validation/Tests**: Security tests: Client A cannot access Client B's case. Lawyer cannot access unassigned case.
- **Completion Criteria**: Middleware correctly blocks unauthorized requests and allows authorized ones.
- **Dependencies**: Authentication.

### PHASE 5: CORE BUSINESS MODULES (CASES & LAWYERS)
- **Objective**: Implement core case management and lawyer discovery/profiles.
- **Prerequisites**: Phase 4.
- **Implementation Work**: Implement Case creation, updates, and participant mapping. Implement Lawyer profiles and search/discovery logic.
- **Validation/Tests**: Unit tests for business logic. API tests for Case CRUD and Lawyer endpoints. Negative tests for case access.
- **Completion Criteria**: Clients can create cases, Lawyers can be listed and assigned to cases.
- **Dependencies**: Authorization.

### PHASE 6: DOCUMENT SYSTEM
- **Objective**: Implement secure file storage and document metadata management.
- **Prerequisites**: Phase 5.
- **Implementation Work**: Setup AWS S3 integration. Implement document metadata DB operations. Implement upload quarantine, MIME/size validation (10MB max), and malware scanning pipeline before marking documents safe. Implement pre-signed URL generation for secure upload/download. Enforce document authorization.
- **Validation/Tests**: Integration tests with mocked S3 and mock malware scanner. Security tests verifying unauthorized users cannot generate pre-signed URLs or access raw S3 objects.
- **Completion Criteria**: Authorized users can securely upload and retrieve documents for their cases.
- **Dependencies**: Cases, AWS S3 infrastructure.

### PHASE 7: CONSULTATIONS & PAYMENTS
- **Objective**: Implement consultation booking and payment integration.
- **Prerequisites**: Phase 5 (Lawyer Discovery).
- **Implementation Work**: Implement consultation booking logic. Integrate payment provider (Decision Required: Stripe). Implement server-side webhook verification and idempotency logic.
- **Validation/Tests**: API tests for booking. E2E tests for payment flow using test cards. Webhook security and idempotency tests.
- **Completion Criteria**: Client can successfully book and pay for a consultation, updating state securely via webhooks.
- **Dependencies**: Consultation booking logic, Payment Provider.

### PHASE 8: AI INTEGRATION
- **Objective**: Implement evidence-grounded AI assistance using OpenAI.
- **Prerequisites**: Phase 6 (Documents), Phase 5 (Cases).
- **Implementation Work**: Integrate OpenAI API. Implement authorized data retrieval (RAG) ensuring context isolation. Implement prompt injection defenses and claim verification logic.
- **Validation/Tests**: AI security tests (prompt injection). Grounding tests. Case isolation tests (AI cannot access wrong case).
- **Completion Criteria**: AI successfully answers case-related queries using only authorized context without hallucinating.
- **Dependencies**: Documents, Cases, OpenAI provider.

### PHASE 9: DEPLOYMENT & PRODUCTION READINESS
- **Objective**: Deploy the system to Render and finalize production observability.
- **Prerequisites**: All previous phases.
- **Implementation Work**: Configure Render deployment pipeline (CI/CD). Setup production secrets, monitoring, and database backups.
- **Validation/Tests**: Deployment testing. Smoke testing in Staging. Backup/restore verification.
- **Completion Criteria**: System is live on Staging and Production with passing health checks and monitoring alerts configured.
- **Dependencies**: CI/CD pipeline, Cloud Provider (Render).
