# Comprehensive Route Inventory: Legal Case Companion (LCC)

**Auditor**: Antigravity Engineering  
**Backend Scope**: FastAPI REST & WebSocket Endpoints (Extracted from OpenAPI & App Router)  
**Frontend Scope**: Next.js 16 App Router Routes (`frontend/src/app`)  

---

## 1. Backend Route Summary & Statistics

- **Total Unique URL Paths**: **329**
- **Total API Operations**: **388**
- **HTTP Methods Breakdown**:
  - `GET`: 182 operations
  - `POST`: 168 operations
  - `PATCH`: 21 operations
  - `DELETE`: 15 operations
  - `PUT`: 2 operations
  - `WebSocket`: 1 endpoint (`/api/v1/video/signaling`)

---

## 2. Backend Route Domain Catalog

| Domain Tag | Operations Count | Key Endpoints Sample | Primary Router File |
| :--- | :---: | :--- | :--- |
| **Authentication & Identity** | 18 | `POST /api/v1/auth/login`, `POST /api/v1/auth/register`, `POST /api/v1/auth/refresh`, `POST /api/v1/auth/logout`, `GET /api/v1/auth/me`, `POST /api/v1/auth/password-reset/request`, `POST /api/v1/auth/verify-email` | `app/api/v1/auth.py` |
| **Profiles & Onboarding** | 12 | `GET /api/v1/profiles/me`, `PATCH /api/v1/profiles/client`, `PATCH /api/v1/profiles/lawyer`, `GET /api/v1/profiles/{id}` | `app/api/v1/profiles.py` |
| **Cases & Matters** | 22 | `GET /api/v1/cases`, `POST /api/v1/cases`, `GET /api/v1/cases/{id}`, `PATCH /api/v1/cases/{id}`, `POST /api/v1/cases/{id}/participants`, `GET /api/v1/cases/{id}/chronology` | `app/api/v1/cases.py` |
| **Case Intelligence** | 14 | `POST /api/v1/case-intelligence/analyze`, `GET /api/v1/case-intelligence/{case_id}/limitations`, `GET /api/v1/case-intelligence/{case_id}/risks` | `app/api/v1/case_intelligence.py` |
| **Workflow & Deadlines** | 16 | `GET /api/v1/workflow/cases/{case_id}/deadlines`, `POST /api/v1/workflow/deadlines`, `POST /api/v1/workflow/hearings`, `PATCH /api/v1/workflow/deadlines/{id}` | `app/api/v1/workflow.py` |
| **Consultations & Video** | 19 | `GET /api/v1/consultations`, `POST /api/v1/consultations`, `GET /api/v1/consultations/{id}`, `POST /api/v1/consultations/{id}/cancel`, `GET /api/v1/consultations/{id}/video/join`, `POST /api/v1/consultations/{id}/video/reconnect` | `app/api/v1/consultations.py` |
| **Video WebRTC Signaling** | 1 | `WebSocket /api/v1/video/signaling` | `app/api/v1/video_signaling.py` |
| **Documents & Locker** | 24 | `POST /api/v1/documents/upload`, `GET /api/v1/documents/{id}/download`, `POST /api/v1/documents/{id}/process`, `GET /api/v1/evidence`, `POST /api/v1/evidence/{id}/verify` | `app/api/v1/documents.py`, `app/api/v1/evidence.py` |
| **Evidentiary Bundles** | 8 | `POST /api/v1/bundles/generate`, `GET /api/v1/bundles/{id}`, `GET /api/v1/bundles/{id}/bsa-certificate` | `app/api/v1/bundles.py` |
| **Legal Authority & Search** | 11 | `GET /api/v1/legal-authority/statutes`, `GET /api/v1/legal-authority/precedents`, `POST /api/v1/search/unified` | `app/api/v1/legal_authority.py`, `app/api/v1/search.py` |
| **Payments & Commercial** | 20 | `POST /api/v1/payments/intent`, `POST /api/v1/payments/webhook`, `GET /api/v1/commercial/transactions`, `GET /api/v1/commercial/settlements` | `app/api/v1/payments.py`, `app/api/v1/commercial.py` |
| **Advocate Directory** | 9 | `GET /api/v1/lawyers`, `GET /api/v1/lawyers/{id}`, `GET /api/v1/lawyers/{id}/slots` | `app/api/v1/lawyers.py` |
| **AI Legal Copilot** | 15 | `POST /api/v1/ai/query`, `POST /api/v1/ai/conversations`, `POST /api/v1/assistant/chat` | `app/api/v1/ai.py`, `app/api/v1/assistant.py` |
| **Calendar & Attention** | 10 | `GET /api/v1/calendar/events`, `GET /api/v1/attention/cases` | `app/api/v1/calendar.py`, `app/api/v1/attention.py` |
| **Court Tracking (CNR)** | 8 | `POST /api/v1/court-cases/track`, `GET /api/v1/court-cases/{id}/hearings` | `app/api/v1/court_cases.py` |
| **Admin & Audit** | 26 | `GET /api/v1/admin/users`, `PATCH /api/v1/admin/users/{id}`, `GET /api/v1/audit/events` | `app/api/v1/admin.py`, `app/api/v1/audit.py` |
| **Health & Probes** | 8 | `GET /health`, `GET /health/live`, `GET /health/ready`, `GET /api/v1/health`, `GET /api/v1/health/live`, `GET /api/v1/health/ready` | `app/api/v1/health.py` |
| **Mock Storage (Local Emulation)**| 2 | `PUT /mock-storage/upload`, `GET /mock-storage/download` | `app/main.py` |

