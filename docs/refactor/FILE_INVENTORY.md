# Complete File Inventory: Legal Case Companion (LCC)

**Auditor**: Antigravity Engineering  
**Scope**: Full recursive repository inventory  
**Total File Count in Repository Workspace**: **39,742 files**  
**Tracked Git Files**: 737 files  

---

## 1. Inventory Summary by Functional Category

| Category | File Count | Primary Location | Typical Extensions | Tracking Status |
| :--- | :--- | :--- | :--- | :--- |
| **Backend Source** | 230 | `app/` | `.py` | Tracked |
| **Frontend Source** | 152 | `frontend/src/`, `frontend/` | `.ts`, `.tsx`, `.css`, `.json` | Tracked |
| **Test Suites** | 162 | `tests/` | `.py`, `.json`, `.pem` | Tracked |
| **Database Migrations** | 54 | `migrations/` | `.py`, `.ini`, `.mako` | Tracked |
| **Configuration** | 16 | Root, `frontend/`, `coturn/` | `.toml`, `.ini`, `.yaml`, `.json` | Tracked & Local Untracked |
| **Operations & Scripts** | 19 | `scripts/`, `frontend/*.mjs` | `.py`, `.bat`, `.cs`, `.mjs` | Tracked |
| **Documentation & Runbooks** | 95 | `docs/`, Root markdown files | `.md`, `.json` | Tracked |
| **Generated Artifacts** | 4 | Root, `docs/` | `.json` (`sbom-*`, `manifest`, `openapi`) | Tracked (Incorrectly committed) |
| **Caches & Build Artifacts** | 878 | `.mypy_cache/`, `.pytest_cache/`, `__pycache__/`, `.next/` | `.pyc`, `.cache`, `.tsbuildinfo` | Ignored |
| **Virtual Environments** | 13,754 | `.venv/` | `.py`, `.pyd`, `.exe`, `.h` | Ignored |
| **Node Modules** | 22,768 | `frontend/node_modules/` | `.js`, `.json`, `.ts`, `.wasm` | Ignored |
| **Runtime & Storage Data** | 304 | `storage/`, `test.db` | `.webm`, `.pdf`, `.db` | Local Untracked / Seed Data |
| **Compiled Binaries** | 2 | Root & nested root | `.exe` (`LegalCaseCompanion.exe`) | Tracked (Binary artifact) |
| **Duplicate Content Groups** | 11 | Cross-project | `.exe`, `.ico`, `.png`, `.json`, `.webm` | Redundant Copies |
| **Legacy Files & Aliases** | 5 | Cross-project | `uv.lock.local`, `app/db/session.py`, etc. | Retained |

---

## 2. Backend Source Inventory (`app/` — 230 Files)

### 2.1 API Layer (`app/api/` — 44 Files)
- `app/api/deps.py`: Shared FastAPI dependencies (`get_current_user`, `RequireRole`, `get_db`, `get_token_session`).
- `app/api/v1/`: 43 endpoint router modules:
  - `admin.py`: Administrative control, metrics, user impersonation, tenant management.
  - `ai.py`: Legal research queries, prompt generation, grounding retrieval.
  - `ai_conversations.py`: Conversational thread management, context retention.
  - `ai_review.py`: Human-in-the-loop review of AI legal summaries.
  - `analytics.py`: Aggregate platform usage, consultation velocity, case turnover.
  - `assistant.py`: Interactive copilot queries and matter drafting assistance.
  - `attention.py`: Case urgency heuristics, unread alerts, missed deadlines.
  - `audit.py`: Immutable audit trail retrieval for compliance officers.
  - `auth.py`: Ed25519 authentication, login, register, token refresh, OTP, reset password.
  - `bundles.py`: Evidentiary bundle generation, index sheets, BSA Section 63 certificates.
  - `calendar.py`: Agenda views, schedule slots, statutory hearing calendar.
  - `case_intelligence.py`: Chronology, cause of action classification, limitation alerts.
  - `cases.py`: Case matter CRUD, participant assignment, status transitions.
  - `change_feed.py`: Real-time change log for collaborative matter synchronization.
  - `commercial.py`: Transaction records, platform commissions, GST invoices, settlements.
  - `compliance.py`: Data retention rules, statutory compliance checks.
  - `consultations.py`: Video consultation scheduling, booking, intake briefs.
  - `court_cases.py`: E-Courts tracking integration, CNR numbering, cause lists.
  - `data_quality.py`: Case metadata consistency, missing document identification.
  - `documents.py`: Document upload, metadata tagging, versioning, access control.
  - `evidence.py`: Evidence locker, chain of custody logging, SHA-256 verification.
  - `experiments.py`: A/B feature experimentation gates for pilot rollout.
  - `feedback.py`: User satisfaction ratings, NPS, bug reports.
  - `health.py`: LCC health, readiness, and liveness probes (`/health`, `/health/ready`).
  - `incidents.py`: Operational incidents, severity classification, status updates.
  - `launch_gates.py`: Go/No-Go release readiness telemetry checks.
  - `lawyers.py`: Advocate directory, Bar Council verification badge, slot availability.
  - `legal_authority.py`: Indian legal statutes, Supreme Court/High Court precedent search.
  - `legal_documents.py`: Template repository (vakalatnama, legal notices, pleadings).
  - `localization.py`: Multi-language strings (Hindi, English, Marathi, Tamil, etc.).
  - `messages.py`: In-matter direct and group messaging between clients and counsel.
  - `notifications.py`: User notification inbox, push delivery status.
  - `payments.py`: Stripe / Razorpay payment intent initialization, webhooks.
  - `pilot.py`: Controlled pilot access allowlist, cohort management.
  - `profiles.py`: User profile mutations (client profile, advocate bar details).
  - `recordings.py`: Ephemeral recording playback tickets, video consent ledger.
  - `search.py`: Unified full-text and semantic search over cases and documents.
  - `support.py`: Customer support tickets, issue triage.
  - `trust.py`: Transparency reports, SLA uptime tracking.
  - `verification.py`: Advocate Bar Council certificate review and approval workflow.
  - `video_signaling.py`: WebSocket WebRTC signaling server (SDP offer/answer, ICE exchange).
  - `webhooks.py`: Inbound webhooks from payment processors and document scanners.
  - `workflow.py`: Task deadlines, hearing dates, workflow automation stages.

