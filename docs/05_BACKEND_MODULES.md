STATUS: DRAFT

AUTHORITY: DERIVED FROM PROJECT SOURCE OF TRUTH

SOURCE DOCUMENTS:
- docs/00_PROJECT_CONTEXT.md
- docs/01_SYSTEM_ARCHITECTURE.md
- docs/02_DATABASE_DESIGN.md
- docs/03_API_SPECIFICATION.md
- docs/04_AUTHORIZATION_SECURITY.md

IMPLEMENTATION STATUS: NOT STARTED

RULE:
BACKEND MODULES MUST IMPLEMENT DOCUMENTED REQUIREMENTS, NOT INVENT NEW ONES

# Backend Modules

## 1. PURPOSE
The backend must be divided into logical modules to achieve:
- **separation of concerns**: Ensuring domains like payments and cases do not leak logic into each other.
- **maintainability**: Making it easier to locate, update, and fix domain-specific logic.
- **testability**: Allowing individual domains to be unit tested in isolation.
- **security**: Enforcing authorization boundaries strictly per module.
- **clear ownership**: Establishing responsibilities for each part of the codebase.
- **controlled dependencies**: Preventing tangled, circular imports across the application.
- **easier future scaling**: Laying the foundation for future extraction into independent services if required.
- **easier onboarding**: Helping new developers understand domain boundaries.
- **easier debugging**: Localizing bugs to specific modules.

## 2. ARCHITECTURAL STYLE
Based on `docs/01_SYSTEM_ARCHITECTURE.md`, the backend organization style is:
STATUS: FINAL
FINAL: Modular Monolith. The codebase will be deployed as a single application, but internally structured into strict, isolated domain modules.

## 3. MODULE DESIGN PRINCIPLES
- **each module has a clear responsibility**: Modules should do one thing well (e.g., Document module handles file metadata).
- **business logic should not be duplicated**: Shared behaviors should be centralized in their authoritative module.
- **modules should not bypass authorization**: Internal module boundaries must still respect context-based access control.
- **modules should not directly manipulate unrelated domains**: A module should call the API/service of another module rather than writing directly to its database tables.
- **sensitive operations require explicit access control**: Modules exposing AI or payment features must validate roles and permissions.
- **dependencies should flow in predictable directions**: e.g., API layer → Business Logic → Infrastructure.
- **shared utilities must remain limited**: A shared/core module should not become a dumping ground for unrelated code.

## 4. MODULE CATEGORIES
Backend functionality is organized into logical categories based on the source documents:
- **IDENTITY**: Authentication and general Users.
- **BUSINESS**: Cases, Case Timeline, Tasks/Deadlines, Consultations.
- **DOCUMENTS**: Documents domain.
- **AI**: AI interactions and orchestration.
- **PAYMENTS**: Payment orchestrations.
- **COMMUNICATION**: Notifications.
- **ADMINISTRATION**: Admin and Lawyer Verification.
- **INFRASTRUCTURE**: Shared, DB access, external integrations.

## 5. IDENTITY / AUTHENTICATION MODULE
**Responsibility**: To manage and verify the identity of callers.
- user identity establishing
- registration and login
- logout and session termination
- account verification workflows
- credential lifecycle (e.g., password reset, if applicable)
- session/token lifecycle management

(Exact authentication technology is FINAL: JWT with refresh tokens).

## 6. USER MODULE
**Responsibility**: General user domain management.
Distinction:
- **USER IDENTITY**: Belongs to the Authentication module (credentials, tokens).
- **USER PROFILE**: Belongs to the User module (general system references to the user entity).

Profile fields are currently UNDEFINED.

## 7. CLIENT MODULE
**Responsibility**: Client-specific profile functionality.
- client profile management.
- handling client-specific attributes.
*(Note: Client-owned case interactions belong to the Case module, and consultations to the Consultation module. The Client module manages the Client entity only).*

## 8. LAWYER MODULE
**Responsibility**: Lawyer-specific professional domain.
- lawyer profile management.
- professional information.
- practice areas.
- availability configurations.
- lawyer-facing operations (profile updates).

