# Phase 10 Backend Module Inventory

**Total Modules Audited:** 238
**Target Architecture:** Clean, Domain-Oriented Layering (`API -> Domain / Application Services -> Repositories / Providers`)

| File | Current Role | Target Role | Move / Action | Risk | Dependencies Count | Dependents Count | Description |
|---|---|---|---|---|---|---|---|
| `app/api/deps.py` | API | API | KEEP | LOW | 8 | 42 | FastAPI authentication & database dependency injection |
| `app/api/v1/admin.py` | API | API | KEEP | LOW | 22 | 1 | API Route Router for admin |
| `app/api/v1/ai.py` | API | API | KEEP | LOW | 6 | 1 | API Route Router for ai |
| `app/api/v1/ai_conversations.py` | API | API | KEEP | LOW | 5 | 1 | API Route Router for ai_conversations |
| `app/api/v1/ai_review.py` | API | API | KEEP | LOW | 7 | 1 | API Route Router for ai_review |
| `app/api/v1/analytics.py` | API | API | KEEP | LOW | 11 | 1 | API Route Router for analytics |
| `app/api/v1/assistant.py` | API | API | KEEP | LOW | 6 | 1 | API Route Router for assistant |
| `app/api/v1/attention.py` | API | API | KEEP | LOW | 3 | 1 | API Route Router for attention |
| `app/api/v1/audit.py` | API | API | KEEP | LOW | 5 | 1 | API Route Router for audit |
| `app/api/v1/auth.py` | API | API | KEEP | LOW | 15 | 17 | API Route Router for auth |
| `app/api/v1/bundles.py` | API | API | KEEP | LOW | 6 | 1 | API Route Router for bundles |
| `app/api/v1/calendar.py` | API | API | KEEP | LOW | 10 | 1 | API Route Router for calendar |
| `app/api/v1/case_intelligence.py` | API | API | KEEP | LOW | 5 | 1 | API Route Router for case_intelligence |
| `app/api/v1/cases.py` | API | API | KEEP | LOW | 15 | 1 | API Route Router for cases |
| `app/api/v1/change_feed.py` | API | API | KEEP | LOW | 3 | 1 | API Route Router for change_feed |
| `app/api/v1/commercial.py` | API | API | KEEP | LOW | 7 | 1 | API Route Router for commercial |
| `app/api/v1/compliance.py` | API | API | KEEP | LOW | 5 | 1 | API Route Router for compliance |
| `app/api/v1/consultations.py` | API | API | KEEP | LOW | 35 | 1 | API Route Router for consultations |
| `app/api/v1/court_cases.py` | API | API | KEEP | LOW | 10 | 1 | API Route Router for court_cases |
| `app/api/v1/data_quality.py` | API | API | KEEP | LOW | 5 | 1 | API Route Router for data_quality |
| `app/api/v1/documents.py` | API | API | KEEP | LOW | 20 | 1 | API Route Router for documents |
| `app/api/v1/evidence.py` | API | API | KEEP | LOW | 8 | 1 | API Route Router for evidence |
| `app/api/v1/experiments.py` | API | API | KEEP | LOW | 6 | 1 | API Route Router for experiments |
| `app/api/v1/feedback.py` | API | API | KEEP | LOW | 6 | 1 | API Route Router for feedback |
| `app/api/v1/health.py` | API | API | KEEP | LOW | 7 | 1 | API Route Router for health |
| `app/api/v1/incidents.py` | API | API | KEEP | LOW | 6 | 1 | API Route Router for incidents |
| `app/api/v1/launch_gates.py` | API | API | KEEP | LOW | 3 | 1 | API Route Router for launch_gates |
| `app/api/v1/lawyers.py` | API | API | KEEP | LOW | 11 | 1 | API Route Router for lawyers |
| `app/api/v1/legal_authority.py` | API | API | KEEP | LOW | 8 | 1 | API Route Router for legal_authority |
| `app/api/v1/legal_documents.py` | API | API | KEEP | LOW | 5 | 1 | API Route Router for legal_documents |
| `app/api/v1/localization.py` | API | API | KEEP | LOW | 6 | 1 | API Route Router for localization |
| `app/api/v1/messages.py` | API | API | KEEP | LOW | 10 | 1 | API Route Router for messages |
| `app/api/v1/notifications.py` | API | API | KEEP | LOW | 5 | 1 | API Route Router for notifications |
| `app/api/v1/payments.py` | API | API | KEEP | LOW | 5 | 1 | API Route Router for payments |
| `app/api/v1/pilot.py` | API | API | KEEP | LOW | 20 | 1 | API Route Router for pilot |
| `app/api/v1/profiles.py` | API | API | KEEP | LOW | 6 | 1 | API Route Router for profiles |
| `app/api/v1/recordings.py` | API | API | KEEP | LOW | 7 | 1 | API Route Router for recordings |
| `app/api/v1/search.py` | API | API | KEEP | LOW | 5 | 1 | API Route Router for search |
| `app/api/v1/support.py` | API | API | KEEP | LOW | 7 | 1 | API Route Router for support |
| `app/api/v1/trust.py` | API | API | KEEP | LOW | 2 | 1 | API Route Router for trust |
| `app/api/v1/verification.py` | API | API | KEEP | LOW | 7 | 1 | API Route Router for verification |
| `app/api/v1/video_signaling.py` | API | API | KEEP | LOW | 7 | 3 | API Route Router for video_signaling |
| `app/api/v1/webhooks.py` | API | API | KEEP | LOW | 4 | 1 | API Route Router for webhooks |
| `app/api/v1/workflow.py` | API | API | KEEP | LOW | 8 | 1 | API Route Router for workflow |
| `app/core/ai_config.py` | CONFIG | CONFIG | KEEP | LOW | 0 | 6 | Application settings and environment validation |
| `app/core/ai_exceptions.py` | CONFIG | CORE INFRA | KEEP | LOW | 1 | 1 | Core runtime infrastructure (ai_exceptions) |
| `app/core/authorization.py` | CONFIG | CORE INFRA | KEEP | LOW | 7 | 18 | Core runtime infrastructure (authorization) |
| `app/core/config.py` | CONFIG | CONFIG | KEEP | LOW | 0 | 42 | Application settings and environment validation |
| `app/core/csrf.py` | CONFIG | CORE INFRA | KEEP | LOW | 1 | 1 | Core runtime infrastructure (csrf) |
| `app/core/exceptions.py` | CONFIG | CORE INFRA | KEEP | LOW | 0 | 64 | Core runtime infrastructure (exceptions) |
| `app/core/file_validation.py` | CONFIG | CORE INFRA | KEEP | LOW | 1 | 6 | Core runtime infrastructure (file_validation) |
| `app/core/i18n.py` | CONFIG | CORE INFRA | KEEP | LOW | 1 | 3 | Core runtime infrastructure (i18n) |
| `app/core/identifiers.py` | CONFIG | CORE INFRA | KEEP | LOW | 0 | 94 | Core runtime infrastructure (identifiers) |
| `app/core/locking.py` | CONFIG | CORE INFRA | KEEP | LOW | 1 | 1 | Core runtime infrastructure (locking) |
| `app/core/logging.py` | UTILITY | CORE INFRA | KEEP | LOW | 2 | 3 | Structured logging, correlation, and secret scrubbing |
| `app/core/metrics.py` | CONFIG | CORE INFRA | KEEP | LOW | 0 | 10 | Core runtime infrastructure (metrics) |
| `app/core/oauth_security.py` | SECURITY | SECURITY | KEEP | LOW | 2 | 2 | Authentication, hashing, and token cryptography |
| `app/core/redis.py` | CONFIG | CORE INFRA | KEEP | LOW | 1 | 4 | Core runtime infrastructure (redis) |
| `app/core/security.py` | SECURITY | SECURITY | KEEP | LOW | 1 | 6 | Authentication, hashing, and token cryptography |
| `app/core/storage.py` | CONFIG | CORE INFRA | KEEP | LOW | 2 | 10 | Core runtime infrastructure (storage) |
| `app/db/database.py` | REPOSITORY | REPOSITORY | KEEP | LOW | 1 | 7 | Database engine & session lifecycle: database |
| `app/db/session.py` | REPOSITORY | REPOSITORY | KEEP | LOW | 1 | 0 | Database engine & session lifecycle: session |
| `app/main.py` | API | API | KEEP | LOW | 54 | 1 | FastAPI root application & middleware mounting |
| `app/middleware/correlation_id.py` | SECURITY | SECURITY | KEEP | LOW | 1 | 3 | Request pipeline middleware: correlation_id |
| `app/middleware/metrics.py` | SECURITY | SECURITY | KEEP | LOW | 1 | 1 | Request pipeline middleware: metrics |
| `app/middleware/payload.py` | SECURITY | SECURITY | KEEP | LOW | 0 | 1 | Request pipeline middleware: payload |
| `app/middleware/pilot.py` | SECURITY | SECURITY | KEEP | LOW | 1 | 1 | Request pipeline middleware: pilot |
| `app/middleware/security.py` | SECURITY | SECURITY | KEEP | LOW | 1 | 1 | Request pipeline middleware: security |
| `app/models/__init__.py` | ORM MODEL | ORM MODEL | KEEP | LOW | 44 | 0 | SQLAlchemy ORM model for __init__ |
| `app/models/ai.py` | ORM MODEL | ORM MODEL | KEEP | LOW | 5 | 12 | SQLAlchemy ORM model for ai |
| `app/models/ai_review.py` | ORM MODEL | ORM MODEL | KEEP | LOW | 5 | 4 | SQLAlchemy ORM model for ai_review |
| `app/models/analytics.py` | ORM MODEL | ORM MODEL | KEEP | LOW | 4 | 5 | SQLAlchemy ORM model for analytics |
| `app/models/audit.py` | ORM MODEL | ORM MODEL | KEEP | LOW | 2 | 22 | SQLAlchemy ORM model for audit |
| `app/models/auth.py` | ORM MODEL | ORM MODEL | KEEP | LOW | 3 | 6 | SQLAlchemy ORM model for auth |
| `app/models/availability.py` | ORM MODEL | ORM MODEL | KEEP | LOW | 3 | 4 | SQLAlchemy ORM model for availability |
| `app/models/base.py` | ORM MODEL | ORM MODEL | KEEP | LOW | 0 | 46 | SQLAlchemy ORM model for base |
| `app/models/bundle.py` | ORM MODEL | ORM MODEL | KEEP | LOW | 6 | 5 | SQLAlchemy ORM model for bundle |
| `app/models/case.py` | ORM MODEL | ORM MODEL | KEEP | LOW | 8 | 48 | SQLAlchemy ORM model for case |
| `app/models/case_collaboration.py` | ORM MODEL | ORM MODEL | KEEP | LOW | 6 | 10 | SQLAlchemy ORM model for case_collaboration |
| `app/models/case_intelligence.py` | ORM MODEL | ORM MODEL | KEEP | LOW | 5 | 5 | SQLAlchemy ORM model for case_intelligence |
| `app/models/commercial.py` | ORM MODEL | ORM MODEL | KEEP | LOW | 2 | 8 | SQLAlchemy ORM model for commercial |
| `app/models/compliance.py` | ORM MODEL | ORM MODEL | KEEP | LOW | 2 | 3 | SQLAlchemy ORM model for compliance |
| `app/models/consultation.py` | ORM MODEL | ORM MODEL | KEEP | LOW | 10 | 40 | SQLAlchemy ORM model for consultation |
| `app/models/consultation_document.py` | ORM MODEL | ORM MODEL | KEEP | LOW | 4 | 3 | SQLAlchemy ORM model for consultation_document |
| `app/models/consultation_note.py` | ORM MODEL | ORM MODEL | KEEP | LOW | 4 | 3 | SQLAlchemy ORM model for consultation_note |
| `app/models/court_case.py` | ORM MODEL | ORM MODEL | KEEP | LOW | 4 | 7 | SQLAlchemy ORM model for court_case |
| `app/models/data_quality.py` | ORM MODEL | ORM MODEL | KEEP | LOW | 3 | 3 | SQLAlchemy ORM model for data_quality |
| `app/models/direct_message.py` | ORM MODEL | ORM MODEL | KEEP | LOW | 3 | 4 | SQLAlchemy ORM model for direct_message |
| `app/models/document.py` | ORM MODEL | ORM MODEL | KEEP | LOW | 6 | 27 | SQLAlchemy ORM model for document |
| `app/models/document_page.py` | ORM MODEL | ORM MODEL | KEEP | LOW | 4 | 4 | SQLAlchemy ORM model for document_page |
| `app/models/evaluation.py` | ORM MODEL | ORM MODEL | KEEP | LOW | 2 | 2 | SQLAlchemy ORM model for evaluation |
| `app/models/evidence.py` | ORM MODEL | ORM MODEL | KEEP | LOW | 5 | 13 | SQLAlchemy ORM model for evidence |
| `app/models/experiment.py` | ORM MODEL | ORM MODEL | KEEP | LOW | 3 | 4 | SQLAlchemy ORM model for experiment |
| `app/models/feedback.py` | ORM MODEL | ORM MODEL | KEEP | LOW | 4 | 5 | SQLAlchemy ORM model for feedback |
| `app/models/incident.py` | ORM MODEL | ORM MODEL | KEEP | LOW | 2 | 9 | SQLAlchemy ORM model for incident |
| `app/models/job.py` | ORM MODEL | ORM MODEL | KEEP | LOW | 4 | 10 | SQLAlchemy ORM model for job |
| `app/models/legal_authority.py` | ORM MODEL | ORM MODEL | KEEP | LOW | 3 | 9 | SQLAlchemy ORM model for legal_authority |
| `app/models/legal_document.py` | ORM MODEL | ORM MODEL | KEEP | LOW | 2 | 3 | SQLAlchemy ORM model for legal_document |
| `app/models/localization.py` | ORM MODEL | ORM MODEL | KEEP | LOW | 2 | 3 | SQLAlchemy ORM model for localization |
| `app/models/message.py` | ORM MODEL | ORM MODEL | KEEP | LOW | 4 | 3 | SQLAlchemy ORM model for message |
| `app/models/note.py` | ORM MODEL | ORM MODEL | KEEP | LOW | 4 | 4 | SQLAlchemy ORM model for note |
| `app/models/notification.py` | ORM MODEL | ORM MODEL | KEEP | LOW | 8 | 18 | SQLAlchemy ORM model for notification |
| `app/models/operator.py` | ORM MODEL | ORM MODEL | KEEP | LOW | 2 | 14 | SQLAlchemy ORM model for operator |
| `app/models/outbox.py` | ORM MODEL | ORM MODEL | KEEP | LOW | 2 | 3 | SQLAlchemy ORM model for outbox |
| `app/models/payment.py` | ORM MODEL | ORM MODEL | KEEP | LOW | 4 | 8 | SQLAlchemy ORM model for payment |
| `app/models/pilot.py` | ORM MODEL | ORM MODEL | KEEP | LOW | 3 | 3 | SQLAlchemy ORM model for pilot |
| `app/models/support.py` | ORM MODEL | ORM MODEL | KEEP | LOW | 4 | 5 | SQLAlchemy ORM model for support |
| `app/models/task.py` | ORM MODEL | ORM MODEL | KEEP | LOW | 6 | 18 | SQLAlchemy ORM model for task |
| `app/models/user.py` | ORM MODEL | ORM MODEL | KEEP | LOW | 6 | 116 | SQLAlchemy ORM model for user |
| `app/models/user_feed.py` | ORM MODEL | ORM MODEL | KEEP | LOW | 3 | 2 | SQLAlchemy ORM model for user_feed |
| `app/models/video_meeting.py` | ORM MODEL | ORM MODEL | KEEP | LOW | 3 | 6 | SQLAlchemy ORM model for video_meeting |
| `app/models/video_recording.py` | ORM MODEL | ORM MODEL | KEEP | LOW | 5 | 7 | SQLAlchemy ORM model for video_recording |
| `app/models/webhook.py` | ORM MODEL | ORM MODEL | KEEP | LOW | 2 | 2 | SQLAlchemy ORM model for webhook |
| `app/models/workflow.py` | ORM MODEL | ORM MODEL | KEEP | LOW | 5 | 20 | SQLAlchemy ORM model for workflow |
| `app/providers/ai/__init__.py` | PROVIDER | PROVIDER | KEEP | LOW | 4 | 0 | External provider abstraction/adapter for __init__ |
| `app/providers/ai/base.py` | PROVIDER | PROVIDER | KEEP | LOW | 2 | 9 | External provider abstraction/adapter for base |
| `app/providers/ai/factory.py` | PROVIDER | PROVIDER | KEEP | LOW | 4 | 6 | External provider abstraction/adapter for factory |
| `app/providers/ai/mock.py` | PROVIDER | PROVIDER | KEEP | LOW | 5 | 4 | External provider abstraction/adapter for mock |
| `app/providers/ai/openai.py` | PROVIDER | PROVIDER | KEEP | LOW | 7 | 4 | External provider abstraction/adapter for openai |
| `app/scheduler.py` | UTILITY | UTILITY | KEEP | LOW | 4 | 0 | Module: scheduler.py |
| `app/schemas/admin.py` | SCHEMA | SCHEMA | KEEP | LOW | 5 | 2 | Pydantic schema definitions for admin |
| `app/schemas/ai.py` | SCHEMA | SCHEMA | KEEP | LOW | 3 | 9 | Pydantic schema definitions for ai |
| `app/schemas/ai_review.py` | SCHEMA | SCHEMA | KEEP | LOW | 1 | 1 | Pydantic schema definitions for ai_review |
| `app/schemas/analytics.py` | SCHEMA | SCHEMA | KEEP | LOW | 1 | 1 | Pydantic schema definitions for analytics |
| `app/schemas/assistant.py` | SCHEMA | SCHEMA | KEEP | LOW | 2 | 5 | Pydantic schema definitions for assistant |
| `app/schemas/audit.py` | SCHEMA | SCHEMA | KEEP | LOW | 0 | 2 | Pydantic schema definitions for audit |
| `app/schemas/auth.py` | SCHEMA | SCHEMA | KEEP | LOW | 0 | 3 | Pydantic schema definitions for auth |
| `app/schemas/availability.py` | SCHEMA | SCHEMA | KEEP | LOW | 0 | 3 | Pydantic schema definitions for availability |
| `app/schemas/bundle.py` | SCHEMA | SCHEMA | KEEP | LOW | 1 | 2 | Pydantic schema definitions for bundle |
| `app/schemas/calendar.py` | SCHEMA | SCHEMA | KEEP | LOW | 0 | 1 | Pydantic schema definitions for calendar |
| `app/schemas/case.py` | SCHEMA | SCHEMA | KEEP | LOW | 1 | 4 | Pydantic schema definitions for case |
| `app/schemas/case_intelligence.py` | SCHEMA | SCHEMA | KEEP | LOW | 1 | 2 | Pydantic schema definitions for case_intelligence |
| `app/schemas/collaboration.py` | SCHEMA | SCHEMA | KEEP | LOW | 1 | 2 | Pydantic schema definitions for collaboration |
| `app/schemas/consultation.py` | SCHEMA | SCHEMA | KEEP | LOW | 1 | 3 | Pydantic schema definitions for consultation |
| `app/schemas/consultation_note.py` | SCHEMA | SCHEMA | KEEP | LOW | 0 | 1 | Pydantic schema definitions for consultation_note |
| `app/schemas/court_case.py` | SCHEMA | SCHEMA | KEEP | LOW | 0 | 1 | Pydantic schema definitions for court_case |
| `app/schemas/document.py` | SCHEMA | SCHEMA | KEEP | LOW | 1 | 2 | Pydantic schema definitions for document |
| `app/schemas/evidence.py` | SCHEMA | SCHEMA | KEEP | LOW | 1 | 3 | Pydantic schema definitions for evidence |
| `app/schemas/experiment.py` | SCHEMA | SCHEMA | KEEP | LOW | 1 | 1 | Pydantic schema definitions for experiment |
| `app/schemas/feedback.py` | SCHEMA | SCHEMA | KEEP | LOW | 1 | 1 | Pydantic schema definitions for feedback |
| `app/schemas/incident.py` | SCHEMA | SCHEMA | KEEP | LOW | 1 | 1 | Pydantic schema definitions for incident |
| `app/schemas/job.py` | SCHEMA | SCHEMA | KEEP | LOW | 1 | 2 | Pydantic schema definitions for job |
| `app/schemas/lawyer_dashboard.py` | SCHEMA | SCHEMA | KEEP | LOW | 0 | 2 | Pydantic schema definitions for lawyer_dashboard |
| `app/schemas/legal_authority.py` | SCHEMA | SCHEMA | KEEP | LOW | 2 | 7 | Pydantic schema definitions for legal_authority |
| `app/schemas/localization.py` | SCHEMA | SCHEMA | KEEP | LOW | 1 | 1 | Pydantic schema definitions for localization |
| `app/schemas/message.py` | SCHEMA | SCHEMA | KEEP | LOW | 0 | 2 | Pydantic schema definitions for message |
| `app/schemas/note.py` | SCHEMA | SCHEMA | KEEP | LOW | 0 | 2 | Pydantic schema definitions for note |
| `app/schemas/notification.py` | SCHEMA | SCHEMA | KEEP | LOW | 1 | 2 | Pydantic schema definitions for notification |
| `app/schemas/pagination.py` | SCHEMA | SCHEMA | KEEP | LOW | 0 | 7 | Pydantic schema definitions for pagination |
| `app/schemas/payment.py` | SCHEMA | SCHEMA | KEEP | LOW | 1 | 3 | Pydantic schema definitions for payment |
| `app/schemas/presence.py` | SCHEMA | SCHEMA | KEEP | LOW | 0 | 4 | Pydantic schema definitions for presence |
| `app/schemas/profile.py` | SCHEMA | SCHEMA | KEEP | LOW | 0 | 6 | Pydantic schema definitions for profile |
| `app/schemas/report.py` | SCHEMA | SCHEMA | KEEP | LOW | 0 | 1 | Pydantic schema definitions for report |
| `app/schemas/retrieval.py` | SCHEMA | SCHEMA | KEEP | LOW | 0 | 6 | Pydantic schema definitions for retrieval |
| `app/schemas/search.py` | SCHEMA | SCHEMA | KEEP | LOW | 1 | 10 | Pydantic schema definitions for search |
| `app/schemas/support.py` | SCHEMA | SCHEMA | KEEP | LOW | 1 | 1 | Pydantic schema definitions for support |
| `app/schemas/task.py` | SCHEMA | SCHEMA | KEEP | LOW | 1 | 5 | Pydantic schema definitions for task |
| `app/schemas/user.py` | SCHEMA | SCHEMA | KEEP | LOW | 0 | 3 | Pydantic schema definitions for user |
| `app/schemas/verification.py` | SCHEMA | SCHEMA | KEEP | LOW | 0 | 2 | Pydantic schema definitions for verification |
| `app/schemas/video_meeting.py` | SCHEMA | SCHEMA | KEEP | LOW | 1 | 3 | Pydantic schema definitions for video_meeting |
| `app/schemas/video_recording.py` | SCHEMA | SCHEMA | KEEP | LOW | 1 | 2 | Pydantic schema definitions for video_recording |
| `app/schemas/workflow.py` | SCHEMA | SCHEMA | KEEP | LOW | 2 | 2 | Pydantic schema definitions for workflow |
| `app/services/abuse_defense_service.py` | APPLICATION SERVICE | DOMAIN (domain/governance) | KEEP | LOW | 3 | 2 | Business domain service: abuse_defense_service |
| `app/services/admin_service.py` | APPLICATION SERVICE | DOMAIN (domain/users) | KEEP | LOW | 11 | 2 | Business domain service: admin_service |
| `app/services/ai_budget_service.py` | APPLICATION SERVICE | DOMAIN (domain/ai) | KEEP | LOW | 5 | 3 | Business domain service: ai_budget_service |
| `app/services/ai_conversation_service.py` | APPLICATION SERVICE | DOMAIN (domain/ai) | KEEP | LOW | 20 | 1 | Business domain service: ai_conversation_service |
| `app/services/ai_evaluation_service.py` | APPLICATION SERVICE | DOMAIN (domain/ai) | KEEP | LOW | 2 | 1 | Business domain service: ai_evaluation_service |
| `app/services/ai_prompt_policy.py` | APPLICATION SERVICE | DOMAIN (domain/ai) | KEEP | LOW | 2 | 4 | Business domain service: ai_prompt_policy |
| `app/services/ai_provider.py` | APPLICATION SERVICE | DOMAIN (domain/ai) | KEEP | LOW | 8 | 1 | Business domain service: ai_provider |
| `app/services/ai_research_service.py` | APPLICATION SERVICE | DOMAIN (domain/ai) | KEEP | LOW | 8 | 1 | Business domain service: ai_research_service |
| `app/services/ai_review_service.py` | APPLICATION SERVICE | DOMAIN (domain/ai) | KEEP | LOW | 5 | 1 | Business domain service: ai_review_service |
| `app/services/alert_service.py` | APPLICATION SERVICE | DOMAIN (domain/notifications) | KEEP | LOW | 2 | 1 | Business domain service: alert_service |
| `app/services/assistant_service.py` | APPLICATION SERVICE | DOMAIN (domain/ai) | KEEP | LOW | 16 | 1 | Business domain service: assistant_service |
| `app/services/auth_service.py` | APPLICATION SERVICE | DOMAIN (domain/auth) | KEEP | LOW | 10 | 13 | Business domain service: auth_service |
| `app/services/bundle_pdf_engine.py` | APPLICATION SERVICE | DOMAIN (domain/cases) | KEEP | LOW | 0 | 1 | Business domain service: bundle_pdf_engine |
| `app/services/bundle_service.py` | APPLICATION SERVICE | DOMAIN (domain/cases) | KEEP | LOW | 12 | 1 | Business domain service: bundle_service |
| `app/services/cancellation_policy_service.py` | APPLICATION SERVICE | DOMAIN (domain/payments) | KEEP | LOW | 6 | 1 | Business domain service: cancellation_policy_service |
| `app/services/case_attention_service.py` | APPLICATION SERVICE | DOMAIN (domain/cases) | KEEP | LOW | 8 | 1 | Business domain service: case_attention_service |
| `app/services/case_intelligence_service.py` | APPLICATION SERVICE | DOMAIN (domain/cases) | KEEP | LOW | 8 | 2 | Business domain service: case_intelligence_service |
| `app/services/case_report_service.py` | APPLICATION SERVICE | DOMAIN (domain/cases) | KEEP | LOW | 12 | 1 | Business domain service: case_report_service |
| `app/services/case_service.py` | APPLICATION SERVICE | DOMAIN (domain/cases) | KEEP | LOW | 18 | 8 | Business domain service: case_service |
| `app/services/case_workflow_service.py` | APPLICATION SERVICE | DOMAIN (domain/cases) | KEEP | LOW | 15 | 2 | Business domain service: case_workflow_service |
| `app/services/change_feed_service.py` | APPLICATION SERVICE | DOMAIN (domain/jobs) | KEEP | LOW | 10 | 1 | Business domain service: change_feed_service |
| `app/services/citation_normalizer.py` | APPLICATION SERVICE | DOMAIN (domain/ai) | KEEP | LOW | 0 | 1 | Business domain service: citation_normalizer |
| `app/services/claim_verifier.py` | APPLICATION SERVICE | DOMAIN (domain/ai) | KEEP | LOW | 3 | 2 | Business domain service: claim_verifier |
| `app/services/cohort_governance_service.py` | APPLICATION SERVICE | DOMAIN (domain/governance) | KEEP | LOW | 3 | 1 | Business domain service: cohort_governance_service |
| `app/services/collaboration_service.py` | APPLICATION SERVICE | DOMAIN (domain/cases) | KEEP | LOW | 13 | 1 | Business domain service: collaboration_service |
| `app/services/commercial_service.py` | APPLICATION SERVICE | DOMAIN (domain/payments) | KEEP | LOW | 7 | 4 | Business domain service: commercial_service |
| `app/services/compliance_service.py` | APPLICATION SERVICE | DOMAIN (domain/governance) | KEEP | LOW | 5 | 1 | Business domain service: compliance_service |
| `app/services/consultation_service.py` | APPLICATION SERVICE | DOMAIN (domain/consultations) | KEEP | LOW | 26 | 6 | Business domain service: consultation_service |
| `app/services/document_processor.py` | APPLICATION SERVICE | DOMAIN (domain/documents) | KEEP | LOW | 10 | 2 | Business domain service: document_processor |
| `app/services/document_service.py` | APPLICATION SERVICE | DOMAIN (domain/documents) | KEEP | LOW | 14 | 1 | Business domain service: document_service |
| `app/services/email_service.py` | APPLICATION SERVICE | DOMAIN (domain/ai) | KEEP | LOW | 2 | 2 | Business domain service: email_service |
| `app/services/embedding_provider.py` | APPLICATION SERVICE | DOMAIN (domain/ai) | KEEP | LOW | 2 | 1 | Business domain service: embedding_provider |
| `app/services/embedding_service.py` | APPLICATION SERVICE | DOMAIN (domain/ai) | KEEP | LOW | 1 | 5 | Business domain service: embedding_service |
| `app/services/evidence_service.py` | APPLICATION SERVICE | DOMAIN (domain/evidence) | KEEP | LOW | 17 | 3 | Business domain service: evidence_service |
| `app/services/experiment_service.py` | APPLICATION SERVICE | DOMAIN (domain/governance) | KEEP | LOW | 5 | 1 | Business domain service: experiment_service |
| `app/services/google_oauth_service.py` | APPLICATION SERVICE | DOMAIN (domain/auth) | KEEP | LOW | 3 | 1 | Business domain service: google_oauth_service |
| `app/services/incident_service.py` | APPLICATION SERVICE | DOMAIN (domain/jobs) | KEEP | LOW | 5 | 1 | Business domain service: incident_service |
| `app/services/job_scheduler.py` | APPLICATION SERVICE | DOMAIN (domain/jobs) | KEEP | LOW | 3 | 2 | Business domain service: job_scheduler |
| `app/services/job_service.py` | APPLICATION SERVICE | DOMAIN (domain/jobs) | KEEP | LOW | 4 | 5 | Business domain service: job_service |
| `app/services/job_worker.py` | WORKER | WORKER | KEEP | LOW | 26 | 2 | Asynchronous job/worker execution: job_worker |
| `app/services/launch_gate_service.py` | APPLICATION SERVICE | DOMAIN (domain/governance) | KEEP | LOW | 1 | 1 | Business domain service: launch_gate_service |
| `app/services/lawyer_call_channel.py` | APPLICATION SERVICE | DOMAIN (domain/consultations) | KEEP | LOW | 1 | 2 | Business domain service: lawyer_call_channel |
| `app/services/lawyer_dashboard_service.py` | APPLICATION SERVICE | DOMAIN (domain/verification) | KEEP | LOW | 10 | 1 | Business domain service: lawyer_dashboard_service |
| `app/services/lawyer_verification_service.py` | APPLICATION SERVICE | DOMAIN (domain/verification) | KEEP | LOW | 9 | 2 | Business domain service: lawyer_verification_service |
| `app/services/legal_authority_ingestion.py` | APPLICATION SERVICE | DOMAIN (domain/auth) | KEEP | LOW | 5 | 1 | Business domain service: legal_authority_ingestion |
| `app/services/legal_authority_retrieval.py` | APPLICATION SERVICE | DOMAIN (domain/auth) | KEEP | LOW | 7 | 3 | Business domain service: legal_authority_retrieval |
| `app/services/legal_data_pipeline.py` | APPLICATION SERVICE | DOMAIN (domain/ai) | KEEP | LOW | 7 | 2 | Business domain service: legal_data_pipeline |
| `app/services/legal_document_service.py` | APPLICATION SERVICE | DOMAIN (domain/documents) | KEEP | LOW | 5 | 1 | Business domain service: legal_document_service |
| `app/services/legal_source_providers/base.py` | APPLICATION SERVICE | DOMAIN (domain/governance) | KEEP | LOW | 1 | 3 | Business domain service: base |
| `app/services/legal_source_providers/curated_fixtures.py` | APPLICATION SERVICE | DOMAIN (domain/governance) | KEEP | LOW | 2 | 1 | Business domain service: curated_fixtures |
| `app/services/legal_source_providers/ecourts_provider.py` | APPLICATION SERVICE | DOMAIN (domain/governance) | KEEP | LOW | 0 | 1 | Business domain service: ecourts_provider |
| `app/services/lifecycle_service.py` | APPLICATION SERVICE | DOMAIN (domain/users) | KEEP | LOW | 5 | 0 | Business domain service: lifecycle_service |
| `app/services/llm_provider.py` | APPLICATION SERVICE | DOMAIN (domain/ai) | KEEP | LOW | 7 | 1 | Business domain service: llm_provider |
| `app/services/message_service.py` | APPLICATION SERVICE | DOMAIN (domain/governance) | KEEP | LOW | 7 | 1 | Business domain service: message_service |
| `app/services/notification_service.py` | APPLICATION SERVICE | DOMAIN (domain/notifications) | KEEP | LOW | 7 | 15 | Business domain service: notification_service |
| `app/services/operator_service.py` | APPLICATION SERVICE | DOMAIN (domain/users) | KEEP | LOW | 5 | 1 | Business domain service: operator_service |
| `app/services/outbox_service.py` | APPLICATION SERVICE | DOMAIN (domain/jobs) | KEEP | LOW | 6 | 3 | Business domain service: outbox_service |
| `app/services/payment_service.py` | APPLICATION SERVICE | DOMAIN (domain/payments) | KEEP | LOW | 15 | 4 | Business domain service: payment_service |
| `app/services/presence_service.py` | APPLICATION SERVICE | DOMAIN (domain/consultations) | KEEP | LOW | 3 | 5 | Business domain service: presence_service |
| `app/services/profile_service.py` | APPLICATION SERVICE | DOMAIN (domain/users) | KEEP | LOW | 9 | 3 | Business domain service: profile_service |
| `app/services/query_understanding.py` | APPLICATION SERVICE | DOMAIN (domain/ai) | KEEP | LOW | 0 | 2 | Business domain service: query_understanding |
| `app/services/reconciliation_service.py` | APPLICATION SERVICE | DOMAIN (domain/payments) | KEEP | LOW | 8 | 1 | Business domain service: reconciliation_service |
| `app/services/recording_storage.py` | APPLICATION SERVICE | DOMAIN (domain/governance) | KEEP | LOW | 2 | 1 | Business domain service: recording_storage |
| `app/services/reminder_service.py` | APPLICATION SERVICE | DOMAIN (domain/notifications) | KEEP | LOW | 9 | 1 | Business domain service: reminder_service |
| `app/services/retrieval_service.py` | APPLICATION SERVICE | DOMAIN (domain/ai) | KEEP | LOW | 11 | 5 | Business domain service: retrieval_service |
| `app/services/scanner_service.py` | APPLICATION SERVICE | DOMAIN (domain/evidence) | KEEP | LOW | 8 | 4 | Business domain service: scanner_service |
| `app/services/session_cleanup_service.py` | APPLICATION SERVICE | DOMAIN (domain/auth) | KEEP | LOW | 1 | 1 | Business domain service: session_cleanup_service |
| `app/services/support_service.py` | APPLICATION SERVICE | DOMAIN (domain/users) | KEEP | LOW | 6 | 2 | Business domain service: support_service |
| `app/services/translation_service.py` | APPLICATION SERVICE | DOMAIN (domain/governance) | KEEP | LOW | 6 | 1 | Business domain service: translation_service |
| `app/services/unit_economics_service.py` | APPLICATION SERVICE | DOMAIN (domain/payments) | KEEP | LOW | 2 | 1 | Business domain service: unit_economics_service |
| `app/services/user_service.py` | APPLICATION SERVICE | DOMAIN (domain/users) | KEEP | LOW | 7 | 6 | Business domain service: user_service |
| `app/services/video_meeting_service.py` | APPLICATION SERVICE | DOMAIN (domain/consultations) | KEEP | LOW | 13 | 4 | Business domain service: video_meeting_service |
| `app/services/video_recording_service.py` | APPLICATION SERVICE | DOMAIN (domain/consultations) | KEEP | LOW | 12 | 3 | Business domain service: video_recording_service |
| `app/services/video_telemetry_service.py` | APPLICATION SERVICE | DOMAIN (domain/consultations) | KEEP | LOW | 0 | 1 | Business domain service: video_telemetry_service |
| `app/services/workflow_telemetry_service.py` | APPLICATION SERVICE | DOMAIN (domain/governance) | KEEP | LOW | 5 | 1 | Business domain service: workflow_telemetry_service |
| `app/worker.py` | WORKER | WORKER | KEEP | LOW | 5 | 0 | Asynchronous job/worker execution: worker |