---

## 3. Duplicate Routes & Legacy Route Aliases

### 3.1 Health Endpoint Duplication
The following health routes exist in duplicate due to dual mounting:

| Operation | Root Path (Mount 1) | Versioned Path (Mount 2) | Purpose & Conflict Analysis |
| :--- | :--- | :--- | :--- |
| **Health Summary** | `GET /health` | `GET /api/v1/health` | Root mount is used by Kubernetes/Render ingress probes; `/api/v1/health` is exposed in versioned OpenAPI spec. Both point to identical handler. |
| **Liveness Probe** | `GET /health/live` | `GET /api/v1/health/live` | Dockerfile `HEALTHCHECK` targets `/api/v1/health/live`. Cloud load balancer targets `/health/live`. |
| **Readiness Probe** | `GET /health/ready` | `GET /api/v1/health/ready` | Checks database connection pool and Redis cache readiness. |
| **Health Details** | `GET /health/details` | `GET /api/v1/health/details` | Admin diagnostic health snapshot. |

*Recommendation*: Retain both mounts during Phase 1 & 2 to avoid breaking orchestrator health probes while maintaining versioned API consistency.

### 3.2 Mock Storage Emulation Endpoints
- `PUT /mock-storage/upload`
- `GET /mock-storage/download`
Mounted directly at application root in `app/main.py:259-287`.
*Analysis*: Emulates S3 presigned PUT/GET URLs during local SQLite development when AWS credentials are not configured.
*Security Guard*: Must ensure mock storage cannot be invoked in production or used for arbitrary file retrieval across hosts.

---

## 4. Frontend Route Inventory (`frontend/src/app/` — 36 Routes)