## 9. LAWYER VERIFICATION MODULE
Whether lawyer verification deserves its own module or belongs inside the Lawyer or Admin module:
STATUS: DECISION REQUIRED
PROPOSED: Place inside the Admin module as an administrative workflow, interacting with the Lawyer module.
(Verification providers and exact workflow states are DECISION REQUIRED).

## 10. LAWYER DISCOVERY MODULE
**Responsibility**: Finding suitable lawyers for clients.
- search and filtering.
- location-based queries.
- practice area queries.
- availability checking.

CRITICAL: Ranking algorithms and recommendation logic are NOT defined.
STATUS: DECISION REQUIRED.

## 11. CASE MODULE
**Responsibility**: Core legal case domain.
- case creation and lifecycle.
- case ownership mapping.
- case retrieval and updates.
- case participant management (authorized lawyers).

## 12. CASE TIMELINE / EVENT MODULE
Whether case events belong inside the Case module or should be separated:
STATUS: DECISION REQUIRED
PROPOSED: Inside the Case module as a sub-domain, since timeline events tightly couple to the case lifecycle.

## 13. TASK / DEADLINE MODULE
**Responsibility**: Tracking action items and time limits related to cases.
- tasks and deadlines creation/updates.
- status tracking.
(Reminder mechanisms are UNDEFINED; Notifications will handle delivery).

## 14. DOCUMENT MODULE
**Responsibility**: Document domain metadata and access.
- document metadata storage.
- upload coordination, quarantine, and malware scanning pipeline.
- authorization for viewing/downloading.
- case association.
- retrieval coordination.

Important: This module handles **DOCUMENT BUSINESS LOGIC**, separating it entirely from **FILE STORAGE INFRASTRUCTURE** (e.g., S3/Blob storage adapters).

## 15. CONSULTATION MODULE
**Responsibility**: Consultation domain and workflow.
- consultation relationship mapping (client, lawyer, case).
- consultation information handling.
- consultation lifecycle.
(Consultation states are DECISION REQUIRED).

## 16. APPOINTMENT / SCHEDULING MODULE
Whether appointment scheduling belongs inside Consultation or requires a separate module:
STATUS: DECISION REQUIRED
(Scheduling complexity, rules, and future calendar integrations are undefined).

## 17. PAYMENT MODULE
**Responsibility**: Coordinating application-level payment operations with an external provider.
Conceptual flow: Application → Payment Module → External Provider → Payment Module → Application.
DO NOT: choose a provider, implement provider logic, invent payment statuses, or store unnecessary payment credentials.

## 18. NOTIFICATION MODULE
**Responsibility**: Notification domain.
- create notification records on domain events (`NotificationService.create_notification`).
- determine recipients (case participants, consultation parties, payment actors).
- manage notification state (`is_read`, `read_at`, `mark_all_as_read`).
- bounded pagination and unread counts (`GET /api/v1/notifications`, `GET /api/v1/notifications/unread-count`).
- delivery boundary coordination (non-blocking invocation of `EmailService` / future Push providers).
- strict BOLA isolation and 404 security defense.

STATUS: FINAL (Implemented via `NotificationService` and `app/api/v1/notifications.py`).

## 19. AI MODULE
**Responsibility**: Backend boundary around AI interactions.
CRITICAL: The AI module must NOT provide unrestricted database access to AI systems.
Expected flow:
Authenticated User → Authorization → AI Module → retrieve only authorized data → prepare controlled AI request → AI Provider → validate/process response → return result.
- AI request orchestration.
- authorization-aware data retrieval.
- grounding/data preparation.
- AI provider communication.
- response handling and traceability.
- audit support.

(AI provider, model, vector DB, embeddings belong to `docs/06_AI_INTEGRATION.md` and are DECISION REQUIRED).

## 20. LEGAL SOURCE MODULE
Whether legal-source handling belongs in its own module:
STATUS: DECISION REQUIRED
(Legal data sources and research functionality are UNDEFINED).

## 21. AUDIT MODULE
**Responsibility**: Audit logging for accountability.
- security-sensitive events.
- case access events.
- document events.
- administrative events.
- payment events.
- AI-sensitive events.
(Audit logging must not unnecessarily store sensitive content. Schema is UNDEFINED).