### 2.2 Core Layer (`app/core/` — 14 Files)
- `config.py`: Authoritative Pydantic settings (`Settings`), environment variable ingestion.
- `database.py`: SQLAlchemy database engine initialization, connection pooling.
- `exceptions.py`: Application domain exception hierarchy (`AppException`, `AuthorizationError`, `ResourceNotFoundError`, `ValidationError`).
- `identifiers.py`: UUIDv7 time-sortable deterministic identifier generation.
- `locking.py`: Distributed and database advisory locking (`job_lock`, `redis_lock`).
- `logging.py`: Structured JSON logging, correlation ID filter, sensitive credential scrubber.
- `metrics.py`: Prometheus metrics collector and registry.
- `middleware.py`: Base middleware interfaces.
- `rate_limiting.py`: SlowAPI rate limiting configuration.
- `security.py`: Argon2id password hashing, Ed25519 JWT keypair signing and verification.
- `storage.py`: Pluggable object storage provider (`S3StorageProvider`, `LocalStorageProvider`, `MockStorageProvider`).
- `telemetry.py`: Application performance and trace spans.
- `timezone.py`: Indian Standard Time (IST) conversion helpers.
- `tokens.py`: CSRF double-submit token generator, email verification token utilities.

### 2.3 Database Layer (`app/db/` — 3 Files)
- `base.py`: Central declarative base re-exporting all models for Alembic auto-discovery.
- `database.py`: Sessionmaker and engine lifecycle.
- `session.py`: **Legacy re-export alias** (exports `engine`, `SessionLocal`, `get_db`).

### 2.4 Middleware Stack (`app/middleware/` — 6 Files)
- `correlation_id.py`: Ingests or injects `X-Correlation-ID` header into request context.
- `metrics.py`: Computes request duration, status code counters, and endpoint latency.
- `payload.py`: Request body size ceiling enforcement (blocks payloads > 5MB).
- `pilot.py`: Evaluates pilot cohort access gates, intercepts unauthorized tenants.
- `security.py`: Enforces hardened HTTP security headers (CSP, HSTS, X-Frame-Options).
- `trusted_host.py`: Protects against host-header poisoning.

