# Phase 5 Complete API Baseline Inventory

## Executive Summary
- **Total Audited Operations**: 398
- **Routers Inspected**: 44 FastAPI modular routers + WebSocket channels + Direct Application Mounts
- **Audit Scope**: Complete request/response lifecycle, dependency injection, authentication enforcement, role boundaries, object ownership, side-effects, and external integrations.

---

## Complete Route Inventory

### 1. `GET /admin/audit`
- **Router**: `admin_router`
- **Handler**: `app.api.v1.admin.get_audit_logs`
- **Auth Required**: Yes
- **Role / Permission**: `Role: ['ADMIN']`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `PaginatedResponse[AuditEventResponse]`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Required
- **Execution Trace**: `GET /admin/audit → [<app.api.deps.RequireRole object at 0x000001C14517F200>, get_db] → AdminService → DB / Engine`

### 2. `GET /admin/cases`
- **Router**: `admin_router`
- **Handler**: `app.api.v1.admin.list_cases`
- **Auth Required**: Yes
- **Role / Permission**: `Role: ['ADMIN']`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `PaginatedResponse[AdminCaseResponse]`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `GET /admin/cases → [<app.api.deps.RequireRole object at 0x000001C145157BF0>, get_db] → AdminService → DB / Engine`

### 3. `GET /admin/consultations`
- **Router**: `admin_router`
- **Handler**: `app.api.v1.admin.list_consultations`
- **Auth Required**: Yes
- **Role / Permission**: `Role: ['ADMIN']`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `PaginatedResponse[AdminConsultationResponse]`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `GET /admin/consultations → [<app.api.deps.RequireRole object at 0x000001C14517CA40>, get_db] → AdminService → DB / Engine`

### 4. `GET /admin/document-security`
- **Router**: `admin_router`
- **Handler**: `app.api.v1.admin.list_document_security`
- **Auth Required**: Yes
- **Role / Permission**: `Role: ['ADMIN']`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `PaginatedResponse[AdminDocumentSecurityResponse]`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Required
- **Execution Trace**: `GET /admin/document-security → [<app.api.deps.RequireRole object at 0x000001C14517E540>, get_db] → AdminService → DB / Engine`

### 5. `GET /admin/jobs`
- **Router**: `admin_router`
- **Handler**: `app.api.v1.admin.list_background_jobs`
- **Auth Required**: Yes
- **Role / Permission**: `Role: ['ADMIN']`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `PaginatedResponse[JobResponse]`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `GET /admin/jobs → [<app.api.deps.RequireRole object at 0x000001C1451B0E00>, get_db] → AdminService → DB / Engine`

### 6. `GET /admin/jobs/stats`
- **Router**: `admin_router`
- **Handler**: `app.api.v1.admin.get_job_stats`
- **Auth Required**: Yes
- **Role / Permission**: `Role: ['ADMIN']`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `JobStatsResponse`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `GET /admin/jobs/stats → [<app.api.deps.RequireRole object at 0x000001C1451B1A30>, get_db] → AdminService → DB / Engine`

### 7. `GET /admin/jobs/{job_id}`
- **Router**: `admin_router`
- **Handler**: `app.api.v1.admin.get_job_by_id`
- **Auth Required**: Yes
- **Role / Permission**: `Role: ['ADMIN']`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `JobResponse`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `GET /admin/jobs/{job_id} → [<app.api.deps.RequireRole object at 0x000001C1451B2270>, get_db] → AdminService → DB / Engine`

### 8. `POST /admin/jobs/{job_id}/execute`
- **Router**: `admin_router`
- **Handler**: `app.api.v1.admin.trigger_job_execution`
- **Auth Required**: Yes
- **Role / Permission**: `Role: ['ADMIN']`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `JobResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /admin/jobs/{job_id}/execute → [<app.api.deps.RequireRole object at 0x000001C1451B2C30>, get_db] → AdminService → DB / Engine`

### 9. `GET /admin/legal-sources`
- **Router**: `admin_router`
- **Handler**: `app.api.v1.admin.list_legal_sources`
- **Auth Required**: Yes
- **Role / Permission**: `Role: ['ADMIN']`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `dict / Raw Response`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `GET /admin/legal-sources → [<app.api.deps.RequireRole object at 0x000001C1451B3F50>, get_db] → AdminService → DB / Engine`

### 10. `POST /admin/legal-sources/import-raw`
- **Router**: `admin_router`
- **Handler**: `app.api.v1.admin.import_raw_legal_source`
- **Auth Required**: Yes
- **Role / Permission**: `Role: ['ADMIN']`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `dict / Raw Response`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /admin/legal-sources/import-raw → [<app.api.deps.RequireRole object at 0x000001C1451D1040>, get_db] → AdminService → DB / Engine`

### 11. `POST /admin/legal-sources/sync-fixtures`
- **Router**: `admin_router`
- **Handler**: `app.api.v1.admin.sync_curated_legal_fixtures`
- **Auth Required**: Yes
- **Role / Permission**: `Role: ['ADMIN']`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `dict / Raw Response`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /admin/legal-sources/sync-fixtures → [<app.api.deps.RequireRole object at 0x000001C1451D0800>, get_db] → AdminService → DB / Engine`

### 12. `POST /admin/legal-sources/{source_id}/reindex`
- **Router**: `admin_router`
- **Handler**: `app.api.v1.admin.reindex_legal_source`
- **Auth Required**: Yes
- **Role / Permission**: `Role: ['ADMIN']`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `dict / Raw Response`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /admin/legal-sources/{source_id}/reindex → [<app.api.deps.RequireRole object at 0x000001C1451D1880>, get_db] → AdminService → DB / Engine`

### 13. `GET /admin/metrics`
- **Router**: `admin_router`
- **Handler**: `app.api.v1.admin.get_operational_metrics`
- **Auth Required**: Yes
- **Role / Permission**: `Role: ['ADMIN']`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `dict / Raw Response`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `GET /admin/metrics → [<app.api.deps.RequireRole object at 0x000001C1451B3620>] → AdminService → DB / Engine`

### 14. `GET /admin/operators/{user_id}/permissions`
- **Router**: `admin_router`
- **Handler**: `app.api.v1.admin.list_operator_permissions`
- **Auth Required**: Yes
- **Role / Permission**: `Operator: None`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `dict / Raw Response`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `GET /admin/operators/{user_id}/permissions → [<app.api.deps.RequireOperatorPermission object at 0x000001C1451D3590>, get_db] → AdminService → DB / Engine`

### 15. `POST /admin/operators/{user_id}/permissions`
- **Router**: `admin_router`
- **Handler**: `app.api.v1.admin.grant_operator_permission`
- **Auth Required**: Yes
- **Role / Permission**: `Operator: None`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `dict / Raw Response`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /admin/operators/{user_id}/permissions → [<app.api.deps.RequireOperatorPermission object at 0x000001C1451D2180>, get_db] → AdminService → DB / Engine`

### 16. `DELETE /admin/operators/{user_id}/permissions/{permission}`
- **Router**: `admin_router`
- **Handler**: `app.api.v1.admin.revoke_operator_permission`
- **Auth Required**: Yes
- **Role / Permission**: `Operator: None`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `dict / Raw Response`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `DELETE /admin/operators/{user_id}/permissions/{permission} → [<app.api.deps.RequireOperatorPermission object at 0x000001C1451D2BA0>, get_db] → AdminService → DB / Engine`

### 17. `GET /admin/overview`
- **Router**: `admin_router`
- **Handler**: `app.api.v1.admin.get_operational_overview`
- **Auth Required**: Yes
- **Role / Permission**: `Role: ['ADMIN']`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `AdminOverviewResponse`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `GET /admin/overview → [<app.api.deps.RequireRole object at 0x000001C14500AB40>, get_db] → AdminService → DB / Engine`

### 18. `GET /admin/payments`
- **Router**: `admin_router`
- **Handler**: `app.api.v1.admin.list_payments`
- **Auth Required**: Yes
- **Role / Permission**: `Role: ['ADMIN']`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `PaginatedResponse[AdminPaymentResponse]`
- **Database Side Effect**: Read Only
- **External Side Effect**: S3 / Stripe / LiveKit / LLM
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Required
- **Execution Trace**: `GET /admin/payments → [<app.api.deps.RequireRole object at 0x000001C14517D760>, get_db] → AdminService → DB / Engine`

### 19. `GET /admin/security-events`
- **Router**: `admin_router`
- **Handler**: `app.api.v1.admin.get_security_events`
- **Auth Required**: Yes
- **Role / Permission**: `Role: ['ADMIN']`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `PaginatedResponse[AdminSecurityEventResponse]`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `GET /admin/security-events → [<app.api.deps.RequireRole object at 0x000001C1451B0230>, get_db] → AdminService → DB / Engine`

### 20. `GET /admin/users`
- **Router**: `admin_router`
- **Handler**: `app.api.v1.admin.list_users`
- **Auth Required**: Yes
- **Role / Permission**: `Role: ['ADMIN']`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `PaginatedResponse[AdminUserResponse]`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `GET /admin/users → [<app.api.deps.RequireRole object at 0x000001C1451170E0>, get_db] → AdminService → DB / Engine`

### 21. `GET /admin/users/{user_id}`
- **Router**: `admin_router`
- **Handler**: `app.api.v1.admin.get_user_details`
- **Auth Required**: Yes
- **Role / Permission**: `Role: ['ADMIN']`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `AdminUserResponse`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `GET /admin/users/{user_id} → [<app.api.deps.RequireRole object at 0x000001C145117B60>, get_db] → AdminService → DB / Engine`

### 22. `POST /admin/users/{user_id}/reactivate`
- **Router**: `admin_router`
- **Handler**: `app.api.v1.admin.reactivate_user`
- **Auth Required**: Yes
- **Role / Permission**: `Role: ['ADMIN']`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `UserResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /admin/users/{user_id}/reactivate → [<app.api.deps.RequireRole object at 0x000001C145154AA0>, get_db] → AdminService → DB / Engine`

### 23. `POST /admin/users/{user_id}/suspend`
- **Router**: `admin_router`
- **Handler**: `app.api.v1.admin.suspend_user`
- **Auth Required**: Yes
- **Role / Permission**: `Role: ['ADMIN']`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `UserResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /admin/users/{user_id}/suspend → [<app.api.deps.RequireRole object at 0x000001C145154290>, get_db] → AdminService → DB / Engine`

### 24. `GET /admin/verifications`
- **Router**: `admin_router`
- **Handler**: `app.api.v1.admin.get_verifications`
- **Auth Required**: Yes
- **Role / Permission**: `Role: ['ADMIN']`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `PaginatedResponse[LawyerVerificationResponse]`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `GET /admin/verifications → [<app.api.deps.RequireRole object at 0x000001C145155A90>, get_db] → AdminService → DB / Engine`

### 25. `POST /admin/verifications/{verification_id}/approve`
- **Router**: `admin_router`
- **Handler**: `app.api.v1.admin.approve_verification`
- **Auth Required**: Yes
- **Role / Permission**: `Role: ['ADMIN']`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `LawyerVerificationResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /admin/verifications/{verification_id}/approve → [<app.api.deps.RequireRole object at 0x000001C1451562A0>, get_db] → AdminService → DB / Engine`

### 26. `POST /admin/verifications/{verification_id}/reject`
- **Router**: `admin_router`
- **Handler**: `app.api.v1.admin.reject_verification`
- **Auth Required**: Yes
- **Role / Permission**: `Role: ['ADMIN']`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `LawyerVerificationResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /admin/verifications/{verification_id}/reject → [<app.api.deps.RequireRole object at 0x000001C145156E10>, get_db] → AdminService → DB / Engine`

### 27. `GET /ai/reviews`
- **Router**: `ai_review_router`
- **Handler**: `app.api.v1.ai_review.list_ai_reviews`
- **Auth Required**: Yes
- **Role / Permission**: `Operator: None`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `list`
- **Database Side Effect**: Read Only
- **External Side Effect**: S3 / Stripe / LiveKit / LLM
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /ai/reviews → [<app.api.deps.RequireOperatorPermission object at 0x000001C145509880>, get_db] → Ai_reviewService → DB / Engine`

### 28. `POST /ai/reviews`
- **Router**: `ai_review_router`
- **Handler**: `app.api.v1.ai_review.submit_ai_review`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `AIReviewResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: S3 / Stripe / LiveKit / LLM
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /ai/reviews → [get_current_user, get_db] → Ai_reviewService → DB / Engine`

### 29. `GET /ai/reviews/analytics/metrics`
- **Router**: `ai_review_router`
- **Handler**: `app.api.v1.ai_review.get_ai_review_metrics`
- **Auth Required**: Yes
- **Role / Permission**: `Role: ['ADMIN']`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `dict`
- **Database Side Effect**: Read Only
- **External Side Effect**: S3 / Stripe / LiveKit / LLM
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /ai/reviews/analytics/metrics → [<app.api.deps.RequireRole object at 0x000001C14550B890>, get_db] → Ai_reviewService → DB / Engine`

### 30. `POST /ai/reviews/benchmark/run`
- **Router**: `ai_review_router`
- **Handler**: `app.api.v1.ai_review.run_ai_benchmark`
- **Auth Required**: Yes
- **Role / Permission**: `Role: ['ADMIN']`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `dict`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: S3 / Stripe / LiveKit / LLM
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /ai/reviews/benchmark/run → [<app.api.deps.RequireRole object at 0x000001C145538140>] → Ai_reviewService → DB / Engine`

### 31. `GET /ai/reviews/{review_id}`
- **Router**: `ai_review_router`
- **Handler**: `app.api.v1.ai_review.get_ai_review`
- **Auth Required**: Yes
- **Role / Permission**: `Operator: None`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `AIReviewResponse`
- **Database Side Effect**: Read Only
- **External Side Effect**: S3 / Stripe / LiveKit / LLM
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /ai/reviews/{review_id} → [<app.api.deps.RequireOperatorPermission object at 0x000001C145509FD0>, get_db] → Ai_reviewService → DB / Engine`

### 32. `POST /ai/reviews/{review_id}/action`
- **Router**: `ai_review_router`
- **Handler**: `app.api.v1.ai_review.action_ai_review`
- **Auth Required**: Yes
- **Role / Permission**: `Operator: None`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `AIReviewResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: S3 / Stripe / LiveKit / LLM
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /ai/reviews/{review_id}/action → [<app.api.deps.RequireOperatorPermission object at 0x000001C14550AE40>, get_db] → Ai_reviewService → DB / Engine`

### 33. `GET /analytics/ai-health`
- **Router**: `analytics_router`
- **Handler**: `app.api.v1.analytics.get_ai_health`
- **Auth Required**: Yes
- **Role / Permission**: `Role: ADMIN`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `AIEvaluationSummary`
- **Database Side Effect**: Read Only
- **External Side Effect**: S3 / Stripe / LiveKit / LLM
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /analytics/ai-health → [get_db, require_admin] → AnalyticsService → DB / Engine`

### 34. `POST /analytics/events`
- **Router**: `analytics_router`
- **Handler**: `app.api.v1.analytics.log_product_event`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `dict / Raw Response`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /analytics/events → [get_current_user, get_db] → AnalyticsService → DB / Engine`

### 35. `GET /analytics/funnel`
- **Router**: `analytics_router`
- **Handler**: `app.api.v1.analytics.get_conversion_funnel`
- **Auth Required**: Yes
- **Role / Permission**: `Role: ADMIN`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `FunnelResponse`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /analytics/funnel → [get_db, require_admin] → AnalyticsService → DB / Engine`

### 36. `GET /analytics/product-health`
- **Router**: `analytics_router`
- **Handler**: `app.api.v1.analytics.get_product_health`
- **Auth Required**: Yes
- **Role / Permission**: `Role: ADMIN`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `ProductHealthSummary`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /analytics/product-health → [get_db, require_admin] → AnalyticsService → DB / Engine`

### 37. `GET /audit`
- **Router**: `audit_router`
- **Handler**: `app.api.v1.audit.get_audit_logs`
- **Auth Required**: Yes
- **Role / Permission**: `Role: ['ADMIN']`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `PaginatedResponse[AuditEventResponse]`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /audit → [<app.api.deps.RequireRole object at 0x000001C1455641A0>, get_db] → AuditService → DB / Engine`

### 38. `DELETE /auth/account`
- **Router**: `auth_router`
- **Handler**: `app.api.v1.auth.delete_user_account_endpoint`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `dict / Raw Response`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Required
- **Execution Trace**: `DELETE /auth/account → [get_db, get_current_user] → AuthService → DB / Engine`

### 39. `POST /auth/email/verify/confirm`
- **Router**: `auth_router`
- **Handler**: `app.api.v1.auth.confirm_email_verification`
- **Auth Required**: No
- **Role / Permission**: `None (Public)`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `EmailVerificationResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: S3 / Stripe / LiveKit / LLM
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Required
- **Execution Trace**: `POST /auth/email/verify/confirm → [get_db] → AuthService → DB / Engine`

### 40. `POST /auth/email/verify/otp`
- **Router**: `auth_router`
- **Handler**: `app.api.v1.auth.verify_email_otp`
- **Auth Required**: No
- **Role / Permission**: `None (Public)`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `Token`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: S3 / Stripe / LiveKit / LLM
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Required
- **Execution Trace**: `POST /auth/email/verify/otp → [get_db] → AuthService → DB / Engine`

### 41. `POST /auth/email/verify/request`
- **Router**: `auth_router`
- **Handler**: `app.api.v1.auth.request_email_verification`
- **Auth Required**: No
- **Role / Permission**: `None (Public)`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `EmailVerificationResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: S3 / Stripe / LiveKit / LLM
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Required
- **Execution Trace**: `POST /auth/email/verify/request → [get_db] → AuthService → DB / Engine`

### 42. `POST /auth/forgot-password`
- **Router**: `auth_router`
- **Handler**: `app.api.v1.auth.request_password_reset`
- **Auth Required**: No
- **Role / Permission**: `None (Public)`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `PasswordResetResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Required
- **Execution Trace**: `POST /auth/forgot-password → [get_db] → AuthService → DB / Engine`