## 22. ADMIN MODULE
**Responsibility**: Administrative functionality.
- user administration.
- platform operations.
- suspicious activity management.
- lawyer verification workflows (proposed).
(Admins do not have unrestricted access by default. Requires strict RBAC).

## 23. SHARED / CORE MODULE
**Responsibility**: Truly shared application infrastructure.
- application configuration.
- standard error handling utilities.
- common types and interfaces.
- logging utilities.
- security primitives (e.g., hashing helpers).
- dependency management.
IMPORTANT: Avoid turning this into a dumping ground.

## 24. INFRASTRUCTURE MODULES
Separate business modules from infrastructure concerns.
Infrastructure concerns include:
- database access (ORM/Query builders).
- object/file storage clients.
- cache clients.
- background job runners.
- external service clients (Email, SMS, Payment, AI).
(Specific technologies are DECISION REQUIRED).

## 25. ROUTER / CONTROLLER LAYER
**API / Router layer**: Handles external HTTP concerns (request parsing, authentication context extraction, basic payload validation, response formatting).
**Business logic**: Handles domain operations, authorization decisions, and business rules.
The API layer should not contain raw business logic.

## 26. SERVICE LAYER
**Role of application/business services**: To encapsulate the core business logic of a module.
Services should be used to orchestrate complex operations (e.g., creating a case and notifying a lawyer). Avoid meaningless pass-through services. Business logic must have a clear module owner.

## 27. REPOSITORY / DATA ACCESS LAYER
**Role**: To separate **BUSINESS LOGIC** from **DATABASE ACCESS**.
The business service should not write raw SQL; it should call a repository or data access component that handles persistence. (Implementation pattern: DECISION REQUIRED).

## 28. EXTERNAL SERVICE INTEGRATION LAYER
**Role**: Architectural boundary for external providers (AI, payment, email, SMS, video, storage).
Each integration must be isolated behind an interface so providers can be replaced without rewriting core business logic.

