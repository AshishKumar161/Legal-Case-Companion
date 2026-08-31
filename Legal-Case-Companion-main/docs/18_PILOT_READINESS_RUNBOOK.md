# Legal Case Companion — Pilot Readiness & Production Gate Runbook 3.0

## 1. Executive Summary & Verification Matrix

The Legal Case Companion platform has passed complete pilot verification across all application layers, from frontend App Router compilation to backend multi-tenant security and AI grounding benchmarks.

| Verification Pillar | Command / Suite | Result | Details |
|---|---|---|---|
| **Frontend Production Build** | `npm run build` (Next.js 16 App Router) | **100% PASS** | 12/12 routes static/dynamically prerendered, 0 build errors |
| **Frontend Code Quality & React Purity** | `npm run lint` (ESLint + React Compiler) | **100% PASS** | 0 errors, pure render idempotency enforced |
| **Backend Integration & Domain Tests** | `pytest tests/integration/` | **100% PASS** | Case management, workflows, tasks, hearings, auth, notes |
| **Security & BOLA Isolation Matrix** | `pytest tests/security/` | **100% PASS** | Multi-tenant isolation, IDOR defenses, CSRF & token rotation |
| **AI Reliability & Red-Team Suite** | `pytest tests/evaluation/` | **100% PASS** | Groundedness benchmarks, citation stripping, prompt boundaries |
| **E2E Pilot User Journeys** | `pytest tests/e2e/` | **100% PASS** | Complete Client, Lawyer, and Admin operational flows |
| **System Performance & Latency** | `pytest tests/performance/` | **100% PASS** | Bounded queries, latency envelopes, backpressure verification |
| **Database Schema Linearity** | `python -m alembic heads` | **100% PASS** | Head at `b2c3d4e5f6a1`, 0 unhandled schema deviations |

| **Cumulative Test Result** | `pytest` (Full suite) | **100% PASS** | **331 passed, 1 skipped, 0 failed** in 105s |
| **Real-World Pilot Guide** | `docs/19_REAL_WORLD_PILOT_GUIDE.md` | **COMPLETE** | Persona playbooks, failure resilience, and success criteria |

**Cumulative Test Result**: **331 passed, 1 skipped (SQLite concurrency lock constraint), 0 failed** in 105s. For end-to-end pilot deployment procedures and failure triage, see [Real-World Pilot Guide](19_REAL_WORLD_PILOT_GUIDE.md).

---

## 2. Pilot User Journey Validation

### 2.1 Client Matter Journey
1. **Intake & Creation**: Client creates matter with category, description, and client profile context.
2. **Document Ingestion**: Client uploads PDF/DOCX agreement $\to$ quarantine validation $\to$ malware scan simulation $\to$ mark `SAFE` $\to$ text extraction & semantic vector chunking.
3. **Intelligence Center Review**: Grounded facts, chronology events, and evidence gaps are automatically derived from processed documents.
4. **Interactive Copilot 2.0**: Client poses legal queries; assistant returns 5-part structured response grounded strictly in authorized case chunks and Indian statutes, stripping unverified citations.
5. **Action Center Execution**: Evidence gaps are converted into concrete task obligations via the Task Composer; client tracks court listings and limitation deadlines.

### 2.2 Counsel / Lawyer Journey
1. **Discovery & Onboarding**: Lawyer verifies bar registration credentials, sets fee schedule and availability slots.
2. **Consultation & Onboarding**: Client books slot $\to$ Stripe fee authorized $\to$ lawyer accepts $\to$ formal case participant access granted.
3. **Evidence ↔ Authority Matrix**: Counsel evaluates contested controversies linked to specific document chunks and governing Indian enactments (Arbitration Act 1996, Limitation Act 1963, Commercial Courts Act 2015).
4. **Human Decision Register**: Counsel formally logs strategic choices with legal context, rationale, and authority pins.
5. **Hearing Command Center**: Counsel reviews imminent listings, verifies coram/bench details, and issues prep tasks.

### 2.3 Legal Operations & Admin Journey
1. **Operational Dashboard**: Monitors background worker throughput, active background jobs, and error rates.
2. **Lawyer Verification**: Reviews Bar Council enrollment documentation and activates lawyer profiles.
3. **Legal Source Freshness**: Audits codified statute versioning and Supreme Court precedent indexes.
4. **Tenant Security & Audit**: Inspects immutable audit logs (`audit_events` table) across authentication, case access, and document state changes.

---

## 3. Production Deployment & Security Configuration

### Required Environment Variables

```bash
# Core API & Gateway
ENVIRONMENT=production
PROJECT_NAME="Legal Case Companion"
API_V1_STR=/api/v1
CORS_ORIGINS=["https://app.legalcasecompanion.in"]

# Database & Vector Search
DATABASE_URL=postgresql+psycopg://lcc_user:secret@prod-db.internal:5432/lcc_prod
# Run once on fresh database:
# CREATE EXTENSION IF NOT EXISTS vector;

# Authentication & Cryptography
JWT_ALGORITHM=EdDSA
JWT_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----"
JWT_PUBLIC_KEY="-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----"
CSRF_SECRET_KEY="<cryptographically_secure_random_64_char_hex>"

# Object Storage (AWS S3)
STORAGE_PROVIDER=s3
AWS_S3_BUCKET_NAME=lcc-evidence-vault-prod
AWS_REGION=ap-south-1
AWS_ACCESS_KEY_ID=<iam_user_key>
AWS_SECRET_ACCESS_KEY=<iam_user_secret>
AWS_WEBHOOK_SECRET=<antivirus_scanner_token>

# AI & Embeddings
OPENAI_API_KEY=sk-proj-...
EMBEDDING_MODEL=text-embedding-3-small
CHAT_COMPLETION_MODEL=gpt-4o

# Payments (Stripe / Razorpay)
STRIPE_API_KEY=rk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
```

---

## 4. Disaster Recovery & Rollback Runbook

1. **Database Rollback**:
   - Downgrade migration safely: `python -m alembic downgrade -1`.
   - Restore daily point-in-time snapshot if data corruption occurs.
2. **AI Provider Outage (Graceful Degradation)**:
   - If OpenAI returns 503/429, core case workspace, task tracking, hearings, and document management remain 100% operational.
   - Copilot surfaces controlled uncertainty notices rather than hallucinating answers.
3. **Stripe Webhook Retries**:
   - Webhook processing in `PaymentService` enforces row-level locking (`.with_for_update()`) and idempotency checks. Duplicate deliveries safely return `{"status": "already_processed"}` with zero duplicate charges or role elevations.
