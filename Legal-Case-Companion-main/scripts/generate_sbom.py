#!/usr/bin/env python3
"""Legal Case Companion (LCC) — Production Software Bill of Materials (SBOM) Generator.

Generates CycloneDX v1.5 compliant JSON SBOM manifests for:
1. Python Backend Dependencies (pyproject.toml / installed wheels)
2. Node.js Frontend Dependencies (frontend/package-lock.json)
"""

import json
import os
import sys
import uuid
from datetime import UTC, datetime
from importlib.metadata import distributions

# Ensure project root is on sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def generate_backend_sbom() -> dict:
    """Generates CycloneDX SBOM for Python backend runtime."""
    components = []
    for dist in distributions():
        name = dist.metadata.get("Name", "unknown")
        version = dist.metadata.get("Version", "unknown")
        summary = dist.metadata.get("Summary", "")
        license_str = dist.metadata.get("License", "Unknown")

        components.append(
            {
                "type": "library",
                "bom-ref": f"pkg:pypi/{name}@{version}",
                "name": name,
                "version": version,
                "description": summary,
                "licenses": [{"license": {"name": license_str}}],
                "purl": f"pkg:pypi/{name}@{version}",
            }
        )

    # Sort components by name
    components.sort(key=lambda x: x["name"].lower())

    sbom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:{uuid.uuid4()}",
        "version": 1,
        "metadata": {
            "timestamp": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "component": {
                "type": "application",
                "name": "legal-case-companion-backend",
                "version": "1.0.0",
                "description": "LCC Production FastAPI Backend Service",
            },
        },
        "components": components,
    }
    return sbom


def generate_frontend_sbom() -> dict:
    """Generates CycloneDX SBOM for Node.js frontend runtime from package-lock.json."""
    lock_path = os.path.join(PROJECT_ROOT, "frontend", "package-lock.json")
    components = []

    if os.path.exists(lock_path):
        with open(lock_path, encoding="utf-8") as f:
            lock_data = json.load(f)

        packages = lock_data.get("packages", {})
        for pkg_path, pkg_info in packages.items():
            if not pkg_path:  # Root package
                continue
            pkg_name = pkg_info.get("name") or pkg_path.split("node_modules/")[-1]
            pkg_version = pkg_info.get("version", "unknown")
            dev = pkg_info.get("dev", False)

            components.append(
                {
                    "type": "library",
                    "bom-ref": f"pkg:npm/{pkg_name}@{pkg_version}",
                    "name": pkg_name,
                    "version": pkg_version,
                    "scope": "optional" if dev else "required",
                    "purl": f"pkg:npm/{pkg_name}@{pkg_version}",
                }
            )

    components.sort(key=lambda x: x["name"].lower())

    sbom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:{uuid.uuid4()}",
        "version": 1,
        "metadata": {
            "timestamp": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "component": {
                "type": "application",
                "name": "legal-case-companion-frontend",
                "version": "1.0.0",
                "description": "LCC Production Next.js Frontend Application",
            },
        },
        "components": components,
    }
    return sbom


def main():
    backend_sbom = generate_backend_sbom()
    frontend_sbom = generate_frontend_sbom()

    backend_out = os.path.join(PROJECT_ROOT, "sbom-backend.json")
    frontend_out = os.path.join(PROJECT_ROOT, "sbom-frontend.json")

    with open(backend_out, "w", encoding="utf-8") as f:
        json.dump(backend_sbom, f, indent=2)

    with open(frontend_out, "w", encoding="utf-8") as f:
        json.dump(frontend_sbom, f, indent=2)

    print("=" * 72)
    print("  LEGAL CASE COMPANION — SBOM GENERATION COMPLETE")
    print("=" * 72)
    print(f"  - Backend SBOM  : {backend_out} ({len(backend_sbom['components'])} components)")
    print(f"  - Frontend SBOM : {frontend_out} ({len(frontend_sbom['components'])} components)")
    print("=" * 72)


if __name__ == "__main__":
    main()
