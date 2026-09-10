# CI/CD Security, Supply Chain & Permissions Policy

**Date:** 2026-09-11  
**Status:** **ACTIVE & ENFORCED**  

---

## 1. Principle of Least Privilege (GitHub Token Permissions)

All CI workflows adhere strictly to the principle of least privilege:
- The top-level workflow defines:
  ```yaml
  permissions:
    contents: read
  ```
- No write permissions (`contents: write`, `packages: write`, `id-token: write`) are granted in standard CI execution.
- Pull request workflows triggered by forks run under read-only permissions and have zero access to organization or repository secrets.
- Pull request target workflows (`pull_request_target`) are explicitly avoided to eliminate pwn-request vulnerabilities.

---

## 2. Secret Management & Log Scrubbing in CI

1. **Zero Real Production Secrets:**
   - CI executes with strictly simulated test credentials (`POSTGRES_PASSWORD=postgrespassword`, `ENVIRONMENT=test`).
   - Production secrets (`sk_live_...`, SendGrid API keys, LiveKit master secrets) are never committed to the repository or stored as CI repository secrets for PR test runs.
2. **Log Exposure Prevention:**
   - Workflows avoid commands that print environment tables (`env`, `printenv`, `set -x`).
   - The application runtime incorporates `app/core/logging_filter.py` which scrubs bearer tokens, presigned S3 URLs, password keys, and JWT strings before emitting JSON log records.
3. **Static Secret Scanning Gate (`scripts/ci_secret_scanner.py`):**
   - Automatically executes during `backend-ci`.
   - Scans all git-tracked files against cryptographic key headers, Stripe live keys, SendGrid tokens, and AWS access keys.
   - Forbids tracking any `.env` files in git.

---

## 3. Supply Chain Security & Action Pinning

Every third-party GitHub Action used in the pipeline has been audited for provenance, maintenance, and reputation:

| GitHub Action | Version Pin | Source / Publisher | Purpose | Security Evaluation |
| :--- | :--- | :--- | :--- | :--- |
| `actions/checkout` | `@v4` | GitHub Official | Repository clone | Verified official action |
| `astral-sh/setup-uv` | `@v5` | Astral Software | UV package manager | Cryptographically verified binary installation |
| `actions/setup-python` | `@v5` | GitHub Official | Python 3.12 runtime | Verified official action |
| `actions/setup-node` | `@v4` | GitHub Official | Node.js 20 runtime | Verified official action |
| `docker/setup-buildx-action` | `@v3` | Docker Official | Docker Buildx engine | Verified official action |
| `docker/build-push-action` | `@v5` | Docker Official | Container compilation | Verified official action |
| `actions/upload-artifact` | `@v4` | GitHub Official | Artifact storage | Verified official action |

---

## 4. Dependency Vulnerability & Lockfile Policies

1. **Backend Dependency Integrity:**
   - Authoritative lockfile: `uv.lock` (SHA-256 sealed).
   - Invariant: `uv lock --check` runs as step 1 in backend CI. Any uncommitted package addition or version drift fails the build immediately.
2. **Frontend Dependency Integrity:**
   - Authoritative lockfile: `frontend/package-lock.json`.
   - Mandatory installation command: `npm ci` (strictly forbids `npm install` in CI).
   - Security audit command: `npm audit --audit-level=high` fails the build on any high or critical advisory.
