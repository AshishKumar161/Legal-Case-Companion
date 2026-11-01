# Legal Case Companion (LCC) — Production Hardening & Improvement Roadmap

**Date**: November 2, 2026  
**Auditor / Lead Engineer**: Principal Backend, DevOps/SRE, and Security Engineer  
**Strategy**: Systematic, phased execution across 10 disciplined stages without breaking existing architecture or discarding working code.

---

## Roadmap Overview

```
[Stage 1: Discovery & Audit] (DONE)
          │
          ▼
[Stage 2: Critical Bugs & Security Vulnerabilities]
  - Fix Google OAuth expired token leeway (BUG-001)
  - Fix Alembic duplicate index collision in afbdf4813237 (BUG-002)
  - Fix direct document upload security bypass (BUG-003)
          │
          ▼
[Stage 3: Backend Correctness & Database Integrity]
  - Synchronize OpenAPI contract parity for /api/v1/advisor (BUG-004)
  - Verify database transaction rollback & connection timeouts
  - Validate reversible Alembic downgrades
          │
          ▼
[Stage 4: Authentication & Authorization Hardening]
  - Pytest configuration & pythonpath standardization (BUG-005)
  - Re-verify IDOR defenses across cases, documents, notes, consultations
  - Sanitize webhook error disclosures (BUG-007)
          │
          ▼
[Stage 5: Docker & CI/CD Pipeline Hardening]
  - Verify multi-stage Docker build with non-root appuser
  - Ensure CI pipeline gates pass 100% (Ruff, Mypy, Secrets, Migrations, OpenAPI, Tests)
  - Verify Render IaC deployment configuration
          │
          ▼
[Stage 6: Observability, Logging & SRE Metrics]
  - Structured JSON logging verification
  - PII and credential scrubbing validation
  - Prometheus metrics instrumentation
          │
          ▼
[Stage 7: Background Processing & Queue Reliability]
  - Idempotency key buckets validation
  - SELECT FOR UPDATE SKIP LOCKED worker concurrency
  - Graceful worker shutdown & heartbeat health checks
          │
          ▼
[Stage 8: Performance & Scalability]
  - RAG vector search optimization assessment (BUG-006)
  - Query indexing verification
  - Memory & latency benchmarking
          │
          ▼
[Stage 9: Full Regression Testing]
  - Execute full unit, integration, pilot, security, and performance test suites
  - Confirm 100% pass rate
          │
          ▼
[Stage 10: Production-Readiness Review]
  - Deliver final LCC_PRODUCTION_READINESS_REPORT.md
  - Production deployment verification checklist
```

---

## Detailed Stage Execution Plan

### Stage 1: Repository Discovery & Audit (COMPLETED)
- **Deliverables**:
  - `AUDIT_REPORT.md` (System architecture, table inventory, test baseline)
  - `BUG_INVENTORY.md` (7 prioritized, verified defects with reproduction steps)
  - `SECURITY_AUDIT.md` (OWASP ASVS & Top 10 threat model)
  - `DEVOPS_AUDIT.md` (Docker, CI/CD, Render, and secret management evaluation)
  - `IMPROVEMENT_ROADMAP.md` (This document)
- **Status**: **Complete**.

---

### Stage 2: Critical Bugs & Security Vulnerabilities
- **Goals**: Resolve confirmed critical and high severity vulnerabilities without side effects.
- **Tasks**:
  1. **Remediate `BUG-001`**: In `app/domain/auth/google_oauth_service.py`, reduce `leeway` from 300s to 10s and verify `test_google_auth_expired_token_rejection` passes.
  2. **Remediate `BUG-002`**: In `migrations/versions/afbdf4813237_sync_remaining_model_indexes_and_.py`, eliminate duplicate creation of `ix_lawyer_verifications_lawyer_profile_id` and `ix_lawyer_verifications_reviewed_by`. Verify clean database creation with `scripts/test_migrations_lifecycle.py`.
  3. **Remediate `BUG-003`**: In `app/api/v1/documents.py` (`upload_case_document_direct`), invoke `validate_file_magic_bytes(file_bytes, mime_type)` and set initial `security_status = DocumentSecurityStatus.QUARANTINED` pending ClamAV verification.