### 2.5 Data Models (`app/models/` — 30 Files)
- `audit.py`: `AuditEvent` immutable compliance audit log.
- `auth.py`: `RefreshTokenSession`, `EmailVerificationToken`, `PasswordResetToken`.
- `base.py`: SQLAlchemy `Base` declarative base class.
- `bsa_certificate.py`: `BSACertificate` Bharatiya Sakshya Adhiniyam Section 63 electronic records certificates.
- `calendar.py`: `CalendarEvent`, `LawyerAvailability`.
- `case.py`: `Case`, `CaseParticipant`.
- `case_collaboration.py`: `MatterMessage`, `MatterRequest`.
- `case_intelligence.py`: `CaseChronologyItem`, `CaseLimitationRisk`.
- `commercial.py`: `CommercialTransaction`, `CommercialEntitlement`, `CommercialSettlement`.
- `compliance.py`: `ComplianceRegistryItem`, `DataRetentionPolicy`.
- `consultation.py`: `Consultation`, `ConsultationNote`.
- `court_case.py`: `CourtCase`, `CourtHearing`, `CourtCaseSubscription`.
- `data_quality.py`: `DataQualityAudit`.
- `document.py`: `Document`, `DocumentChunk`, `DocumentPage`.
- `evidence.py`: `Evidence`, `EvidenceAuditLog`, `EvidenceAccessGrant`.
- `exhibit.py`: `CaseExhibit`, `ExhibitEvidenceLink`.
- `experiment.py`: `ExperimentVariant`, `ExperimentAssignment`.
- `feedback.py`: `UserFeedback`, `PilotSurveyResponse`.
- `incident.py`: `ProductionIncident`, `IncidentActionItem`.
- `job.py`: `BackgroundJob`.
- `launch_gate.py`: `LaunchGateTelemetry`.
- `legal_authority.py`: `LegalStatute`, `LegalProvision`, `CourtPrecedent`.
- `legal_document.py`: `LegalDocumentTemplate`, `LegalDocumentVersion`.
- `localization.py`: `LocalizedContentString`.
- `notification.py`: `Notification`, `NotificationPreference`.
- `outbox.py`: `OutboxEvent`.
- `pilot.py`: `PilotAllowlist`, `PilotTenant`.
- `support.py`: `SupportTicket`, `SupportMessage`.
- `task.py`: `CaseTask`.
- `user.py`: `User`, `ClientProfile`, `LawyerProfile`, `LawyerVerification`.
- `video_meeting.py`: `VideoMeeting`, `VideoRecordingConsent`.
- `video_recording.py`: `VideoRecording`.
- `workflow.py`: `CaseDeadline`, `CaseHearing`.

### 2.6 Schemas (`app/schemas/` — 36 Files)
Pydantic v2 schemas providing strict input validation and response contracts matching each domain model.

### 2.7 Services (`app/services/` — 74 Files)
Domain business logic services including `auth_service.py`, `case_service.py`, `document_processor.py`, `evidence_service.py`, `video_meeting_service.py`, `video_recording_service.py`, `job_worker.py`, `job_scheduler.py`, `reconciliation_engine.py`, etc.

### 2.8 Top-Level Backend Entrypoints (`app/` — 3 Files)
- `main.py`: FastAPI application bootstrap, middleware assembly, router mounting.
- `scheduler.py`: Dedicated background job scheduler process entrypoint (`python -m app.scheduler`).
- `worker.py`: Dedicated background asynchronous worker process entrypoint (`python -m app.worker`).

---

## 3. Frontend Source Inventory (`frontend/` — 152 Files)

### 3.1 Next.js App Router (`frontend/src/app/` — 36 Routes)
- `layout.tsx`: Root shell layout (font, dark mode theme providers).
- `page.tsx`: Marketing landing page.
- `globals.css`: Design system CSS custom properties and obsidian color palette.
- `admin/`: Admin console (dashboard, reports, users, verification review).
- `auth/callback/`: OAuth2 redirect callback receiver.
- `calendar/`: Hearing and consultation calendar view.
- `cases/`: Matter dashboard, `/cases/new`, and dynamic case detail routes (`/cases/[caseId]`, `/cases/[caseId]/evidence`, `/cases/[caseId]/bundles`, `/cases/[caseId]/timeline`).
- `consultations/`: Booking management and live room (`/consultations/[id]/room`).
- `court-tracking/`: E-Courts case tracker.
- `dashboard/`: Role-specific central dashboard.
- `documents/`: Unified document repository.
- `lawyers/`: Advocate directory and profile view (`/lawyers/[lawyerId]`).
- `login/`, `register/`, `forgot-password/`, `reset-password/`, `verify-email/`: Auth flows.
- `messages/`: Matter chat.
- `notifications/`: Inbox.
- `onboarding/`: Client and advocate onboarding steps.
- `payments/`: Financial transactions and billing history.
- `profile/`: Account settings.
- `support/`: Ticket desk.
- `trust/`: Public transparency page.

