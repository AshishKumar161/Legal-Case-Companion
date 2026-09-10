# CI/CD Pipeline Technical Reference Manual

**Workflow Name:** `LCC Production CI Pipeline`  
**Location:** `.github/workflows/ci.yml`  
**Target Runner:** `ubuntu-latest`  

---

## 1. Pipeline Overview & Topology

The production CI pipeline executes 4 primary jobs across parallel and dependent stages:

```
+-------------------------------------------------------------------------------+
|                             TRIGGER: PR / PUSH / TAG                          |
+-------------------------------------------------------------------------------+
           |                                                   |
           v                                                   v
+-----------------------------+             +----------------------------------+
|         backend-ci          |             |           frontend-ci            |
| - uv lock check             |             | - npm ci                         |
| - compileall                |             | - npm audit                      |
| - Ruff check                |             | - tsc --noEmit                   |
| - Mypy app                  |             | - ESLint                         |
| - Secret scanner            |             | - Next.js production build       |
| - Alembic migrations        |             +----------------------------------+
| - OpenAPI contract (329/388)|                                |
| - Full pytest (848 tests)   |                                |
| - Security tests (129 tests)|                                |
+-----------------------------+                                |
           |                                                   |
           +-------------------------+-------------------------+
                                     |
                                     +-----------------------------------------+
                                     |                                         |
                                     v                                         v
                  +------------------------------------+    +------------------------------------+
                  |          docker-build-ci           |    |        release-artifacts-ci        |
                  | - Backend Dockerfile (no-cache)    |    | - CycloneDX Backend SBOM (83 pkgs) |
                  | - Frontend Dockerfile (no-cache)   |    | - CycloneDX Frontend SBOM (431)    |
                  |                                    |    | - Release Manifest (263 src files) |
                  |                                    |    | - Artifact Upload (30d retention)  |
                  +------------------------------------+    +------------------------------------+
```

---

## 2. Job Specifications

### 2.1 `backend-ci`
- **Purpose:** Exhaustive Python backend quality, type safety, database migration, contract, and test verification.
- **Service Containers:**
  - `postgres:15-alpine` (`5432:5432`, healthcheck: `pg_isready -U postgres`)
  - `redis:7-alpine` (`6379:6379`, healthcheck: `redis-cli ping`)
- **Key Commands:**
  ```bash
  uv lock --check
  uv pip install --system -e ".[dev]"
  python -m compileall app tests scripts migrations
  ruff check .
  mypy app
  python scripts/ci_secret_scanner.py
  alembic heads && alembic upgrade head
  python scripts/test_migrations_lifecycle.py
  python scripts/verify_openapi_contract.py
  pytest -v --maxfail=5
  pytest tests/security/ -v
  ```

### 2.2 `frontend-ci`
- **Purpose:** TypeScript compilation, lint enforcement, dependency vulnerability audit, and production build generation.
- **Node Environment:** Node.js 20 LTS with NPM caching against `frontend/package-lock.json`.
- **Key Commands:**
  ```bash
  npm ci
  npm audit --audit-level=high
  npx tsc --noEmit
  npm run lint
  npm run build
  ```

### 2.3 `docker-build-ci`
- **Purpose:** Validates that both backend and frontend Docker images build cleanly without cache corruption, secrets, or missing layers.
- **Key Actions:**
  - `docker/setup-buildx-action@v3`
  - `docker/build-push-action@v5` (Backend & Frontend, `push: false`, `no-cache: true`).

### 2.4 `release-artifacts-ci`
- **Purpose:** Generates reproducible release manifests and CycloneDX SBOMs for software supply-chain provenance.
- **Outputs:**
  - `release-manifest.json` (SHA-256 sealed source inventory)
  - `sbom-backend.json` (CycloneDX 1.5 JSON)
  - `sbom-frontend.json` (CycloneDX 1.5 JSON)
  - Uploaded via `actions/upload-artifact@v4`.
