# Legal Case Companion (LCC) — Comprehensive Backend Audit Report

**Date**: November 2, 2026  
**Auditor**: Principal Backend, DevOps/SRE, and Application Security Engineer  
**Scope**: Full repository audit across architecture, API contracts, database integrity, authentication, authorization, background processing, AI retrieval, and deployment infrastructure.

---

## 1. Executive Summary

The Legal Case Companion (LCC) backend is a modular monolith built with **FastAPI**, **SQLAlchemy 2.0**, **PostgreSQL**, and **Alembic**. It incorporates Indian legal technology domain requirements, including time-ordered UUIDv7 identifiers, multi-tenant RBAC, Ed25519 asymmetric JWT authentication, and Evidence Locker integrity.

The audit verified **533 Python source files**, **84 database tables**, **54 Alembic migrations**, **333 API endpoints**, and an automated test suite comprising **848 test cases**.

### Key Audit Metrics
- **Automated Tests**: 846 Passing, 2 Failing (pre-repair baseline).
- **Bytecode Integrity**: 100% compilation across `app/`, `tests/`, `scripts/`, `migrations/`.
- **Static Secret Leakage**: 0 committed secrets or private keys detected across 906 git-tracked files.
- **Architectural Boundary Adherence**: High. Router-to-service-to-repository layering is maintained across domains.

---

## 2. Subsystem Architectural Analysis

### 2.1 Backend & API Architecture
- **Framework**: FastAPI with Pydantic v2 schemas and dependency injection (`get_db`, `get_current_user`, `RequireRole`, `RequireOperatorPermission`).
- **Endpoint Structure**: 333 versioned paths under `/api/v1` organized across 25 domain routers.
- **Layering**:
  - API Routers (`app/api/v1/`): Request validation, route definition, rate limiting, and dependency injection.
  - Domain Services (`app/domain/`): Business logic, state transitions, domain events, and transaction orchestration.
  - Data Access Models (`app/models/`): Declarative SQLAlchemy 2.0 ORM entities with mixins (`TimestampMixin`, `SoftDeleteMixin`).
  - Schemas (`app/schemas/`): Strict Pydantic v2 serialization and contract validation.

### 2.2 Database Engineering & ORM
- **Engine Configuration**: Connection pooling with `pool_pre_ping=True`, configurable `pool_size`, `max_overflow`, `pool_recycle`, and statement timeouts.
- **Identifier Strategy**: Uniform use of application-generated UUIDv7 (`generate_uuid7()`), providing B-tree index locality without database sequence lock contention.
- **Migrations**: Alembic linear revision tree with 54 revisions.
- **Transactions & Concurrency**: Atomic transactions with explicit commits in service operations; `SELECT ... FOR UPDATE SKIP LOCKED` employed for background job scheduling.

### 2.3 Authentication & Authorization
- **Asymmetric JWT**: Ed25519 digital signatures with key-rotation fallback (`JWT_PREVIOUS_PUBLIC_KEY`). Explicit validation of claims: `iss`, `aud`, `exp`, `iat`, `jti`, and `type="access"`.
- **Password Security**: Argon2id hashing with cryptographic salt and parameterized work factors.
- **Session Lifecycle**: High-entropy refresh tokens (32 bytes urlsafe) hashed via SHA-256 in `refresh_token_sessions` with token rotation and family revocation on reuse.
- **Authorization & IDOR Protection**: Centralized policy enforcement in `app/core/authorization.py`. Resource lookups obscure unauthorized items via `ResourceNotFoundError` (HTTP 404) to prevent enumeration.

### 2.4 Evidence Locker & File Security
- **Storage Abstraction**: `StorageProvider` protocol with `S3StorageProvider` (production) and `LocalStorageProvider` (development).
- **MIME & Signature Verification**: Content inspection via `validate_file_magic_bytes` and filename sanitization via `validate_filename_security`.
- **Archive Defense**: Zip bomb detection with max uncompressed size (200MB), max compression ratio (100:1), and nested archive prevention.
- **Malware Scanning**: Integration with ClamAV daemon (`clamdscan`) and AWS EventBridge malware callbacks.

