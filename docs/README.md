# Legal Case Companion (LCC) — Documentation Index

Welcome to the comprehensive technical documentation repository for the **Legal Case Companion** platform. This index organizes all architectural specifications, operational runbooks, security audits, and validation reports.

---

## 📚 Documentation Catalog

### 1. Operations, Deployment & Disaster Recovery (`docs/ops/`)
Core deployment topologies, infrastructure automation, and business continuity runbooks.

- [LCC_DEPLOYMENT_ARCHITECTURE.md](ops/LCC_DEPLOYMENT_ARCHITECTURE.md) — Multi-tier AWS/Docker container architecture, KMS encryption, TLS termination, and reverse proxy topology.
- [LCC_DISASTER_RECOVERY_PLAN.md](ops/LCC_DISASTER_RECOVERY_PLAN.md) — Disaster recovery strategy, RPO/RTO objectives (< 15 min), and cryptographic envelope backup protocols.
- [LCC_PRODUCTION_DEPLOYMENT_CHECKLIST.md](ops/LCC_PRODUCTION_DEPLOYMENT_CHECKLIST.md) — Step-by-step production gate checklist and rollout criteria.

---

### 2. Engineering Verification & Validation Reports (`docs/reports/`)
Milestone reports, remediation tracking, and pre-production test certifications.

- [LCC_FINAL_PRODUCTION_READINESS_REPORT.md](reports/LCC_FINAL_PRODUCTION_READINESS_REPORT.md) — Comprehensive production readiness scorecard across all subsystems.
- [LCC_STAGE_4_DEVSECOPS_REPORT.md](reports/LCC_STAGE_4_DEVSECOPS_REPORT.md) — DevSecOps pipeline certification (Trivy, Bandit, Secret Scanning, SBOM).
- [LCC_STAGE_4_CI_CD_VALIDATION_REPORT.md](reports/LCC_STAGE_4_CI_CD_VALIDATION_REPORT.md) — GitHub Actions CI/CD workflows, automation gates, and matrix execution.
- [LCC_STAGE_4_DR_VALIDATION_REPORT.md](reports/LCC_STAGE_4_DR_VALIDATION_REPORT.md) — Validated PostgreSQL DR drill benchmarks, envelope encryption, and restore telemetry.
- [LCC_STAGE_4_OPERATIONAL_READINESS_REPORT.md](reports/LCC_STAGE_4_OPERATIONAL_READINESS_REPORT.md) — SRE observability, OpenTelemetry traces, Prometheus metrics, and Grafana alerting.
- [LCC_FINAL_SECURITY_AND_PRODUCTION_VERIFICATION.md](reports/LCC_FINAL_SECURITY_AND_PRODUCTION_VERIFICATION.md) — End-to-end security audits, JWT rotation, and IDOR validation.
- [LCC_FINAL_INFRASTRUCTURE_SECURITY_REPORT.md](reports/LCC_FINAL_INFRASTRUCTURE_SECURITY_REPORT.md) — Infrastructure security, ClamAV antivirus quarantine, and network egress controls.
- [LCC_FINAL_ENGINEERING_GAP_CLOSURE.md](reports/LCC_FINAL_ENGINEERING_GAP_CLOSURE.md) — Root cause analysis and resolution of historical bugs.
- [LCC_FINAL_ENGINEERING_VERIFICATION.md](reports/LCC_FINAL_ENGINEERING_VERIFICATION.md) — Full automated test suite verification (unit, integration, e2e, performance).
- [LCC_PRE_PRODUCTION_BACKEND_VALIDATION.md](reports/LCC_PRE_PRODUCTION_BACKEND_VALIDATION.md) — Backend service integration and contract compliance.
- [STAGE_3_BACKEND_ENGINEERING_REPORT.md](reports/STAGE_3_BACKEND_ENGINEERING_REPORT.md) — Stage 3 backend architectural remediation report.
- [STAGE_2_REMEDIATION_REPORT.md](reports/STAGE_2_REMEDIATION_REPORT.md) — Stage 2 code hygiene and static analysis remediation.
- [LCC_BACKEND_ENGINEERING_STATUS.md](reports/LCC_BACKEND_ENGINEERING_STATUS.md) — Engineering status tracking.
- [IMPROVEMENT_ROADMAP.md](reports/IMPROVEMENT_ROADMAP.md) — Long-term architectural improvement roadmap.

---

### 3. Audits, Security & Bug Inventories (`docs/audit/` & `docs/security/`)
Vulnerability scanning, threat modeling, and bug registers.

