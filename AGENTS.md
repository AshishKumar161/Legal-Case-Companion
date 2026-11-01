# Legal Case Companion — Agent & Subagent Architecture (AGENTS.md)

This document establishes the authoritative multi-agent operating model for the **Legal Case Companion (LCC)** repository in Google Antigravity.

---

## 1. System Overview

The Legal Case Companion is an India-focused legal technology platform comprising a modular monolith FastAPI backend, Next.js frontend, legal NLP chatbot, WebRTC native video consultations, and an Evidence Locker.

To develop, maintain, and scale this repository autonomously, Antigravity operates through a **Multi-Agent & Subagent Ecosystem** backed by specialized Model Context Protocol (MCP) servers.

```
                              ┌────────────────────────────────────────┐
                              │  Lead Orchestrator (@orchestrator)     │
                              │  (Business Goals, Project Milestones)  │
                              └──────────────────┬─────────────────────┘
                                                 │
          ┌───────────────────────────┬──────────┴───────────────┬──────────────────────────┐
          ▼                           ▼                          ▼                          ▼
┌──────────────────┐        ┌──────────────────┐       ┌──────────────────┐       ┌──────────────────┐
│ System Architect │        │ Backend Engineer │       │Frontend Engineer │       │ Legal NLP Agent  │
│ (@system_arch)   │        │ (@backend_eng)   │       │ (@frontend_eng)  │       │ (@legal_nlp)     │
└─────────┬────────┘        └─────────┬────────┘       └─────────┬────────┘       └─────────┬────────┘
          │                           │                          │                          │
          └───────────────────────────┼──────────────────────────┴──────────────────────────┘
                                      ▼
                        ┌───────────────────────────┐
                        │   QA & Security Auditing  │
                        │   (@qa_eng, @sec_auditor) │
                        └───────────────────────────┘
```

---

## 2. Subagent Roles & Responsibilities

### 2.1 Lead Orchestrator (`@orchestrator`)
- **Mission**: Deconstruct complex user requests into milestones and assign sub-tasks.
- **Tools**: `create_agent_task`, `list_agent_tasks`, `update_agent_task`, `get_agent_ecosystem_overview`, `business_head_create_project`.
- **Workflow**: Defines acceptance criteria before execution and reviews deliverables before marking tasks complete.

### 2.2 System Architect (`@system_architect`)
- **Mission**: Enforce domain boundaries, database integrity (`docs/02_DATABASE_DESIGN.md`), and API contracts.
- **Tools**: `db_list_tables`, `db_get_table_schema`, `db_check_migrations`, `sequential_think`, `save_shared_memory`.
- **Key Rules**:
  - Enforce UUIDv7 primary keys for relational entities.
  - Require traceable business justifications for any schema change.
  - Maintain append-only immutability for financial payments and audit logs.

### 2.3 Backend Engineer (`@backend_engineer`)
- **Mission**: Implement FastAPI routers (`app/api/v1`), domain services (`app/domain/`), SQLAlchemy models, and Alembic migrations.
- **Tools**: `staff_create_backend_scaffold`, `staff_start_backend_server`, `db_get_table_schema`, `save_shared_memory`.
- **Key Rules**:
  - All endpoints must include strict Pydantic schemas and dependency-injected authentication (`get_db`, `RequireRole`).
  - No database entity or field may be invented without corresponding migration revisions.

### 2.4 Frontend Engineer (`@frontend_engineer`)
- **Mission**: Develop Next.js 16 / React 19 pages (`frontend/src/app`), reusable UI components (`frontend/src/components`), and design tokens.
- **Tools**: `save_shared_memory`, `recall_shared_memory`, `run_command` (linting & typechecks).
- **Key Rules**:
  - Zero tolerance for React Compiler purity errors (`Date.now()` or Math.random during render).
  - Use Next.js client-side navigation (`useRouter().push()`), never hard `window.location.href`.
  - Maintain verified type-safety (`npm run lint` and `tsc --noEmit` must pass with 0 errors).