### 43. `GET /auth/google/callback`
- **Router**: `auth_router`
- **Handler**: `app.api.v1.auth.google_callback_get`
- **Auth Required**: No
- **Role / Permission**: `None (Public)`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `Token`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /auth/google/callback → [get_db] → AuthService → DB / Engine`

### 44. `POST /auth/google/callback`
- **Router**: `auth_router`
- **Handler**: `app.api.v1.auth.google_callback_post`
- **Auth Required**: No
- **Role / Permission**: `None (Public)`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `Token`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Required
- **Execution Trace**: `POST /auth/google/callback → [get_db] → AuthService → DB / Engine`

### 45. `POST /auth/google/direct`
- **Router**: `auth_router`
- **Handler**: `app.api.v1.auth.google_direct_auth`
- **Auth Required**: No
- **Role / Permission**: `None (Public)`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `Token`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Required
- **Execution Trace**: `POST /auth/google/direct → [get_db] → AuthService → DB / Engine`

### 46. `POST /auth/google/link`
- **Router**: `auth_router`
- **Handler**: `app.api.v1.auth.google_link_account`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `ExternalIdentityResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Required
- **Execution Trace**: `POST /auth/google/link → [get_db, get_current_user] → AuthService → DB / Engine`

### 47. `GET /auth/google/login`
- **Router**: `auth_router`
- **Handler**: `app.api.v1.auth.google_login_init`
- **Auth Required**: No
- **Role / Permission**: `None (Public)`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `GoogleAuthUrlResponse`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /auth/google/login → [Direct] → AuthService → DB / Engine`

### 48. `POST /auth/google/unlink`
- **Router**: `auth_router`
- **Handler**: `app.api.v1.auth.google_unlink_account`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `dict / Raw Response`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Required
- **Execution Trace**: `POST /auth/google/unlink → [get_db, get_current_user] → AuthService → DB / Engine`

### 49. `GET /auth/identities`
- **Router**: `auth_router`
- **Handler**: `app.api.v1.auth.get_user_identities`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `list`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /auth/identities → [get_db, get_current_user] → AuthService → DB / Engine`

### 50. `POST /auth/login`
- **Router**: `auth_router`
- **Handler**: `app.api.v1.auth.login`
- **Auth Required**: No
- **Role / Permission**: `None (Public)`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `Token`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Required
- **Execution Trace**: `POST /auth/login → [get_db] → AuthService → DB / Engine`

### 51. `POST /auth/logout`
- **Router**: `auth_router`
- **Handler**: `app.api.v1.auth.logout`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `dict / Raw Response`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Required
- **Execution Trace**: `POST /auth/logout → [get_db, get_current_user] → AuthService → DB / Engine`

### 52. `GET /auth/me`
- **Router**: `auth_router`
- **Handler**: `app.api.v1.auth.get_current_user_identity`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `CurrentUserResponse`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /auth/me → [get_current_user, get_db] → AuthService → DB / Engine`

### 53. `POST /auth/password/change`
- **Router**: `auth_router`
- **Handler**: `app.api.v1.auth.change_password`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `dict / Raw Response`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Required
- **Execution Trace**: `POST /auth/password/change → [get_db, get_current_user] → AuthService → DB / Engine`

### 54. `POST /auth/password/reset/confirm`
- **Router**: `auth_router`
- **Handler**: `app.api.v1.auth.confirm_password_reset`
- **Auth Required**: No
- **Role / Permission**: `None (Public)`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `PasswordResetResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Required
- **Execution Trace**: `POST /auth/password/reset/confirm → [get_db] → AuthService → DB / Engine`

### 55. `POST /auth/password/reset/request`
- **Router**: `auth_router`
- **Handler**: `app.api.v1.auth.request_password_reset`
- **Auth Required**: No
- **Role / Permission**: `None (Public)`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `PasswordResetResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Required
- **Execution Trace**: `POST /auth/password/reset/request → [get_db] → AuthService → DB / Engine`

### 56. `POST /auth/refresh`
- **Router**: `auth_router`
- **Handler**: `app.api.v1.auth.refresh`
- **Auth Required**: No
- **Role / Permission**: `None (Public)`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `Token`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Required
- **Execution Trace**: `POST /auth/refresh → [get_db] → AuthService → DB / Engine`

### 57. `POST /auth/register`
- **Router**: `auth_router`
- **Handler**: `app.api.v1.auth.register`
- **Auth Required**: No
- **Role / Permission**: `None (Public)`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `UserResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Required
- **Execution Trace**: `POST /auth/register → [get_db] → AuthService → DB / Engine`

### 58. `POST /auth/reset-password`
- **Router**: `auth_router`
- **Handler**: `app.api.v1.auth.confirm_password_reset`
- **Auth Required**: No
- **Role / Permission**: `None (Public)`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `PasswordResetResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Required
- **Execution Trace**: `POST /auth/reset-password → [get_db] → AuthService → DB / Engine`

### 59. `GET /calendar/events`
- **Router**: `calendar_router`
- **Handler**: `app.api.v1.calendar.get_calendar_events`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `CalendarEventsResponse`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /calendar/events → [get_db, get_current_user] → CalendarService → DB / Engine`

### 60. `GET /cases`
- **Router**: `cases_router`
- **Handler**: `app.api.v1.cases.get_cases`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `PaginatedResponse[CaseResponse]`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /cases → [get_current_user, get_db] → CasesService → DB / Engine`

### 61. `POST /cases`
- **Router**: `cases_router`
- **Handler**: `app.api.v1.cases.create_case`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `CaseResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /cases → [get_current_user, get_db] → CasesService → DB / Engine`

### 62. `DELETE /cases/{case_id}`
- **Router**: `cases_router`
- **Handler**: `app.api.v1.cases.delete_case`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `dict / Raw Response`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `DELETE /cases/{case_id} → [get_current_user, get_db] → CasesService → DB / Engine`

### 63. `GET /cases/{case_id}`
- **Router**: `cases_router`
- **Handler**: `app.api.v1.cases.get_case`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `CaseResponse`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /cases/{case_id} → [get_current_user, get_db] → CasesService → DB / Engine`

### 64. `PATCH /cases/{case_id}`
- **Router**: `cases_router`
- **Handler**: `app.api.v1.cases.update_case`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `CaseResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `PATCH /cases/{case_id} → [get_current_user, get_db] → CasesService → DB / Engine`

### 65. `GET /cases/{case_id}/ai/conversations`
- **Router**: `ai_conversations_router`
- **Handler**: `app.api.v1.ai_conversations.list_conversations`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `list`
- **Database Side Effect**: Read Only
- **External Side Effect**: S3 / Stripe / LiveKit / LLM
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /cases/{case_id}/ai/conversations → [get_db, get_current_user] → Ai_conversationsService → DB / Engine`

### 66. `POST /cases/{case_id}/ai/conversations`
- **Router**: `ai_conversations_router`
- **Handler**: `app.api.v1.ai_conversations.create_conversation`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `AIConversationResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: S3 / Stripe / LiveKit / LLM
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /cases/{case_id}/ai/conversations → [get_db, get_current_user] → Ai_conversationsService → DB / Engine`

### 67. `DELETE /cases/{case_id}/ai/conversations/{conversation_id}`
- **Router**: `ai_conversations_router`
- **Handler**: `app.api.v1.ai_conversations.delete_conversation`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `dict / Raw Response`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: S3 / Stripe / LiveKit / LLM
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `DELETE /cases/{case_id}/ai/conversations/{conversation_id} → [get_db, get_current_user] → Ai_conversationsService → DB / Engine`

### 68. `GET /cases/{case_id}/ai/conversations/{conversation_id}`
- **Router**: `ai_conversations_router`
- **Handler**: `app.api.v1.ai_conversations.get_conversation`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `AIConversationResponse`
- **Database Side Effect**: Read Only
- **External Side Effect**: S3 / Stripe / LiveKit / LLM
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /cases/{case_id}/ai/conversations/{conversation_id} → [get_db, get_current_user] → Ai_conversationsService → DB / Engine`

### 69. `PATCH /cases/{case_id}/ai/conversations/{conversation_id}`
- **Router**: `ai_conversations_router`
- **Handler**: `app.api.v1.ai_conversations.update_conversation`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `AIConversationResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: S3 / Stripe / LiveKit / LLM
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `PATCH /cases/{case_id}/ai/conversations/{conversation_id} → [get_db, get_current_user] → Ai_conversationsService → DB / Engine`

### 70. `GET /cases/{case_id}/ai/conversations/{conversation_id}/messages`
- **Router**: `ai_conversations_router`
- **Handler**: `app.api.v1.ai_conversations.list_messages`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `list`
- **Database Side Effect**: Read Only
- **External Side Effect**: S3 / Stripe / LiveKit / LLM
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /cases/{case_id}/ai/conversations/{conversation_id}/messages → [get_db, get_current_user] → Ai_conversationsService → DB / Engine`

### 71. `POST /cases/{case_id}/ai/conversations/{conversation_id}/messages`
- **Router**: `ai_conversations_router`
- **Handler**: `app.api.v1.ai_conversations.send_message`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `AIMessageResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: S3 / Stripe / LiveKit / LLM
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /cases/{case_id}/ai/conversations/{conversation_id}/messages → [get_db, get_current_user] → Ai_conversationsService → DB / Engine`

### 72. `POST /cases/{case_id}/ai/research`
- **Router**: `ai_router`
- **Handler**: `app.api.v1.ai.generate_ai_research`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `AIResearchResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: S3 / Stripe / LiveKit / LLM
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /cases/{case_id}/ai/research → [get_db, get_current_user] → AiService → DB / Engine`

### 73. `POST /cases/{case_id}/assistant/query`
- **Router**: `assistant_router`
- **Handler**: `app.api.v1.assistant.query_case_assistant`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `CaseAssistantQueryResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /cases/{case_id}/assistant/query → [get_db, get_current_user] → AssistantService → DB / Engine`

### 74. `GET /cases/{case_id}/attention`
- **Router**: `attention_router`
- **Handler**: `app.api.v1.attention.get_case_attention`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `dict`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /cases/{case_id}/attention → [get_current_user, get_db] → AttentionService → DB / Engine`

### 75. `GET /cases/{case_id}/bundles`
- **Router**: `bundles_router`
- **Handler**: `app.api.v1.bundles.list_bundles`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `list`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /cases/{case_id}/bundles → [get_db, get_current_user] → BundlesService → DB / Engine`

### 76. `POST /cases/{case_id}/bundles`
- **Router**: `bundles_router`
- **Handler**: `app.api.v1.bundles.create_bundle`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `BundleDetailResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /cases/{case_id}/bundles → [get_db, get_current_user] → BundlesService → DB / Engine`

### 77. `GET /cases/{case_id}/bundles/{bundle_id}`
- **Router**: `bundles_router`
- **Handler**: `app.api.v1.bundles.get_bundle`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `BundleDetailResponse`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /cases/{case_id}/bundles/{bundle_id} → [get_db, get_current_user] → BundlesService → DB / Engine`

### 78. `PUT /cases/{case_id}/bundles/{bundle_id}`
- **Router**: `bundles_router`
- **Handler**: `app.api.v1.bundles.update_bundle`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `BundleDetailResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `PUT /cases/{case_id}/bundles/{bundle_id} → [get_db, get_current_user] → BundlesService → DB / Engine`

### 79. `POST /cases/{case_id}/bundles/{bundle_id}/certificate`
- **Router**: `bundles_router`
- **Handler**: `app.api.v1.bundles.prepare_bsa_certificate`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `BSACertificateResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /cases/{case_id}/bundles/{bundle_id}/certificate → [get_db, get_current_user] → BundlesService → DB / Engine`

### 80. `GET /cases/{case_id}/bundles/{bundle_id}/certificate/{certificate_id}/download`
- **Router**: `bundles_router`
- **Handler**: `app.api.v1.bundles.get_certificate_download`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `dict / Raw Response`
- **Database Side Effect**: Read Only
- **External Side Effect**: S3 / Stripe / LiveKit / LLM
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /cases/{case_id}/bundles/{bundle_id}/certificate/{certificate_id}/download → [get_db, get_current_user] → BundlesService → DB / Engine`

### 81. `GET /cases/{case_id}/bundles/{bundle_id}/download`
- **Router**: `bundles_router`
- **Handler**: `app.api.v1.bundles.get_bundle_download`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `dict / Raw Response`
- **Database Side Effect**: Read Only
- **External Side Effect**: S3 / Stripe / LiveKit / LLM
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /cases/{case_id}/bundles/{bundle_id}/download → [get_db, get_current_user] → BundlesService → DB / Engine`

### 82. `POST /cases/{case_id}/bundles/{bundle_id}/finalize`
- **Router**: `bundles_router`
- **Handler**: `app.api.v1.bundles.finalize_bundle`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `BundleDetailResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /cases/{case_id}/bundles/{bundle_id}/finalize → [get_db, get_current_user] → BundlesService → DB / Engine`

### 83. `GET /cases/{case_id}/collaboration/brief`
- **Router**: `cases_router`
- **Handler**: `app.api.v1.cases.get_matter_brief`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `MatterBriefResponse`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /cases/{case_id}/collaboration/brief → [get_current_user, get_db] → CasesService → DB / Engine`

### 84. `GET /cases/{case_id}/collaboration/messages`
- **Router**: `cases_router`
- **Handler**: `app.api.v1.cases.get_case_messages`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `list`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /cases/{case_id}/collaboration/messages → [get_current_user, get_db] → CasesService → DB / Engine`

### 85. `POST /cases/{case_id}/collaboration/messages`
- **Router**: `cases_router`
- **Handler**: `app.api.v1.cases.send_case_message`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `CaseMessageResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /cases/{case_id}/collaboration/messages → [get_current_user, get_db] → CasesService → DB / Engine`

### 86. `GET /cases/{case_id}/collaboration/participants`
- **Router**: `cases_router`
- **Handler**: `app.api.v1.cases.get_matter_participants_detailed`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `list`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /cases/{case_id}/collaboration/participants → [get_current_user, get_db] → CasesService → DB / Engine`

### 87. `GET /cases/{case_id}/collaboration/requests`
- **Router**: `cases_router`
- **Handler**: `app.api.v1.cases.get_matter_requests`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `list`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /cases/{case_id}/collaboration/requests → [get_current_user, get_db] → CasesService → DB / Engine`

### 88. `POST /cases/{case_id}/collaboration/requests`
- **Router**: `cases_router`
- **Handler**: `app.api.v1.cases.create_matter_request`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `MatterRequestResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /cases/{case_id}/collaboration/requests → [get_current_user, get_db] → CasesService → DB / Engine`

### 89. `POST /cases/{case_id}/collaboration/requests/{request_id}/review`
- **Router**: `cases_router`
- **Handler**: `app.api.v1.cases.review_matter_request`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `MatterRequestResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /cases/{case_id}/collaboration/requests/{request_id}/review → [get_current_user, get_db] → CasesService → DB / Engine`

### 90. `POST /cases/{case_id}/collaboration/requests/{request_id}/submit`
- **Router**: `cases_router`
- **Handler**: `app.api.v1.cases.submit_matter_request`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `MatterRequestResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /cases/{case_id}/collaboration/requests/{request_id}/submit → [get_current_user, get_db] → CasesService → DB / Engine`

### 91. `GET /cases/{case_id}/consultations`
- **Router**: `cases_router`
- **Handler**: `app.api.v1.cases.get_case_consultations`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `PaginatedResponse[ConsultationResponse]`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /cases/{case_id}/consultations → [get_current_user, get_db] → CasesService → DB / Engine`

### 92. `POST /cases/{case_id}/consultations`
- **Router**: `cases_router`
- **Handler**: `app.api.v1.cases.create_case_consultation`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `ConsultationResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /cases/{case_id}/consultations → [get_current_user, get_db] → CasesService → DB / Engine`

### 93. `GET /cases/{case_id}/deadlines`
- **Router**: `workflow_router`
- **Handler**: `app.api.v1.workflow.list_deadlines`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `list`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /cases/{case_id}/deadlines → [get_db, get_current_user] → WorkflowService → DB / Engine`

### 94. `POST /cases/{case_id}/deadlines`
- **Router**: `workflow_router`
- **Handler**: `app.api.v1.workflow.create_deadline`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `CaseDeadlineResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /cases/{case_id}/deadlines → [get_db, get_current_user] → WorkflowService → DB / Engine`

### 95. `PATCH /cases/{case_id}/deadlines/{deadline_id}`
- **Router**: `workflow_router`
- **Handler**: `app.api.v1.workflow.update_deadline`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `CaseDeadlineResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `PATCH /cases/{case_id}/deadlines/{deadline_id} → [get_db, get_current_user] → WorkflowService → DB / Engine`

### 96. `POST /cases/{case_id}/deadlines/{deadline_id}/cancel`
- **Router**: `workflow_router`
- **Handler**: `app.api.v1.workflow.cancel_deadline`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `CaseDeadlineResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /cases/{case_id}/deadlines/{deadline_id}/cancel → [get_db, get_current_user] → WorkflowService → DB / Engine`

### 97. `POST /cases/{case_id}/deadlines/{deadline_id}/complete`
- **Router**: `workflow_router`
- **Handler**: `app.api.v1.workflow.complete_deadline`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `CaseDeadlineResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /cases/{case_id}/deadlines/{deadline_id}/complete → [get_db, get_current_user] → WorkflowService → DB / Engine`

### 98. `POST /cases/{case_id}/deadlines/{deadline_id}/confirm`
- **Router**: `workflow_router`
- **Handler**: `app.api.v1.workflow.confirm_deadline`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `CaseDeadlineResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /cases/{case_id}/deadlines/{deadline_id}/confirm → [get_db, get_current_user] → WorkflowService → DB / Engine`

