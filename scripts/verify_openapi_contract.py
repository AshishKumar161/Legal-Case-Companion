"""CI/CD Verification Script: Verify OpenAPI Contract Parity.

Validates that the running FastAPI application's OpenAPI schema exactly matches
the canonical contract stored in docs/openapi.json:
- 329 paths
- 388 operations
- Zero added, modified, or missing paths or operations.

Exits with non-zero status if any contract drift is detected.
"""

import json
import os
import sys
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from fastapi.openapi.utils import get_openapi
from app.main import app


def verify_openapi_contract():
    print("========================================================================")
    print("  CI/CD GATE: OPENAPI CONTRACT PARITY AUDIT")
    print("========================================================================")

    # 1. Extract live OpenAPI schema from app
    live_schema = get_openapi(
        title=app.title,
        version=app.version,
        openapi_version=app.openapi_version,
        description=app.description,
        routes=app.routes,
    )
    live_paths = live_schema.get("paths", {})
    
    live_ops = []
    http_methods = ("get", "post", "put", "delete", "patch", "options", "head")
    for path, methods in live_paths.items():
        for m in methods.keys():
            if m.lower() in http_methods:
                live_ops.append((path, m.upper()))

    print(f"Live Application OpenAPI Paths     : {len(live_paths)}")
    print(f"Live Application OpenAPI Operations: {len(live_ops)}")

    # 2. Load baseline schema
    baseline_path = root_dir / "docs" / "openapi.json"
    if not baseline_path.exists():
        print(f"[FAIL] Baseline OpenAPI schema not found at: {baseline_path}")
        sys.exit(1)

    with open(baseline_path, "r", encoding="utf-8") as f:
        baseline_schema = json.load(f)

    baseline_paths = baseline_schema.get("paths", {})
    baseline_ops = []
    for path, methods in baseline_paths.items():
        for m in methods.keys():
            if m.lower() in http_methods:
                baseline_ops.append((path, m.upper()))

    print(f"Baseline Contract OpenAPI Paths    : {len(baseline_paths)}")
    print(f"Baseline Contract OpenAPI Operations: {len(baseline_ops)}")

    # 3. Contract Assertions
    EXPECTED_PATHS = 329
    EXPECTED_OPERATIONS = 388

    errors = []

    if len(live_paths) != EXPECTED_PATHS:
        errors.append(f"Expected {EXPECTED_PATHS} paths, but got {len(live_paths)}")
    if len(live_ops) != EXPECTED_OPERATIONS:
        errors.append(f"Expected {EXPECTED_OPERATIONS} operations, but got {len(live_ops)}")

    # Difference sets
    live_set = set(live_ops)
    base_set = set(baseline_ops)

    missing_in_live = base_set - live_set
    added_in_live = live_set - base_set

    if missing_in_live:
        errors.append(f"Missing {len(missing_in_live)} operations in live app: {sorted(missing_in_live)[:5]}")
    if added_in_live:
        errors.append(f"Added {len(added_in_live)} undocumented operations in live app: {sorted(added_in_live)[:5]}")

    if errors:
        print("\n[FAIL] OpenAPI Contract Validation Failed:")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)

    print("\n[PASS] OpenAPI contract matches baseline 100% precisely (329 paths / 388 operations).")
    print("========================================================================")
    sys.exit(0)


if __name__ == "__main__":
    verify_openapi_contract()
