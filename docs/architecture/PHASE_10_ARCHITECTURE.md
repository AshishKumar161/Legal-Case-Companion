# Phase 10: Backend Domain-Oriented Architecture Specification

**Phase Status:** Complete & Verified  
**Baseline Tests:** 848/848 pytest tests passing, 129/129 security tests passing  
**Linters & Compilers:** Python `compileall` (0 errors), Ruff (0 errors), Mypy (0 errors across all source files), TypeScript (0 errors), ESLint (0 errors, 0 warnings), Next.js Build (PASS)

---

## 1. Executive Summary

Phase 10 refactors the Legal Case Companion (LCC) backend from a flat, centralized `app/services/` organization (75 services in a single folder) into a clean, domain-oriented architecture under `app/domain/` without altering API contracts, changing database migrations, or breaking test coverage.

### Key Architectural Achievements:
1. **Domain Bounded Contexts Established:** 11 domain packages created under `app/domain/` with explicit public API exports.
2. **Persistence Repositories Introduced:** 6 domain repositories established under `app/repositories/` to encapsulate query patterns.
3. **Strict Layer Direction Enforced:** `API -> Domain / Application Services -> Repositories / Providers`. Zero reverse imports from Domain or Repositories into the API layer.
4. **Signaling Layer Decoupling:** Relocated `VideoSignalingManager` from `app/api/v1/video_signaling.py` to `app/domain/consultations/video_signaling_manager.py`, eliminating all 6 circular dependency chains involving services and the API.
5. **100% Backward Compatibility:** Transparent compatibility facades maintained in `app/services/*.py` to guarantee zero disruptions to external callers, cron daemons, Celery tasks, or existing test suites.

---

## 2. Target Directory Hierarchy

```
app/
├── api/                                      # Presentation Layer (FastAPI)
│   ├── deps.py                               # Dependency Injection (Auth, DB, RBAC)
│   └── v1/                                   # 44 versioned API routers (329 paths, 388 operations)
│
├── core/                                     # Core runtime infrastructure
│   ├── config.py                             # Settings & environment validation
│   ├── security.py                           # Cryptography, JWT, password hashing
│   ├── logging.py                            # Structured JSON logging & correlation IDs
│   ├── errors.py                             # Exception hierarchy
│   ├── metrics.py                            # Telemetry & Prometheus metrics
│   └── identifiers.py                        # UUIDv7 generation
│
├── domain/                                   # Bounded Domain Contexts
│   ├── auth/                                 # AuthService, GoogleOAuthService, SessionCleanupService
│   ├── cases/                                # CaseService, Workflow, Attention, Intelligence, Bundle
│   ├── documents/                            # DocumentService, DocumentProcessor, LegalDocumentService
│   ├── evidence/                             # EvidenceService, ScannerService (ClamAV & Heuristics)
│   ├── consultations/                        # ConsultationService, VideoMeetingService, Signaling, Recording
│   ├── verification/                         # LawyerVerificationService, Dashboard, CohortGovernance
│   ├── payments/                             # PaymentService, CommercialService, Reconciliation
│   ├── ai/                                   # AI Conversation, Research, Retrieval, Pipeline, Citations
│   │   └── legal_source_providers/           # Legal data ingestion adapters (e-Courts, Curated)
│   ├── notifications/                        # NotificationService, ReminderService, EmailService
│   ├── users/                                # UserService, ProfileService, Lifecycle, Admin, Support
│   ├── jobs/                                 # JobService, OutboxService, JobWorker, JobScheduler
│   └── governance/                           # LaunchGateService, IncidentService, Compliance, Abuse
│
├── models/                                   # SQLAlchemy 2.0 ORM Declarative Models
├── schemas/                                  # Pydantic V2 Request & Response Schemas
├── repositories/                             # Domain Persistence Repositories
│   ├── user_repository.py                    # User & Profile persistence queries
│   ├── case_repository.py                    # Case & CaseParticipant queries
│   ├── document_repository.py                # Document storage & metadata queries
│   ├── consultation_repository.py            # Consultation & VideoMeeting queries
│   ├── payment_repository.py                 # Payment & Transaction queries
│   └── job_repository.py                     # BackgroundJob & Idempotency queries
│
├── providers/                                # Infrastructure Provider Boundary
│   └── ai/                                   # Canonical AI Providers (OpenAI, Mock, Base)
│
├── db/                                       # Database engine & session pooling
├── middleware/                               # Request pipeline middleware (CORS, CSRF, Correlation ID)
├── scheduler.py                              # Scheduler daemon CLI entry point
└── worker.py                                 # Worker daemon CLI entry point
```

---

## 3. Domain Responsibility Mapping

