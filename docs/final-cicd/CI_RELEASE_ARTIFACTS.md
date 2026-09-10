# CI/CD Release Artifacts & Software Supply Chain Provenance

**Date:** 2026-09-11  
**Status:** **VERIFIED & AUTOMATED**  

---

## 1. Executive Summary

As part of the CI/CD hardening, automated generation, integrity validation, and uploading of software supply-chain provenance artifacts was integrated into `.github/workflows/ci.yml`. Every successful build on `main` or release tag generates and preserves immutable artifacts.

---

## 2. Artifact Specifications & Generators

| Artifact File | Generating Tool | Standard / Specification | Components Documented | SHA-256 Checksum |
| :--- | :--- | :--- | :--- | :--- |
| **`release-manifest.json`** | `scripts/generate_release_manifest.py` | LCC Manifest Schema v1 | 263 source files, 52 migrations | Sealed dynamically per commit |
| **`sbom-backend.json`** | `scripts/generate_sbom.py` | CycloneDX 1.5 JSON | 83 backend packages | Sealed dynamically per commit |
| **`sbom-frontend.json`** | `scripts/generate_sbom.py` | CycloneDX 1.5 JSON | 431 frontend packages | Sealed dynamically per commit |

---

## 3. Artifact Integrity & Exclusion Safeguards

1. **Deterministic Sourcing:**
   - `sbom-backend.json` derives directly from `uv.lock`.
   - `sbom-frontend.json` derives directly from `frontend/package-lock.json`.
   - `release-manifest.json` inspects git-tracked files and computes SHA-256 hashes of the actual checked-out filesystem.
2. **Exclusion of Sensitive Data:**
   - Artifacts never contain `.env` files, private cryptographic keys, test databases (`test.db`, `test_pytest.db`), or local consultation recordings (`storage/recordings/`).
   - The upload step (`actions/upload-artifact@v4`) targets only the 3 canonical provenance files.
3. **Retention & Traceability:**
   - Configured with `retention-days: 30` on GitHub Actions artifact storage.
   - Pinned to the commit SHA and workflow run ID for complete end-to-end traceability.
