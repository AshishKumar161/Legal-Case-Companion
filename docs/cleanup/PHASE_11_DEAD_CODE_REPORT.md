# Phase 11: Dead Code & Deprecation Cleanup Report

## 1. Executive Summary

Phase 11 performed a comprehensive, evidence-driven cleanup of all safely removable compatibility facades, duplicate files, and legacy shims across the Legal Case Companion repository.

Strict safety constraints were maintained:
- 0 business logic changes.
- 0 API route changes (329 paths, 388 operations verified 1:1).
- 0 test regressions (848/848 pytest tests passing, 129/129 security tests passing).
- 0 Mypy errors, 0 Ruff errors, 0 TypeScript errors, 0 ESLint errors.
- Only verified dead code with 0 callers was removed; 5 facades with active test monkeypatching were intentionally retained.

---

## 2. Deleted Files & Detailed Reference Checks

### `app/db/session.py`
- **Type**: Database Session Compatibility Shim
- **Reason for Removal**: Superseded by app.db.database. Direct imports of SessionLocal, engine, get_db were migrated.
- **Reference Check**: Zero references remain across app, tests, and scripts (5 maintenance scripts and docs/23_INCIDENT_RESPONSE.md updated).
- **Dynamic Reference Check**: Zero dynamic or string-based references.
- **Canonical Replacement**: `app.db.database (SessionLocal, get_db, engine)`
- **Test Verification**: 848/848 pytest tests passing, 0 Mypy errors, 0 Ruff errors.

### `app/services/ai_provider.py`
- **Type**: Legacy AI Provider Facade
- **Reason for Removal**: Superseded by canonical app.domain.ai.ai_provider. All callers migrated to canonical domain path.
- **Reference Check**: Zero references remain across app, tests, and scripts (test_ai_privacy.py, test_infrastructure_failures.py, etc. updated).
- **Dynamic Reference Check**: Zero dynamic references.
- **Canonical Replacement**: `app.domain.ai.ai_provider`
- **Test Verification**: 16/16 targeted AI tests passed, 129/129 security tests passed, full suite 848/848 passed.

### `app/services/legal_source_providers/ (base.py, curated_fixtures.py, ecourts_provider.py)`
- **Type**: Duplicate Directory of Legal Source Providers
- **Reason for Removal**: 100% duplicate of app/domain/ai/legal_source_providers/. All remaining callers migrated to canonical domain package.
- **Reference Check**: Zero references remain across app, tests, and scripts (legal_data_pipeline.py, admin.py, test_legal_data_pipeline.py updated).
- **Dynamic Reference Check**: Zero dynamic references.
- **Canonical Replacement**: `app.domain.ai.legal_source_providers`
- **Test Verification**: test_legal_data_pipeline.py passed, full test suite passed.

### Safely Removed Service Facades (66 files under `app/services/`)

The following 66 compatibility facades were verified to have **0 production callers**, **0 test callers**, **0 script callers**, and **0 dynamic string references** after production routers and test suites were migrated to canonical `app.domain.*` paths:

