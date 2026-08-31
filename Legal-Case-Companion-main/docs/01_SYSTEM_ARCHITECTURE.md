STATUS: DRAFT
AUTHORITY: DERIVED FROM PROJECT SOURCE OF TRUTH
SOURCE DOCUMENT: docs/00_PROJECT_CONTEXT.md
IMPLEMENTATION STATUS: NOT STARTED
RULE: ARCHITECTURE MUST NOT INVENT PRODUCT REQUIREMENTS

# System Architecture

## 1. ARCHITECTURE OBJECTIVES
The technical goals of the system are intended to support a sensitive, secure, and reliable legal assistance platform:
- **reliability**: The system must be highly available for clients and lawyers, especially during consultations and document uploads.
- **security**: Given the nature of legal cases and payment information, security is a paramount architectural driver.
- **maintainability**: The architecture must allow clean separation of different domains (e.g., cases, lawyers, payments) for long-term maintainability.
- **scalability**: The system must be capable of scaling, especially concerning potentially heavy AI workloads and document storage.
- **modularity**: Clear boundaries between logical modules to prevent tightly coupled code.
- **data isolation**: Strict enforcement of data access rules where a client or lawyer can only access authorized information.
- **observability**: Comprehensive logging, metrics, and tracing to detect anomalies, errors, or unauthorized access attempts.
- **testability**: Separation of business logic from external dependencies to allow thorough unit and integration testing.
- **deployment flexibility**: The architecture should not be heavily vendor-locked at the application code level, allowing deployment to various environments.

## 2. SYSTEM BOUNDARY

**INSIDE SYSTEM**
The following components and responsibilities belong inside the Legal Case Companion:
- client-facing application interaction
- lawyer-facing application interaction
- admin operations
- backend API
- authentication
- authorization
- case management
- document management
- consultation management
- payment orchestration
- AI orchestration
- notifications orchestration
- audit logging

**OUTSIDE SYSTEM**
The following services are external dependencies:
- payment provider: PROPOSED: Stripe (STATUS: DECISION REQUIRED)
- email provider: EXTERNAL PROVIDER — DECISION REQUIRED
- SMS provider: EXTERNAL PROVIDER — DECISION REQUIRED
- video consultation provider: EXTERNAL PROVIDER — DECISION REQUIRED
- AI provider: FINAL: OpenAI (Model: DECISION REQUIRED)
- cloud infrastructure: FINAL: Render
- object storage provider: FINAL: AWS S3

## 3. HIGH-LEVEL ARCHITECTURE

```text
       Client Applications
   (Client, Lawyer, Admin User Interfaces)
                |
                v
        API / Backend Layer
    (API, Auth, Validation, Logic)
                |
       +--------+--------+
       |                 |
       v                 v
   Database         External Services
 (Relational/     (AI, Payments, Email,
  Document)        Storage, Video, SMS)
       |
       v
Internal Services
(Background Jobs)
```

- **Client Applications**: The user interfaces through which users interact with the system.
- **API / Backend Layer**: The core system processing requests, enforcing security, and containing the business logic.
- **Database**: Stores the persistent, structured application data.
- **External Services**: Third-party providers used for specialized functionality.
- **Internal Services**: Asynchronous workers handling background tasks like notifications or document processing.

## 4. CLIENT APPLICATIONS
The known users interacting with the backend are:
- CLIENT
- LAWYER
- ADMIN

These users will interact with the backend API to perform their respective activities.

Frontend technology (e.g., web, Android, iOS, React, Flutter): DECISION REQUIRED.

## 5. BACKEND ARCHITECTURE
The backend architecture consists of several logical layers:
- **API layer**: Exposes endpoints and handles HTTP requests/responses.
- **authentication layer**: Verifies the identity of the incoming request.
- **authorization layer**: Ensures the authenticated user has the rights to perform the requested action.
- **validation**: Ensures the incoming data payload is structurally and logically correct.
- **business logic**: Implements the core product rules (e.g., booking a consultation, managing a case).
- **data access**: Manages reading from and writing to the database.
- **external service integration**: Adapters that communicate with external providers (e.g., payment gateways).
- **background processing**: Manages asynchronous tasks to prevent blocking API responses.
- **error handling**: Catches exceptions and returns standardized error responses.
- **audit logging**: Records critical and sensitive operations for traceability.