### 99. `GET /cases/{case_id}/documents`
- **Router**: `documents_router`
- **Handler**: `app.api.v1.documents.get_case_documents`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `PaginatedResponse[DocumentResponse]`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /cases/{case_id}/documents → [get_current_user, get_db] → DocumentsService → DB / Engine`

### 100. `POST /cases/{case_id}/documents`
- **Router**: `documents_router`
- **Handler**: `app.api.v1.documents.upload_case_document_direct`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `DocumentResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Required
- **Execution Trace**: `POST /cases/{case_id}/documents → [get_current_user, get_db] → DocumentsService → DB / Engine`

### 101. `GET /cases/{case_id}/documents/summary`
- **Router**: `documents_router`
- **Handler**: `app.api.v1.documents.get_case_documents_summary`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `DocumentSummaryStats`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /cases/{case_id}/documents/summary → [get_current_user, get_db] → DocumentsService → DB / Engine`

### 102. `POST /cases/{case_id}/documents/upload-init`
- **Router**: `documents_router`
- **Handler**: `app.api.v1.documents.create_document_metadata`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `UploadDocumentResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: S3 / Stripe / LiveKit / LLM
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Required
- **Execution Trace**: `POST /cases/{case_id}/documents/upload-init → [get_current_user, get_db] → DocumentsService → DB / Engine`

### 103. `DELETE /cases/{case_id}/documents/{document_id}`
- **Router**: `documents_router`
- **Handler**: `app.api.v1.documents.delete_case_document`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `dict / Raw Response`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Required
- **Execution Trace**: `DELETE /cases/{case_id}/documents/{document_id} → [get_current_user, get_db] → DocumentsService → DB / Engine`

### 104. `GET /cases/{case_id}/documents/{document_id}`
- **Router**: `documents_router`
- **Handler**: `app.api.v1.documents.get_case_document_by_id`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `DocumentResponse`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /cases/{case_id}/documents/{document_id} → [get_current_user, get_db] → DocumentsService → DB / Engine`

### 105. `PATCH /cases/{case_id}/documents/{document_id}`
- **Router**: `documents_router`
- **Handler**: `app.api.v1.documents.update_case_document_metadata`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `DocumentResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Required
- **Execution Trace**: `PATCH /cases/{case_id}/documents/{document_id} → [get_current_user, get_db] → DocumentsService → DB / Engine`

### 106. `GET /cases/{case_id}/documents/{document_id}/chunks`
- **Router**: `documents_router`
- **Handler**: `app.api.v1.documents.get_case_document_chunks`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `PaginatedResponse[DocumentChunkResponse]`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /cases/{case_id}/documents/{document_id}/chunks → [get_current_user, get_db] → DocumentsService → DB / Engine`

### 107. `POST /cases/{case_id}/documents/{document_id}/complete`
- **Router**: `documents_router`
- **Handler**: `app.api.v1.documents.complete_case_document_upload`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `DocumentResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Required
- **Execution Trace**: `POST /cases/{case_id}/documents/{document_id}/complete → [get_current_user, get_db] → DocumentsService → DB / Engine`

### 108. `GET /cases/{case_id}/documents/{document_id}/download`
- **Router**: `documents_router`
- **Handler**: `app.api.v1.documents.get_case_document_download_url`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `DownloadDocumentResponse`
- **Database Side Effect**: Read Only
- **External Side Effect**: S3 / Stripe / LiveKit / LLM
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /cases/{case_id}/documents/{document_id}/download → [get_current_user, get_db] → DocumentsService → DB / Engine`

### 109. `GET /cases/{case_id}/documents/{document_id}/pages`
- **Router**: `documents_router`
- **Handler**: `app.api.v1.documents.get_case_document_pages`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `PaginatedResponse[DocumentPageResponse]`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /cases/{case_id}/documents/{document_id}/pages → [get_current_user, get_db] → DocumentsService → DB / Engine`

### 110. `POST /cases/{case_id}/documents/{document_id}/process`
- **Router**: `documents_router`
- **Handler**: `app.api.v1.documents.trigger_case_document_processing`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `DocumentProcessingStatusResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Required
- **Execution Trace**: `POST /cases/{case_id}/documents/{document_id}/process → [get_current_user, get_db] → DocumentsService → DB / Engine`

### 111. `GET /cases/{case_id}/documents/{document_id}/processing-status`
- **Router**: `documents_router`
- **Handler**: `app.api.v1.documents.get_case_document_processing_status`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `DocumentProcessingStatusResponse`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /cases/{case_id}/documents/{document_id}/processing-status → [get_current_user, get_db] → DocumentsService → DB / Engine`

### 112. `GET /cases/{case_id}/evidence`
- **Router**: `evidence_router`
- **Handler**: `app.api.v1.evidence.list_evidence`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `list`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /cases/{case_id}/evidence → [get_current_user, get_db] → EvidenceService → DB / Engine`

### 113. `GET /cases/{case_id}/evidence-shared-with-me`
- **Router**: `evidence_router`
- **Handler**: `app.api.v1.evidence.list_case_shared_with_me`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `list`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /cases/{case_id}/evidence-shared-with-me → [get_current_user, get_db] → EvidenceService → DB / Engine`

### 114. `POST /cases/{case_id}/evidence/batch`
- **Router**: `evidence_router`
- **Handler**: `app.api.v1.evidence.batch_evidence_actions`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `EvidenceBatchResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Required
- **Execution Trace**: `POST /cases/{case_id}/evidence/batch → [get_current_user, get_db] → EvidenceService → DB / Engine`

### 115. `POST /cases/{case_id}/evidence/upload-init`
- **Router**: `evidence_router`
- **Handler**: `app.api.v1.evidence.init_evidence_upload`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `EvidenceUploadInitResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: S3 / Stripe / LiveKit / LLM
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Required
- **Execution Trace**: `POST /cases/{case_id}/evidence/upload-init → [get_current_user, get_db] → EvidenceService → DB / Engine`

### 116. `DELETE /cases/{case_id}/evidence/{evidence_id}`
- **Router**: `evidence_router`
- **Handler**: `app.api.v1.evidence.delete_evidence`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `dict / Raw Response`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Required
- **Execution Trace**: `DELETE /cases/{case_id}/evidence/{evidence_id} → [get_current_user, get_db] → EvidenceService → DB / Engine`

### 117. `GET /cases/{case_id}/evidence/{evidence_id}`
- **Router**: `evidence_router`
- **Handler**: `app.api.v1.evidence.get_evidence_detail`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `EvidenceDetailResponse`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /cases/{case_id}/evidence/{evidence_id} → [get_current_user, get_db] → EvidenceService → DB / Engine`

### 118. `PATCH /cases/{case_id}/evidence/{evidence_id}`
- **Router**: `evidence_router`
- **Handler**: `app.api.v1.evidence.update_evidence_metadata`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `EvidenceResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Required
- **Execution Trace**: `PATCH /cases/{case_id}/evidence/{evidence_id} → [get_current_user, get_db] → EvidenceService → DB / Engine`

### 119. `POST /cases/{case_id}/evidence/{evidence_id}/archive`
- **Router**: `evidence_router`
- **Handler**: `app.api.v1.evidence.archive_evidence`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `EvidenceResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Required
- **Execution Trace**: `POST /cases/{case_id}/evidence/{evidence_id}/archive → [get_current_user, get_db] → EvidenceService → DB / Engine`

### 120. `POST /cases/{case_id}/evidence/{evidence_id}/complete`
- **Router**: `evidence_router`
- **Handler**: `app.api.v1.evidence.complete_evidence_upload`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `EvidenceResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Required
- **Execution Trace**: `POST /cases/{case_id}/evidence/{evidence_id}/complete → [get_current_user, get_db] → EvidenceService → DB / Engine`

### 121. `GET /cases/{case_id}/evidence/{evidence_id}/custody`
- **Router**: `evidence_router`
- **Handler**: `app.api.v1.evidence.get_evidence_custody_chain`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `list`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /cases/{case_id}/evidence/{evidence_id}/custody → [get_current_user, get_db] → EvidenceService → DB / Engine`

### 122. `GET /cases/{case_id}/evidence/{evidence_id}/download`
- **Router**: `evidence_router`
- **Handler**: `app.api.v1.evidence.download_evidence`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `EvidenceSignedUrlResponse`
- **Database Side Effect**: Read Only
- **External Side Effect**: S3 / Stripe / LiveKit / LLM
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /cases/{case_id}/evidence/{evidence_id}/download → [get_current_user, get_db] → EvidenceService → DB / Engine`

### 123. `GET /cases/{case_id}/evidence/{evidence_id}/exhibits`
- **Router**: `evidence_router`
- **Handler**: `app.api.v1.evidence.list_exhibits_for_evidence`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `list`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /cases/{case_id}/evidence/{evidence_id}/exhibits → [get_current_user, get_db] → EvidenceService → DB / Engine`

### 124. `POST /cases/{case_id}/evidence/{evidence_id}/exhibits`
- **Router**: `evidence_router`
- **Handler**: `app.api.v1.evidence.create_case_exhibit`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `CaseExhibitResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Required
- **Execution Trace**: `POST /cases/{case_id}/evidence/{evidence_id}/exhibits → [get_current_user, get_db] → EvidenceService → DB / Engine`

### 125. `GET /cases/{case_id}/evidence/{evidence_id}/grants`
- **Router**: `evidence_router`
- **Handler**: `app.api.v1.evidence.list_evidence_grants`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `list`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /cases/{case_id}/evidence/{evidence_id}/grants → [get_current_user, get_db] → EvidenceService → DB / Engine`

### 126. `POST /cases/{case_id}/evidence/{evidence_id}/legal-hold`
- **Router**: `evidence_router`
- **Handler**: `app.api.v1.evidence.set_evidence_legal_hold`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `EvidenceResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Required
- **Execution Trace**: `POST /cases/{case_id}/evidence/{evidence_id}/legal-hold → [get_current_user, get_db] → EvidenceService → DB / Engine`

### 127. `POST /cases/{case_id}/evidence/{evidence_id}/restore`
- **Router**: `evidence_router`
- **Handler**: `app.api.v1.evidence.restore_evidence`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `EvidenceResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Required
- **Execution Trace**: `POST /cases/{case_id}/evidence/{evidence_id}/restore → [get_current_user, get_db] → EvidenceService → DB / Engine`

### 128. `POST /cases/{case_id}/evidence/{evidence_id}/revoke`
- **Router**: `evidence_router`
- **Handler**: `app.api.v1.evidence.revoke_evidence_access`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `EvidenceAccessGrantResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Required
- **Execution Trace**: `POST /cases/{case_id}/evidence/{evidence_id}/revoke → [get_current_user, get_db] → EvidenceService → DB / Engine`

### 129. `POST /cases/{case_id}/evidence/{evidence_id}/share`
- **Router**: `evidence_router`
- **Handler**: `app.api.v1.evidence.share_evidence`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `EvidenceAccessGrantResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Required
- **Execution Trace**: `POST /cases/{case_id}/evidence/{evidence_id}/share → [get_current_user, get_db] → EvidenceService → DB / Engine`

### 130. `GET /cases/{case_id}/evidence/{evidence_id}/shareable-participants`
- **Router**: `evidence_router`
- **Handler**: `app.api.v1.evidence.get_shareable_participants`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `list`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /cases/{case_id}/evidence/{evidence_id}/shareable-participants → [get_current_user, get_db] → EvidenceService → DB / Engine`

### 131. `POST /cases/{case_id}/evidence/{evidence_id}/verify-integrity`
- **Router**: `evidence_router`
- **Handler**: `app.api.v1.evidence.verify_evidence_integrity`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `EvidenceIntegrityVerifyResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Required
- **Execution Trace**: `POST /cases/{case_id}/evidence/{evidence_id}/verify-integrity → [get_current_user, get_db] → EvidenceService → DB / Engine`

### 132. `GET /cases/{case_id}/evidence/{evidence_id}/versions`
- **Router**: `evidence_router`
- **Handler**: `app.api.v1.evidence.list_evidence_versions`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `list`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /cases/{case_id}/evidence/{evidence_id}/versions → [get_current_user, get_db] → EvidenceService → DB / Engine`

### 133. `POST /cases/{case_id}/evidence/{evidence_id}/versions/upload-init`
- **Router**: `evidence_router`
- **Handler**: `app.api.v1.evidence.init_version_upload`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `EvidenceUploadInitResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: S3 / Stripe / LiveKit / LLM
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Required
- **Execution Trace**: `POST /cases/{case_id}/evidence/{evidence_id}/versions/upload-init → [get_current_user, get_db] → EvidenceService → DB / Engine`

### 134. `GET /cases/{case_id}/evidence/{evidence_id}/versions/{version_id}`
- **Router**: `evidence_router`
- **Handler**: `app.api.v1.evidence.get_evidence_version`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `EvidenceVersionResponse`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /cases/{case_id}/evidence/{evidence_id}/versions/{version_id} → [get_current_user, get_db] → EvidenceService → DB / Engine`

### 135. `POST /cases/{case_id}/evidence/{evidence_id}/versions/{version_id}/complete`
- **Router**: `evidence_router`
- **Handler**: `app.api.v1.evidence.complete_version_upload`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `EvidenceResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Required
- **Execution Trace**: `POST /cases/{case_id}/evidence/{evidence_id}/versions/{version_id}/complete → [get_current_user, get_db] → EvidenceService → DB / Engine`

### 136. `GET /cases/{case_id}/evidence/{evidence_id}/view-url`
- **Router**: `evidence_router`
- **Handler**: `app.api.v1.evidence.view_evidence`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `EvidenceSignedUrlResponse`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /cases/{case_id}/evidence/{evidence_id}/view-url → [get_current_user, get_db] → EvidenceService → DB / Engine`

### 137. `GET /cases/{case_id}/exhibits`
- **Router**: `evidence_router`
- **Handler**: `app.api.v1.evidence.list_case_exhibits`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `list`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /cases/{case_id}/exhibits → [get_current_user, get_db] → EvidenceService → DB / Engine`

### 138. `DELETE /cases/{case_id}/exhibits/{exhibit_id}`
- **Router**: `evidence_router`
- **Handler**: `app.api.v1.evidence.delete_case_exhibit`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `dict / Raw Response`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `DELETE /cases/{case_id}/exhibits/{exhibit_id} → [get_current_user, get_db] → EvidenceService → DB / Engine`

### 139. `GET /cases/{case_id}/exhibits/{exhibit_id}`
- **Router**: `evidence_router`
- **Handler**: `app.api.v1.evidence.get_case_exhibit`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `CaseExhibitResponse`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /cases/{case_id}/exhibits/{exhibit_id} → [get_current_user, get_db] → EvidenceService → DB / Engine`

### 140. `PATCH /cases/{case_id}/exhibits/{exhibit_id}`
- **Router**: `evidence_router`
- **Handler**: `app.api.v1.evidence.update_case_exhibit`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `CaseExhibitResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `PATCH /cases/{case_id}/exhibits/{exhibit_id} → [get_current_user, get_db] → EvidenceService → DB / Engine`

### 141. `POST /cases/{case_id}/grant-lawyer-access`
- **Router**: `cases_router`
- **Handler**: `app.api.v1.cases.grant_lawyer_access`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `ParticipantResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /cases/{case_id}/grant-lawyer-access → [get_current_user, get_db] → CasesService → DB / Engine`

### 142. `GET /cases/{case_id}/hearings`
- **Router**: `workflow_router`
- **Handler**: `app.api.v1.workflow.list_hearings`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `list`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /cases/{case_id}/hearings → [get_db, get_current_user] → WorkflowService → DB / Engine`

### 143. `POST /cases/{case_id}/hearings`
- **Router**: `workflow_router`
- **Handler**: `app.api.v1.workflow.create_hearing`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `CaseHearingResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /cases/{case_id}/hearings → [get_db, get_current_user] → WorkflowService → DB / Engine`

### 144. `POST /cases/{case_id}/hearings/import-ecourts`
- **Router**: `workflow_router`
- **Handler**: `app.api.v1.workflow.import_ecourts_hearing`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `CaseHearingResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /cases/{case_id}/hearings/import-ecourts → [get_db, get_current_user] → WorkflowService → DB / Engine`

### 145. `PATCH /cases/{case_id}/hearings/{hearing_id}`
- **Router**: `workflow_router`
- **Handler**: `app.api.v1.workflow.update_hearing`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `CaseHearingResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `PATCH /cases/{case_id}/hearings/{hearing_id} → [get_db, get_current_user] → WorkflowService → DB / Engine`

### 146. `POST /cases/{case_id}/hearings/{hearing_id}/adjourn`
- **Router**: `workflow_router`
- **Handler**: `app.api.v1.workflow.adjourn_hearing`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `CaseHearingResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /cases/{case_id}/hearings/{hearing_id}/adjourn → [get_db, get_current_user] → WorkflowService → DB / Engine`

### 147. `POST /cases/{case_id}/hearings/{hearing_id}/complete`
- **Router**: `workflow_router`
- **Handler**: `app.api.v1.workflow.complete_hearing`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `CaseHearingResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /cases/{case_id}/hearings/{hearing_id}/complete → [get_db, get_current_user] → WorkflowService → DB / Engine`

### 148. `POST /cases/{case_id}/hearings/{hearing_id}/confirm`
- **Router**: `workflow_router`
- **Handler**: `app.api.v1.workflow.confirm_hearing`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `CaseHearingResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /cases/{case_id}/hearings/{hearing_id}/confirm → [get_db, get_current_user] → WorkflowService → DB / Engine`

### 149. `GET /cases/{case_id}/intelligence`
- **Router**: `case_intelligence_router`
- **Handler**: `app.api.v1.case_intelligence.get_case_intelligence`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `CaseIntelligenceResponse`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /cases/{case_id}/intelligence → [get_db, get_current_user] → Case_intelligenceService → DB / Engine`

