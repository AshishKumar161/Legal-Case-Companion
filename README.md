# Legal Case Companion (LCC)

[![Architecture](https://img.shields.io/badge/Architecture-Modular%20Monolith-blue.svg)](#architecture)
[![Backend](https://img.shields.io/badge/Backend-FastAPI%20%7C%20Python%203.12+-green.svg)](app/)
[![Frontend](https://img.shields.io/badge/Frontend-Next.js%2016%20%7C%20React%2019-black.svg)](frontend/)
[![Database](https://img.shields.io/badge/Database-PostgreSQL%20%7C%20SQLAlchemy%202.0-orange.svg)](app/models/)
[![Agents](https://img.shields.io/badge/Agents-Antigravity%20MCP%20Ecosystem-purple.svg)](AGENTS.md)

An India-focused legal technology platform providing automated case tracking, plain-language document intelligence, verified advocate consultations, native WebRTC video meetings, and a tamper-evident Evidence Locker.

---

## 1. Professional Repository Architecture

```text
legal-case-companion/
├── app/                        # FastAPI Backend Application (Modular Monolith)
│   ├── api/                    # HTTP REST routers (v1 endpoints, dependencies)
│   │   └── v1/                 # Versioned API routes (auth, cases, consultations, evidence, etc.)
│   ├── core/                   # Cross-cutting concerns (config, security, storage, logging, redis)
│   ├── db/                     # Database engine, SessionLocal, dependency injection (get_db)
│   ├── domain/                 # Domain business services organized by bounded context
│   │   ├── ai/                 # AI legal reasoning & source retrieval
│   │   ├── auth/               # Authentication & session rotation
│   │   ├── cases/              # Legal matter workflows & milestones
│   │   ├── consultations/      # Video & in-person booking state machines
│   │   ├── documents/          # Document metadata & ingestion
│   │   ├── evidence/           # Evidence Locker (Phase XIV cryptographic vault)
│   │   └── payments/           # Financial transaction processing
│   ├── middleware/             # HTTP middleware (CORS, rate limiting, request logging)
│   ├── models/                 # Authoritative SQLAlchemy ORM models (02_DATABASE_DESIGN.md)
│   ├── providers/              # External service adapters (OpenAI, Groq, S3, LiveKit, Stripe)
│   ├── repositories/           # Data access layer abstractions
│   ├── schemas/                # Strict Pydantic validation schemas & DTOs
│   ├── scheduler.py            # Background job scheduler
│   ├── worker.py               # Asynchronous task worker
│   └── main.py                 # FastAPI application factory & lifespan handler
│
├── frontend/                   # Next.js 16 / React 19 Client Application
│   ├── src/
│   │   ├── api/                # Authoritative API client & multi-tab session manager
│   │   ├── app/                # Next.js App Router (pages, layouts, route handlers)
│   │   ├── components/         # Reusable React components & design tokens
│   │   │   ├── ui/             # Atomic design system (Button, Modal, Card, Icons)
│   │   │   └── AppShell/       # Header, Sidebar, BottomNav, WhatChangedBanner
│   │   ├── i18n/               # Multi-language localization (English, Hindi)
│   │   ├── lib/                # Shared utilities, canonical status mappers, formatters
│   │   ├── providers/          # React Context providers (Auth, Theme, I18n)
│   │   └── types/              # TypeScript interfaces & domain contract types
│   ├── public/                 # Static assets, branding logos, icons
│   └── scripts/                # End-to-end browser verification scripts
│
├── chatbot/                    # Legal NLP & AI Conversation Engine
│   ├── data/                   # Indian case law datasets
│   ├── model_backend/          # Rerankers, retrievers, reasoners, and safety filters
│   ├── pipeline.py             # Case ingestion & embedding pipeline
│   └── eval.py                 # Legal benchmark evaluation harness
│
├── migrations/                 # Alembic Database Migrations
│   ├── versions/               # Versioned migration revision scripts
│   └── env.py                  # Alembic environment runner
│
├── tests/                      # Automated Verification & Test Harnesses
│   ├── unit/                   # Isolated unit test suites
│   ├── integration/            # Cross-module service & database tests
│   ├── e2e/                    # End-to-end journey tests
│   ├── security/               # RBAC, JWT rotation, and quarantine audits
│   ├── performance/            # Latency baselines and load tests
│   └── pilot/                  # Real-world pilot execution simulation
│
├── docs/                       # System Specifications, Runbooks & Reports (see docs/README.md)
│   ├── ops/                    # Deployment topology, DR plans, and checklists
│   ├── reports/                # Milestone, DevSecOps, and verification reports
│   ├── audit/                  # Security audits, vulnerability registers, bug tracker
│   ├── legal/                  # DPDPA 2023 & BSA statutory compliance policies
│   ├── 01_SYSTEM_ARCHITECTURE.md
│   ├── 02_DATABASE_DESIGN.md   # Authoritative database model rules & constraints
│   └── 24_PRODUCTION_DEPLOYMENT_RUNBOOK.md
│
├── scripts/                    # Operational & Maintenance Utilities
│   ├── inspect_db.py           # Database inspector
│   ├── seed_court_cases.py     # Demo & test case seeder
│   └── production_smoke_test.py# Production health check & smoke tests
│
├── .agents/                    # Google Antigravity Agent Configuration
│   ├── mcp_config.json         # Workspace MCP servers (agent-system, database, thinking)
│   ├── rules/                  # Directory engineering constraints (database, architecture)
│   └── skills/                 # Specialist workflows (subagent orchestration, database ops)
│
├── AGENTS.md                   # Authoritative Multi-Agent operating hierarchy
├── pyproject.toml              # Python project metadata, dependencies, and tooling configs
├── alembic.ini                 # Database migrations configuration
├── docker-compose.yml          # Local container orchestration (Postgres, Redis, Backend, Frontend)
├── docker-compose.prod.yml     # Hardened production container setup
└── Dockerfile                  # Multi-stage production container build
```

---

## 2. Core Subsystems

### 2.1 Backend (`app/`)
- **FastAPI Modular Monolith**: Distinct domain packages with explicit boundaries.
- **Dependency Injection**: Strict RBAC via `RequireRole`, database sessions via `get_db`.
- **Primary Keys**: UUIDv7 for time-ordered relational indexing.
- **Audit Immutability**: All security and access history recorded in append-only `AuditEvent` logs.

### 2.2 Database & Migrations (`app/models/` & `migrations/`)
- **Engine**: PostgreSQL with SQLAlchemy 2.0 ORM.
- **Alembic Revisions**: All schema evolutions are version-controlled under `migrations/versions/`.
- **Soft Deletes**: Enabled on business entities (`deleted_at`), prohibited on financial/security records.

### 2.3 Frontend (`frontend/`)
- **Framework**: Next.js 16 with React 19 and App Router.
- **State & Theme**: React Context (`AuthProvider`, `ThemeProvider`) with dark/light mode engine.
- **Navigation**: Clean SPA client-side routing (`router.push`).
- **Quality Gates**: Strict React Compiler purity and 0-error TypeScript checking.

### 2.4 Evidence Locker (Phase XIV)
- **High-Security Domain**: Dedicated tamper-evident evidence objects with cryptographic SHA-256 hashing.
- **Quarantine Pipeline**: Automatic virus quarantine, integrity verification, and legal hold locks.

---

## 3. Quickstart & Development

### Backend Setup
```bash
# 1. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -e .[dev]

# 3. Configure environment
cp .env.example .env

# 4. Apply database migrations
alembic upgrade head

# 5. Start the FastAPI development server
uvicorn app.main:app --reload --port 8000
```

### Frontend Setup
```bash
cd frontend

# 1. Install dependencies
npm install

# 2. Run the Next.js development server
npm run dev
# Accessible at http://localhost:3000
```

### Full-Stack with Docker Compose
```bash
docker compose up -d
```

---

## 4. Verification & Testing

```bash
# Run unit tests
pytest tests/unit

# Run full test suite
pytest

# Verify frontend types and linting
cd frontend
node node_modules/typescript/bin/tsc --noEmit
node node_modules/eslint/bin/eslint.js .
```

---

## 5. Multi-Agent Collaboration (Antigravity)

This repository includes a multi-agent orchestration architecture documented in [AGENTS.md](AGENTS.md) and connected via 6 Model Context Protocol (MCP) servers:
- **`lcc-agent-system`**: Task allocation, status tracking, shared cross-agent memory, peer reviews.
- **`lcc-database`**: Live SQLAlchemy model discovery, schema inspection, migration checking, safe read-only SQL queries.
- **`sequential-thinking`**: Structured hypothesis verification and decision trees.
- **`backend-hierarchy`**: Business head objectives, tech lead architecture, and staff server management.
- **`git` & `fetch`**: Git workflows and web documentation retrieval.

---

## 6. Technical Documentation Hub

All detailed system specifications, operational runbooks, and audit reports are organized in the [`docs/`](docs/README.md) directory:

- 🚀 **[Operations & Deployment](docs/ops/LCC_DEPLOYMENT_ARCHITECTURE.md)**: Deployment topology, disaster recovery strategy, and production rollout gates.
- 📋 **[Verification & Audit Reports](docs/reports/LCC_FINAL_PRODUCTION_READINESS_REPORT.md)**: Stage 1–4 validation reports, DevSecOps certifications, and bug resolution matrix.
- 🔒 **[Security & Authorization](docs/security/API_AUTHORIZATION_MATRIX.md)**: RBAC permission matrices, IDOR protection tests, and prompt security guardrails.
- 📜 **[Legal & Statutory Compliance](docs/legal/PRIVACY_NOTICE.md)**: DPDPA 2023 privacy notices, BCI advocate terms, and BSA 2023 evidence retention policies.
- 📖 **[Master Documentation Index](docs/README.md)**: Full catalog of all 56+ system design specifications and runbooks.
