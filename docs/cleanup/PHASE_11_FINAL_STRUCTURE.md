# Phase 11: Final Repository Structure & Architecture

## 1. Overview & Clean Layout

Following the completion of Phase 10 (Domain-Oriented Backend Architecture Refactoring) and Phase 11 (Repository-Wide Dead Code & Compatibility Cleanup), the repository layout is structured strictly by architectural layers and bounded domains.

```
Legal-Case-Companion-main/
├── app/                           # Canonical Backend Application
│   ├── api/                       # Presentation & Routing Layer
│   │   ├── deps.py                # FastApi Dependencies & RBAC Guards
│   │   └── v1/                    # Versioned REST & WebSocket Endpoints (329 paths)
│   ├── core/                      # Application Infrastructure (Config, Security, Logging)
│   ├── db/                        # Database Engine & Migrations Foundation
│   │   ├── base.py
│   │   ├── database.py            # SessionLocal, get_db, engine
│   │   └── engine.py
│   ├── domain/                    # Pure Domain Bounded Contexts (11 contexts)
│   │   ├── ai/                    # Statutory Research, Citations, Providers, Policy
│   │   ├── auth/                  # Authentication, Session Lifecycle, OAuth
│   │   ├── cases/                 # Case Management, Workflows, Bundles, PDF Engine
│   │   ├── consultations/         # Bookings, Signaling, Room Telemetry, Presence
│   │   ├── documents/             # Document Storage, Parsing, OCR
│   │   ├── evidence/              # Evidence Locker, Chain of Custody, Scanner
│   │   ├── governance/            # Launch Gates, Incidents, Compliance, Abuse Defense
│   │   ├── jobs/                  # Background Worker Execution, Outbox, Change Feed
│   │   ├── notifications/         # Notification Channels, Email, Reminders
│   │   ├── payments/              # Stripe Checkout, Commercial Tiers, Reconciliation
│   │   ├── users/                 # User Accounts, Advocate & Client Profiles, Admin
│   │   └── verification/          # Bar Council Verification, Lawyer Onboarding
│   ├── models/                    # Declarative SQLAlchemy ORM Entities (19 models)
│   ├── providers/                 # External Service Adapters & Interfaces (16 providers)
│   │   ├── ai/                    # Canonical OpenAI & Mock Provider Adapters
│   │   ├── email/                 # SMTP & Console Email Adapters
│   │   ├── payment/               # Stripe SDK Encapsulation & Mock Providers
│   │   ├── storage/               # S3/MinIO Storage Adapter & Traversal Guards
│   │   └── video/                 # LiveKit Video Integration
│   ├── repositories/              # Encapsulated Persistence Repositories (6 repositories)
│   │   ├── case_repository.py
│   │   ├── consultation_repository.py
│   │   ├── document_repository.py
│   │   ├── job_repository.py
│   │   ├── payment_repository.py
│   │   └── user_repository.py
│   ├── schemas/                   # Pydantic Request/Response DTOs (18 schemas)
│   ├── services/                  # Retained Compatibility Facades (5 isolated files)
│   └── utils/                     # Generic Domain-Agnostic Utilities
│
├── frontend/                      # Canonical Frontend Web Application (Next.js 16)
│   ├── src/
│   │   ├── app/                   # App Router Pages & Layouts (36 routes)
│   │   ├── components/            # Reusable UI & Domain Components
│   │   ├── hooks/                 # React Hooks & State Management
│   │   ├── lib/                   # API Client, Validation, Utilities
│   │   └── types/                 # Shared TypeScript Type Definitions
│   └── package.json
│
├── tests/                         # Comprehensive Automated Test Suite (848 tests)
│   ├── e2e/                       # End-to-End Business Workflows
│   ├── evaluation/                # AI Grounding & Citation Quality Benchmarks
│   ├── integration/               # Multi-Module Integration Tests
│   ├── performance/               # Latency & Concurrency Stress Tests
│   ├── pilot/                     # Pilot Persona & Operational Validations
│   ├── public_readiness/          # Launch Gate Readiness Checks
│   ├── reliability/               # Cross-System Failure Recovery Tests
│   ├── security/                  # 129 Red-Team & Security Hardening Tests
│   └── unit/                      # Isolated Unit Tests
│
├── scripts/                       # Maintenance & Scale Validation CLI Tools
├── migrations/                    # Alembic Database Migration History
└── docs/                          # Comprehensive Architectural & Reliability Docs
    ├── architecture/              # Phase 10 Domain Architecture Records
    ├── cleanup/                   # Phase 11 Cleanup & Baseline Records
    ├── frontend/                  # Phase 8 Frontend Architecture Records
    ├── reliability/               # Phase 9 Cross-System Reliability Records
    └── security/                  # Security Audit & Pen-Test Documentation
```

---

## 2. Generated & Runtime Exclusions

The repository strictly excludes ephemeral development, runtime, and build artifacts via `.gitignore`:
- Python: `.venv/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`
- Node/Frontend: `node_modules/`, `frontend/.next/`, `frontend/out/`
- Runtime Data: `storage/recordings/`, `storage/documents/`, `*.db`, `*.sqlite3`
- Environment: `.env`, `.env.local`

---

## 3. Quality Invariants Enforced

- **Zero Route Loss**: 329 OpenAPI paths, 388 operations verified 1:1.
- **Zero Test Regressions**: 848/848 pytest tests passing.
- **Zero Security Drift**: 129/129 security tests passing.
- **Zero Lint / Type Errors**: Python Ruff 0, Mypy 0 across 263 source files, Frontend TypeScript 0, ESLint 0.
- **Passing Production Build**: Next.js 16 production build compiles all 36 routes cleanly.
