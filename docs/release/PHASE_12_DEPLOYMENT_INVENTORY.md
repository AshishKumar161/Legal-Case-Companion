# Phase 12: Deployment & Operational Manifest Inventory

**Date:** 2026-09-10  
**Phase:** Phase 12: Production Readiness & Hardening  

---

## 1. Overview of Deployment Assets

This inventory catalogs every deployment manifest, container definition, orchestration file, continuous integration pipeline, and operational script in the Legal Case Companion (LCC) repository.

| Asset Path | Component | Purpose | Target Runtime |
| :--- | :--- | :--- | :--- |
| `Dockerfile` | Backend Service | Multi-stage container build for FastAPI backend, background worker, and scheduler | Docker / Container Engine |
| `frontend/Dockerfile` | Frontend App | 3-stage standalone container build for Next.js 16 App Router frontend | Docker / Container Engine |
| `.dockerignore` | Backend Context | Prevents `.venv`, `.git`, `.env*`, test artifacts from entering backend build | Docker CLI |
| `frontend/.dockerignore` | Frontend Context | Prevents host `node_modules`, `.next`, `.env*` from entering frontend build | Docker CLI |
| `docker-compose.yml` | Local Development | Multi-container dev environment with hot-reload and local SQLite/Postgres options | Local Dev / QA |
| `docker-compose.prod.yml` | Self-Hosted Prod | Hardened multi-container production orchestration (Postgres, Redis, ClamAV, Turn, Backend, Worker, Scheduler, Frontend) | Self-Hosted / On-Prem |
| `render.yaml` | Cloud PaaS Deploy | Declarative infrastructure-as-code for Render cloud deployment (web, worker, scheduler, database) | Render PaaS |
| `.github/workflows/ci.yml` | CI/CD Pipeline | Automated quality gates: Python lint, type check (mypy), linear migrations, pytest suite, frontend lint/build, docker smoke | GitHub Actions |
| `scripts/verify_production_config.py` | Config Diagnostics | Pre-flight environment variable validation, network reachability, and secret presence verification | Operational CLI |
| `scripts/verify_backup_restore.py` | Disaster Recovery | Atomic backup, SHA-256 verification, clean target restore, and data integrity audit | Operational CLI |
| `scripts/production_smoke_test.py` | Post-Deploy Validation | 7-step zero-destructive smoke verification (health, readiness, details, registration, login, cases, uploads, ws-tickets) | Release Smoke Runner |
| `scripts/generate_sbom.py` | Supply Chain | CycloneDX v1.5 compliant Software Bill of Materials (SBOM) generator for Python & NPM packages | Release Pipeline |
| `scripts/generate_release_manifest.py` | Release Governance | Cryptographic release manifest recording commit SHA, Alembic head, quality gates, and SBOM hashes | Release Pipeline |
| `release-manifest.json` | Release Record | Machine-readable release artifact cataloging build metadata and quality gate decisions | Audit / Compliance |
| `sbom-backend.json` | Supply Chain | CycloneDX SBOM cataloging all 83 backend dependencies and licenses | Audit / Compliance |
| `sbom-frontend.json` | Supply Chain | CycloneDX SBOM cataloging all 431 frontend dependencies | Audit / Compliance |

---

## 2. Container & Image Architecture

### Backend Container (`Dockerfile`)
- **Base Image:** `python:3.11-slim` (minimal attack surface, glibc compatibility for cryptography/psycopg).
- **Multi-Stage Build:**
  - `builder` stage: Installs `build-essential` and `libpq-dev`, builds `/opt/venv`, and pre-compiles wheel packages.
  - `runner` stage: Copies only `/opt/venv` and necessary application code (`app/`, `alembic.ini`, `migrations/`). Strips compiler toolchains.
- **Security & User:** Runs as non-root system user `appuser:appuser`.
- **Healthcheck:** Configured with `curl -f http://localhost:8000/api/v1/health/live` (30s interval, 5s timeout, 3 retries).
- **Port:** Exposes internal HTTP port 8000.

### Frontend Container (`frontend/Dockerfile`)
- **Base Image:** `node:20-alpine` (hardened Alpine Linux).
- **Multi-Stage Build:**
  - `deps` stage: Installs production and dev dependencies via `npm ci` with lockfile caching.
  - `builder` stage: Executes `npm run build` using Next.js Webpack engine.
  - `runner` stage: Minimal Alpine runner copying only `.next`, `public`, `node_modules`, and `next.config.ts`.
- **Security & User:** Runs as non-root system user `nextjs:nodejs` (UID 1001).
- **Healthcheck:** Configured with `wget --spider http://localhost:3000/` (20s interval, 5s timeout, 3 retries).
- **Port:** Exposes internal HTTP port 3000.

---

## 3. Network Exposure & Service Topology

| Service | Container Name | Internal Port | Host Port Published | Network Scope | Exposure Justification |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **PostgreSQL** | `lcc_postgres_prod` | 5432 | *None* | `lcc_internal` only | Internal persistence; database never exposed publicly. |
| **Redis** | `lcc_redis_prod` | 6379 | *None* | `lcc_internal` only | Internal cache & presence; never exposed publicly. |
| **ClamAV** | `lcc_clamav_prod` | 3310 | *None* | `lcc_internal` only | Internal antivirus daemon; never exposed publicly. |
| **Coturn TURN** | `lcc_coturn_prod` | 3478, 5349 | 3478 (TCP/UDP), 5349 (TCP/UDP) | Host / Internet | NAT traversal relay for WebRTC video consultations. |
| **Backend API** | `lcc_backend_prod` | 8000 | 8000:8000 | Reverse Proxy / Host | REST API & WebSocket signaling gateway. |
| **Worker** | `lcc_worker_prod` | *None* | *None* | `lcc_internal` only | Background async job processor; no inbound network ports. |
| **Scheduler** | `lcc_scheduler_prod`| *None* | *None* | `lcc_internal` only | Background job scheduler; no inbound network ports. |
| **Frontend** | `lcc_frontend_prod`| 3000 | 3000:3000 | Reverse Proxy / Host | User-facing Next.js web application. |