- **Acceptance Criteria**:
  - Zero test regressions.
  - `scripts/test_migrations_lifecycle.py` passes 100%.
  - `test_google_auth_expired_token_rejection` passes.

---

### Stage 3: Backend Correctness & Database Integrity
- **Goals**: Enforce contract parity and database session consistency.
- **Tasks**:
  1. **Remediate `BUG-004`**: Synchronize `docs/openapi.json` to include the 4 missing `/api/v1/advisor` operations. Verify `python scripts/verify_openapi_contract.py` passes.
  2. Verify database session lifecycle in `app/db/database.py`: ensure rollback on unhandled service exceptions.
  3. Verify transaction isolation levels and foreign key cascades on relational models.
- **Acceptance Criteria**:
  - `scripts/verify_openapi_contract.py` passes with zero contract drift.
  - Database migrations remain reversible.

---

### Stage 4: Authentication & Authorization Hardening
- **Goals**: Harden test infrastructure, verify zero IDOR across all entities, and eliminate info leaks.
- **Tasks**:
  1. **Remediate `BUG-005`**: Add `pythonpath = ["."]` to `pyproject.toml` under `[tool.pytest.ini_options]` and ensure `pytest-asyncio` is active.
  2. **Remediate `BUG-007`**: Sanitize webhook error responses in `app/api/v1/webhooks.py` to prevent disclosure of internal environment variable names.
  3. Run comprehensive security test suite (`pytest tests/security/ -v`).
- **Acceptance Criteria**:
  - All security tests in `tests/security/` pass.
  - Pytest runs without requiring external `PYTHONPATH` exports.

---

### Stage 5: Docker & CI/CD Pipeline Hardening
- **Goals**: Validate build reproducibility, container security, and CI gates.
- **Tasks**:
  1. Verify multi-stage `Dockerfile` and ensure `.dockerignore` excludes unnecessary development bloat.
  2. Verify `docker-compose.prod.yml` service health dependencies and network isolation.
  3. Validate GitHub Actions workflow `.github/workflows/ci.yml` gates.
- **Acceptance Criteria**:
  - Clean container builds without root privileges.
  - CI pipeline passes all static, lint, typecheck, and contract checks.

---

### Stage 6: Observability, Logging & SRE Metrics
- **Goals**: Ensure production-grade visibility without data leakage.
- **Tasks**:
  1. Verify structured JSON output in production (`JsonFormatter`).
  2. Verify regex scrubbing for credentials, Aadhaar, PAN, and card numbers.
  3. Verify Prometheus metrics collection in `app/middleware/metrics.py`.
- **Acceptance Criteria**:
  - Sensitive data is never emitted into logs.
  - HTTP request latencies and error counts are accurately recorded.

---

### Stage 7: Background Processing & Reliability
- **Goals**: Guarantee background job idempotency, failure recovery, and zero data corruption.
- **Tasks**:
  1. Verify `JobScheduler` hourly, 5-minute, and daily idempotency keys.
  2. Verify `SELECT ... FOR UPDATE SKIP LOCKED` worker claiming under concurrent worker execution.
  3. Validate graceful worker termination on `SIGTERM`.
- **Acceptance Criteria**:
  - Multi-instance worker tests pass without race conditions or duplicate execution.

---

### Stage 8: Performance & Scalability
- **Goals**: Benchmark database queries and optimize RAG retrieval architecture.
- **Tasks**:
  1. Address `BUG-006`: Document pgvector migration strategy for native vector indexing.
  2. Verify indexing on all foreign keys and high-cardinality status columns.
  3. Profile API response times on heavy endpoints.
- **Acceptance Criteria**:
  - Zero missing foreign key indexes.
  - Sub-50ms database lookup times on standard case operations.

---

### Stage 9: Full Regression Testing
- **Goals**: Comprehensive validation across all test suites.
- **Tasks**:
  1. Run full test suite: unit, integration, pilot, security, and performance.
  2. Verify 100% passing status.
- **Acceptance Criteria**:
  - `848 passed, 0 failed` across the test suite.

---

### Stage 10: Production-Readiness Review
- **Goals**: Final sign-off and production documentation.
- **Tasks**:
  1. Generate `LCC_PRODUCTION_READINESS_REPORT.md`.
  2. Document production deployment checklist and remaining operational risks.
- **Acceptance Criteria**:
  - Production readiness report delivered and signed off.