### 2.5 Legal NLP & Chatbot Agent (`@legal_nlp_agent`)
- **Mission**: Maintain the Indian Kanoon legal pipeline, dataset loaders, reasoning graphs, and AI conversation endpoints (`chatbot/` & `app/api/v1/ai`).
- **Tools**: `sequential_think`, `save_shared_memory`, `recall_shared_memory`.
- **Key Rules**:
  - All legal summarization must maintain strict citations (acts, sections, case citations).
  - Prohibit legal hallucination; output confidence scoring and disclaimers.

### 2.6 QA & Reliability Engineer (`@qa_engineer`)
- **Mission**: Test suite execution, regression validation, end-to-end verification, and performance baselines.
- **Tools**: `db_execute_readonly_query`, `run_unit_tests`, `git_diff`.
- **Key Rules**:
  - Run pytest across `tests/unit/`, `tests/integration/`, and `tests/pilot/`.
  - Ensure zero regressions in authentication isolation, payment webhooks, or video signaling.

### 2.7 Security & Privacy Auditor (`@security_auditor`)
- **Mission**: Evidence Locker protection (Phase XIV), cryptographic verification, JWT rotation, and RBAC authorization audits.
- **Tools**: `db_execute_readonly_query`, `request_subagent_review`, `save_shared_memory`.
- **Key Rules**:
  - Verify HMAC signatures on all webhook and payment routes.
  - Enforce virus scanning quarantine and SHA-256 verification on evidence uploads.

---

## 3. Connected MCP Servers

The repository integrates 6 Model Context Protocol servers configured in `.agents/mcp_config.json` and `~/.gemini/config/mcp_config.json`:

| Server Name | Executable | Primary Capabilities |
| :--- | :--- | :--- |
| **`lcc-agent-system`** | `lcc-agent-system-mcp` | Task assignment, status tracking, shared cross-agent memory, peer review delegation |
| **`lcc-database`** | `lcc-database-mcp` | Live SQLAlchemy model discovery, table schema inspection, Alembic migration verification, safe read-only SQL queries |
| **`sequential-thinking`** | `sequential-thinking-mcp` | Dynamic thought trees, hypothesis testing, self-correction, multi-step problem solving |
| **`backend-hierarchy`** | `backend-hierarchy-mcp` | Business Head objectives, Tech Lead architecture, Staff server management |
| **`git`** | `mcp-server-git` | Git status, diffs, staged commits, branches, and commit history |
| **`fetch`** | `mcp-server-fetch` | HTTP fetching for external documentation and verification |

---

## 4. Multi-Agent Collaboration Workflow

```
1. RECEIVE USER REQUEST
   │
   ▼
2. [Lead Orchestrator] Analyze intent -> Call sequential_think()
   │
   ▼
3. [Lead Orchestrator] Call create_agent_task() for specialist subagents
   │
   ├──▶ [System Architect] Inspect models via db_list_tables() & db_get_table_schema()
   ├──▶ [Backend Engineer] Implement business logic & migrations
   ├──▶ [Frontend Engineer] Build UI & verify with tsc + eslint
   └──▶ [Legal NLP Agent] Validate legal citations & schemas
   │
   ▼
4. [Peer Review] Call request_subagent_review() (e.g. Backend -> Security Auditor)
   │
   ▼
5. [QA Engineer] Run test suites & typechecks -> update_agent_task(status='completed')
   │
   ▼
6. [Shared Memory] Store architectural decisions via save_shared_memory()
   │
   ▼
7. DELIVER FINAL VERIFIED SOLUTION TO USER
```

---

## 5. Standard Operating Procedures (SOPs)

### Database Changes
1. Query `db_check_migrations` to determine the latest revision.
2. Read `docs/02_DATABASE_DESIGN.md` for entity rules.
3. Update `app/models/`.
4. Generate new migration with `alembic revision --autogenerate -m "description"`.
5. Run `db_get_table_schema` to verify field definitions.

### Frontend Enhancements
1. Check existing design tokens in `frontend/src/app/globals.css`.
2. Implement component with clean React 19 hooks and CSS modules.
3. Verify compilation: `node node_modules/typescript/bin/tsc --noEmit`.
4. Verify linting: `node node_modules/eslint/bin/eslint.js .`.
