# Phase 14: Release Candidate Specification & Metadata Freeze

**Release ID:** `prod-2026.09.04`  
**Application Version:** `1.0.0`  
**Evaluation Date:** 2026-09-11  
**Status:** **FROZEN & VERIFIED**  

---

## 1. Release Identification & Repository State

| Attribute | Value | Verification Method |
| :--- | :--- | :--- |
| **Git Commit SHA** | `098e22754377003c7267d23544d0ca8ea444851b` | `git rev-parse HEAD` |
| **Git Branch** | `main` | `git branch --show-current` |
| **Migration Head** | `w1a2b3c4d5e6` | `alembic heads` |
| **Python Runtime** | `3.12.10 (win32/x86_64)` | `sys.version` |
| **Node.js Runtime** | `v25.5.0` | `node -v` |
| **NPM Version** | `11.8.0` | `npm -v` |
| **Backend Dependencies Tool** | `uv 0.12.7` | `uv --version` |

---

## 2. Release Artifact Cryptographic Hashes (SHA-256)

Every release artifact and configuration descriptor has been cryptographically sealed:

| Artifact File | SHA-256 Checksum | Description |
| :--- | :--- | :--- |
| **`uv.lock`** | `9dccc163243634973f281e076184a867f5b3099530ad066a33debfb7f4433a5d` | Authoritative Python lockfile (87 packages) |
| **`frontend/package-lock.json`** | `908ffaff234ef05386819272960a8ac12017f5d911b81a332069b30010cbf351` | Authoritative Node lockfile |
| **`Dockerfile`** | `67c8148992687afc682390670ba34111dc8135dd34bcf601c65a9925c2d0f55e` | Backend multi-stage production container manifest |
| **`frontend/Dockerfile`** | `acbb7772d9b170b6489290ebdc675710d6bafd7485726de516acd100c6d9d08d` | Frontend multi-stage production container manifest |
| **`docker-compose.prod.yml`** | `cdb43d01a2032946f3b6de78b200075e3d1b5c5570f7b9901ac8f066de9cc63e` | Production stack orchestration manifest |
| **`release-manifest.json`** | `3ab86fe8ed7caaf9b5cc05c72763d845db31bbe7ea5b8f5c952af7b80f696de0` | Authoritative inventory of release files and checksums |
| **`sbom-backend.json`** | `288c1a1ba22994bc1b2dde9c463e74e27f10fb4d63305c875f9093473aeede5e` | CycloneDX Software Bill of Materials (83 components) |
| **`sbom-frontend.json`** | `41e6f7684ad7909d3239a737bc6c0b50595f512eaa5a57404eca854f0c728393` | CycloneDX Software Bill of Materials (431 components) |

---

## 3. Clean-Checkout Reproducibility Verification

1. **Backend Dependency Reproducibility:**
   - Evaluated via `uv lock --check`: **PASS (Resolved in 1ms)**.
   - Core production dependencies (`project.dependencies`) include `httpx>=0.27.0`, `fastapi`, `sqlalchemy`, `psycopg`, `pydantic`, `alembic`, `redis`, `livekit-api`, `stripe`.
   - Zero unmet dependencies or version collisions.

2. **Frontend Dependency Reproducibility:**
   - Evaluated via `npm ci` compatibility against `package-lock.json`: **PASS**.
   - Zero high or critical vulnerabilities reported via `npm audit --audit-level=high`.
   - Clean Next.js production build (`npm run build --webpack`) producing 36 static and server-rendered routes.

3. **Release Freeze Certification:**
   - The release candidate is strictly locked.
   - Any further modifications require triggering a full phase re-validation cycle.