| Domain Package | Canonical Services | Primary Responsibilities |
|---|---|---|
| **`app/domain/auth/`** | `AuthService`<br>`GoogleOAuthService`<br>`SessionCleanupService` | Credential validation, token issuance, OAuth 2.0 code exchange, cryptographic verification, expired session cleanup. |
| **`app/domain/cases/`** | `CaseService`<br>`CaseWorkflowService`<br>`CaseAttentionService`<br>`CaseIntelligenceService`<br>`CaseReportService`<br>`CollaborationService`<br>`BundleService`<br>`BundlePdfEngine` | Matter management, participant roles (Owner, Lawyer, Viewer), stage transitions, case summaries, court bundle PDF compilation. |
| **`app/domain/documents/`** | `DocumentService`<br>`DocumentProcessor`<br>`LegalDocumentService` | Case document lifecycle, PDF text extraction, chunking, legal templates. |
| **`app/domain/evidence/`** | `EvidenceService`<br>`ScannerService` | Cryptographic SHA-256 evidence locker, chain-of-custody logging, ClamAV and heuristic virus scanning. |
| **`app/domain/consultations/`** | `ConsultationService`<br>`VideoMeetingService`<br>`VideoSignalingManager`<br>`VideoRecordingService`<br>`RecordingStorage`<br>`PresenceService`<br>`IncomingCallChannelManager` | Consultation scheduling, LiveKit/WebRTC meeting room access tokens, real-time WebSocket signaling, video recording preservation. |
| **`app/domain/verification/`** | `LawyerVerificationService`<br>`LawyerDashboardService`<br>`CohortGovernanceService` | Bar council credential verification, manual review workflows, lawyer discovery metrics, advocate cohort staging. |
| **`app/domain/payments/`** | `PaymentService`<br>`CommercialService`<br>`ReconciliationService`<br>`CancellationPolicyService`<br>`UnitEconomicsService` | Stripe payment intents, webhook deduplication, financial reconciliation, banker's rounding, refund economics. |
| **`app/domain/ai/`** | `AIConversationService`<br>`AIResearchService`<br>`CaseAssistantService`<br>`AIBudgetService`<br>`AIReviewService`<br>`PromptSecurityPolicy`<br>`RetrievalService`<br>`LegalDataPipeline` | Conversational legal AI, pgvector semantic retrieval, prompt injection defense, statutory citation normalization. |
| **`app/domain/notifications/`**| `NotificationService`<br>`ReminderService`<br>`EmailService`<br>`AlertService` | In-app notification feeds, hearing deadline alerts, transactional emails via SMTP/Console, operational alerts. |
| **`app/domain/users/`** | `UserService`<br>`ProfileService`<br>`LifecycleService`<br>`AdminService`<br>`OperatorService`<br>`SupportService` | User account management, lawyer & client profiles, GDPR data export/deletion, administrative audit operations. |
| **`app/domain/jobs/`** | `JobService`<br>`OutboxService`<br>`JobWorker`<br>`JobScheduler`<br>`ChangeFeedService` | Transactional outbox event emission, distributed worker execution, lease locking (`SKIP LOCKED`), scheduled cron jobs. |
| **`app/domain/governance/`** | `LaunchGateService`<br>`IncidentService`<br>`ComplianceService`<br>`AbuseDefenseService`<br>`TranslationService`<br>`ExperimentService` | Public launch gates, incident response tracking, disposable email defense, multilanguage translation, A/B testing. |

---

## 4. Repositories Layer Specification

To prevent repeated inline SQLAlchemy queries throughout service modules while preserving database transactions and concurrency semantics:

1. **`UserRepository` (`app/repositories/user_repository.py`)**:
   - `get_by_id(user_id: UUID) -> User | None`
   - `get_by_email(email: str) -> User | None`
   - `get_advocate_profile(user_id: UUID) -> AdvocateProfile | None`
   - `get_client_profile(user_id: UUID) -> ClientProfile | None`
   - `exists_by_email(email: str) -> bool`
2. **`CaseRepository` (`app/repositories/case_repository.py`)**:
   - `get_by_id(case_id: UUID) -> Case | None`
   - `get_by_id_and_owner(case_id: UUID, user_id: UUID) -> Case | None`
   - `list_by_user(user_id: UUID, status: CaseStatus | None = None) -> list[Case]`
   - `count_by_user(user_id: UUID, status: CaseStatus | None = None) -> int`
3. **`DocumentRepository` (`app/repositories/document_repository.py`)**:
   - `get_by_id(document_id: UUID) -> Document | None`
   - `list_by_case(case_id: UUID) -> list[Document]`
   - `count_by_case(case_id: UUID) -> int`
4. **`ConsultationRepository` (`app/repositories/consultation_repository.py`)**:
   - `get_by_id(consultation_id: UUID) -> Consultation | None`
   - `list_by_client(client_id: UUID) -> list[Consultation]`
   - `list_by_lawyer(lawyer_id: UUID) -> list[Consultation]`
   - `get_video_meeting(consultation_id: UUID) -> VideoMeeting | None`
5. **`PaymentRepository` (`app/repositories/payment_repository.py`)**:
   - `get_by_id(payment_id: UUID) -> Payment | None`
   - `get_by_consultation(consultation_id: UUID) -> Payment | None`
   - `get_by_provider_payment_id(provider_payment_id: str) -> Payment | None`
   - `list_by_payer(payer_user_id: UUID) -> list[Payment]`
6. **`JobRepository` (`app/repositories/job_repository.py`)**:
   - `get_by_id(job_id: UUID) -> BackgroundJob | None`
   - `get_by_idempotency_key(idempotency_key: str) -> BackgroundJob | None`
   - `list_by_status(status: JobStatus) -> list[BackgroundJob]`
   - `count_by_status(status: JobStatus) -> int`

---

## 5. Backward-Compatibility Strategy

All 75 original service files under `app/services/*.py` are maintained as clean, lightweight backward-compatibility facades. Each facade explicitly re-exports canonical domain classes, types, and constants.

```python
"""Backward-compatibility facade for AuthService.

Canonical domain implementation: app.domain.auth.auth_service.
This facade preserves existing imports across legacy callers and tests.
"""

from app.domain.auth.auth_service import AuthService

__all__ = ["AuthService"]
```

This guarantees:
- **Zero test regressions:** Any existing test importing from `app.services.<module>` resolves immediately.
- **Zero Celery/Worker failures:** Job types and task modules continue to function without modifying operational configurations.
- **Future safe deprecation:** In Phase 11 and 12, callers will be systematically updated, allowing safe eventual retirement of `app/services`.