### 150. `GET /cases/{case_id}/intelligence/evidence-gaps`
- **Router**: `case_intelligence_router`
- **Handler**: `app.api.v1.case_intelligence.list_evidence_gaps`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `list`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /cases/{case_id}/intelligence/evidence-gaps → [get_db, get_current_user] → Case_intelligenceService → DB / Engine`

### 151. `POST /cases/{case_id}/intelligence/evidence-gaps`
- **Router**: `case_intelligence_router`
- **Handler**: `app.api.v1.case_intelligence.create_evidence_gap`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `CaseEvidenceGapResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Required
- **Execution Trace**: `POST /cases/{case_id}/intelligence/evidence-gaps → [get_db, get_current_user] → Case_intelligenceService → DB / Engine`

### 152. `PATCH /cases/{case_id}/intelligence/evidence-gaps/{gap_id}`
- **Router**: `case_intelligence_router`
- **Handler**: `app.api.v1.case_intelligence.update_evidence_gap`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `CaseEvidenceGapResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Required
- **Execution Trace**: `PATCH /cases/{case_id}/intelligence/evidence-gaps/{gap_id} → [get_db, get_current_user] → Case_intelligenceService → DB / Engine`

### 153. `GET /cases/{case_id}/intelligence/facts`
- **Router**: `case_intelligence_router`
- **Handler**: `app.api.v1.case_intelligence.list_facts`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `list`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /cases/{case_id}/intelligence/facts → [get_db, get_current_user] → Case_intelligenceService → DB / Engine`

### 154. `POST /cases/{case_id}/intelligence/facts`
- **Router**: `case_intelligence_router`
- **Handler**: `app.api.v1.case_intelligence.create_fact`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `CaseFactResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /cases/{case_id}/intelligence/facts → [get_db, get_current_user] → Case_intelligenceService → DB / Engine`

### 155. `PATCH /cases/{case_id}/intelligence/facts/{fact_id}`
- **Router**: `case_intelligence_router`
- **Handler**: `app.api.v1.case_intelligence.update_fact`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `CaseFactResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `PATCH /cases/{case_id}/intelligence/facts/{fact_id} → [get_db, get_current_user] → Case_intelligenceService → DB / Engine`

### 156. `GET /cases/{case_id}/intelligence/issues`
- **Router**: `case_intelligence_router`
- **Handler**: `app.api.v1.case_intelligence.list_issues`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `list`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /cases/{case_id}/intelligence/issues → [get_db, get_current_user] → Case_intelligenceService → DB / Engine`

### 157. `POST /cases/{case_id}/intelligence/issues`
- **Router**: `case_intelligence_router`
- **Handler**: `app.api.v1.case_intelligence.create_issue`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `LegalIssueResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /cases/{case_id}/intelligence/issues → [get_db, get_current_user] → Case_intelligenceService → DB / Engine`

### 158. `PATCH /cases/{case_id}/intelligence/issues/{issue_id}`
- **Router**: `case_intelligence_router`
- **Handler**: `app.api.v1.case_intelligence.update_issue`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `LegalIssueResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `PATCH /cases/{case_id}/intelligence/issues/{issue_id} → [get_db, get_current_user] → Case_intelligenceService → DB / Engine`

### 159. `POST /cases/{case_id}/intelligence/refresh`
- **Router**: `case_intelligence_router`
- **Handler**: `app.api.v1.case_intelligence.refresh_case_intelligence`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `CaseIntelligenceResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /cases/{case_id}/intelligence/refresh → [get_db, get_current_user] → Case_intelligenceService → DB / Engine`

### 160. `GET /cases/{case_id}/intelligence/risks`
- **Router**: `case_intelligence_router`
- **Handler**: `app.api.v1.case_intelligence.list_risks`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `list`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /cases/{case_id}/intelligence/risks → [get_db, get_current_user] → Case_intelligenceService → DB / Engine`

### 161. `POST /cases/{case_id}/intelligence/risks`
- **Router**: `case_intelligence_router`
- **Handler**: `app.api.v1.case_intelligence.create_risk`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `CaseRiskIndicatorResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /cases/{case_id}/intelligence/risks → [get_db, get_current_user] → Case_intelligenceService → DB / Engine`

### 162. `PATCH /cases/{case_id}/intelligence/risks/{risk_id}`
- **Router**: `case_intelligence_router`
- **Handler**: `app.api.v1.case_intelligence.update_risk`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `CaseRiskIndicatorResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `PATCH /cases/{case_id}/intelligence/risks/{risk_id} → [get_db, get_current_user] → Case_intelligenceService → DB / Engine`

### 163. `GET /cases/{case_id}/intelligence/timeline`
- **Router**: `case_intelligence_router`
- **Handler**: `app.api.v1.case_intelligence.list_timeline`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `list`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /cases/{case_id}/intelligence/timeline → [get_db, get_current_user] → Case_intelligenceService → DB / Engine`

### 164. `POST /cases/{case_id}/intelligence/timeline`
- **Router**: `case_intelligence_router`
- **Handler**: `app.api.v1.case_intelligence.create_timeline_event`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `CaseChronologyEventResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /cases/{case_id}/intelligence/timeline → [get_db, get_current_user] → Case_intelligenceService → DB / Engine`

### 165. `PATCH /cases/{case_id}/intelligence/timeline/{event_id}`
- **Router**: `case_intelligence_router`
- **Handler**: `app.api.v1.case_intelligence.update_timeline_event`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `CaseChronologyEventResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `PATCH /cases/{case_id}/intelligence/timeline/{event_id} → [get_db, get_current_user] → Case_intelligenceService → DB / Engine`

### 166. `GET /cases/{case_id}/notes`
- **Router**: `cases_router`
- **Handler**: `app.api.v1.cases.get_notes`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `PaginatedResponse[CaseNoteResponse]`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /cases/{case_id}/notes → [get_current_user, get_db] → CasesService → DB / Engine`

### 167. `POST /cases/{case_id}/notes`
- **Router**: `cases_router`
- **Handler**: `app.api.v1.cases.create_note`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `CaseNoteResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /cases/{case_id}/notes → [get_current_user, get_db] → CasesService → DB / Engine`

### 168. `DELETE /cases/{case_id}/notes/{note_id}`
- **Router**: `cases_router`
- **Handler**: `app.api.v1.cases.delete_note`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `dict / Raw Response`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `DELETE /cases/{case_id}/notes/{note_id} → [get_current_user, get_db] → CasesService → DB / Engine`

### 169. `GET /cases/{case_id}/notes/{note_id}`
- **Router**: `cases_router`
- **Handler**: `app.api.v1.cases.get_note`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `CaseNoteResponse`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /cases/{case_id}/notes/{note_id} → [get_current_user, get_db] → CasesService → DB / Engine`

### 170. `PATCH /cases/{case_id}/notes/{note_id}`
- **Router**: `cases_router`
- **Handler**: `app.api.v1.cases.update_note`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `CaseNoteResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `PATCH /cases/{case_id}/notes/{note_id} → [get_current_user, get_db] → CasesService → DB / Engine`

### 171. `GET /cases/{case_id}/participants`
- **Router**: `cases_router`
- **Handler**: `app.api.v1.cases.get_participants`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `PaginatedResponse[ParticipantResponse]`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /cases/{case_id}/participants → [get_current_user, get_db] → CasesService → DB / Engine`

### 172. `POST /cases/{case_id}/participants`
- **Router**: `cases_router`
- **Handler**: `app.api.v1.cases.add_participant`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `ParticipantResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /cases/{case_id}/participants → [get_current_user, get_db] → CasesService → DB / Engine`

### 173. `DELETE /cases/{case_id}/participants/{user_id}`
- **Router**: `cases_router`
- **Handler**: `app.api.v1.cases.remove_participant`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `dict / Raw Response`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `DELETE /cases/{case_id}/participants/{user_id} → [get_current_user, get_db] → CasesService → DB / Engine`

### 174. `PATCH /cases/{case_id}/participants/{user_id}`
- **Router**: `cases_router`
- **Handler**: `app.api.v1.cases.update_participant_role`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `ParticipantResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `PATCH /cases/{case_id}/participants/{user_id} → [get_current_user, get_db] → CasesService → DB / Engine`

### 175. `GET /cases/{case_id}/report`
- **Router**: `cases_router`
- **Handler**: `app.api.v1.cases.export_case_report`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `dict / Raw Response`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /cases/{case_id}/report → [get_current_user, get_db] → CasesService → DB / Engine`

### 176. `POST /cases/{case_id}/search`
- **Router**: `search_router`
- **Handler**: `app.api.v1.search.search_case_evidence`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `CaseSearchResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /cases/{case_id}/search → [get_current_user, get_db] → SearchService → DB / Engine`

### 177. `GET /cases/{case_id}/tasks`
- **Router**: `cases_router`
- **Handler**: `app.api.v1.cases.get_tasks`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `PaginatedResponse[CaseTaskResponse]`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /cases/{case_id}/tasks → [get_current_user, get_db] → CasesService → DB / Engine`

### 178. `POST /cases/{case_id}/tasks`
- **Router**: `cases_router`
- **Handler**: `app.api.v1.cases.create_task`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `CaseTaskResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /cases/{case_id}/tasks → [get_current_user, get_db] → CasesService → DB / Engine`

### 179. `POST /cases/{case_id}/tasks/batch`
- **Router**: `workflow_router`
- **Handler**: `app.api.v1.workflow.batch_task_operations`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `dict / Raw Response`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /cases/{case_id}/tasks/batch → [get_db, get_current_user] → WorkflowService → DB / Engine`

### 180. `DELETE /cases/{case_id}/tasks/{task_id}`
- **Router**: `cases_router`
- **Handler**: `app.api.v1.cases.delete_task`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `dict / Raw Response`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `DELETE /cases/{case_id}/tasks/{task_id} → [get_current_user, get_db] → CasesService → DB / Engine`

### 181. `GET /cases/{case_id}/tasks/{task_id}`
- **Router**: `cases_router`
- **Handler**: `app.api.v1.cases.get_task`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `CaseTaskResponse`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /cases/{case_id}/tasks/{task_id} → [get_current_user, get_db] → CasesService → DB / Engine`

### 182. `PATCH /cases/{case_id}/tasks/{task_id}`
- **Router**: `cases_router`
- **Handler**: `app.api.v1.cases.update_task`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `CaseTaskResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `PATCH /cases/{case_id}/tasks/{task_id} → [get_current_user, get_db] → CasesService → DB / Engine`

### 183. `POST /cases/{case_id}/tasks/{task_id}/cancel`
- **Router**: `workflow_router`
- **Handler**: `app.api.v1.workflow.cancel_task`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `CaseTaskResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /cases/{case_id}/tasks/{task_id}/cancel → [get_db, get_current_user] → WorkflowService → DB / Engine`

### 184. `POST /cases/{case_id}/tasks/{task_id}/complete`
- **Router**: `workflow_router`
- **Handler**: `app.api.v1.workflow.complete_task`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `CaseTaskResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /cases/{case_id}/tasks/{task_id}/complete → [get_db, get_current_user] → WorkflowService → DB / Engine`

### 185. `POST /cases/{case_id}/tasks/{task_id}/confirm`
- **Router**: `workflow_router`
- **Handler**: `app.api.v1.workflow.confirm_task`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `CaseTaskResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /cases/{case_id}/tasks/{task_id}/confirm → [get_db, get_current_user] → WorkflowService → DB / Engine`

### 186. `POST /cases/{case_id}/tasks/{task_id}/reassign`
- **Router**: `workflow_router`
- **Handler**: `app.api.v1.workflow.reassign_task`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `CaseTaskResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /cases/{case_id}/tasks/{task_id}/reassign → [get_db, get_current_user] → WorkflowService → DB / Engine`

### 187. `POST /cases/{case_id}/tasks/{task_id}/reopen`
- **Router**: `workflow_router`
- **Handler**: `app.api.v1.workflow.reopen_task`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `CaseTaskResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /cases/{case_id}/tasks/{task_id}/reopen → [get_db, get_current_user] → WorkflowService → DB / Engine`

### 188. `POST /cases/{case_id}/tasks/{task_id}/start`
- **Router**: `workflow_router`
- **Handler**: `app.api.v1.workflow.start_task`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `CaseTaskResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /cases/{case_id}/tasks/{task_id}/start → [get_db, get_current_user] → WorkflowService → DB / Engine`

### 189. `GET /cases/{case_id}/timeline`
- **Router**: `cases_router`
- **Handler**: `app.api.v1.cases.get_timeline`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `PaginatedResponse[TimelineEventResponse]`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /cases/{case_id}/timeline → [get_current_user, get_db] → CasesService → DB / Engine`

### 190. `GET /cases/{case_id}/workflow`
- **Router**: `workflow_router`
- **Handler**: `app.api.v1.workflow.get_case_workflow`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `CaseWorkflowResponse`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /cases/{case_id}/workflow → [get_db, get_current_user] → WorkflowService → DB / Engine`

### 191. `GET /cases/{case_id}/workflow/deadlines`
- **Router**: `workflow_router`
- **Handler**: `app.api.v1.workflow.get_filtered_deadlines`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `dict / Raw Response`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /cases/{case_id}/workflow/deadlines → [get_db, get_current_user] → WorkflowService → DB / Engine`

### 192. `GET /cases/{case_id}/workflow/health-summary`
- **Router**: `workflow_router`
- **Handler**: `app.api.v1.workflow.get_case_health_summary`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `CaseHealthSummaryResponse`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /cases/{case_id}/workflow/health-summary → [get_db, get_current_user] → WorkflowService → DB / Engine`

### 193. `POST /cases/{case_id}/workflow/suggestions/generate`
- **Router**: `workflow_router`
- **Handler**: `app.api.v1.workflow.generate_workflow_suggestions`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `dict / Raw Response`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /cases/{case_id}/workflow/suggestions/generate → [get_db, get_current_user] → WorkflowService → DB / Engine`

### 194. `GET /cases/{case_id}/workflow/tasks`
- **Router**: `workflow_router`
- **Handler**: `app.api.v1.workflow.get_filtered_tasks`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `dict / Raw Response`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /cases/{case_id}/workflow/tasks → [get_db, get_current_user] → WorkflowService → DB / Engine`

### 195. `POST /cases/{case_id}/workflow/templates/apply`
- **Router**: `workflow_router`
- **Handler**: `app.api.v1.workflow.apply_workflow_template`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `list`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /cases/{case_id}/workflow/templates/apply → [get_db, get_current_user] → WorkflowService → DB / Engine`

### 196. `GET /cases/{case_id}/workspace`
- **Router**: `cases_router`
- **Handler**: `app.api.v1.cases.get_case_workspace`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `CaseWorkspaceResponse`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /cases/{case_id}/workspace → [get_current_user, get_db] → CasesService → DB / Engine`

### 197. `GET /commercial/entitlements/my`
- **Router**: `commercial_router`
- **Handler**: `app.api.v1.commercial.get_my_entitlements`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `list`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Required
- **Execution Trace**: `GET /commercial/entitlements/my → [get_current_user, get_db] → CommercialService → DB / Engine`

### 198. `GET /commercial/invoices/{transaction_identifier}/receipt`
- **Router**: `commercial_router`
- **Handler**: `app.api.v1.commercial.get_invoice_receipt`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `dict`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Required
- **Execution Trace**: `GET /commercial/invoices/{transaction_identifier}/receipt → [get_db, get_current_user] → CommercialService → DB / Engine`

### 199. `POST /commercial/payouts/process`
- **Router**: `commercial_router`
- **Handler**: `app.api.v1.commercial.process_payout`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `dict`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: S3 / Stripe / LiveKit / LLM
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Required
- **Execution Trace**: `POST /commercial/payouts/process → [get_db, get_current_user] → CommercialService → DB / Engine`

### 200. `POST /commercial/refunds/request`
- **Router**: `commercial_router`
- **Handler**: `app.api.v1.commercial.request_deterministic_refund`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `dict`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Required
- **Execution Trace**: `POST /commercial/refunds/request → [get_db, get_current_user] → CommercialService → DB / Engine`

### 201. `GET /commercial/settlements/reconciliation`
- **Router**: `commercial_router`
- **Handler**: `app.api.v1.commercial.get_settlement_reconciliation`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `dict`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Required
- **Execution Trace**: `GET /commercial/settlements/reconciliation → [get_db, get_current_user] → CommercialService → DB / Engine`

### 202. `GET /commercial/strategy`
- **Router**: `commercial_router`
- **Handler**: `app.api.v1.commercial.get_billing_strategy`
- **Auth Required**: No
- **Role / Permission**: `None (Public)`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `dict`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Required
- **Execution Trace**: `GET /commercial/strategy → [get_db] → CommercialService → DB / Engine`

### 203. `POST /commercial/strategy`
- **Router**: `commercial_router`
- **Handler**: `app.api.v1.commercial.update_billing_strategy`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `dict`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Required
- **Execution Trace**: `POST /commercial/strategy → [get_db, get_current_user] → CommercialService → DB / Engine`

### 204. `GET /commercial/transactions/{transaction_id}`
- **Router**: `commercial_router`
- **Handler**: `app.api.v1.commercial.get_transaction`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `dict`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Required
- **Execution Trace**: `GET /commercial/transactions/{transaction_id} → [get_current_user, get_db] → CommercialService → DB / Engine`

### 205. `POST /commercial/transactions/{transaction_id}/capture`
- **Router**: `commercial_router`
- **Handler**: `app.api.v1.commercial.capture_transaction`
- **Auth Required**: Yes
- **Role / Permission**: `Operator: None`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `dict`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Required
- **Execution Trace**: `POST /commercial/transactions/{transaction_id}/capture → [<app.api.deps.RequireOperatorPermission object at 0x000001C1457AB500>, get_db] → CommercialService → DB / Engine`

### 206. `GET /commercial/transactions/{transaction_id}/invoice`
- **Router**: `commercial_router`
- **Handler**: `app.api.v1.commercial.get_invoice_record`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `dict`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Required
- **Execution Trace**: `GET /commercial/transactions/{transaction_id}/invoice → [get_current_user, get_db] → CommercialService → DB / Engine`

### 207. `POST /commercial/transactions/{transaction_id}/refund`
- **Router**: `commercial_router`
- **Handler**: `app.api.v1.commercial.process_refund`
- **Auth Required**: Yes
- **Role / Permission**: `Operator: None`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `dict`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Required
- **Execution Trace**: `POST /commercial/transactions/{transaction_id}/refund → [<app.api.deps.RequireOperatorPermission object at 0x000001C1457DC050>, get_db] → CommercialService → DB / Engine`

### 208. `GET /commercial/unit-economics`
- **Router**: `commercial_router`
- **Handler**: `app.api.v1.commercial.get_unit_economics`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `dict`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Required
- **Execution Trace**: `GET /commercial/unit-economics → [get_db, get_current_user] → CommercialService → DB / Engine`

### 209. `GET /compliance/items`
- **Router**: `compliance_router`
- **Handler**: `app.api.v1.compliance.list_compliance_items`
- **Auth Required**: Yes
- **Role / Permission**: `Operator: None`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `list`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /compliance/items → [<app.api.deps.RequireOperatorPermission object at 0x000001C1457FEC30>, get_db] → ComplianceService → DB / Engine`