### 3.2 UI Components (`frontend/src/components/` — 38 Files)
- `AppShell/`: `Sidebar.tsx`, `TopBar.tsx`, `Navigation.tsx`.
- `Collaboration/`: `MatterChat.tsx`, `DocumentSharingDrawer.tsx`, `MatterBriefCard.tsx` (unused), `MatterRequestsBoard.tsx` (unused).
- `Consultation/`: `LiveRoomDrawer.tsx`, `VideoRoom.tsx`, `ParticipantTile.tsx`, `DeviceSelector.tsx`.
- `Intelligence/`: `CopilotChat.tsx`, `ChronologyView.tsx`, `IntelligenceCenter.tsx` (unused).
- `UI/`: Buttons, modals, tabs, badges, cards, data tables.

### 3.3 Utilities & Library (`frontend/src/lib/` & `src/hooks/` — 24 Files)
- `apiClient.ts`: Strongly-typed Fetch client with automatic Bearer token injection and refresh.
- `authContext.tsx`: Session state, user role, login/logout dispatch.
- `webrtc.ts`: Native browser RTCPeerConnection and ICE candidate management.

---

## 4. Test Suite Inventory (`tests/` — 162 Files)

| Subdirectory | File Count | Purpose |
| :--- | :--- | :--- |
| `tests/unit/` | 18 | Isolated business logic tests (reconciliation, token signing, rounding, state machines) |
| `tests/integration/` | 26 | Multi-component integration tests (auth, video signaling, storage, evidence locker) |
| `tests/e2e/` | 8 | End-to-end user journeys (client onboarding, consultation booking to completion) |
| `tests/evaluation/` | 12 | AI retrieval accuracy, hallucination defense, prompt grounding |
| `tests/pilot/` | 15 | Real-world pilot validation scenarios |
| `tests/public_readiness/` | 18 | Production readiness scorecards, SLA checks, rate limiting |
| `tests/reliability/` | 14 | Crash recovery, outbox retries, transaction rollbacks |
| `tests/security/` | 22 | Red team, IDOR, BOLA, injection, token tampering, header security |
| `tests/performance/` | 10 | Benchmark harnesses for DB indexing, chunk search, WebSocket load |
| `tests/fixtures/` | 19 | Test certificates, sample PDFs, mock law reports, seed JSONs |

---

## 5. Configuration, Scripts, & Generated Artifacts

### 5.1 Configuration Files (16 Files)
- `pyproject.toml`: Backend packaging and tool configurations (`ruff`, `mypy`, `black`, `isort`).
- `pytest.ini`: Pytest CLI flags and warning filters.
- `alembic.ini`: Database migration configuration.
- `Dockerfile` & `frontend/Dockerfile`: Multi-stage production container definitions.
- `docker-compose.yml` & `docker-compose.prod.yml`: Local and staging orchestrator setups.
- `render.yaml`: Cloud deployment spec (web service, worker service, scheduler, db).
- `.env.example`, `.env.prod.example`: Environment variable schema templates.
- `frontend/tsconfig.json`: TypeScript compiler configuration.
- `frontend/eslint.config.mjs`: ESLint flat config.
- `frontend/next.config.ts`: Next.js build options and rewrites.

### 5.2 Scripts & Tooling (19 Files)
- `scripts/build_launcher.bat`: C# compiler script compiling `launcher.cs` into `LegalCaseCompanion.exe`.
- `scripts/launcher.cs`: C# Windows desktop launcher with embedded app icon.
- `scripts/load_test_phase_10.py`: Concurrency load test harness (contains 9 ruff errors).
- `scripts/generate_sbom.py` & `scripts/generate_release_manifest.py`: Release governance tools.
- `frontend/*.mjs`: Standalone browser automation scripts (`test_browser_flow.mjs`, `capture_redesign_screenshots.mjs`).

### 5.3 Generated Artifacts Committed to Git (4 Files)
- `sbom-backend.json` (120 KB): Software Bill of Materials for Python dependencies.
- `sbom-frontend.json` (95 KB): Software Bill of Materials for npm dependencies.
- `release-manifest.json` (1.6 KB): Checksums and metadata for release build.
- `openapi.json` (806 KB): Static snapshot of FastAPI OpenAPI specification.

---

## 6. Runtime, Caches, & Binary Artifacts

- **Binaries**:
  * `Legal-Case-Companion-main/LegalCaseCompanion.exe` (77,824 bytes) — in repository root.
  * `Legal-Case-Companion-main/Legal-Case-Companion-main/LegalCaseCompanion.exe` (77,824 bytes) — duplicate copy in nested project folder.
- **Runtime & Storage Data**:
  * `storage/recordings/`: 304 recorded test session webm files generated during automated video tests.
  * `test.db`: 2.2 MB local SQLite database file with test data.
- **Caches**:
  * `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `__pycache__/`, `frontend/.next/`.
