# Legal Case Companion — Production Deployment Security & Supply-Chain Hardening

**Document Reference**: `docs/22_DEPLOYMENT_SECURITY.md`  
**Phase**: Phase XVI — Production Security Hardening, Privacy, Data Protection & Deployment Readiness  
**Target System**: Legal Case Companion (LCC)  
**Deployment Model**: Multi-Container Docker / Orchestrated Cloud Runtime

---

## 1. Production Container Architecture

### 1.1 Backend Container (`Dockerfile`)
- **Base Image**: Pinned minimal runtime `python:3.11-slim`.
- **Multi-Stage Build**:
  - `builder` stage installs build tooling (`build-essential`, `libpq-dev`) and compiles wheels into a virtual environment (`/opt/venv`).
  - `runner` stage copies ONLY the compiled `/opt/venv` and application code, keeping the attack surface minimal.
- **Non-Root User**: Runs under an unprivileged system user `appuser` (`UID/GID 1000`).
- **Health Check**: Configured `HEALTHCHECK` checking `/api/v1/health/live` every 30 seconds.
- **Root Filesystem**: All application paths are owned by `appuser`.

### 1.2 Frontend Container (`frontend/Dockerfile`)
- **Base Image**: Pinned minimal runtime `node:20-alpine`.
- **Multi-Stage Build**:
  - `deps` stage: runs `npm ci` with immutable package locks.
  - `builder` stage: executes Next.js production compilation (`npm run build`).
  - `runner` stage: copies only `/app/.next`, `/app/public`, `/app/node_modules`, and `/app/package.json`.
- **Non-Root User**: Runs under `nextjs` system user (`UID/GID 1001`).
- **Telemetry Disabled**: `NEXT_TELEMETRY_DISABLED=1`.
- **Source Maps**: `productionBrowserSourceMaps: false` to prevent leaking frontend source code.

---

## 2. Environment Segregation Matrix

| Configuration Variable | Development (`development`) | Test (`test`) | Production (`production`) |
| :--- | :--- | :--- | :--- |
| `DEBUG` | `true` | `false` | `false` (Strictly enforced) |
| `DATABASE_URL` | SQLite or Local Postgres | PostgreSQL container / test DB | Managed PostgreSQL (psycopg driver) |
| `ENABLE_TEST_PAYMENTS` | `true` | `true` | `false` (Strictly enforced) |
| `EMAIL_PROVIDER` | `console` | `console` | `sendgrid`, `smtp`, or `ses` |
| `JWT Keys` | Auto-generated ephemeral keys | Auto-generated or test keys | High-entropy PEM Ed25519 keys (Strictly required) |
| `CSRF_SECRET_KEY` | Dev mock permitted | Dev mock permitted | 32+ byte cryptographic secret (Strictly required) |
| `Storage Provider` | `LocalMockStorageProvider` | `LocalMockStorageProvider` | `S3StorageProvider` (Private S3 bucket) |
| `Malware Scanner` | Mock or localhost ClamAV | Mock scanner | ClamAV TCP daemon (Fails closed) |
| `Redis` | Optional / Local Redis | Optional / Mock Redis | Dedicated cluster (Fails closed) |

---

## 3. Production Deployment Security Checklist

Prior to promoting any release to production, the deployment pipeline must verify:

- [ ] **Secrets & Credentials**:
  - [ ] `JWT_PRIVATE_KEY` and `JWT_PUBLIC_KEY` are valid PEM strings injected via secret manager.
  - [ ] `CSRF_SECRET_KEY` is a unique, cryptographically random string (min 32 bytes).
  - [ ] `DATABASE_URL` points to an authenticated PostgreSQL instance; SQLite is rejected.
  - [ ] `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` are scoped to least-privilege S3 bucket policy.
  - [ ] Zero secrets exist in repository source code or Docker build logs.
- [ ] **Network & TLS**:
  - [ ] All public endpoints terminate TLS 1.3 with valid CA certificates.
  - [ ] HSTS preload is enabled on root and all subdomains.
  - [ ] Redis and PostgreSQL instances are isolated in private VPC subnets with no public exposure.
- [ ] **Application Runtime**:
  - [ ] FastAPI startup executes `settings.validate_production_secrets()` without error.
  - [ ] Container runs as non-root `appuser`.
  - [ ] ClamAV scanner is reachable; health probe `/api/v1/health/details` reports `HEALTHY`.
- [ ] **Database & Migrations**:
  - [ ] `alembic upgrade head` executes with zero pending or branched migrations.
  - [ ] Database user has DML permissions but lacks superuser authority.

---

## 4. Software Bill of Materials (SBOM) & Supply Chain Security

### 4.1 SBOM Generation Procedure
LCC supports automated SBOM generation in CycloneDX / SPDX format using `pip-audit` and `cyclonedx-bom`:

1. **Python Backend SBOM**:
   ```bash
   pip install cyclonedx-bom
   cyclonedx-py requirements pyproject.toml -o sbom-backend.json
   ```
2. **Frontend Node.js SBOM**:
   ```bash
   cd frontend
   npx @cyclonedx/cyclonedx-npm --output-file sbom-frontend.json
   ```

### 4.2 Vulnerability Scanning Gates
Automated dependency scanning runs in the CI/CD pipeline:
- `npm audit`: Fails build if any `high` or `critical` vulnerabilities are present in production dependencies.
- `pip-audit`: Fails build if any known CVEs affect installed backend packages.

---

## 5. Security Release Gates

A production build or PR merge is **STRICTLY BLOCKED** if any of the following occur:
1. **Critical or High Dependency Vulnerability** in production runtime.
2. **Alembic Migration Divergence**: Multi-head migrations or missing migrations.
3. **Secret Scan Detection**: Any token, private key, or password found in git diff.
4. **Automated Test Failure**: Any regression in authorization, session isolation, or evidence custody tests.
5. **Lint / Static Analysis Error**: Security rule failures in `ruff` or TypeScript compiler.