### 210. `POST /compliance/items`
- **Router**: `compliance_router`
- **Handler**: `app.api.v1.compliance.register_compliance_item`
- **Auth Required**: Yes
- **Role / Permission**: `Operator: None`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `dict / Raw Response`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /compliance/items → [<app.api.deps.RequireOperatorPermission object at 0x000001C1457FF200>, get_db] → ComplianceService → DB / Engine`

### 211. `POST /compliance/items/{compliance_item_id}/review`
- **Router**: `compliance_router`
- **Handler**: `app.api.v1.compliance.record_legal_review`
- **Auth Required**: Yes
- **Role / Permission**: `Operator: None`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `dict / Raw Response`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /compliance/items/{compliance_item_id}/review → [<app.api.deps.RequireOperatorPermission object at 0x000001C145828110>, get_db] → ComplianceService → DB / Engine`

### 212. `GET /compliance/scorecard`
- **Router**: `compliance_router`
- **Handler**: `app.api.v1.compliance.get_compliance_scorecard`
- **Auth Required**: Yes
- **Role / Permission**: `Operator: None`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `dict`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /compliance/scorecard → [<app.api.deps.RequireOperatorPermission object at 0x000001C1457FE060>, get_db] → ComplianceService → DB / Engine`

### 213. `GET /consultations`
- **Router**: `consultations_router`
- **Handler**: `app.api.v1.consultations.get_consultations`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `PaginatedResponse[ConsultationResponse]`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /consultations → [get_current_user, get_db] → ConsultationsService → DB / Engine`

### 214. `POST /consultations`
- **Router**: `consultations_router`
- **Handler**: `app.api.v1.consultations.request_consultation`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `ConsultationResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /consultations → [get_current_user, get_db] → ConsultationsService → DB / Engine`

### 215. `GET /consultations/incoming-calls`
- **Router**: `consultations_router`
- **Handler**: `app.api.v1.consultations.get_incoming_calls_for_lawyer`
- **Auth Required**: Yes
- **Role / Permission**: `Role: ['LAWYER', 'ADMIN']`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `dict / Raw Response`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /consultations/incoming-calls → [get_db, <app.api.deps.RequireRole object at 0x000001C145636720>] → ConsultationsService → DB / Engine`

### 216. `POST /consultations/instant-call`
- **Router**: `consultations_router`
- **Handler**: `app.api.v1.consultations.request_instant_video_call`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `dict / Raw Response`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /consultations/instant-call → [get_current_user, get_db] → ConsultationsService → DB / Engine`

### 217. `GET /consultations/lawyer-call-status`
- **Router**: `consultations_router`
- **Handler**: `app.api.v1.consultations.get_lawyer_call_status`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `dict / Raw Response`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /consultations/lawyer-call-status → [get_current_user, get_db] → ConsultationsService → DB / Engine`

### 218. `GET /consultations/pricing-preview`
- **Router**: `consultations_router`
- **Handler**: `app.api.v1.consultations.get_consultation_pricing_preview`
- **Auth Required**: No
- **Role / Permission**: `None (Public)`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `ConsultationPricingResponse`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /consultations/pricing-preview → [get_db] → ConsultationsService → DB / Engine`

### 219. `POST /consultations/ws-ticket`
- **Router**: `consultations_router`
- **Handler**: `app.api.v1.consultations.create_websocket_ticket`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `WSTicketResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /consultations/ws-ticket → [get_current_user, get_db] → ConsultationsService → DB / Engine`

### 220. `WS /consultations/ws/incoming-calls`
- **Router**: `consultations_router`
- **Handler**: `app.api.v1.consultations.websocket_incoming_calls`
- **Auth Required**: Yes
- **Role / Permission**: `Participant / Verified Lawyer`
- **Object Ownership Check**: Enforced (Room Token / Session Binding)
- **Request Schema**: `WebSocket Frame / JSON Signaling`
- **Response Schema**: `WebSocket Frame / WebRTC SDP/ICE`
- **Database Side Effect**: Presence Heartbeat / Meeting State Update
- **External Side Effect**: WebRTC Signaling / Redis Channel Broadcast
- **Rate Limit**: `Connection Concurrency Bounded`
- **CSRF Requirement**: Ticket Authenticated
- **Sensitive Data**: Yes (Realtime Audio/Video Stream Signaling)
- **Audit Requirement**: Security Event Logged on Connect/Disconnect
- **Execution Trace**: `WS /consultations/ws/incoming-calls → [Ticket/HMAC Token Validation] → SignalingManager / LawyerCallChannel → Redis PubSub`

### 221. `GET /consultations/{consultation_id}`
- **Router**: `consultations_router`
- **Handler**: `app.api.v1.consultations.get_consultation`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `ConsultationResponse`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /consultations/{consultation_id} → [get_current_user, get_db] → ConsultationsService → DB / Engine`

### 222. `POST /consultations/{consultation_id}/accept`
- **Router**: `consultations_router`
- **Handler**: `app.api.v1.consultations.accept_consultation`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `ConsultationResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /consultations/{consultation_id}/accept → [get_current_user, get_db] → ConsultationsService → DB / Engine`

### 223. `POST /consultations/{consultation_id}/cancel`
- **Router**: `consultations_router`
- **Handler**: `app.api.v1.consultations.cancel_consultation`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `ConsultationResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /consultations/{consultation_id}/cancel → [get_current_user, get_db] → ConsultationsService → DB / Engine`

### 224. `POST /consultations/{consultation_id}/complete`
- **Router**: `consultations_router`
- **Handler**: `app.api.v1.consultations.complete_consultation`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `ConsultationResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /consultations/{consultation_id}/complete → [get_current_user, get_db] → ConsultationsService → DB / Engine`

### 225. `POST /consultations/{consultation_id}/confirm`
- **Router**: `consultations_router`
- **Handler**: `app.api.v1.consultations.confirm_consultation`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `ConsultationResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /consultations/{consultation_id}/confirm → [get_current_user, get_db] → ConsultationsService → DB / Engine`

### 226. `POST /consultations/{consultation_id}/create-case`
- **Router**: `consultations_router`
- **Handler**: `app.api.v1.consultations.create_case_from_consultation`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `CaseResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /consultations/{consultation_id}/create-case → [get_current_user, get_db] → ConsultationsService → DB / Engine`

### 227. `GET /consultations/{consultation_id}/documents`
- **Router**: `consultations_router`
- **Handler**: `app.api.v1.consultations.get_consultation_documents`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `list`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /consultations/{consultation_id}/documents → [get_current_user, get_db] → ConsultationsService → DB / Engine`

### 228. `POST /consultations/{consultation_id}/documents`
- **Router**: `consultations_router`
- **Handler**: `app.api.v1.consultations.upload_consultation_document`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `ConsultationDocumentResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Required
- **Execution Trace**: `POST /consultations/{consultation_id}/documents → [get_current_user, get_db] → ConsultationsService → DB / Engine`

### 229. `GET /consultations/{consultation_id}/documents/{document_id}/download`
- **Router**: `consultations_router`
- **Handler**: `app.api.v1.consultations.download_consultation_document`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `dict / Raw Response`
- **Database Side Effect**: Read Only
- **External Side Effect**: S3 / Stripe / LiveKit / LLM
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /consultations/{consultation_id}/documents/{document_id}/download → [get_current_user, get_db] → ConsultationsService → DB / Engine`

### 230. `POST /consultations/{consultation_id}/link-case`
- **Router**: `consultations_router`
- **Handler**: `app.api.v1.consultations.link_consultation_to_case`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `ConsultationResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /consultations/{consultation_id}/link-case → [get_current_user, get_db] → ConsultationsService → DB / Engine`

### 231. `GET /consultations/{consultation_id}/messages`
- **Router**: `consultations_router`
- **Handler**: `app.api.v1.consultations.get_messages`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `list`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /consultations/{consultation_id}/messages → [get_db, get_current_user] → ConsultationsService → DB / Engine`

### 232. `POST /consultations/{consultation_id}/messages`
- **Router**: `consultations_router`
- **Handler**: `app.api.v1.consultations.send_message`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `MessageResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /consultations/{consultation_id}/messages → [get_db, get_current_user] → ConsultationsService → DB / Engine`

### 233. `POST /consultations/{consultation_id}/no-show`
- **Router**: `consultations_router`
- **Handler**: `app.api.v1.consultations.mark_no_show`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `ConsultationResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /consultations/{consultation_id}/no-show → [get_current_user, get_db] → ConsultationsService → DB / Engine`

### 234. `GET /consultations/{consultation_id}/notes`
- **Router**: `consultations_router`
- **Handler**: `app.api.v1.consultations.get_consultation_notes`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `list`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /consultations/{consultation_id}/notes → [get_current_user, get_db] → ConsultationsService → DB / Engine`

### 235. `POST /consultations/{consultation_id}/notes`
- **Router**: `consultations_router`
- **Handler**: `app.api.v1.consultations.add_consultation_note`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `ConsultationNoteResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /consultations/{consultation_id}/notes → [get_current_user, get_db] → ConsultationsService → DB / Engine`

### 236. `POST /consultations/{consultation_id}/pay-test`
- **Router**: `consultations_router`
- **Handler**: `app.api.v1.consultations.process_test_payment`
- **Auth Required**: Yes
- **Role / Permission**: `Role: ['CLIENT', 'ADMIN']`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `ConsultationResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: S3 / Stripe / LiveKit / LLM
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /consultations/{consultation_id}/pay-test → [get_db, <app.api.deps.RequireRole object at 0x000001C1458D40B0>] → ConsultationsService → DB / Engine`

### 237. `GET /consultations/{consultation_id}/payments`
- **Router**: `consultations_router`
- **Handler**: `app.api.v1.consultations.get_consultation_payments`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `list`
- **Database Side Effect**: Read Only
- **External Side Effect**: S3 / Stripe / LiveKit / LLM
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /consultations/{consultation_id}/payments → [get_db, get_current_user] → ConsultationsService → DB / Engine`

### 238. `POST /consultations/{consultation_id}/payments`
- **Router**: `consultations_router`
- **Handler**: `app.api.v1.consultations.create_payment`
- **Auth Required**: Yes
- **Role / Permission**: `Role: ['CLIENT']`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `PaymentIntentResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: S3 / Stripe / LiveKit / LLM
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Required
- **Execution Trace**: `POST /consultations/{consultation_id}/payments → [get_db, <app.api.deps.RequireRole object at 0x000001C1458BB7D0>] → ConsultationsService → DB / Engine`

### 239. `GET /consultations/{consultation_id}/recordings`
- **Router**: `consultations_router`
- **Handler**: `app.api.v1.consultations.list_consultation_recordings`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `RecordingListResponse`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /consultations/{consultation_id}/recordings → [get_current_user, get_db] → ConsultationsService → DB / Engine`

### 240. `POST /consultations/{consultation_id}/reject`
- **Router**: `consultations_router`
- **Handler**: `app.api.v1.consultations.reject_consultation`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `ConsultationResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /consultations/{consultation_id}/reject → [get_current_user, get_db] → ConsultationsService → DB / Engine`

### 241. `POST /consultations/{consultation_id}/reschedule`
- **Router**: `consultations_router`
- **Handler**: `app.api.v1.consultations.reschedule_consultation`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `ConsultationResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /consultations/{consultation_id}/reschedule → [get_current_user, get_db] → ConsultationsService → DB / Engine`

### 242. `POST /consultations/{consultation_id}/schedule`
- **Router**: `consultations_router`
- **Handler**: `app.api.v1.consultations.schedule_consultation`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `ConsultationResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /consultations/{consultation_id}/schedule → [get_current_user, get_db] → ConsultationsService → DB / Engine`

### 243. `GET /consultations/{consultation_id}/video/access-status`
- **Router**: `consultations_router`
- **Handler**: `app.api.v1.consultations.get_video_meeting_access_status`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `VideoRoomAccessStatusResponse`
- **Database Side Effect**: Read Only
- **External Side Effect**: S3 / Stripe / LiveKit / LLM
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /consultations/{consultation_id}/video/access-status → [get_current_user, get_db] → ConsultationsService → DB / Engine`

### 244. `POST /consultations/{consultation_id}/video/end`
- **Router**: `consultations_router`
- **Handler**: `app.api.v1.consultations.end_video_meeting`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `VideoMeetingResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: S3 / Stripe / LiveKit / LLM
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /consultations/{consultation_id}/video/end → [get_current_user, get_db] → ConsultationsService → DB / Engine`

### 245. `GET /consultations/{consultation_id}/video/join`
- **Router**: `consultations_router`
- **Handler**: `app.api.v1.consultations.join_video_meeting`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `VideoJoinInfoResponse`
- **Database Side Effect**: Read Only
- **External Side Effect**: S3 / Stripe / LiveKit / LLM
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /consultations/{consultation_id}/video/join → [get_current_user, get_db] → ConsultationsService → DB / Engine`

### 246. `POST /consultations/{consultation_id}/video/reconnect`
- **Router**: `consultations_router`
- **Handler**: `app.api.v1.consultations.reconnect_video_meeting`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `VideoJoinInfoResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: S3 / Stripe / LiveKit / LLM
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /consultations/{consultation_id}/video/reconnect → [get_current_user, get_db] → ConsultationsService → DB / Engine`

### 247. `POST /consultations/{consultation_id}/video/recording/consent`
- **Router**: `consultations_router`
- **Handler**: `app.api.v1.consultations.grant_recording_consent`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `RecordingConsentResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: S3 / Stripe / LiveKit / LLM
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Required
- **Execution Trace**: `POST /consultations/{consultation_id}/video/recording/consent → [get_current_user, get_db] → ConsultationsService → DB / Engine`

### 248. `GET /consultations/{consultation_id}/video/recording/consent-status`
- **Router**: `consultations_router`
- **Handler**: `app.api.v1.consultations.get_recording_consent_status`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `ConsentStatusResponse`
- **Database Side Effect**: Read Only
- **External Side Effect**: S3 / Stripe / LiveKit / LLM
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /consultations/{consultation_id}/video/recording/consent-status → [get_current_user, get_db] → ConsultationsService → DB / Engine`

### 249. `POST /consultations/{consultation_id}/video/recording/start`
- **Router**: `consultations_router`
- **Handler**: `app.api.v1.consultations.start_recording`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `RecordingStartResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: S3 / Stripe / LiveKit / LLM
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Required
- **Execution Trace**: `POST /consultations/{consultation_id}/video/recording/start → [get_current_user, get_db] → ConsultationsService → DB / Engine`

### 250. `POST /consultations/{consultation_id}/video/recording/stop`
- **Router**: `consultations_router`
- **Handler**: `app.api.v1.consultations.stop_recording`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `RecordingStopResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: S3 / Stripe / LiveKit / LLM
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Required
- **Execution Trace**: `POST /consultations/{consultation_id}/video/recording/stop → [get_current_user, get_db] → ConsultationsService → DB / Engine`

### 251. `POST /consultations/{consultation_id}/video/recording/upload`
- **Router**: `consultations_router`
- **Handler**: `app.api.v1.consultations.upload_recording_file`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `RecordingResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: S3 / Stripe / LiveKit / LLM
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Required
- **Execution Trace**: `POST /consultations/{consultation_id}/video/recording/upload → [get_current_user, get_db] → ConsultationsService → DB / Engine`

### 252. `POST /consultations/{consultation_id}/video/start`
- **Router**: `consultations_router`
- **Handler**: `app.api.v1.consultations.start_video_meeting`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `VideoMeetingResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: S3 / Stripe / LiveKit / LLM
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /consultations/{consultation_id}/video/start → [get_current_user, get_db] → ConsultationsService → DB / Engine`

### 253. `WS /consultations/{consultation_id}/video/ws`
- **Router**: `video_signaling_router`
- **Handler**: `app.api.v1.video_signaling.video_signaling_websocket`
- **Auth Required**: Yes
- **Role / Permission**: `Participant / Verified Lawyer`
- **Object Ownership Check**: Enforced (Room Token / Session Binding)
- **Request Schema**: `WebSocket Frame / JSON Signaling`
- **Response Schema**: `WebSocket Frame / WebRTC SDP/ICE`
- **Database Side Effect**: Presence Heartbeat / Meeting State Update
- **External Side Effect**: WebRTC Signaling / Redis Channel Broadcast
- **Rate Limit**: `Connection Concurrency Bounded`
- **CSRF Requirement**: Ticket Authenticated
- **Sensitive Data**: Yes (Realtime Audio/Video Stream Signaling)
- **Audit Requirement**: Security Event Logged on Connect/Disconnect
- **Execution Trace**: `WS /consultations/{consultation_id}/video/ws → [Ticket/HMAC Token Validation] → SignalingManager / LawyerCallChannel → Redis PubSub`

