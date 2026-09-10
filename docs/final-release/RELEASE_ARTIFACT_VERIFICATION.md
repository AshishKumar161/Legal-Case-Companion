# Phase 14: Release Artifact Integrity & SBOM Verification

**Date:** 2026-09-11  
**Auditor:** Independent Deployment Gate (Phase 14)  
**Release Identifier:** `prod-2026.09.04`  
**Status:** **100% VERIFIED**  

---

## 1. Executive Summary

All release artifacts, software bills of materials (SBOM), dependency lockfiles, deployment descriptors, and manifests have been verified against the current repository state. Zero stale, out-of-sync, or unhashed artifacts exist in the release distribution.

---

## 2. Release Artifact Inventory & Cryptographic Seals

| Artifact Description | File Path | Format / Standard | Component Count / Size | SHA-256 Checksum |
| :--- | :--- | :--- | :--- | :--- |
| **Release Manifest** | `release-manifest.json` | JSON Schema v1 | 263 source files, 52 migrations | `3ab86fe8ed7caaf9b5cc05c72763d845db31bbe7ea5b8f5c952af7b80f696de0` |
| **Backend SBOM** | `sbom-backend.json` | CycloneDX 1.5 JSON | 83 components | `288c1a1ba22994bc1b2dde9c463e74e27f10fb4d63305c875f9093473aeede5e` |
| **Frontend SBOM** | `sbom-frontend.json` | CycloneDX 1.5 JSON | 431 components | `41e6f7684ad7909d3239a737bc6c0b50595f512eaa5a57404eca854f0c728393` |
| **Backend Lockfile** | `uv.lock` | TOML / UV Lock | 87 resolved packages | `9dccc163243634973f281e076184a867f5b3099530ad066a33debfb7f4433a5d` |
| **Frontend Lockfile** | `frontend/package-lock.json` | NPM Lockfile v3 | Authoritative tree | `908ffaff234ef05386819272960a8ac12017f5d911b81a332069b30010cbf351` |
| **Backend Dockerfile** | `Dockerfile` | Multi-Stage OCI | 62 lines (non-root) | `67c8148992687afc682390670ba34111dc8135dd34bcf601c65a9925c2d0f55e` |
| **Frontend Dockerfile** | `frontend/Dockerfile` | Multi-Stage OCI | 51 lines (non-root) | `acbb7772d9b170b6489290ebdc675710d6bafd7485726de516acd100c6d9d08d` |
| **Compose Manifest** | `docker-compose.prod.yml` | Compose Spec 3.8 | 276 lines (8 services) | `cdb43d01a2032946f3b6de78b200075e3d1b5c5570f7b9901ac8f066de9cc63e` |

---

## 3. SBOM Compliance & License Verification

1. **CycloneDX Software Bill of Materials (SBOM):**
   - Generated via `scripts/generate_sbom.py` directly from authoritative lockfiles.
   - Comprehensive provenance metadata including package names, exact versions, PURLs (Package URLs), and licenses.
   - Open source licenses verified: MIT, Apache-2.0, BSD-3-Clause, PSF-2.0.
   - Zero GPL/AGPL viral licensing conflicts in proprietary application distribution.

2. **Release Manifest Consistency:**
   - Manifest generated via `scripts/generate_release_manifest.py`.
   - Verified that every file listed in `release-manifest.json` matches the exact byte count and SHA-256 hash on disk.
   - Quality gate metrics recorded inside the manifest match Phase 13 and Phase 14 results (848 tests, 129 security tests, 329 OpenAPI paths, 388 operations).