| Facade Removed | Canonical Replacement Path | References Before | References After | Verification Status |
| :--- | :--- | :--- | :--- | :--- |
| `app/services/abuse_defense_service.py` | `app.domain.*.abuse_defense_service` | Migrated | 0 | **PASS (Deleted)** |
| `app/services/admin_service.py` | `app.domain.*.admin_service` | Migrated | 0 | **PASS (Deleted)** |
| `app/services/ai_budget_service.py` | `app.domain.*.ai_budget_service` | Migrated | 0 | **PASS (Deleted)** |
| `app/services/ai_conversation_service.py` | `app.domain.*.ai_conversation_service` | Migrated | 0 | **PASS (Deleted)** |
| `app/services/ai_evaluation_service.py` | `app.domain.*.ai_evaluation_service` | Migrated | 0 | **PASS (Deleted)** |
| `app/services/ai_prompt_policy.py` | `app.domain.*.ai_prompt_policy` | Migrated | 0 | **PASS (Deleted)** |
| `app/services/ai_research_service.py` | `app.domain.*.ai_research_service` | Migrated | 0 | **PASS (Deleted)** |
| `app/services/ai_review_service.py` | `app.domain.*.ai_review_service` | Migrated | 0 | **PASS (Deleted)** |
| `app/services/alert_service.py` | `app.domain.*.alert_service` | Migrated | 0 | **PASS (Deleted)** |
| `app/services/assistant_service.py` | `app.domain.*.assistant_service` | Migrated | 0 | **PASS (Deleted)** |
| `app/services/auth_service.py` | `app.domain.*.auth_service` | Migrated | 0 | **PASS (Deleted)** |
| `app/services/bundle_pdf_engine.py` | `app.domain.*.bundle_pdf_engine` | Migrated | 0 | **PASS (Deleted)** |
| `app/services/bundle_service.py` | `app.domain.*.bundle_service` | Migrated | 0 | **PASS (Deleted)** |
| `app/services/cancellation_policy_service.py` | `app.domain.*.cancellation_policy_service` | Migrated | 0 | **PASS (Deleted)** |
| `app/services/case_attention_service.py` | `app.domain.*.case_attention_service` | Migrated | 0 | **PASS (Deleted)** |
| `app/services/case_intelligence_service.py` | `app.domain.*.case_intelligence_service` | Migrated | 0 | **PASS (Deleted)** |
| `app/services/case_report_service.py` | `app.domain.*.case_report_service` | Migrated | 0 | **PASS (Deleted)** |
| `app/services/case_service.py` | `app.domain.*.case_service` | Migrated | 0 | **PASS (Deleted)** |
| `app/services/case_workflow_service.py` | `app.domain.*.case_workflow_service` | Migrated | 0 | **PASS (Deleted)** |
| `app/services/change_feed_service.py` | `app.domain.*.change_feed_service` | Migrated | 0 | **PASS (Deleted)** |
| `app/services/citation_normalizer.py` | `app.domain.*.citation_normalizer` | Migrated | 0 | **PASS (Deleted)** |
| `app/services/claim_verifier.py` | `app.domain.*.claim_verifier` | Migrated | 0 | **PASS (Deleted)** |
| `app/services/cohort_governance_service.py` | `app.domain.*.cohort_governance_service` | Migrated | 0 | **PASS (Deleted)** |
| `app/services/collaboration_service.py` | `app.domain.*.collaboration_service` | Migrated | 0 | **PASS (Deleted)** |
| `app/services/commercial_service.py` | `app.domain.*.commercial_service` | Migrated | 0 | **PASS (Deleted)** |
| `app/services/compliance_service.py` | `app.domain.*.compliance_service` | Migrated | 0 | **PASS (Deleted)** |
| `app/services/consultation_service.py` | `app.domain.*.consultation_service` | Migrated | 0 | **PASS (Deleted)** |
| `app/services/document_service.py` | `app.domain.*.document_service` | Migrated | 0 | **PASS (Deleted)** |
| `app/services/email_service.py` | `app.domain.*.email_service` | Migrated | 0 | **PASS (Deleted)** |
| `app/services/embedding_provider.py` | `app.domain.*.embedding_provider` | Migrated | 0 | **PASS (Deleted)** |
| `app/services/embedding_service.py` | `app.domain.*.embedding_service` | Migrated | 0 | **PASS (Deleted)** |
| `app/services/evidence_service.py` | `app.domain.*.evidence_service` | Migrated | 0 | **PASS (Deleted)** |
| `app/services/experiment_service.py` | `app.domain.*.experiment_service` | Migrated | 0 | **PASS (Deleted)** |
| `app/services/google_oauth_service.py` | `app.domain.*.google_oauth_service` | Migrated | 0 | **PASS (Deleted)** |
| `app/services/incident_service.py` | `app.domain.*.incident_service` | Migrated | 0 | **PASS (Deleted)** |
| `app/services/job_scheduler.py` | `app.domain.*.job_scheduler` | Migrated | 0 | **PASS (Deleted)** |
| `app/services/job_worker.py` | `app.domain.*.job_worker` | Migrated | 0 | **PASS (Deleted)** |
| `app/services/launch_gate_service.py` | `app.domain.*.launch_gate_service` | Migrated | 0 | **PASS (Deleted)** |
| `app/services/lawyer_call_channel.py` | `app.domain.*.lawyer_call_channel` | Migrated | 0 | **PASS (Deleted)** |
| `app/services/lawyer_dashboard_service.py` | `app.domain.*.lawyer_dashboard_service` | Migrated | 0 | **PASS (Deleted)** |
| `app/services/lawyer_verification_service.py` | `app.domain.*.lawyer_verification_service` | Migrated | 0 | **PASS (Deleted)** |
| `app/services/legal_authority_ingestion.py` | `app.domain.*.legal_authority_ingestion` | Migrated | 0 | **PASS (Deleted)** |
| `app/services/legal_authority_retrieval.py` | `app.domain.*.legal_authority_retrieval` | Migrated | 0 | **PASS (Deleted)** |
| `app/services/legal_data_pipeline.py` | `app.domain.*.legal_data_pipeline` | Migrated | 0 | **PASS (Deleted)** |
| `app/services/legal_document_service.py` | `app.domain.*.legal_document_service` | Migrated | 0 | **PASS (Deleted)** |
| `app/services/lifecycle_service.py` | `app.domain.*.lifecycle_service` | Migrated | 0 | **PASS (Deleted)** |
| `app/services/llm_provider.py` | `app.domain.*.llm_provider` | Migrated | 0 | **PASS (Deleted)** |
| `app/services/message_service.py` | `app.domain.*.message_service` | Migrated | 0 | **PASS (Deleted)** |
| `app/services/notification_service.py` | `app.domain.*.notification_service` | Migrated | 0 | **PASS (Deleted)** |
| `app/services/operator_service.py` | `app.domain.*.operator_service` | Migrated | 0 | **PASS (Deleted)** |
| `app/services/outbox_service.py` | `app.domain.*.outbox_service` | Migrated | 0 | **PASS (Deleted)** |
| `app/services/profile_service.py` | `app.domain.*.profile_service` | Migrated | 0 | **PASS (Deleted)** |
| `app/services/query_understanding.py` | `app.domain.*.query_understanding` | Migrated | 0 | **PASS (Deleted)** |
| `app/services/reconciliation_service.py` | `app.domain.*.reconciliation_service` | Migrated | 0 | **PASS (Deleted)** |
| `app/services/recording_storage.py` | `app.domain.*.recording_storage` | Migrated | 0 | **PASS (Deleted)** |
| `app/services/reminder_service.py` | `app.domain.*.reminder_service` | Migrated | 0 | **PASS (Deleted)** |
| `app/services/scanner_service.py` | `app.domain.*.scanner_service` | Migrated | 0 | **PASS (Deleted)** |
| `app/services/session_cleanup_service.py` | `app.domain.*.session_cleanup_service` | Migrated | 0 | **PASS (Deleted)** |
| `app/services/support_service.py` | `app.domain.*.support_service` | Migrated | 0 | **PASS (Deleted)** |
| `app/services/translation_service.py` | `app.domain.*.translation_service` | Migrated | 0 | **PASS (Deleted)** |
| `app/services/unit_economics_service.py` | `app.domain.*.unit_economics_service` | Migrated | 0 | **PASS (Deleted)** |
| `app/services/user_service.py` | `app.domain.*.user_service` | Migrated | 0 | **PASS (Deleted)** |
| `app/services/video_meeting_service.py` | `app.domain.*.video_meeting_service` | Migrated | 0 | **PASS (Deleted)** |
| `app/services/video_recording_service.py` | `app.domain.*.video_recording_service` | Migrated | 0 | **PASS (Deleted)** |
| `app/services/video_telemetry_service.py` | `app.domain.*.video_telemetry_service` | Migrated | 0 | **PASS (Deleted)** |
| `app/services/workflow_telemetry_service.py` | `app.domain.*.workflow_telemetry_service` | Migrated | 0 | **PASS (Deleted)** |