- [BUG_INVENTORY.md](audit/BUG_INVENTORY.md) — Authoritative bug inventory with resolution matrix and regression test coverage.
- [SECURITY_AUDIT.md](audit/SECURITY_AUDIT.md) — OWASP Top 10 threat model and API penetration audit.
- [DEVOPS_AUDIT.md](audit/DEVOPS_AUDIT.md) — Container security, environment separation, and CI secret hygiene audit.
- [AUDIT_REPORT.md](audit/AUDIT_REPORT.md) — Full codebase quality and security audit summary.
- [API_AUTHORIZATION_MATRIX.md](security/API_AUTHORIZATION_MATRIX.md) — Role-based access control (RBAC) endpoint authorization permissions.
- [IDOR_TEST_MATRIX.md](security/IDOR_TEST_MATRIX.md) — Insecure Direct Object Reference protection test cases.
- [PROMPT_SECURITY.md](security/PROMPT_SECURITY.md) — LLM prompt injection defense and Indian legal reasoning guardrails.

---

### 4. Core System Specifications (00–56)
Authoritative domain blueprints, schemas, and operational architectures.

| Document | Topic | Description |
| :--- | :--- | :--- |
| [00_PROJECT_CONTEXT.md](00_PROJECT_CONTEXT.md) | Overview | Vision, problem statement, and high-level goals. |
| [01_SYSTEM_ARCHITECTURE.md](01_SYSTEM_ARCHITECTURE.md) | Architecture | Modular monolith topology and inter-service communications. |
| [02_DATABASE_DESIGN.md](02_DATABASE_DESIGN.md) | Database | Authoritative SQLAlchemy models, schema constraints, and pgvector indexes. |
| [03_API_SPECIFICATION.md](03_API_SPECIFICATION.md) | API | REST API contract definitions and OpenAPI schema specifications. |
| [04_AUTHORIZATION_SECURITY.md](04_AUTHORIZATION_SECURITY.md) | Security | Authentication, JWT claims, refresh tokens, and RBAC policies. |
| [05_BACKEND_MODULES.md](05_BACKEND_MODULES.md) | Backend | Domain services: cases, evidence, consultations, payments. |
| [06_AI_INTEGRATION.md](06_AI_INTEGRATION.md) | AI / NLP | Indian Kanoon RAG pipeline, legal reasoning, and citation accuracy. |
| [07_FILE_DOCUMENT_SYSTEM.md](07_FILE_DOCUMENT_SYSTEM.md) | Storage | Evidence Locker, S3/MinIO storage, and ClamAV virus scanning. |
| [08_FRONTEND_ARCHITECTURE.md](08_FRONTEND_ARCHITECTURE.md) | Frontend | Next.js 16 / React 19 App Router architecture and design tokens. |
| [09_INFRASTRUCTURE_DEPLOYMENT.md](09_INFRASTRUCTURE_DEPLOYMENT.md) | Infrastructure | Docker, Redis, PostgreSQL, and reverse proxy deployment. |
| [10_TESTING_STRATEGY.md](10_TESTING_STRATEGY.md) | QA | Testing taxonomy: unit, integration, e2e, and security tests. |
| [18_DISASTER_RECOVERY.md](18_DISASTER_RECOVERY.md) | DR | DR operational procedures and point-in-time recovery. |
| [24_PRODUCTION_DEPLOYMENT_RUNBOOK.md](24_PRODUCTION_DEPLOYMENT_RUNBOOK.md) | Runbook | Production deployment runbook and smoke testing steps. |
| [27_NATIVE_VIDEO_MEETING_SYSTEM.md](27_NATIVE_VIDEO_MEETING_SYSTEM.md) | WebRTC | Native video consultation engine and signaling protocols. |
| [29_SRE_SLOS_AND_ALERTING.md](29_SRE_SLOS_AND_ALERTING.md) | SRE | Service level objectives, error budgets, and alert rules. |

---

### 5. Legal & Compliance Policies (`docs/legal/`)
Statutory, regulatory, and privacy policies governing the Indian jurisdiction.

- [TERMS_OF_SERVICE.md](legal/TERMS_OF_SERVICE.md) — User terms and conditions.
- [PRIVACY_NOTICE.md](legal/PRIVACY_NOTICE.md) — Digital Personal Data Protection Act (DPDPA 2023) privacy framework.
- [ADVOCATE_TERMS.md](legal/ADVOCATE_TERMS.md) — Bar Council of India compliant advocate engagement terms.
- [DOCUMENT_RETENTION_POLICY.md](legal/DOCUMENT_RETENTION_POLICY.md) — Bharatiya Sakshya Adhiniyam (BSA 2023) electronic record retention rules.
- [REFUND_POLICY.md](legal/REFUND_POLICY.md) — Client payment cancellation and consultation refund policies.

---

### 6. Interactive Walkthrough & Runbooks
- [walkthrough.md](walkthrough.md) — Step-by-step developer and operator walkthrough guide.
- [production_runbook.md](production_runbook.md) — Operational runbook for site reliability engineers.
