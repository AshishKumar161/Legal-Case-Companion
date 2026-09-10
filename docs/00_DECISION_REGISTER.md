# Centralized Decision Register

> [!NOTE]
> **AUTHORITATIVE ARCHITECTURE DECISION REGISTER (ADR)**
> The authoritative record for the complete Phase 1 architecture decisions (Database Identity Strategy, Authentication & Security Strategy, Domain Model Strategy) is now **`docs/15_ARCHITECTURE_DECISION_REGISTER.md`**.
> The partial draft `docs/14_ARCHITECTURE_DECISION_REGISTER.md` has been deprecated and removed to prevent fragmentation.

| Area | Decision | Status | Source | Notes |
|---|---|---|---|---|
| Architecture | Modular Monolith | FINAL | 01_SYSTEM_ARCHITECTURE.md | Approved to minimize operational complexity |
| Backend framework | FastAPI | FINAL | 01_SYSTEM_ARCHITECTURE.md | Approved |
| Database | PostgreSQL | FINAL | 02_DATABASE_DESIGN.md | Approved |
| ORM | SQLAlchemy | FINAL | 02_DATABASE_DESIGN.md | Approved |
| Migrations | Alembic | FINAL | 02_DATABASE_DESIGN.md | Approved |
| Authentication | JWT with refresh-tokens | FINAL | 15_ARCHITECTURE_DECISION_REGISTER.md | Approved |
| Authorization | Resource-based | FINAL | 15_ARCHITECTURE_DECISION_REGISTER.md | Strict boundaries per case/user |
| Storage | AWS S3 | FINAL | 07_FILE_DOCUMENT_SYSTEM.md | Object storage for legal docs |
| Cloud/deployment | Render | FINAL | 09_INFRASTRUCTURE_DEPLOYMENT.md | Approved for MVP |
| AI provider | OpenAI | FINAL | 06_AI_INTEGRATION.md | Approved |
| AI model | Undefined | DECISION REQUIRED | 06_AI_INTEGRATION.md | Needs selection |
| Embeddings | Undefined | DECISION REQUIRED | 06_AI_INTEGRATION.md | Needs selection |
| Vector storage | Undefined | DECISION REQUIRED | 06_AI_INTEGRATION.md | Needs selection |
| Payments | Stripe (Proposed) | DECISION REQUIRED | 08_PAYMENT_CONSULTATION.md | Not final unless explicitly approved |
| Notifications | Undefined | DECISION REQUIRED | 08_PAYMENT_CONSULTATION.md | Email/SMS provider pending |
| Video | Undefined | DECISION REQUIRED | 08_PAYMENT_CONSULTATION.md | Video consultation provider pending |
| Caching | Undefined | DECISION REQUIRED | 09_INFRASTRUCTURE_DEPLOYMENT.md | Whether dedicated cache is needed |
| Workers | Undefined | DECISION REQUIRED | 09_INFRASTRUCTURE_DEPLOYMENT.md | Queue technology pending |
| Testing | Continuous per phase | FINAL | 10_TESTING_STRATEGY.md | Mandatory validation per phase |
| CI/CD | Undefined | DECISION REQUIRED | 09_INFRASTRUCTURE_DEPLOYMENT.md | CI/CD platform pending |
| Monitoring | Undefined | DECISION REQUIRED | 09_INFRASTRUCTURE_DEPLOYMENT.md | Stack/tools pending |
| Security | Multi-layered | FINAL | 15_ARCHITECTURE_DECISION_REGISTER.md | Case isolation, document protection |
| Data retention | Undefined | DECISION REQUIRED | 04_AUTHORIZATION_SECURITY.md | Policy pending |