### 254. `GET /court-cases`
- **Router**: `court_cases_router`
- **Handler**: `app.api.v1.court_cases.search_court_cases`
- **Auth Required**: No
- **Role / Permission**: `Optional User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `list`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /court-cases → [get_db, get_optional_current_user] → Court_casesService → DB / Engine`

### 255. `GET /court-cases/{id_or_cnr}`
- **Router**: `court_cases_router`
- **Handler**: `app.api.v1.court_cases.get_court_case_detail`
- **Auth Required**: No
- **Role / Permission**: `Optional User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `CourtCaseDetail`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /court-cases/{id_or_cnr} → [get_db, get_optional_current_user] → Court_casesService → DB / Engine`

### 256. `DELETE /court-cases/{id_or_cnr}/follow`
- **Router**: `court_cases_router`
- **Handler**: `app.api.v1.court_cases.unfollow_court_case`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `CourtCaseFollowResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `DELETE /court-cases/{id_or_cnr}/follow → [get_current_user, get_db] → Court_casesService → DB / Engine`

### 257. `POST /court-cases/{id_or_cnr}/follow`
- **Router**: `court_cases_router`
- **Handler**: `app.api.v1.court_cases.follow_court_case`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `CourtCaseFollowResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /court-cases/{id_or_cnr}/follow → [get_current_user, get_db] → Court_casesService → DB / Engine`

### 258. `POST /court-cases/{id_or_cnr}/link-matter`
- **Router**: `court_cases_router`
- **Handler**: `app.api.v1.court_cases.link_matter`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `CourtCaseLinkMatterResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /court-cases/{id_or_cnr}/link-matter → [get_current_user, get_db] → Court_casesService → DB / Engine`

### 259. `POST /court-cases/{id_or_cnr}/sync`
- **Router**: `court_cases_router`
- **Handler**: `app.api.v1.court_cases.sync_court_case`
- **Auth Required**: No
- **Role / Permission**: `Optional User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `CourtCaseSyncResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /court-cases/{id_or_cnr}/sync → [get_db, get_optional_current_user] → Court_casesService → DB / Engine`

### 260. `POST /data-quality/reconcile`
- **Router**: `data_quality_router`
- **Handler**: `app.api.v1.data_quality.trigger_reconciliation`
- **Auth Required**: Yes
- **Role / Permission**: `Operator: None`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `dict`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /data-quality/reconcile → [<app.api.deps.RequireOperatorPermission object at 0x000001C145949A00>, get_db] → Data_qualityService → DB / Engine`

### 261. `GET /data-quality/runs`
- **Router**: `data_quality_router`
- **Handler**: `app.api.v1.data_quality.list_reconciliation_runs`
- **Auth Required**: Yes
- **Role / Permission**: `Operator: None`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `list`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /data-quality/runs → [<app.api.deps.RequireOperatorPermission object at 0x000001C14594A270>, get_db] → Data_qualityService → DB / Engine`

### 262. `GET /documents/shared-with-me`
- **Router**: `documents_router`
- **Handler**: `app.api.v1.documents.get_documents_shared_with_me`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `list`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /documents/shared-with-me → [get_current_user, get_db] → DocumentsService → DB / Engine`

### 263. `DELETE /documents/{document_id}`
- **Router**: `documents_router`
- **Handler**: `app.api.v1.documents.delete_document`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `dict / Raw Response`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Required
- **Execution Trace**: `DELETE /documents/{document_id} → [get_current_user, get_db] → DocumentsService → DB / Engine`

### 264. `GET /documents/{document_id}`
- **Router**: `documents_router`
- **Handler**: `app.api.v1.documents.get_document`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `DocumentResponse`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /documents/{document_id} → [get_current_user, get_db] → DocumentsService → DB / Engine`

### 265. `PATCH /documents/{document_id}`
- **Router**: `documents_router`
- **Handler**: `app.api.v1.documents.update_document`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `DocumentResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Required
- **Execution Trace**: `PATCH /documents/{document_id} → [get_current_user, get_db] → DocumentsService → DB / Engine`

### 266. `GET /documents/{document_id}/chunks`
- **Router**: `documents_router`
- **Handler**: `app.api.v1.documents.get_document_chunks`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `PaginatedResponse[DocumentChunkResponse]`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /documents/{document_id}/chunks → [get_current_user, get_db] → DocumentsService → DB / Engine`

### 267. `POST /documents/{document_id}/complete`
- **Router**: `documents_router`
- **Handler**: `app.api.v1.documents.complete_document_upload`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `DocumentResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Required
- **Execution Trace**: `POST /documents/{document_id}/complete → [get_current_user, get_db] → DocumentsService → DB / Engine`

### 268. `GET /documents/{document_id}/download`
- **Router**: `documents_router`
- **Handler**: `app.api.v1.documents.get_document_download_url`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `DownloadDocumentResponse`
- **Database Side Effect**: Read Only
- **External Side Effect**: S3 / Stripe / LiveKit / LLM
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /documents/{document_id}/download → [get_current_user, get_db] → DocumentsService → DB / Engine`

### 269. `GET /documents/{document_id}/pages`
- **Router**: `documents_router`
- **Handler**: `app.api.v1.documents.get_document_pages`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `PaginatedResponse[DocumentPageResponse]`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /documents/{document_id}/pages → [get_current_user, get_db] → DocumentsService → DB / Engine`

### 270. `POST /documents/{document_id}/process`
- **Router**: `documents_router`
- **Handler**: `app.api.v1.documents.trigger_document_processing`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `DocumentProcessingStatusResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Required
- **Execution Trace**: `POST /documents/{document_id}/process → [get_current_user, get_db] → DocumentsService → DB / Engine`

### 271. `GET /documents/{document_id}/processing-status`
- **Router**: `documents_router`
- **Handler**: `app.api.v1.documents.get_document_processing_status`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `DocumentProcessingStatusResponse`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /documents/{document_id}/processing-status → [get_current_user, get_db] → DocumentsService → DB / Engine`

### 272. `POST /documents/{document_id}/scan`
- **Router**: `documents_router`
- **Handler**: `app.api.v1.documents.simulate_malware_scan`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `dict / Raw Response`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Required
- **Execution Trace**: `POST /documents/{document_id}/scan → [get_current_user, get_db] → DocumentsService → DB / Engine`

### 273. `GET /feed/what-changed`
- **Router**: `change_feed_router`
- **Handler**: `app.api.v1.change_feed.get_what_changed_since_last_visit`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `dict`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /feed/what-changed → [get_current_user, get_db] → Change_feedService → DB / Engine`

### 274. `POST /feed/what-changed/acknowledge`
- **Router**: `change_feed_router`
- **Handler**: `app.api.v1.change_feed.acknowledge_what_changed`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `dict`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /feed/what-changed/acknowledge → [get_current_user, get_db] → Change_feedService → DB / Engine`

### 275. `GET /feedback`
- **Router**: `feedback_router`
- **Handler**: `app.api.v1.feedback.list_pilot_feedback`
- **Auth Required**: Yes
- **Role / Permission**: `Role: ['ADMIN']`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `list`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /feedback → [<app.api.deps.RequireRole object at 0x000001C145B84B00>, get_db] → FeedbackService → DB / Engine`

### 276. `POST /feedback`
- **Router**: `feedback_router`
- **Handler**: `app.api.v1.feedback.submit_pilot_feedback`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `PilotFeedbackResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /feedback → [get_current_user, get_db] → FeedbackService → DB / Engine`

### 277. `PATCH /feedback/{feedback_id}`
- **Router**: `feedback_router`
- **Handler**: `app.api.v1.feedback.update_pilot_feedback`
- **Auth Required**: Yes
- **Role / Permission**: `Role: ['ADMIN']`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `PilotFeedbackResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `PATCH /feedback/{feedback_id} → [<app.api.deps.RequireRole object at 0x000001C145B851C0>, get_db] → FeedbackService → DB / Engine`

### 278. `GET /health`
- **Router**: `health_router`
- **Handler**: `app.api.v1.health.liveness_check`
- **Auth Required**: No
- **Role / Permission**: `None (Public)`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `dict / Raw Response`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /health → [Direct] → HealthService → DB / Engine`

### 279. `GET /health/details`
- **Router**: `health_router`
- **Handler**: `app.api.v1.health.dependency_health_check`
- **Auth Required**: No
- **Role / Permission**: `None (Public)`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `dict / Raw Response`
- **Database Side Effect**: Read Only
- **External Side Effect**: S3 / Stripe / LiveKit / LLM
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /health/details → [get_db] → HealthService → DB / Engine`

### 280. `GET /health/live`
- **Router**: `health_router`
- **Handler**: `app.api.v1.health.liveness_check`
- **Auth Required**: No
- **Role / Permission**: `None (Public)`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `dict / Raw Response`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /health/live → [Direct] → HealthService → DB / Engine`

### 281. `GET /health/ready`
- **Router**: `health_router`
- **Handler**: `app.api.v1.health.readiness_check`
- **Auth Required**: No
- **Role / Permission**: `None (Public)`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `dict / Raw Response`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /health/ready → [get_db] → HealthService → DB / Engine`

### 282. `GET /incidents`
- **Router**: `incidents_router`
- **Handler**: `app.api.v1.incidents.list_incidents`
- **Auth Required**: Yes
- **Role / Permission**: `Operator: None`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `list`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /incidents → [<app.api.deps.RequireOperatorPermission object at 0x000001C145BB3440>, get_db] → IncidentsService → DB / Engine`

### 283. `POST /incidents`
- **Router**: `incidents_router`
- **Handler**: `app.api.v1.incidents.create_incident`
- **Auth Required**: Yes
- **Role / Permission**: `Operator: None`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `IncidentResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /incidents → [<app.api.deps.RequireOperatorPermission object at 0x000001C145BD8380>, get_db] → IncidentsService → DB / Engine`

### 284. `GET /incidents/{incident_id}`
- **Router**: `incidents_router`
- **Handler**: `app.api.v1.incidents.get_incident`
- **Auth Required**: Yes
- **Role / Permission**: `Operator: None`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `IncidentResponse`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /incidents/{incident_id} → [<app.api.deps.RequireOperatorPermission object at 0x000001C145BD8AD0>, get_db] → IncidentsService → DB / Engine`

### 285. `POST /incidents/{incident_id}/notes`
- **Router**: `incidents_router`
- **Handler**: `app.api.v1.incidents.add_incident_note`
- **Auth Required**: Yes
- **Role / Permission**: `Operator: None`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `IncidentTimelineResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /incidents/{incident_id}/notes → [<app.api.deps.RequireOperatorPermission object at 0x000001C145BDA0C0>, get_db] → IncidentsService → DB / Engine`

### 286. `POST /incidents/{incident_id}/transition`
- **Router**: `incidents_router`
- **Handler**: `app.api.v1.incidents.transition_incident_status`
- **Auth Required**: Yes
- **Role / Permission**: `Operator: None`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `IncidentResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /incidents/{incident_id}/transition → [<app.api.deps.RequireOperatorPermission object at 0x000001C145BD9490>, get_db] → IncidentsService → DB / Engine`

### 287. `GET /launch-gates/evaluation`
- **Router**: `launch_gates_router`
- **Handler**: `app.api.v1.launch_gates.get_launch_gate_evaluation`
- **Auth Required**: No
- **Role / Permission**: `None (Public)`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `dict`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /launch-gates/evaluation → [get_current_admin_user, get_db] → Launch_gatesService → DB / Engine`

### 288. `GET /lawyers`
- **Router**: `lawyers_router`
- **Handler**: `app.api.v1.lawyers.search_lawyers`
- **Auth Required**: No
- **Role / Permission**: `Optional User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `PaginatedResponse[LawyerPublicResponse]`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /lawyers → [get_optional_current_user, get_db] → LawyersService → DB / Engine`

### 289. `GET /lawyers/dashboard`
- **Router**: `lawyers_router`
- **Handler**: `app.api.v1.lawyers.get_lawyer_operational_dashboard`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `LawyerDashboardResponse`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /lawyers/dashboard → [get_current_user, get_db] → LawyersService → DB / Engine`

### 290. `POST /lawyers/heartbeat`
- **Router**: `lawyers_router`
- **Handler**: `app.api.v1.lawyers.record_lawyer_heartbeat`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `dict / Raw Response`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /lawyers/heartbeat → [get_current_user, get_db] → LawyersService → DB / Engine`

### 291. `GET /lawyers/{lawyer_id}/availability`
- **Router**: `lawyers_router`
- **Handler**: `app.api.v1.lawyers.get_public_lawyer_availability`
- **Auth Required**: No
- **Role / Permission**: `Optional User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `list`
- **Database Side Effect**: Read Only
- **External Side Effect**: S3 / Stripe / LiveKit / LLM
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /lawyers/{lawyer_id}/availability → [get_optional_current_user, get_db] → LawyersService → DB / Engine`

### 292. `GET /lawyers/{lawyer_id}/presence`
- **Router**: `lawyers_router`
- **Handler**: `app.api.v1.lawyers.get_lawyer_presence`
- **Auth Required**: No
- **Role / Permission**: `Optional User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `LawyerPresenceStatusResponse`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /lawyers/{lawyer_id}/presence → [get_optional_current_user, get_db] → LawyersService → DB / Engine`

### 293. `GET /lawyers/{lawyer_id}/slots`
- **Router**: `lawyers_router`
- **Handler**: `app.api.v1.lawyers.get_lawyer_slots`
- **Auth Required**: No
- **Role / Permission**: `Optional User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `list`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /lawyers/{lawyer_id}/slots → [get_optional_current_user, get_db] → LawyersService → DB / Engine`

### 294. `GET /lawyers/{user_id}`
- **Router**: `lawyers_router`
- **Handler**: `app.api.v1.lawyers.get_lawyer_profile`
- **Auth Required**: No
- **Role / Permission**: `Optional User`
- **Object Ownership Check**: Public Identifier Access
- **Request Schema**: `None`
- **Response Schema**: `LawyerPublicResponse`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /lawyers/{user_id} → [get_optional_current_user, get_db] → LawyersService → DB / Engine`

### 295. `POST /legal-authorities/ingest`
- **Router**: `legal_authority_router`
- **Handler**: `app.api.v1.legal_authority.ingest_legal_authority`
- **Auth Required**: Yes
- **Role / Permission**: `Role: ['ADMIN']`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `LegalAuthorityResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Required
- **Execution Trace**: `POST /legal-authorities/ingest → [get_db, <app.api.deps.RequireRole object at 0x000001C145C4BB90>] → Legal_authorityService → DB / Engine`

### 296. `POST /legal-authorities/search`
- **Router**: `legal_authority_router`
- **Handler**: `app.api.v1.legal_authority.search_legal_authorities`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `LegalAuthoritySearchResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Required
- **Execution Trace**: `POST /legal-authorities/search → [get_db, get_current_user] → Legal_authorityService → DB / Engine`

### 297. `GET /legal-authorities/{canonical_id}`
- **Router**: `legal_authority_router`
- **Handler**: `app.api.v1.legal_authority.get_legal_authority`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `LegalAuthorityResponse`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /legal-authorities/{canonical_id} → [get_db, get_current_user] → Legal_authorityService → DB / Engine`

### 298. `POST /legal-documents/accept`
- **Router**: `legal_documents_router`
- **Handler**: `app.api.v1.legal_documents.accept_document_terms`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `dict`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Required
- **Execution Trace**: `POST /legal-documents/accept → [get_current_user, get_db] → Legal_documentsService → DB / Engine`

### 299. `GET /legal-documents/consents/my`
- **Router**: `legal_documents_router`
- **Handler**: `app.api.v1.legal_documents.list_my_consents`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `list`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /legal-documents/consents/my → [get_current_user, get_db] → Legal_documentsService → DB / Engine`

### 300. `POST /legal-documents/publish`
- **Router**: `legal_documents_router`
- **Handler**: `app.api.v1.legal_documents.publish_document_version`
- **Auth Required**: Yes
- **Role / Permission**: `Operator: None`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `dict`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Required
- **Execution Trace**: `POST /legal-documents/publish → [<app.api.deps.RequireOperatorPermission object at 0x000001C145C6DE50>, get_db] → Legal_documentsService → DB / Engine`

### 301. `GET /legal-documents/{document_type}/current`
- **Router**: `legal_documents_router`
- **Handler**: `app.api.v1.legal_documents.get_current_document_version`
- **Auth Required**: No
- **Role / Permission**: `None (Public)`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `dict`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /legal-documents/{document_type}/current → [get_db] → Legal_documentsService → DB / Engine`

### 302. `GET /liveness`
- **Router**: `root_health_router`
- **Handler**: `app.api.v1.health.liveness_check`
- **Auth Required**: No
- **Role / Permission**: `None (Public)`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `dict / Raw Response`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /liveness → [Direct] → Root_healthService → DB / Engine`

### 303. `GET /localization/locales`
- **Router**: `localization_router`
- **Handler**: `app.api.v1.localization.list_supported_locales`
- **Auth Required**: No
- **Role / Permission**: `None (Public)`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `dict`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /localization/locales → [get_db] → LocalizationService → DB / Engine`