### 2.5 Background Jobs & Reliability
- **Architecture**: Database-backed job queue with `BackgroundJob` model, lease-based locking, and outbox event pattern (`OutboxService`).
- **Workers**: Dedicated worker loop (`app/worker.py`) with signal handling (`SIGINT`, `SIGTERM`), atomic batch claiming (`SKIP LOCKED`), and JSON heartbeat reporting.
- **Scheduler**: Periodic cron scanner (`app/scheduler.py`) enforcing idempotency key buckets across deadlines, overdue tasks, and token cleanup.

### 2.6 AI & RAG Intelligence
- **Retrieval Pipeline**: Evidence-grounded case-scoped search (`RetrievalService.search_case_evidence`).
- **Authorization Barrier**: Mandatory `authorize_case_access` before document chunks reach the embedding or retrieval layer.
- **AI Safety**: Anti-hallucination policies, confidence scoring, legal disclaimer enforcement, and strict Indian citation normalization.

---

## 3. High-Priority Issues Discovered

| Issue ID | Area | Severity | Description |
|---|---|---|---|
| **BUG-001** | Auth / OAuth | **CRITICAL** | `jwt.decode` hardcodes `leeway=300` (5 min) in `GoogleOAuthService`, accepting expired Google ID tokens. |
| **BUG-002** | Migrations | **CRITICAL** | Migration `afbdf4813237` attempts duplicate creation of `ix_lawyer_verifications_lawyer_profile_id` and `ix_lawyer_verifications_reviewed_by`, crashing `alembic upgrade head`. |
| **BUG-003** | Storage / Security | **HIGH** | Direct upload `/cases/{case_id}/documents` marks files `SAFE` and `READY` immediately, bypassing magic byte validation and ClamAV quarantine. |
| **BUG-004** | CI/CD | **HIGH** | `scripts/verify_openapi_contract.py` fails due to 4 added `/api/v1/advisor` operations not present in `docs/openapi.json`. |
| **BUG-005** | Dev / Testing | **MEDIUM** | Missing `pythonpath = ["."]` in `pyproject.toml` causing `ModuleNotFoundError: No module named 'app'` when running pytest without environment variables. |
| **BUG-006** | Performance / DB | **MEDIUM** | In-memory Python cosine similarity loop in `RetrievalService` loads all case chunks into memory rather than pushing vector queries to the database. |
| **BUG-007** | Information Disclosure | **LOW** | Webhook endpoint raises HTTP 500 with descriptive detail `"Webhook secret not configured"`, disclosing backend internal state. |

---

## 4. Architectural Scorecard

| Domain | Rating | Current State | Target State |
|---|---|---|---|
| **Security & Auth** | 8.8 / 10 | Ed25519 & Argon2id solid; OAuth leeway & direct upload validation need hardening. | 9.8 / 10 |
| **Database Integrity** | 8.5 / 10 | Clean UUIDv7 & models; Alembic index duplicate in revision `afbdf4813237` needs resolution. | 9.8 / 10 |
| **API Robustness** | 9.0 / 10 | Consistent Pydantic validation; OpenAPI contract baseline requires synchronization. | 9.9 / 10 |
| **DevOps & CI/CD** | 8.7 / 10 | Multi-stage Docker with non-root appuser; CI pipelines require lock and test environment stabilization. | 9.8 / 10 |
| **Observability** | 9.2 / 10 | Structured JSON logging with regex PII/credential scrubbing and Prometheus HTTP metrics. | 9.7 / 10 |
| **Scalability** | 8.0 / 10 | Worker polling & SKIP LOCKED effective; RAG vector calculation needs database-level vector indexing. | 9.5 / 10 |

---

## 5. Next Steps

Proceed immediately to author the accompanying audit documentation:
1. `BUG_INVENTORY.md` — Complete reproduction and remediation blueprints for each confirmed bug.
2. `SECURITY_AUDIT.md` — Comprehensive OWASP ASVS and Top 10 threat model assessment.
3. `DEVOPS_AUDIT.md` — Docker, CI/CD, and Render deployment evaluation.
4. `IMPROVEMENT_ROADMAP.md` — Phased, step-by-step engineering execution strategy.