Communication generally flows downwards: API → Auth → Validation → Business Logic → Data Access / External Integration.

## 6. BACKEND MODULES
Logical modules identified from the project context:
- **authentication**: Manages user identity, login, and sessions.
- **users**: Manages general user profiles.
- **lawyers**: Manages lawyer-specific professional profiles.
- **lawyer verification**: Handles the workflow for verifying lawyer credentials.
- **lawyer discovery**: Logic for searching and displaying suitable lawyers (e.g., by location).
- **cases**: Core case information management.
- **case participants**: Maps the relationships between cases and users (clients/lawyers).
- **consultations**: Manages consultation requests and state.
- **appointments**: Handles scheduling and availability.
- **documents**: Manages document metadata and access control.
- **payments**: Orchestrates fee collection and payment state.
- **notifications**: Triggers alerts to users.
- **case timeline**: Tracks events and case history.
- **tasks/deadlines**: Manages action items and time limits.
- **AI**: Orchestrates AI interactions and controls data exposure.
- **audit**: Handles recording of system and access events.
- **administration**: Supports platform-level operations.

*IMPORTANT: These are logical modules and do NOT automatically represent microservices or specific database tables.*

## 7. MODULAR MONOLITH VS MICROSERVICES

**FINAL ARCHITECTURAL DECISION**

Comparison considerations:
- **project complexity**: Current known features can be encapsulated in a single codebase.
- **development speed**: Monoliths are generally faster to develop initially.
- **operational complexity**: Microservices require complex orchestration, networking, and tracing.
- **scalability**: Monoliths can scale horizontally behind a load balancer; microservices allow independent scaling.
- **deployment**: Monoliths have simpler deployment pipelines.
- **debugging**: Tracing requests across microservices is significantly harder.
- **team size**: Microservices benefit large, distributed teams; monoliths suit smaller initial teams.
- **future evolution**: A well-structured modular monolith can be split later if needed.

**FINAL**: Modular Monolith. Given the project stage, a modular monolith minimizes operational complexity while maintaining logical boundaries, accelerating initial development.

## 8. REQUEST LIFECYCLE
A standard backend request follows this lifecycle:
1. **Client**: Sends an HTTP request.
2. **API**: Receives the request and routes it.
3. **authentication**: Verifies who the user is.
4. **authorization**: Checks if the user is allowed to access the specific resource.
5. **validation**: Validates the payload format and constraints.
6. **business logic**: Executes the core functionality.
7. **database/external service**: Persists data or calls third parties.
8. **response**: Formats and returns the result to the client.
9. **logging/audit**: Records the outcome asynchronously where applicable.

## 9. AUTHENTICATION ARCHITECTURE
The system must establish and verify identity.
- **identity**: Uniquely identifying a user across the system.
- **login**: The process of proving identity.
- **session/token concept**: The mechanism to maintain authentication across multiple requests.
- **authentication verification**: The middleware that checks tokens/sessions on incoming requests.
- **logout**: Invalidating the current session.
- **account security**: Mechanisms to protect user accounts.

Exact authentication method: FINAL: JWT-based authentication with securely hashed passwords and refresh-token architecture.

## 10. AUTHORIZATION ARCHITECTURE
The system must distinguish access between CLIENT, LAWYER, and ADMIN.
- **role-level access**: Admins have different baseline permissions than Clients or Lawyers.
- **resource-level access**: A user must be authorized for the specific resource ID requested.
- **case ownership**: A client strictly owns their case data.
- **authorized case participants**: Lawyers granted access to a specific case by the client.
- **document access**: Document retrieval is strictly tied to case authorization.

## 11. CASE DATA FLOW
1. **Client** → **authenticated request**
2. → **authorization** (ensures user is authorized via CaseParticipant)
3. → **case service** (business logic)
4. → **database** (retrieval/storage)

The system must prevent unauthorized access to another user's case at the authorization layer before any data is returned.

## 12. DOCUMENT DATA FLOW
**Upload:**
Client → upload request → authorization → document handling → storage (quarantine) → validation/malware scan → mark safe → metadata (database) → case association.

**Retrieval:**
Lawyer (or Client) → authorization (checks case participation) → document access → retrieval from storage.