### 304. `GET /localization/messages`
- **Router**: `localization_router`
- **Handler**: `app.api.v1.localization.get_localized_messages`
- **Auth Required**: No
- **Role / Permission**: `None (Public)`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `dict`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /localization/messages → [get_db] → LocalizationService → DB / Engine`

### 305. `POST /localization/messages`
- **Router**: `localization_router`
- **Handler**: `app.api.v1.localization.register_translation_message`
- **Auth Required**: Yes
- **Role / Permission**: `Operator: None`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `TranslationResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /localization/messages → [<app.api.deps.RequireOperatorPermission object at 0x000001C145CA54C0>, get_db] → LocalizationService → DB / Engine`

### 306. `POST /localization/messages/{message_id}/review`
- **Router**: `localization_router`
- **Handler**: `app.api.v1.localization.review_translation_message`
- **Auth Required**: Yes
- **Role / Permission**: `Operator: None`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `TranslationResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /localization/messages/{message_id}/review → [<app.api.deps.RequireOperatorPermission object at 0x000001C145CA5E20>, get_db] → LocalizationService → DB / Engine`

### 307. `GET /messages/threads`
- **Router**: `messages_router`
- **Handler**: `app.api.v1.messages.list_message_threads`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `list`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /messages/threads → [get_current_user, get_db] → MessagesService → DB / Engine`

### 308. `GET /messages/threads/{partner_id}`
- **Router**: `messages_router`
- **Handler**: `app.api.v1.messages.get_thread_messages`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `dict`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /messages/threads/{partner_id} → [get_current_user, get_db] → MessagesService → DB / Engine`

### 309. `POST /messages/threads/{partner_id}`
- **Router**: `messages_router`
- **Handler**: `app.api.v1.messages.send_direct_message`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `dict`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /messages/threads/{partner_id} → [get_current_user, get_db] → MessagesService → DB / Engine`

### 310. `GET /mock-storage/download`
- **Router**: `app_direct`
- **Handler**: `app.main.mock_storage_download`
- **Auth Required**: Gated (Dev Only / Blocked in Prod)
- **Role / Permission**: `Dev Environment Only (404 in Prod/Staging)`
- **Object Ownership Check**: Path Traversal Sanitized
- **Request Schema**: `Query params`
- **Response Schema**: `File Stream`
- **Database Side Effect**: None
- **External Side Effect**: Local Emulated Storage Provider
- **Rate Limit**: `Default`
- **CSRF Requirement**: N/A
- **Sensitive Data**: Mock Storage Emulation Only
- **Audit Requirement**: Diagnostic
- **Execution Trace**: `GET /mock-storage/download → [Environment Guard] → LocalMockStorageProvider`

### 311. `PUT /mock-storage/upload`
- **Router**: `app_direct`
- **Handler**: `app.main.mock_storage_upload`
- **Auth Required**: Gated (Dev Only / Blocked in Prod)
- **Role / Permission**: `Dev Environment Only (404 in Prod/Staging)`
- **Object Ownership Check**: Path Traversal Sanitized
- **Request Schema**: `Binary Body`
- **Response Schema**: `200 OK`
- **Database Side Effect**: None
- **External Side Effect**: Local Emulated Storage Provider
- **Rate Limit**: `Default`
- **CSRF Requirement**: N/A
- **Sensitive Data**: Mock Storage Emulation Only
- **Audit Requirement**: Diagnostic
- **Execution Trace**: `PUT /mock-storage/upload → [Environment Guard] → LocalMockStorageProvider`

### 312. `GET /notifications`
- **Router**: `notifications_router`
- **Handler**: `app.api.v1.notifications.list_notifications`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `PaginatedResponse[NotificationResponse]`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /notifications → [get_current_user, get_db] → NotificationsService → DB / Engine`

### 313. `POST /notifications/bulk-delete`
- **Router**: `notifications_router`
- **Handler**: `app.api.v1.notifications.bulk_delete_notifications`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `NotificationBulkDeleteResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /notifications/bulk-delete → [get_current_user, get_db] → NotificationsService → DB / Engine`

### 314. `POST /notifications/bulk-read`
- **Router**: `notifications_router`
- **Handler**: `app.api.v1.notifications.bulk_mark_as_read`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `NotificationReadAllResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /notifications/bulk-read → [get_current_user, get_db] → NotificationsService → DB / Engine`

### 315. `GET /notifications/preferences`
- **Router**: `notifications_router`
- **Handler**: `app.api.v1.notifications.get_notification_preferences`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `NotificationPreferenceResponse`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /notifications/preferences → [get_current_user, get_db] → NotificationsService → DB / Engine`

### 316. `PATCH /notifications/preferences`
- **Router**: `notifications_router`
- **Handler**: `app.api.v1.notifications.update_notification_preferences`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `NotificationPreferenceResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `PATCH /notifications/preferences → [get_current_user, get_db] → NotificationsService → DB / Engine`

### 317. `POST /notifications/read-all`
- **Router**: `notifications_router`
- **Handler**: `app.api.v1.notifications.mark_all_as_read`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `NotificationReadAllResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /notifications/read-all → [get_current_user, get_db] → NotificationsService → DB / Engine`

### 318. `GET /notifications/unread-count`
- **Router**: `notifications_router`
- **Handler**: `app.api.v1.notifications.get_unread_count`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `UnreadCountResponse`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /notifications/unread-count → [get_current_user, get_db] → NotificationsService → DB / Engine`

### 319. `DELETE /notifications/{notification_id}`
- **Router**: `notifications_router`
- **Handler**: `app.api.v1.notifications.delete_notification`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `dict / Raw Response`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `DELETE /notifications/{notification_id} → [get_current_user, get_db] → NotificationsService → DB / Engine`

### 320. `POST /notifications/{notification_id}/read`
- **Router**: `notifications_router`
- **Handler**: `app.api.v1.notifications.mark_as_read`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `NotificationResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /notifications/{notification_id}/read → [get_current_user, get_db] → NotificationsService → DB / Engine`

### 321. `POST /notifications/{notification_id}/unread`
- **Router**: `notifications_router`
- **Handler**: `app.api.v1.notifications.mark_as_unread`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `NotificationResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /notifications/{notification_id}/unread → [get_current_user, get_db] → NotificationsService → DB / Engine`

### 322. `GET /payments/{payment_id}`
- **Router**: `payments_router`
- **Handler**: `app.api.v1.payments.get_payment`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `PaymentResponse`
- **Database Side Effect**: Read Only
- **External Side Effect**: S3 / Stripe / LiveKit / LLM
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /payments/{payment_id} → [get_db, get_current_user] → PaymentsService → DB / Engine`

### 323. `GET /pilot/advocate-supply-roster`
- **Router**: `pilot_router`
- **Handler**: `app.api.v1.pilot.get_advocate_supply_roster`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `dict`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /pilot/advocate-supply-roster → [get_db, get_current_user] → PilotService → DB / Engine`

### 324. `GET /pilot/alerts`
- **Router**: `pilot_router`
- **Handler**: `app.api.v1.pilot.get_active_alerts`
- **Auth Required**: Yes
- **Role / Permission**: `Role: ['ADMIN']`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `list`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /pilot/alerts → [<app.api.deps.RequireRole object at 0x000001C145D032C0>, get_db] → PilotService → DB / Engine`

### 325. `GET /pilot/allowlist`
- **Router**: `pilot_router`
- **Handler**: `app.api.v1.pilot.list_allowlist`
- **Auth Required**: Yes
- **Role / Permission**: `Operator: None`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `list`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /pilot/allowlist → [<app.api.deps.RequireOperatorPermission object at 0x000001C145D01FD0>, get_db] → PilotService → DB / Engine`

### 326. `POST /pilot/allowlist`
- **Router**: `pilot_router`
- **Handler**: `app.api.v1.pilot.add_allowlist_entry`
- **Auth Required**: Yes
- **Role / Permission**: `Operator: None`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `AllowlistResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /pilot/allowlist → [<app.api.deps.RequireOperatorPermission object at 0x000001C145D00C20>, get_db] → PilotService → DB / Engine`

### 327. `DELETE /pilot/allowlist/{entry_id}`
- **Router**: `pilot_router`
- **Handler**: `app.api.v1.pilot.revoke_allowlist_entry`
- **Auth Required**: Yes
- **Role / Permission**: `Operator: None`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `dict / Raw Response`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `DELETE /pilot/allowlist/{entry_id} → [<app.api.deps.RequireOperatorPermission object at 0x000001C145D01520>, get_db] → PilotService → DB / Engine`

### 328. `POST /pilot/cohort-2/advance-stage`
- **Router**: `pilot_router`
- **Handler**: `app.api.v1.pilot.advance_cohort_2_stage`
- **Auth Required**: Yes
- **Role / Permission**: `Operator: None`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `dict`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /pilot/cohort-2/advance-stage → [get_db, <app.api.deps.RequireOperatorPermission object at 0x000001C145D452E0>] → PilotService → DB / Engine`

### 329. `GET /pilot/cohort-2/status`
- **Router**: `pilot_router`
- **Handler**: `app.api.v1.pilot.get_cohort_2_status`
- **Auth Required**: Yes
- **Role / Permission**: `Operator: None`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `dict`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /pilot/cohort-2/status → [get_db, <app.api.deps.RequireOperatorPermission object at 0x000001C145D44A40>] → PilotService → DB / Engine`

### 330. `GET /pilot/conversion-funnel`
- **Router**: `pilot_router`
- **Handler**: `app.api.v1.pilot.get_commercial_conversion_funnel`
- **Auth Required**: Yes
- **Role / Permission**: `Role: ['ADMIN']`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `dict`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /pilot/conversion-funnel → [<app.api.deps.RequireRole object at 0x000001C145D21490>, get_db] → PilotService → DB / Engine`

### 331. `GET /pilot/costs`
- **Router**: `pilot_router`
- **Handler**: `app.api.v1.pilot.get_cost_report`
- **Auth Required**: Yes
- **Role / Permission**: `Role: ['ADMIN']`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `dict`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /pilot/costs → [<app.api.deps.RequireRole object at 0x000001C145D03B60>] → PilotService → DB / Engine`

### 332. `GET /pilot/court-data-quality`
- **Router**: `pilot_router`
- **Handler**: `app.api.v1.pilot.get_court_data_quality_metrics`
- **Auth Required**: Yes
- **Role / Permission**: `Role: ['ADMIN']`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `dict`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /pilot/court-data-quality → [<app.api.deps.RequireRole object at 0x000001C145D22F00>, get_db] → PilotService → DB / Engine`

### 333. `GET /pilot/experiments`
- **Router**: `experiments_router`
- **Handler**: `app.api.v1.experiments.list_experiments`
- **Auth Required**: Yes
- **Role / Permission**: `Operator: None`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `list`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /pilot/experiments → [<app.api.deps.RequireOperatorPermission object at 0x000001C145B4CB60>, get_db] → ExperimentsService → DB / Engine`

### 334. `POST /pilot/experiments`
- **Router**: `experiments_router`
- **Handler**: `app.api.v1.experiments.create_experiment`
- **Auth Required**: Yes
- **Role / Permission**: `Operator: None`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `ExperimentResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /pilot/experiments → [<app.api.deps.RequireOperatorPermission object at 0x000001C145B4D1C0>, get_db] → ExperimentsService → DB / Engine`

### 335. `GET /pilot/experiments/{experiment_id}`
- **Router**: `experiments_router`
- **Handler**: `app.api.v1.experiments.get_experiment`
- **Auth Required**: Yes
- **Role / Permission**: `Operator: None`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `ExperimentResponse`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /pilot/experiments/{experiment_id} → [<app.api.deps.RequireOperatorPermission object at 0x000001C145B4DFD0>, get_db] → ExperimentsService → DB / Engine`

### 336. `POST /pilot/experiments/{experiment_id}/transition`
- **Router**: `experiments_router`
- **Handler**: `app.api.v1.experiments.transition_experiment_status`
- **Auth Required**: Yes
- **Role / Permission**: `Operator: None`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `ExperimentResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /pilot/experiments/{experiment_id}/transition → [<app.api.deps.RequireOperatorPermission object at 0x000001C145B4E990>, get_db] → ExperimentsService → DB / Engine`

### 337. `POST /pilot/feedback/structured`
- **Router**: `pilot_router`
- **Handler**: `app.api.v1.pilot.submit_structured_feedback`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `dict`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /pilot/feedback/structured → [get_current_user, get_db] → PilotService → DB / Engine`

### 338. `GET /pilot/funnel`
- **Router**: `pilot_router`
- **Handler**: `app.api.v1.pilot.get_funnel_report`
- **Auth Required**: Yes
- **Role / Permission**: `Role: ['ADMIN']`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `dict`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /pilot/funnel → [<app.api.deps.RequireRole object at 0x000001C145D20410>, get_db] → PilotService → DB / Engine`

### 339. `GET /pilot/marketplace-balance`
- **Router**: `pilot_router`
- **Handler**: `app.api.v1.pilot.get_marketplace_balance`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `dict`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /pilot/marketplace-balance → [get_db, get_current_user] → PilotService → DB / Engine`

### 340. `GET /pilot/marketplace-quality`
- **Router**: `pilot_router`
- **Handler**: `app.api.v1.pilot.get_marketplace_quality_indicators`
- **Auth Required**: Yes
- **Role / Permission**: `Role: ['ADMIN']`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `dict`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /pilot/marketplace-quality → [<app.api.deps.RequireRole object at 0x000001C145D226C0>, get_db] → PilotService → DB / Engine`

### 341. `GET /pilot/operations-overview`
- **Router**: `pilot_router`
- **Handler**: `app.api.v1.pilot.get_operations_overview`
- **Auth Required**: Yes
- **Role / Permission**: `Role: ['ADMIN']`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `dict`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /pilot/operations-overview → [<app.api.deps.RequireRole object at 0x000001C145D44050>, get_db] → PilotService → DB / Engine`

### 342. `GET /pilot/retention-metrics`
- **Router**: `pilot_router`
- **Handler**: `app.api.v1.pilot.get_pilot_retention_metrics`
- **Auth Required**: Yes
- **Role / Permission**: `Role: ['ADMIN']`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `dict`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /pilot/retention-metrics → [<app.api.deps.RequireRole object at 0x000001C145D21E50>, get_db] → PilotService → DB / Engine`

### 343. `GET /pilot/slos`
- **Router**: `pilot_router`
- **Handler**: `app.api.v1.pilot.get_slo_report`
- **Auth Required**: Yes
- **Role / Permission**: `Role: ['ADMIN']`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `dict`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /pilot/slos → [<app.api.deps.RequireRole object at 0x000001C145D02900>] → PilotService → DB / Engine`

### 344. `GET /pilot/status`
- **Router**: `pilot_router`
- **Handler**: `app.api.v1.pilot.get_pilot_status`
- **Auth Required**: Yes
- **Role / Permission**: `Operator: None`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `dict`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /pilot/status → [<app.api.deps.RequireOperatorPermission object at 0x000001C145D000E0>, get_db] → PilotService → DB / Engine`

### 345. `GET /pilot/support-analytics`
- **Router**: `pilot_router`
- **Handler**: `app.api.v1.pilot.get_pilot_support_analytics`
- **Auth Required**: Yes
- **Role / Permission**: `Role: ['ADMIN']`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `dict`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /pilot/support-analytics → [<app.api.deps.RequireRole object at 0x000001C145D23770>, get_db] → PilotService → DB / Engine`

### 346. `POST /pilot/telemetry/event`
- **Router**: `pilot_router`
- **Handler**: `app.api.v1.pilot.record_pilot_telemetry_event`
- **Auth Required**: No
- **Role / Permission**: `Optional User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `dict`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /pilot/telemetry/event → [get_optional_current_user, get_db] → PilotService → DB / Engine`

### 347. `PATCH /profiles/client`
- **Router**: `profiles_router`
- **Handler**: `app.api.v1.profiles.update_client_profile`
- **Auth Required**: Yes
- **Role / Permission**: `Role: ['CLIENT']`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `ClientProfileResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `PATCH /profiles/client → [<app.api.deps.RequireRole object at 0x000001C145D47AA0>, get_db] → ProfilesService → DB / Engine`

### 348. `PATCH /profiles/lawyer`
- **Router**: `profiles_router`
- **Handler**: `app.api.v1.profiles.update_lawyer_profile`
- **Auth Required**: Yes
- **Role / Permission**: `Role: ['LAWYER']`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `LawyerProfileResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `PATCH /profiles/lawyer → [<app.api.deps.RequireRole object at 0x000001C145D583E0>, get_db] → ProfilesService → DB / Engine`

### 349. `GET /profiles/lawyer/availability`
- **Router**: `profiles_router`
- **Handler**: `app.api.v1.profiles.get_lawyer_availabilities`
- **Auth Required**: Yes
- **Role / Permission**: `Role: ['LAWYER']`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `list`
- **Database Side Effect**: Read Only
- **External Side Effect**: S3 / Stripe / LiveKit / LLM
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /profiles/lawyer/availability → [<app.api.deps.RequireRole object at 0x000001C145D595E0>, get_db] → ProfilesService → DB / Engine`

### 350. `POST /profiles/lawyer/availability`
- **Router**: `profiles_router`
- **Handler**: `app.api.v1.profiles.create_lawyer_availability`
- **Auth Required**: Yes
- **Role / Permission**: `Role: ['LAWYER']`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `LawyerAvailabilityResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: S3 / Stripe / LiveKit / LLM
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /profiles/lawyer/availability → [<app.api.deps.RequireRole object at 0x000001C145D59E50>, get_db] → ProfilesService → DB / Engine`

### 351. `DELETE /profiles/lawyer/availability/{availability_id}`
- **Router**: `profiles_router`
- **Handler**: `app.api.v1.profiles.delete_lawyer_availability`
- **Auth Required**: Yes
- **Role / Permission**: `Role: ['LAWYER']`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `dict / Raw Response`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: S3 / Stripe / LiveKit / LLM
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `DELETE /profiles/lawyer/availability/{availability_id} → [<app.api.deps.RequireRole object at 0x000001C145D5B260>, get_db] → ProfilesService → DB / Engine`

### 352. `PATCH /profiles/lawyer/availability/{availability_id}`
- **Router**: `profiles_router`
- **Handler**: `app.api.v1.profiles.update_lawyer_availability`
- **Auth Required**: Yes
- **Role / Permission**: `Role: ['LAWYER']`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `LawyerAvailabilityResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: S3 / Stripe / LiveKit / LLM
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `PATCH /profiles/lawyer/availability/{availability_id} → [<app.api.deps.RequireRole object at 0x000001C145D5A7B0>, get_db] → ProfilesService → DB / Engine`

