# Phase 3: Service Hookup & Integration Matrix

**Execution Date**: September 10, 2026  
**Repository**: Legal Case Companion (LCC)  
**Phase**: Phase 3 Service Integration & Background Worker Reliability  
**Audit Scope**: All 71 service files in `app/services/`  

---

## 1. Classification Scheme

Each domain service in the application is audited and classified into one of five categories:
- **A. REQUIRED AND WIRED**: Active in production API workflows, background worker jobs, or domain business operations.
- **B. INTENTIONALLY UNUSED**: Feature flags, experiment cohorts, or dormant integrations intentionally isolated.
- **C. OBSOLETE / REPLACED**: Superseded by modern implementations; retained safely without deletion per non-destructive refactoring rules.
- **D. TEST-ONLY**: Test harnesses or mocks specifically scoped to testing suites.
- **E. UNKNOWN**: Requires further architectural clarification.

---

## 2. Complete Service Audit Matrix

| # | Service Class / Module | File Path | Classification | Production Trigger / Hook Point | Notes & Integrations |
|---|---|---|---|---|---|
| 1 | `AbuseDefenseService` | `app/services/abuse_defense_service.py` | **A. REQUIRED AND WIRED** | `app/api/v1/auth.py` (`/register`), `app/services/consultation_service.py` (`request_consultation`) | Disposable email domain blocking, registration risk evaluation, and client consultation booking velocity limit enforcement. |
| 2 | `AdminService` | `app/services/admin_service.py` | **A. REQUIRED AND WIRED** | `app/api/v1/admin.py` | Platform health monitoring, user account administrative management, and system-wide metrics. |
| 3 | `AIBudgetService` | `app/services/ai_budget_service.py` | **A. REQUIRED AND WIRED** | `app/api/v1/ai.py` (`/research`), `app/api/v1/assistant.py` (`/query`) | Server-side quota validation and token budget tracking executed prior to invoking LLM providers. |
| 4 | `AIConversationService` | `app/services/ai_conversation_service.py` | **A. REQUIRED AND WIRED** | `app/api/v1/ai.py` | Conversational legal copilot context management and persistence. |
| 5 | `AIEvaluationService` | `app/services/ai_evaluation_service.py` | **A. REQUIRED AND WIRED** | `app/api/v1/ai.py` | RAG answer quality, hallucination detection, and citation faithfulness scoring. |
| 6 | `AIProvider` / `GeminiProvider` / `OpenAIProvider` | `app/services/ai_provider.py` | **A. REQUIRED AND WIRED** | `app/services/ai_conversation_service.py`, `assistant_service.py` | Multi-provider LLM abstraction layer with automatic failover and structured output formatting. |
| 7 | `AIResearchService` | `app/services/ai_research_service.py` | **A. REQUIRED AND WIRED** | `app/api/v1/ai.py` | Automated case law synthesis, statutory analysis, and legal research brief generation. |
| 8 | `AIReviewService` | `app/services/ai_review_service.py` | **A. REQUIRED AND WIRED** | `app/services/document_service.py` | AI-assisted contract review and risk clause identification. |
| 9 | `AlertService` | `app/services/alert_service.py` | **A. REQUIRED AND WIRED** | `app/api/v1/alerts.py` | SRE and security incident alerting thresholds. |
| 10 | `CaseAssistantService` | `app/services/assistant_service.py` | **A. REQUIRED AND WIRED** | `app/api/v1/assistant.py` | Context-aware legal case copilot grounded in uploaded case evidence. |
| 11 | `AuthService` | `app/services/auth_service.py` | **A. REQUIRED AND WIRED** | `app/api/v1/auth.py`, `app/api/deps.py` | JWT generation, password hashing, MFA verification, and audit event recording. |
| 12 | `BundlePdfEngine` | `app/services/bundle_pdf_engine.py` | **A. REQUIRED AND WIRED** | `app/services/bundle_service.py` | PDF compilation, watermark rendering, pagination, and legal bundle index generation. |
| 13 | `BundleService` | `app/services/bundle_service.py` | **A. REQUIRED AND WIRED** | `app/api/v1/bundles.py` | Court bundle assembly, evidence sequencing, and secure bundle generation. |
| 14 | `CancellationPolicyService` | `app/services/cancellation_policy_service.py` | **A. REQUIRED AND WIRED** | `app/services/consultation_service.py` (`cancel_consultation`) | Canonical tier-based cancellation evaluation, fee calculation, and automated refund dispatch. |
| 15 | `CaseAttentionService` | `app/services/case_attention_service.py` | **A. REQUIRED AND WIRED** | `app/api/v1/cases.py`, `app/api/v1/dashboard.py` | Prioritization scoring for cases requiring imminent attorney intervention. |
| 16 | `CaseIntelligenceService` | `app/services/case_intelligence_service.py` | **A. REQUIRED AND WIRED** | `app/services/case_service.py` | Legal timeline extraction, entity extraction, and case strength assessment. |
| 17 | `CaseReportService` | `app/services/case_report_service.py` | **A. REQUIRED AND WIRED** | `app/api/v1/cases.py` | Comprehensive PDF/JSON summary report generation for court filings. |
| 18 | `CaseService` | `app/services/case_service.py` | **A. REQUIRED AND WIRED** | `app/api/v1/cases.py` | Core legal case CRUD, multi-tenant isolation, and case audit history. |
| 19 | `CaseWorkflowService` | `app/services/case_workflow_service.py` | **A. REQUIRED AND WIRED** | `app/api/v1/cases.py` | State machine governing case lifecycle transitions from intake to judgment. |
| 20 | `ChangeFeedService` | `app/services/change_feed_service.py` | **A. REQUIRED AND WIRED** | `app/services/outbox_service.py` | Real-time domain event streaming and event stream broadcasting. |
| 21 | `CitationNormalizer` | `app/services/citation_normalizer.py` | **A. REQUIRED AND WIRED** | `app/services/legal_authority_retrieval.py` | Normalizes Indian legal citations (e.g., SCC, AIR, ILR) into canonical forms. |
| 22 | `ClaimVerifier` | `app/services/claim_verifier.py` | **A. REQUIRED AND WIRED** | `app/services/ai_research_service.py` | Validates factual and legal claims against authoritative source documents. |
| 23 | `CohortGovernanceService` | `app/services/cohort_governance_service.py` | **A. REQUIRED AND WIRED** | `app/api/v1/pilot.py` | Pilot phase cohort gating, allowlist management, and capacity quotas. |
| 24 | `CollaborationService` | `app/services/collaboration_service.py` | **A. REQUIRED AND WIRED** | `app/api/v1/cases.py` | Co-counsel and paralegal case sharing, permission delegates, and role assignment. |
| 25 | `CommercialService` | `app/services/commercial_service.py` | **A. REQUIRED AND WIRED** | `app/api/v1/payments.py`, `app/services/consultation_service.py` | Fee calculation, platform commission deduction, escrow hold, and refund processing. |
| 26 | `ComplianceService` | `app/services/compliance_service.py` | **A. REQUIRED AND WIRED** | `app/api/v1/compliance.py` | Regulatory retention policies, legal hold management, and data export audits. |
| 27 | `ConsultationService` | `app/services/consultation_service.py` | **A. REQUIRED AND WIRED** | `app/api/v1/consultations.py` | Instant & scheduled consultation bookings, state transitions, access windows, and cancellation. |
| 28 | `DocumentProcessor` | `app/services/document_processor.py` | **A. REQUIRED AND WIRED** | `app/services/job_worker.py` | Background OCR, text extraction, chunking, and embedding generation for legal documents. |
| 29 | `DocumentService` | `app/services/document_service.py` | **A. REQUIRED AND WIRED** | `app/api/v1/documents.py` | Secure S3 pre-signed upload URL generation, virus scan gating, and metadata management. |
| 30 | `EmailService` | `app/services/email_service.py` | **A. REQUIRED AND WIRED** | Auth, notifications, consultations, and verification | Production transactional email delivery (SMTP/SES) with local development logging fallback. |
| 31 | `EmbeddingProvider` | `app/services/embedding_provider.py` | **A. REQUIRED AND WIRED** | `app/services/embedding_service.py` | Text vector embedding interface supporting OpenAI and local sentence transformers. |
| 32 | `EmbeddingService` | `app/services/embedding_service.py` | **A. REQUIRED AND WIRED** | `app/services/document_processor.py` | Document chunk vectorization and indexing into PostgreSQL pgvector / semantic index. |
| 33 | `EvidenceService` | `app/services/evidence_service.py` | **A. REQUIRED AND WIRED** | `app/api/v1/evidence.py` | Chain-of-custody tracking, cryptographic hashing (SHA-256), and evidence metadata. |
| 34 | `ExperimentService` | `app/services/experiment_service.py` | **B. INTENTIONALLY UNUSED** | Feature flags harness | Internal A/B experiment evaluation harness; intentionally dormant during pilot cohort launch. |
| 35 | `GoogleOAuthService` | `app/services/google_oauth_service.py` | **A. REQUIRED AND WIRED** | `app/api/v1/auth.py` | Google OpenID Connect token validation and social registration/login. |
| 36 | `IncidentService` | `app/services/incident_service.py` | **A. REQUIRED AND WIRED** | `app/api/v1/incidents.py` | Production incident response, runbook tracking, and SLA tracking. |
| 37 | `JobScheduler` | `app/services/job_scheduler.py` | **A. REQUIRED AND WIRED** | `app/scheduler.py` | Periodic cron job dispatcher for stale meeting cleanup, deadline reminders, and log rotation. |
| 38 | `JobService` | `app/services/job_service.py` | **A. REQUIRED AND WIRED** | `app/api/v1/jobs.py` | Asynchronous task enqueueing, status polling, and execution metadata. |
| 39 | `JobWorker` | `app/services/job_worker.py` | **A. REQUIRED AND WIRED** | `app/worker.py` | Background job execution engine for video cleanup, deadline reminders, and document processing. |
| 40 | `LaunchGateService` | `app/services/launch_gate_service.py` | **A. REQUIRED AND WIRED** | `app/api/v1/readiness.py` | Production launch readiness checklist and environment verification. |
| 41 | `LawyerCallChannel` | `app/services/lawyer_call_channel.py` | **A. REQUIRED AND WIRED** | `app/api/v1/consultations.py` (`/ws/incoming-calls`) | In-memory & Redis pub/sub channel for broadcasting instant incoming consultation calls to lawyers. |
| 42 | `LawyerDashboardService` | `app/services/lawyer_dashboard_service.py` | **A. REQUIRED AND WIRED** | `app/api/v1/lawyers.py` | Advocate performance metrics, case calendar, revenue summaries, and upcoming schedule. |
| 43 | `LawyerVerificationService` | `app/services/lawyer_verification_service.py` | **A. REQUIRED AND WIRED** | `app/api/v1/verification.py` | Bar Council enrollment verification, certificate validation, and manual admin review queue. |
| 44 | `LegalAuthorityIngestion` | `app/services/legal_authority_ingestion.py` | **A. REQUIRED AND WIRED** | Legal data ingestion pipeline | Parses and ingests Supreme Court & High Court judgments and statutory bare acts. |
| 45 | `LegalAuthorityRetrieval` | `app/services/legal_authority_retrieval.py` | **A. REQUIRED AND WIRED** | `app/services/ai_research_service.py` | Semantic & keyword retrieval over legal corpus for case citations. |
| 46 | `LegalDataPipeline` | `app/services/legal_data_pipeline.py` | **A. REQUIRED AND WIRED** | Scheduled ingestion jobs | Batch ingestion pipeline for public legal data sources and court databases. |
| 47 | `LegalDocumentService` | `app/services/legal_document_service.py` | **A. REQUIRED AND WIRED** | `app/api/v1/documents.py` | Standard legal drafting templates and document generation workflows. |
| 48 | `LifecycleService` | `app/services/lifecycle_service.py` | **A. REQUIRED AND WIRED** | `app/services/case_service.py` | Case status transition validation and audit lifecycle event emitter. |
| 49 | `LLMProvider` | `app/services/llm_provider.py` | **A. REQUIRED AND WIRED** | `app/services/ai_provider.py` | Base abstraction protocol for large language model providers. |
| 50 | `MessageService` | `app/services/message_service.py` | **A. REQUIRED AND WIRED** | `app/api/v1/messages.py` | Secure client-advocate messaging, thread management, and attachment linking. |
| 51 | `NotificationService` | `app/services/notification_service.py` | **A. REQUIRED AND WIRED** | `app/api/v1/notifications.py` | Multi-channel in-app and email notification dispatcher with deduplication keys. |
| 52 | `OperatorService` | `app/services/operator_service.py` | **A. REQUIRED AND WIRED** | `app/api/v1/operator.py` | Maintenance operations, system health overrides, and operational runbooks. |
| 53 | `OutboxService` | `app/services/outbox_service.py` | **A. REQUIRED AND WIRED** | `app/services/job_worker.py` | Transactional outbox pattern implementation guaranteeing at-least-once event delivery. |
| 54 | `PaymentService` | `app/services/payment_service.py` | **A. REQUIRED AND WIRED** | `app/api/v1/payments.py` | Payment intent creation, Razorpay/Stripe webhook verification, and state transitions. |
| 55 | `PresenceService` | `app/services/presence_service.py` | **A. REQUIRED AND WIRED** | `app/api/v1/lawyers.py`, `app/services/consultation_service.py` | Real-time presence tracker backed by Redis with TTL expiration and availability flags. |
| 56 | `ProfileService` | `app/services/profile_service.py` | **A. REQUIRED AND WIRED** | `app/api/v1/profiles.py` | Client and advocate profile management, practice areas, jurisdictions, and fee schedules. |
| 57 | `QueryUnderstanding` | `app/services/query_understanding.py` | **A. REQUIRED AND WIRED** | `app/services/ai_research_service.py` | Natural language legal query parsing, entity recognition, and intent classification. |
| 58 | `ReconciliationService` | `app/services/reconciliation_service.py` | **A. REQUIRED AND WIRED** | `app/services/job_worker.py` | Automated ledger reconciliation comparing database payments against gateway transaction records. |
| 59 | `RecordingStorage` | `app/services/recording_storage.py` | **A. REQUIRED AND WIRED** | `app/services/video_recording_service.py` | S3 encrypted blob storage and signed download URL generator for video session recordings. |
| 60 | `ReminderService` | `app/services/reminder_service.py` | **A. REQUIRED AND WIRED** | `app/services/job_worker.py` (`_handle_deadline_reminder_scan`) | Generates hearing date and consultation reminders with idempotency keys and timezone correctness. |
| 61 | `RetrievalService` | `app/services/retrieval_service.py` | **A. REQUIRED AND WIRED** | `app/services/assistant_service.py` | Hybrid BM25 keyword and dense vector retrieval over case documents. |
| 62 | `ScannerService` | `app/services/scanner_service.py` | **A. REQUIRED AND WIRED** | `app/services/job_worker.py` | Asynchronous antivirus scanner integration (ClamAV daemon) for evidence documents. |
| 63 | `SessionCleanupService` | `app/services/session_cleanup_service.py` | **C. OBSOLETE / REPLACED** | Superseded by `VideoMeetingService.cleanup_stale_meetings` | Generic session cleanup module replaced by authoritative domain-specific video and Redis TTL workflows; preserved non-destructively. |
| 64 | `SupportService` | `app/services/support_service.py` | **A. REQUIRED AND WIRED** | `app/api/v1/support.py` | Customer and advocate support ticketing system. |
| 65 | `TranslationService` | `app/services/translation_service.py` | **A. REQUIRED AND WIRED** | `app/api/v1/cases.py` | Multilingual document and translation pipeline for vernacular legal texts. |
| 66 | `UnitEconomicsService` | `app/services/unit_economics_service.py` | **A. REQUIRED AND WIRED** | `app/api/v1/admin.py` | Platform margin and unit economics aggregation. |
| 67 | `UserService` | `app/services/user_service.py` | **A. REQUIRED AND WIRED** | `app/api/v1/users.py`, `app/api/deps.py` | User account lifecycle management, status updates, and role assignment. |
| 68 | `VideoMeetingService` | `app/services/video_meeting_service.py` | **A. REQUIRED AND WIRED** | `app/api/v1/consultations.py`, `app/services/job_worker.py` | Video meeting room provisioning, participant token generation, time access gating, and stale cleanup. |
| 69 | `VideoRecordingService` | `app/services/video_recording_service.py` | **A. REQUIRED AND WIRED** | `app/api/v1/consultations.py` | Video recording consent tracking, dual-party mutual consent enforcement, and recording lifecycle. |
| 70 | `VideoTelemetryService` | `app/services/video_telemetry_service.py` | **A. REQUIRED AND WIRED** | `app/api/v1/consultations.py` | WebRTC connection quality, bitrate, packet loss, and jitter telemetry logging. |
| 71 | `WorkflowTelemetryService` | `app/services/workflow_telemetry_service.py` | **A. REQUIRED AND WIRED** | `app/services/case_workflow_service.py` | End-to-end legal workflow latency and milestone progression analytics. |

---

## 3. Summary of Findings

- **Total Services Audited**: 71
- **Category A (Required and Wired)**: 69
- **Category B (Intentionally Unused / Feature Flag)**: 1 (`ExperimentService`)
- **Category C (Obsolete / Replaced)**: 1 (`SessionCleanupService`)
- **Category D (Test-Only)**: 0
- **Category E (Unknown)**: 0
- **Unhooked Services Reconnected in Phase 3**:
  1. `AbuseDefenseService` (wired into auth registration & consultation booking velocity)
  2. `AIBudgetService` (wired into AI research & assistant endpoints)
  3. `CancellationPolicyService` (wired into consultation cancellation & automated refunds)
  4. `ReminderService` (registered in background job worker periodic scan)
  5. `VideoMeetingService.cleanup_stale_meetings` (implemented, tested, and wired to background job worker)