## Module Classification Summary

- **API**: 45 modules
- **APPLICATION SERVICE**: 74 modules
- **CONFIG**: 13 modules
- **ORM MODEL**: 46 modules
- **PROVIDER**: 5 modules
- **REPOSITORY**: 2 modules
- **SCHEMA**: 42 modules
- **SECURITY**: 7 modules
- **UTILITY**: 2 modules
- **WORKER**: 2 modules

## Domain Mapping Strategy

The application services currently centralized in `app/services/` map directly into clean domain packages under `app/domain/`:
1. **Auth & Identity Domain** (`app/domain/auth/`): `auth_service`, `google_oauth_service`, `session_cleanup_service`
2. **Cases Domain** (`app/domain/cases/`): `case_service`, `case_workflow_service`, `case_attention_service`, `case_intelligence_service`, `case_report_service`, `collaboration_service`, `bundle_service`, `bundle_pdf_engine`
3. **Documents Domain** (`app/domain/documents/`): `document_service`, `document_processor`, `legal_document_service`
4. **Evidence Domain** (`app/domain/evidence/`): `evidence_service`, `scanner_service`
5. **Consultations & Video Domain** (`app/domain/consultations/`): `consultation_service`, `video_meeting_service`, `video_recording_service`, `recording_storage`, `video_telemetry_service`, `presence_service`, `lawyer_call_channel`
6. **Verification Domain** (`app/domain/verification/`): `lawyer_verification_service`, `lawyer_dashboard_service`, `cohort_governance_service`
7. **Payments & Commercial Domain** (`app/domain/payments/`): `payment_service`, `commercial_service`, `reconciliation_service`, `cancellation_policy_service`, `unit_economics_service`
8. **AI & Legal Intelligence Domain** (`app/domain/ai/`): Canonical AI layer (`ai_conversation_service`, `ai_research_service`, `assistant_service`, `ai_budget_service`, `ai_review_service`, `ai_evaluation_service`, `ai_prompt_policy`, `embedding_service`, `retrieval_service`, `legal_data_pipeline`, `legal_authority_retrieval`, `citation_normalizer`, `claim_verifier`, `query_understanding`)
9. **Notifications & Reminders Domain** (`app/domain/notifications/`): `notification_service`, `reminder_service`, `email_service`, `alert_service`
10. **Users & Administration Domain** (`app/domain/users/`): `user_service`, `profile_service`, `lifecycle_service`, `admin_service`, `operator_service`, `support_service`
11. **Workers & Outbox Infrastructure** (`app/domain/jobs/` or `app/workers/`): `outbox_service`, `job_service`, `job_scheduler`, `job_worker`, `change_feed_service`

### Compatibility Re-Export Strategy
To strictly guarantee zero regressions across all 848 tests, all 44 API routers, and external callers:
- Canonical domain modules are placed in `app/domain/<domain>/`.
- Canonical domain packages export their domain services.
- All existing `app/services/<service_name>.py` modules retain transparent backward-compatibility re-exports (`from app.domain.<domain>.<service_name> import *`).
- Any tests or routers importing from `app.services.<service>` continue working without a single breakage.