### 353. `POST /profiles/lawyer/verification`
- **Router**: `profiles_router`
- **Handler**: `app.api.v1.profiles.submit_lawyer_verification`
- **Auth Required**: Yes
- **Role / Permission**: `Role: ['LAWYER']`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `LawyerVerificationResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /profiles/lawyer/verification → [<app.api.deps.RequireRole object at 0x000001C145D58CE0>, get_db] → ProfilesService → DB / Engine`

### 354. `GET /profiles/me`
- **Router**: `profiles_router`
- **Handler**: `app.api.v1.profiles.get_my_profile`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `app.schemas.profile.ClientProfileResponse | app.schemas.profile.LawyerProfileResponse`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /profiles/me → [get_current_user, get_db] → ProfilesService → DB / Engine`

### 355. `GET /readiness`
- **Router**: `root_health_router`
- **Handler**: `app.api.v1.health.readiness_check`
- **Auth Required**: No
- **Role / Permission**: `None (Public)`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `dict / Raw Response`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /readiness → [get_db] → Root_healthService → DB / Engine`

### 356. `GET /ready`
- **Router**: `root_health_router`
- **Handler**: `app.api.v1.health.readiness_check`
- **Auth Required**: No
- **Role / Permission**: `None (Public)`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `dict / Raw Response`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /ready → [get_db] → Root_healthService → DB / Engine`

### 357. `GET /recordings/{recording_id}/play`
- **Router**: `recordings_router`
- **Handler**: `app.api.v1.recordings.play_recording`
- **Auth Required**: No
- **Role / Permission**: `None (Public)`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `dict / Raw Response`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /recordings/{recording_id}/play → [get_db] → RecordingsService → DB / Engine`

### 358. `POST /recordings/{recording_id}/playback-ticket`
- **Router**: `recordings_router`
- **Handler**: `app.api.v1.recordings.request_playback_ticket`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `dict`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Required
- **Execution Trace**: `POST /recordings/{recording_id}/playback-ticket → [get_current_user, get_db] → RecordingsService → DB / Engine`

### 359. `GET /support/analytics`
- **Router**: `support_router`
- **Handler**: `app.api.v1.support.get_support_analytics`
- **Auth Required**: Yes
- **Role / Permission**: `Operator: None`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `dict`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /support/analytics → [<app.api.deps.RequireOperatorPermission object at 0x000001C145DAA5A0>, get_db] → SupportService → DB / Engine`

### 360. `GET /support/cases`
- **Router**: `support_router`
- **Handler**: `app.api.v1.support.list_support_cases`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `list`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /support/cases → [get_current_user, get_db] → SupportService → DB / Engine`

### 361. `POST /support/cases`
- **Router**: `support_router`
- **Handler**: `app.api.v1.support.create_support_case`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `SupportCaseResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /support/cases → [get_current_user, get_db] → SupportService → DB / Engine`

### 362. `GET /support/cases/{case_id}`
- **Router**: `support_router`
- **Handler**: `app.api.v1.support.get_support_case`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `SupportCaseResponse`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /support/cases/{case_id} → [get_current_user, get_db] → SupportService → DB / Engine`

### 363. `POST /support/cases/{case_id}/escalate`
- **Router**: `support_router`
- **Handler**: `app.api.v1.support.escalate_support_case`
- **Auth Required**: Yes
- **Role / Permission**: `Operator: None`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `SupportCaseResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /support/cases/{case_id}/escalate → [<app.api.deps.RequireOperatorPermission object at 0x000001C145DA9A90>, get_db] → SupportService → DB / Engine`

### 364. `GET /support/cases/{case_id}/messages`
- **Router**: `support_router`
- **Handler**: `app.api.v1.support.get_support_case_messages`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `list`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /support/cases/{case_id}/messages → [get_current_user, get_db] → SupportService → DB / Engine`

### 365. `POST /support/cases/{case_id}/messages`
- **Router**: `support_router`
- **Handler**: `app.api.v1.support.add_support_case_message`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `dict`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /support/cases/{case_id}/messages → [get_current_user, get_db] → SupportService → DB / Engine`

### 366. `POST /support/cases/{case_id}/resolve`
- **Router**: `support_router`
- **Handler**: `app.api.v1.support.resolve_support_case`
- **Auth Required**: Yes
- **Role / Permission**: `Operator: None`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `SupportCaseResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /support/cases/{case_id}/resolve → [<app.api.deps.RequireOperatorPermission object at 0x000001C145DA8E00>, get_db] → SupportService → DB / Engine`

### 367. `GET /support/enhanced-analytics`
- **Router**: `support_router`
- **Handler**: `app.api.v1.support.get_enhanced_support_analytics`
- **Auth Required**: Yes
- **Role / Permission**: `Operator: None`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `dict`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /support/enhanced-analytics → [<app.api.deps.RequireOperatorPermission object at 0x000001C145DAAE10>, get_db] → SupportService → DB / Engine`

### 368. `GET /trust/disclosures`
- **Router**: `trust_router`
- **Handler**: `app.api.v1.trust.get_trust_and_transparency_disclosures`
- **Auth Required**: No
- **Role / Permission**: `None (Public)`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `dict`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /trust/disclosures → [Direct] → TrustService → DB / Engine`

### 369. `GET /trust/transparency`
- **Router**: `trust_router`
- **Handler**: `app.api.v1.trust.get_trust_and_transparency_disclosures`
- **Auth Required**: No
- **Role / Permission**: `None (Public)`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `dict`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Standard Access Log
- **Execution Trace**: `GET /trust/transparency → [Direct] → TrustService → DB / Engine`

### 370. `GET /verification/admin/queue`
- **Router**: `verification_router`
- **Handler**: `app.api.v1.verification.get_admin_verification_queue`
- **Auth Required**: Yes
- **Role / Permission**: `Role: ['ADMIN']`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `LawyerVerificationQueueResponse`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `GET /verification/admin/queue → [<app.api.deps.RequireRole object at 0x000001C145E23CB0>, get_db] → VerificationService → DB / Engine`

### 371. `GET /verification/admin/{verification_id}`
- **Router**: `verification_router`
- **Handler**: `app.api.v1.verification.get_admin_verification_detail`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `AdvocateVerificationDetailResponse`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `GET /verification/admin/{verification_id} → [get_current_user, get_db] → VerificationService → DB / Engine`

### 372. `POST /verification/admin/{verification_id}/approve`
- **Router**: `verification_router`
- **Handler**: `app.api.v1.verification.approve_admin_verification`
- **Auth Required**: Yes
- **Role / Permission**: `Role: ['ADMIN']`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `AdvocateVerificationDetailResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /verification/admin/{verification_id}/approve → [<app.api.deps.RequireRole object at 0x000001C145E47830>, get_db] → VerificationService → DB / Engine`

### 373. `GET /verification/admin/{verification_id}/detail`
- **Router**: `verification_router`
- **Handler**: `app.api.v1.verification.get_admin_verification_detail`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `AdvocateVerificationDetailResponse`
- **Database Side Effect**: Read Only
- **External Side Effect**: S3 / Stripe / LiveKit / LLM
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `GET /verification/admin/{verification_id}/detail → [get_current_user, get_db] → VerificationService → DB / Engine`

### 374. `POST /verification/admin/{verification_id}/reject`
- **Router**: `verification_router`
- **Handler**: `app.api.v1.verification.reject_admin_verification`
- **Auth Required**: Yes
- **Role / Permission**: `Role: ['ADMIN']`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `AdvocateVerificationDetailResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /verification/admin/{verification_id}/reject → [<app.api.deps.RequireRole object at 0x000001C145E68B30>, get_db] → VerificationService → DB / Engine`

### 375. `POST /verification/admin/{verification_id}/request-information`
- **Router**: `verification_router`
- **Handler**: `app.api.v1.verification.request_admin_verification_info`
- **Auth Required**: Yes
- **Role / Permission**: `Role: ['ADMIN']`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `AdvocateVerificationDetailResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /verification/admin/{verification_id}/request-information → [<app.api.deps.RequireRole object at 0x000001C145E69E80>, get_db] → VerificationService → DB / Engine`

### 376. `POST /verification/admin/{verification_id}/review`
- **Router**: `verification_router`
- **Handler**: `app.api.v1.verification.review_lawyer_verification_legacy`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `LawyerVerificationResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /verification/admin/{verification_id}/review → [get_current_user, get_db] → VerificationService → DB / Engine`

### 377. `POST /verification/admin/{verification_id}/revoke`
- **Router**: `verification_router`
- **Handler**: `app.api.v1.verification.revoke_admin_verification`
- **Auth Required**: Yes
- **Role / Permission**: `Role: ['ADMIN']`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `AdvocateVerificationDetailResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /verification/admin/{verification_id}/revoke → [<app.api.deps.RequireRole object at 0x000001C145E6B1A0>, get_db] → VerificationService → DB / Engine`

### 378. `POST /verification/admin/{verification_id}/start-review`
- **Router**: `verification_router`
- **Handler**: `app.api.v1.verification.start_admin_review`
- **Auth Required**: Yes
- **Role / Permission**: `Role: ['ADMIN']`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `AdvocateVerificationDetailResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /verification/admin/{verification_id}/start-review → [<app.api.deps.RequireRole object at 0x000001C145E464E0>, get_db] → VerificationService → DB / Engine`

### 379. `POST /verification/advocate/documents`
- **Router**: `verification_router`
- **Handler**: `app.api.v1.verification.upload_advocate_document`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `AdvocateVerificationDocumentUploadResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Required
- **Execution Trace**: `POST /verification/advocate/documents → [get_current_user, get_db] → VerificationService → DB / Engine`

### 380. `GET /verification/advocate/documents/{document_id}/download`
- **Router**: `verification_router`
- **Handler**: `app.api.v1.verification.get_verification_document_download_url`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `dict / Raw Response`
- **Database Side Effect**: Read Only
- **External Side Effect**: S3 / Stripe / LiveKit / LLM
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Required
- **Execution Trace**: `GET /verification/advocate/documents/{document_id}/download → [get_current_user, get_db] → VerificationService → DB / Engine`

### 381. `GET /verification/advocate/status`
- **Router**: `verification_router`
- **Handler**: `app.api.v1.verification.get_advocate_verification_status`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `AdvocateVerificationDetailResponse`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `GET /verification/advocate/status → [get_current_user, get_db] → VerificationService → DB / Engine`

### 382. `POST /verification/advocate/submit`
- **Router**: `verification_router`
- **Handler**: `app.api.v1.verification.submit_advocate_verification_application`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `AdvocateVerificationDetailResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /verification/advocate/submit → [get_current_user, get_db] → VerificationService → DB / Engine`

### 383. `GET /verification/advocate/{lawyer_id}/badge`
- **Router**: `verification_router`
- **Handler**: `app.api.v1.verification.get_public_advocate_badge`
- **Auth Required**: No
- **Role / Permission**: `None (Public)`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `PublicAdvocateVerificationBadgeResponse`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `GET /verification/advocate/{lawyer_id}/badge → [get_db] → VerificationService → DB / Engine`

### 384. `POST /verification/application/documents`
- **Router**: `verification_router`
- **Handler**: `app.api.v1.verification.upload_advocate_document`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `AdvocateVerificationDocumentUploadResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Required
- **Execution Trace**: `POST /verification/application/documents → [get_current_user, get_db] → VerificationService → DB / Engine`

### 385. `GET /verification/application/status`
- **Router**: `verification_router`
- **Handler**: `app.api.v1.verification.get_advocate_verification_status`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `AdvocateVerificationDetailResponse`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `GET /verification/application/status → [get_current_user, get_db] → VerificationService → DB / Engine`

### 386. `POST /verification/application/submit`
- **Router**: `verification_router`
- **Handler**: `app.api.v1.verification.submit_advocate_verification_application`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `AdvocateVerificationDetailResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /verification/application/submit → [get_current_user, get_db] → VerificationService → DB / Engine`

### 387. `GET /verification/badge/{lawyer_id}`
- **Router**: `verification_router`
- **Handler**: `app.api.v1.verification.get_public_advocate_badge`
- **Auth Required**: No
- **Role / Permission**: `None (Public)`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `PublicAdvocateVerificationBadgeResponse`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `GET /verification/badge/{lawyer_id} → [get_db] → VerificationService → DB / Engine`

### 388. `GET /verification/discovery/transparency`
- **Router**: `verification_router`
- **Handler**: `app.api.v1.verification.get_discovery_ranking_transparency`
- **Auth Required**: No
- **Role / Permission**: `None (Public)`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `dict / Raw Response`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `GET /verification/discovery/transparency → [get_db] → VerificationService → DB / Engine`

### 389. `GET /verification/documents/{document_id}/download-url`
- **Router**: `verification_router`
- **Handler**: `app.api.v1.verification.get_verification_document_download_url`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: Enforced (Participant / Owner / Admin)
- **Request Schema**: `None`
- **Response Schema**: `dict / Raw Response`
- **Database Side Effect**: Read Only
- **External Side Effect**: S3 / Stripe / LiveKit / LLM
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: Yes (Credentials, PII, Legal Evidence, or Financials)
- **Audit Requirement**: Required
- **Execution Trace**: `GET /verification/documents/{document_id}/download-url → [get_current_user, get_db] → VerificationService → DB / Engine`

### 390. `POST /verification/lawyer/submit`
- **Router**: `verification_router`
- **Handler**: `app.api.v1.verification.submit_lawyer_verification_legacy`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `LawyerVerificationResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /verification/lawyer/submit → [get_current_user, get_db] → VerificationService → DB / Engine`

### 391. `GET /verification/{verification_id}`
- **Router**: `verification_router`
- **Handler**: `app.api.v1.verification.get_admin_verification_detail`
- **Auth Required**: Yes
- **Role / Permission**: `Authenticated User`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `AdvocateVerificationDetailResponse`
- **Database Side Effect**: Read Only
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `GET /verification/{verification_id} → [get_current_user, get_db] → VerificationService → DB / Engine`

### 392. `POST /verification/{verification_id}/approve`
- **Router**: `verification_router`
- **Handler**: `app.api.v1.verification.approve_admin_verification`
- **Auth Required**: Yes
- **Role / Permission**: `Role: ['ADMIN']`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `AdvocateVerificationDetailResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /verification/{verification_id}/approve → [<app.api.deps.RequireRole object at 0x000001C145E47830>, get_db] → VerificationService → DB / Engine`

### 393. `POST /verification/{verification_id}/reject`
- **Router**: `verification_router`
- **Handler**: `app.api.v1.verification.reject_admin_verification`
- **Auth Required**: Yes
- **Role / Permission**: `Role: ['ADMIN']`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `AdvocateVerificationDetailResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /verification/{verification_id}/reject → [<app.api.deps.RequireRole object at 0x000001C145E68B30>, get_db] → VerificationService → DB / Engine`

### 394. `POST /verification/{verification_id}/request-information`
- **Router**: `verification_router`
- **Handler**: `app.api.v1.verification.request_admin_verification_info`
- **Auth Required**: Yes
- **Role / Permission**: `Role: ['ADMIN']`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `AdvocateVerificationDetailResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /verification/{verification_id}/request-information → [<app.api.deps.RequireRole object at 0x000001C145E69E80>, get_db] → VerificationService → DB / Engine`

### 395. `POST /verification/{verification_id}/revoke`
- **Router**: `verification_router`
- **Handler**: `app.api.v1.verification.revoke_admin_verification`
- **Auth Required**: Yes
- **Role / Permission**: `Role: ['ADMIN']`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `AdvocateVerificationDetailResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /verification/{verification_id}/revoke → [<app.api.deps.RequireRole object at 0x000001C145E6B1A0>, get_db] → VerificationService → DB / Engine`

### 396. `POST /verification/{verification_id}/start-review`
- **Router**: `verification_router`
- **Handler**: `app.api.v1.verification.start_admin_review`
- **Auth Required**: Yes
- **Role / Permission**: `Role: ['ADMIN']`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `AdvocateVerificationDetailResponse`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: None
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /verification/{verification_id}/start-review → [<app.api.deps.RequireRole object at 0x000001C145E464E0>, get_db] → VerificationService → DB / Engine`

### 397. `POST /webhooks/aws/malware`
- **Router**: `webhooks_router`
- **Handler**: `app.api.v1.webhooks.aws_malware_webhook`
- **Auth Required**: No
- **Role / Permission**: `None (Public)`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `dict / Raw Response`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: S3 / Stripe / LiveKit / LLM
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /webhooks/aws/malware → [get_db] → WebhooksService → DB / Engine`

### 398. `POST /webhooks/stripe`
- **Router**: `webhooks_router`
- **Handler**: `app.api.v1.webhooks.stripe_webhook`
- **Auth Required**: No
- **Role / Permission**: `None (Public)`
- **Object Ownership Check**: N/A
- **Request Schema**: `None`
- **Response Schema**: `dict / Raw Response`
- **Database Side Effect**: Write / State Mutation
- **External Side Effect**: S3 / Stripe / LiveKit / LLM
- **Rate Limit**: `Standard Gateway (60/min default)`
- **CSRF Requirement**: CSRF Header / Bearer Token Binding
- **Sensitive Data**: No
- **Audit Requirement**: Required
- **Execution Trace**: `POST /webhooks/stripe → [get_db] → WebhooksService → DB / Engine`