Storage provider: FINAL: AWS S3.

## 13. AI DATA FLOW
User → Backend → Authorization → Approved case data → AI processing (Backend to AI) → Backend → User.

The AI must NOT automatically have unrestricted database access. The backend acts as an orchestrator, strictly controlling and filtering what case information is sent to the AI system.

AI provider: FINAL: OpenAI. AI model: DECISION REQUIRED. Vector database/embedding model: DECISION REQUIRED.

## 14. PAYMENT FLOW
Client → Backend → Payment Provider (External) → Payment Result (Webhook/Callback) → Backend → Consultation/Booking State (Updated in DB).

Payment provider: PROPOSED: Stripe (STATUS: DECISION REQUIRED).

## 15. NOTIFICATION FLOW
Backend events (e.g., consultation updates, case changes, task deadlines, payment success) trigger notification requests to an internal service or external provider.
Providers (email/SMS/push): DECISION REQUIRED.

## 16. BACKGROUND PROCESSING
The following operations may require asynchronous processing:
- notifications dispatch
- document processing (e.g., OCR, mandatory malware scanning before safe marking)
- AI processing (long-running inferences)
- scheduled tasks (e.g., deadline reminders)
- background maintenance

Queue technology: DECISION REQUIRED.

## 17. DATABASE ARCHITECTURE
The database is responsible for:
- **persistent application data**: Storing users, cases, and metadata securely.
- **relationships**: Mapping clients to lawyers, cases to documents.
- **transactions**: Ensuring data integrity (e.g., booking a consultation and processing payment).
- **consistency**: Maintaining valid application state.
- **authorization boundaries**: Storing the rules mapping users to resources.
- **migrations**: Managing schema changes over time.

Database technology: FINAL: PostgreSQL. ORM: FINAL: SQLAlchemy. Migrations: FINAL: Alembic.

## 18. FILE STORAGE ARCHITECTURE
The architecture distinguishes between structural data and files:
- **DATABASE**: Stores metadata, ownership, relationships, permissions, and references to files.
- **FILE/OBJECT STORAGE**: Stores the actual uploaded legal documents, consultation attachments, and potentially large objects.

Storage provider: FINAL: AWS S3.

## 19. EXTERNAL SERVICES
Conceptual dependencies required:
- payment: PROPOSED: Stripe (STATUS: DECISION REQUIRED)
- AI: FINAL: OpenAI (Model: DECISION REQUIRED)
- email: STATUS: DECISION REQUIRED
- SMS: STATUS: DECISION REQUIRED
- video consultation: STATUS: DECISION REQUIRED
- object storage: FINAL: AWS S3
- maps/location: STATUS: DECISION REQUIRED

## 20. SECURITY BOUNDARIES
Trust boundaries flow as follows:
Client ↓ Internet ↓ Backend API ↓ Internal services ↓ Database ↓ External services

The Backend API is the primary trust boundary. It must:
- enforce authentication and authorization.
- protect sensitive case data from unauthorized access.
- control document access securely.
- manage and hide secrets/API keys from the client.
- validate all data before passing it to internal services or the database.

## 21. DATA OWNERSHIP PRINCIPLE
Users must only access resources they are authorized to access.
- Client A must not access Client B's case.
- A lawyer must only access cases for which the lawyer is authorized.
- An admin may have elevated access according to future administrative rules.

## 22. AUDIT ARCHITECTURE
Important actions must generate audit records to track who did what and when, including:
- authentication events
- case access
- document access
- case modifications
- lawyer verification
- payment events
- administrative actions
- AI-related sensitive operations

## 23. ERROR HANDLING ARCHITECTURE
General principles:
- **validation errors**: Return clear field-level issues to the client (e.g., 400 Bad Request).
- **authentication errors**: Reject unauthenticated requests securely (e.g., 401 Unauthorized).
- **authorization errors**: Reject unauthorized access without revealing resource existence (e.g., 403 or 404).
- **resource-not-found errors**: Standardized missing resource responses.
- **external-service failures**: Handle gracefully and log internally; do not expose third-party stack traces.
- **internal failures**: Log securely and return generic server error messages to the client.