| Frontend Route | Type | Target Feature / Screen | Backend Endpoints Consumed |
| :--- | :--- | :--- | :--- |
| `/` | Static | Marketing landing page | None |
| `/login` | Static | Client/Advocate login | `POST /api/v1/auth/login`, `POST /api/v1/auth/google` |
| `/register` | Static | Account creation | `POST /api/v1/auth/register` |
| `/forgot-password` | Static | Password recovery request | `POST /api/v1/auth/password-reset/request` |
| `/reset-password` | Static | Password reset submission | `POST /api/v1/auth/password-reset/confirm` |
| `/verify-email` | Static | Email verification token handler | `POST /api/v1/auth/verify-email` |
| `/auth/callback` | Static | OAuth2 Google redirect landing | `POST /api/v1/auth/oauth/callback` |
| `/dashboard` | Static | Central role dashboard | `GET /api/v1/auth/me`, `GET /api/v1/cases`, `GET /api/v1/consultations` |
| `/cases` | Static | Matter list & filtering | `GET /api/v1/cases` |
| `/cases/new` | Static | New case creation wizard | `POST /api/v1/cases` |
| `/cases/[caseId]` | Dynamic | Matter master detail | `GET /api/v1/cases/{id}`, `GET /api/v1/case-intelligence/{id}` |
| `/cases/[caseId]/evidence` | Dynamic | Evidence locker tab | `GET /api/v1/cases/{id}/evidence`, `POST /api/v1/evidence` |
| `/cases/[caseId]/evidence/[evidenceId]` | Dynamic | Single exhibit viewer & chain of custody | `GET /api/v1/evidence/{id}`, `GET /api/v1/evidence/{id}/custody` |
| `/cases/[caseId]/bundles` | Dynamic | Court exhibit bundles | `GET /api/v1/bundles?case_id={id}`, `POST /api/v1/bundles/generate` |
| `/cases/[caseId]/timeline` | Dynamic | Procedural hearing timeline | `GET /api/v1/workflow/cases/{id}/hearings` |
| `/consultations` | Static | Video appointments schedule | `GET /api/v1/consultations` |
| `/consultations/[id]/room` | Dynamic | Live WebRTC video consultation room | `GET /api/v1/consultations/{id}/video/join`, `POST /api/v1/consultations/{id}/video/reconnect`, `WS /api/v1/video/signaling` |
| `/calendar` | Static | Calendar & listing diary | `GET /api/v1/calendar/events` |
| `/court-tracking` | Static | E-Courts CNR tracker | `GET /api/v1/court-cases`, `POST /api/v1/court-cases/track` |
| `/lawyers` | Static | Advocate public directory | `GET /api/v1/lawyers` |
| `/lawyers/[lawyerId]` | Dynamic | Advocate profile & booking calendar | `GET /api/v1/lawyers/{id}`, `GET /api/v1/lawyers/{id}/slots`, `POST /api/v1/consultations` |
| `/documents` | Static | Cross-matter document library | `GET /api/v1/documents`, `POST /api/v1/documents/upload` |
| `/messages` | Static | Matter messages & direct messaging | `GET /api/v1/messages/threads`, `POST /api/v1/messages` |
| `/notifications` | Static | Notifications inbox | `GET /api/v1/notifications`, `PATCH /api/v1/notifications/{id}/read` |
| `/payments` | Static | Billing, invoices, and payouts | `GET /api/v1/commercial/transactions`, `POST /api/v1/payments/intent` |
| `/onboarding` | Static | Persona selector (Client vs Advocate) | None |
| `/onboarding/client` | Static | Client identity profile | `PATCH /api/v1/profiles/client` |
| `/onboarding/advocate`| Static | Bar enrollment submission | `POST /api/v1/verification/submit` |
| `/lawyer/dashboard` | Static | Advocate command centre | `GET /api/v1/lawyers/me/dashboard` |
| `/lawyer/profile` | Static | Advocate bio & consultation fee | `PATCH /api/v1/profiles/lawyer` |
| `/profile` | Static | User settings | `GET /api/v1/profiles/me` |
| `/support` | Static | Support portal & ticket submission | `GET /api/v1/support/tickets`, `POST /api/v1/support/tickets` |
| `/trust` | Static | Security & compliance transparency | `GET /api/v1/trust/overview` |
| `/design-system` | Static | UI component showcase (internal) | None |
| `/admin` | Static | Admin redirection | None |
| `/admin/dashboard` | Static | Platform analytics & metrics | `GET /api/v1/admin/analytics` |
| `/admin/reports` | Static | Financial & compliance reports | `GET /api/v1/admin/reports` |
| `/admin/users` | Static | User management console | `GET /api/v1/admin/users`, `PATCH /api/v1/admin/users/{id}` |
| `/admin/verification` | Static | Advocate verification queue | `GET /api/v1/verification/pending`, `POST /api/v1/verification/{id}/approve` |