---

## 3. Retained Compatibility Facades (Category B)

Per Phase 11 Strict Safety Rules (Section 31), the following 5 facades were **intentionally retained** because they are targeted by dynamic string monkeypatching or direct module mock injection in legacy integration/security tests:

| Retained Facade | Why Retained | Referenced By | Expected Future Action |
| :--- | :--- | :--- | :--- |
| `app/services/presence_service.py` | Targeted by string monkeypatching in tests (e.g. tests/e2e/test_distributed_multi_instance.py: 'presence_service.get_redis_client'). | Test Suite | Retain hybrid facade until test harnesses are updated to target app.domain.consultations.presence_service in future maintenance phase. |
| `app/services/job_service.py` | Targeted by string monkeypatching in tests (tests/e2e/test_infrastructure_failures.py: 'job_service.JobService.enqueue_job'). | Test Suite | Retain hybrid facade until tests are updated to target app.domain.jobs.job_service. |
| `app/services/document_processor.py` | Targeted by string monkeypatching in tests (tests/integration/test_ai_conversations.py, test_ai_research.py: 'document_processor.EmbeddingService.generate_embeddings'). | Test Suite | Retain hybrid facade until AI pipeline integration tests target app.domain.documents.document_processor. |
| `app/services/retrieval_service.py` | Targeted by string monkeypatching in tests (tests/integration/test_ai_conversations.py, test_ai_pipeline_hardening.py: 'retrieval_service.EmbeddingService.generate_embeddings'). | Test Suite | Retain hybrid facade until AI research integration tests target app.domain.ai.retrieval_service. |
| `app/services/payment_service.py` | Targeted by module-level patch in tests (tests/security/test_phase_7_6_production_security.py: ps_mod.verify_stripe_webhook_signature = ...). | Test Suite | Retain hybrid facade until security suite imports and patches app.domain.payments.payment_service directly. |

---

## 4. Verification & Regression Metrics

```
Python Compileall:   PASS (0 errors)
Ruff Lint:           PASS (0 errors)
Mypy Check:          PASS (0 errors across 263 source files)
Pytest Tests:        848/848 passed (0 regressions)
Security Tests:      129/129 passed in 11.27s
OpenAPI Routes:      329 paths, 388 operations (100% exact match)
Frontend TypeScript: 0 errors
Frontend ESLint:     0 errors, 0 warnings
Next.js Build:       PASS (36/36 routes generated)
```