## 24. ENVIRONMENTS
- **DEVELOPMENT**: For local engineering and developer testing.
- **STAGING**: A pre-production environment mirroring production for QA and validation.
- **PRODUCTION**: The live environment serving real clients and lawyers.

## 25. DEPLOYMENT ARCHITECTURE
The deployment must conceptually include:
- application runtime
- database
- storage
- networking (load balancers, firewalls)
- secrets management
- logging aggregation
- monitoring tools
- backups

Deployment provider: FINAL: Render.

## 26. SCALABILITY
The system can scale via:
- **stateless backend**: Allowing horizontal scaling of the API layer.
- **horizontal scaling**: Adding more application instances.
- **database scaling**: Read replicas or connection pooling.
- **caching**: Reducing database load for frequently accessed data.
- **background jobs**: Offloading heavy work from the main request thread.
- **file storage**: Using scalable object storage.
- **AI workload isolation**: Running AI requests on separate worker infrastructure to prevent blocking the main API.

## 27. RELIABILITY
The architecture ensures reliability through:
- **failure isolation**: Ensuring one failing module doesn't crash the entire system.
- **retries**: For transient external service failures.
- **timeouts**: Preventing stalled requests.
- **transaction consistency**: Database transactions for critical multi-step updates.
- **backups**: Automated disaster recovery for the database.
- **recovery**: Documented processes for system restoration.
- **external-service failures**: Fallback mechanisms when possible.

## 28. OBSERVABILITY
The system requires:
- **application logs**: To trace application flow and debug issues.
- **error tracking**: To automatically capture and group unhandled exceptions.
- **metrics**: To monitor system health (CPU, memory, request rates).
- **health checks**: Endpoints for load balancers to verify service availability.
- **audit logs**: For security and compliance tracking.
- **monitoring**: Dashboards and alerts for operational oversight.

## 29. ARCHITECTURE DECISION REGISTER

| Frontend Technology | DECISION REQUIRED | Not yet defined | 00_PROJECT_CONTEXT.md | UI Development |
| Backend Framework | FINAL: Python + FastAPI | Approved | 00_PROJECT_CONTEXT.md | API Development |
| Database Technology | FINAL: PostgreSQL | Approved | 00_PROJECT_CONTEXT.md | Data Persistence |
| Arch. Pattern | FINAL: Modular Monolith | Approved | Section 7 | System Topology |
| Authentication Method | FINAL: JWT | Approved | 00_PROJECT_CONTEXT.md | Security |
| Cloud Provider | FINAL: Render | Approved | 00_PROJECT_CONTEXT.md | Infrastructure |
| External Providers (AI) | FINAL: OpenAI | Approved | 00_PROJECT_CONTEXT.md | AI Integration |
| Payment Provider | PROPOSED: Stripe | DECISION REQUIRED | 00_PROJECT_CONTEXT.md | Payments |

## 30. ARCHITECTURE RISKS
- **sensitive legal data**: Risk of exposure if authorization boundaries fail.
- **unauthorized case access**: Potential for data leaks between users.
- **document security**: Unsecured storage leading to confidential file access.
- **external service dependency**: Reliance on third-party uptime (e.g., Payments, AI).
- **AI data exposure**: Accidentally sending too much case context to external AI providers.
- **payment failures**: Dropped webhooks leading to inconsistent consultation states.
- **scalability**: AI or document processing overwhelming the API servers.
- **data consistency**: Incomplete transactions corrupting case state.
- **operational complexity**: Managing logs, secrets, and deployments securely.

## 31. TRACEABILITY
To ensure architecture decisions align with product requirements:
- SOURCE: `00_PROJECT_CONTEXT.md` → Target Users (Validates Client, Lawyer, Admin boundaries in Sections 4, 10)
- SOURCE: `00_PROJECT_CONTEXT.md` → Backend Responsibilities (Validates Backend Modules in Section 6)
- SOURCE: `00_PROJECT_CONTEXT.md` → Important Data (Validates Security Boundaries and Data Ownership in Sections 20, 21)
- SOURCE: `00_PROJECT_CONTEXT.md` → AI Role (Validates AI Data Flow in Section 13)
- SOURCE: `00_PROJECT_CONTEXT.md` → Important Unknown Information (Validates DECISION REQUIRED statuses throughout)
