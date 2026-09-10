# 34 — PRODUCTION RELEASE GOVERNANCE & CHANGE MANAGEMENT

## 1. Change Management Policy

All production changes to Legal Case Companion (LCC) follow a strict, auditable release engineering process. No code or configuration reaches production through ad-hoc or unverified mechanisms.

### Core Release Rules
1. **Trunk-Based Release Model**: All releases are tagged from the `main` branch after passing all CI/CD quality gates.
2. **Machine-Readable Release Manifest**: Every release generates a verified `release-manifest.json` linking the commit SHA, migration head, SBOM checksums, and sign-offs.
3. **Automated Gate Enforcement**: Any failing gate immediately aborts deployment.
4. **Zero-Downtime Rollback Guarantee**: Every release must possess an executable container image rollback plan that operates without requiring backward-incompatible database schema rollbacks.

---

## 2. Mandatory Release Gates

| Gate # | Quality Gate | Verification Command | Enforcement |
| :---: | :--- | :--- | :--- |
| **G1** | **Python Code Quality** | `ruff check .` | 0 errors, 0 warnings |
| **G2** | **Single Linear Migration Head** | `alembic heads` | Exactly 1 head (`k1a2b3c4d5e6`) |
| **G3** | **Security Hardening Suite** | `pytest tests/security/ -v` | 100% pass (33/33) |
| **G4** | **End-to-End Scenario Suite** | `pytest tests/e2e/ -v` | 100% pass |
| **G5** | **Integration Test Suite** | `pytest tests/integration/ -v` | 100% pass |
| **G6** | **Frontend Production Build** | `npm run build` in `frontend/` | 0 TypeScript errors, 25 routes |
| **G7** | **Frontend Supply Chain Audit**| `npm audit --audit-level=high` | 0 high/critical vulnerabilities |
| **G8** | **Software Bill of Materials** | `python scripts/generate_sbom.py` | CycloneDX v1.5 validated |
| **G9** | **Release Manifest Integrity** | `python scripts/generate_release_manifest.py` | SHA-256 hashes generated |

---

## 3. Production Deployment Freeze Triggers

A production release is **AUTOMATICALLY BLOCKED** under any of the following conditions:
1. **Active SEV-1 or SEV-2 Incident**: No deployment permitted while an incident is in `DETECTED`, `ACKNOWLEDGED`, or `INVESTIGATING`.
2. **Error Budget Exhausted**: Rolling 30-day API availability $< 99.90\%$ or error budget consumed $\ge 100\%$.
3. **Alembic Branch Conflict**: Multiple heads present in migration history.
4. **Legal / Compliance Hold**: Active statutory inquiry or unreviewed critical privacy change.
5. **Holiday / High-Volume Court Calendar Window**: Release freeze during supreme court / high court major filing deadline weeks unless resolving a critical SEV-1 vulnerability.