## 29. DEPENDENCY RULES
Allowed dependency direction:
`API / Routers` ↓ `Application / Domain Services` ↓ `Data Access / Infrastructure`
- Modules may call other modules' Domain Services.
- External providers MUST be accessed through integration boundaries in the Infrastructure layer.
- Cross-module database joining (bypassing the owner module's service) is strictly prohibited.

## 30. MODULE OWNERSHIP

| Module | Responsibility | Owns Entity | Consumes | Exposes | Security Sensitivity | Status |
|---|---|---|---|---|---|---|
| Auth | Identity | User | - | Login/Tokens | High | KNOWN |
| Client | Client data | ClientProfile | Auth | Profile updates | Medium | KNOWN |
| Lawyer | Lawyer data | LawyerProfile | Auth | Profile APIs | Medium | KNOWN |
| Case | Legal matters | Case, Participants | Auth, Client, Lawyer | Case APIs | Very High | KNOWN |
| Document | File metadata | Document | Case, Storage | Upload/Download | Very High | KNOWN |
| Consultation | Bookings | Consultation | Client, Lawyer | Booking APIs | High | KNOWN |
| Payment | Financial | Payment | Consultation, Ext. Provider | Checkout APIs | High | KNOWN |
| Notification | Alerting & In-App | Notification | Case, Consultation, Payment, User | Notification APIs | High | FINAL |
| AI | AI assistance | AIInteraction | Case, Document, Ext. AI | AI queries | Very High | KNOWN |
| Admin | Admin tasks | AuditLog | All | Admin workflows | High | KNOWN |

## 31. MODULE INTERACTION MAP
Major interactions supported by documents:
- **Client** → Authentication → Case → Consultation → Payment
- **Case** → Documents, Case Timeline, Tasks, AI
- **Lawyer** → Lawyer Verification, Lawyer Discovery, Consultation, Cases
- **Consultation** → Payment
- **AI** → Case (for authorized context retrieval)

## 32. CROSS-CUTTING CONCERNS
- **authentication**: Applied at the Router/API layer middleware.
- **authorization**: Applied at the Router and Service layers.
- **validation**: Applied at the Router layer (payloads) and Service layer (business rules).
- **logging**: Applied across all layers via Shared core.
- **audit**: Triggered by Business Services into the Audit module.
- **error handling**: Standardized at the Router layer.
- **configuration**: Managed by Shared core.
- **transactions**: Managed at the Service layer (coordinating multiple DB writes).

## 33. TRANSACTION OWNERSHIP
Multi-step business operations require clear ownership:
- *Booking + Payment coordination*: Owned by the Consultation module (or Payment module if acting as the orchestrator).
- *Case + Document association*: Owned by the Case module.
(Detailed transaction designs are justified by source requirements).

## 34. BACKGROUND JOB BOUNDARY
Modules that may eventually need background processing:
- **notifications**: Dispatching emails/SMS asynchronously.
- **document processing**: Malware scanning (mandatory pipeline step before safe marking) or OCR.
- **AI tasks**: Long-running inference jobs.
- **scheduled tasks**: Deadline reminders.
(Job framework: DECISION REQUIRED).

## 35. FUTURE EXTRACTION TO SERVICES
Modules that could potentially become independent microservices later if scaling demands it:
- **AI**: Heavy computational loads or strict isolation needs.
- **payments**: Strict PCI-compliance boundary separation.
- **notifications**: High-throughput async delivery.
- **document processing**: Resource-intensive file operations.
(DO NOT split prematurely. Base architecture remains Modular Monolith).

## 36. MODULE DECISION REGISTER

| Decision | Status | Reason | Source | Impact |
|---|---|---|---|---|
| Arch. Style | FINAL: Modular Monolith | Approved | 01 - Architecture | Deployment |
| Lawyer Verification Boundary | DECISION REQUIRED | Proposed in Admin | Docs | Module design |
| Scheduling Boundary | DECISION REQUIRED | Undefined complexity | Docs | Module design |
| Case Timeline / Events | DECISION REQUIRED | Proposed in Case | Docs | Module design |
| AI Integration Boundary | DECISION REQUIRED | Provider unknown | Docs | Infrastructure |
| Document Storage Boundary | DECISION REQUIRED | Provider unknown | Docs | Infrastructure |

## 37. MODULE TRACEABILITY

| Module | Source Document | Source Section | Requirement | Status |
|---|---|---|---|---|
| Authentication | 01_SYSTEM_ARCHITECTURE.md | 5. Backend Arch. | Prove identity | KNOWN |
| Case | 00_PROJECT_CONTEXT.md | Known Product Flow | Case management | KNOWN |
| Document | 01_SYSTEM_ARCHITECTURE.md | 12. Document Data Flow | File handling | KNOWN |
| Consultation | 00_PROJECT_CONTEXT.md | Known Product Flow | Booking | KNOWN |
| Payment | 00_PROJECT_CONTEXT.md | Known Product Flow | Consultation fee | KNOWN |
| AI | 01_SYSTEM_ARCHITECTURE.md | 13. AI Data Flow | Secure AI access | KNOWN |
| Admin | 00_PROJECT_CONTEXT.md | Target Users | Platform ops | KNOWN |

## 38. MODULE RISKS
- **excessive coupling**: Modules bypassing APIs and importing each other's ORM models.
- **circular dependencies**: e.g., Case depends on Consultation, and Consultation depends on Case.
- **authorization bypass**: Services forgetting to accept or validate the user context object.
- **duplicated business logic**: e.g., Multiple modules writing their own case access checks.
- **shared-module growth**: The core module becoming a monolithic utility bin.
- **sensitive-data leakage**: Logs in the shared module accidentally dumping payment or case data.
- **unclear ownership**: Confusion over who handles appointment time conflicts (Consultation vs Lawyer module).

## 39. UNDEFINED / DECISION REQUIRED
Unresolved module-architecture decisions:

- Exact boundary for Lawyer Verification (Admin vs Lawyer).
- Exact boundary for Scheduling/Appointments (Consultation vs new module).
- Exact boundary for Case Timeline / Events.
- Legal Source handling module.
- Background Job runner framework.
- Specific infrastructure adapters for storage, payments, AI, and notifications.
- Lawyer Discovery ranking algorithms and specific matching logic.
