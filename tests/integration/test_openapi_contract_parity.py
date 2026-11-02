"""
Regression test for BUG-004: OpenAPI Contract Parity.
Ensures that the live FastAPI OpenAPI schema matches the committed canonical contract in docs/openapi.json
with zero undocumented drift or unexpected route removal.
"""
import json
from pathlib import Path
from fastapi.openapi.utils import get_openapi
from app.main import app


def test_openapi_contract_parity():
    # 1. Extract live OpenAPI schema (ignoring ephemeral test routers)
    live_schema = get_openapi(
        title=app.title,
        version=app.version,
        openapi_version=app.openapi_version,
        description=app.description,
        routes=app.routes,
    )
    live_paths = {
        p: methods
        for p, methods in live_schema.get("paths", {}).items()
        if not p.startswith("/test-errors")
    }
    http_methods = ("get", "post", "put", "delete", "patch", "options", "head")
    live_ops = []
    for path, methods in live_paths.items():
        for m in methods.keys():
            if m.lower() in http_methods:
                live_ops.append((path, m.upper()))

    # 2. Load baseline schema
    root_dir = Path(__file__).resolve().parent.parent.parent
    baseline_path = root_dir / "docs" / "openapi.json"
    assert baseline_path.exists(), f"Baseline OpenAPI contract missing at {baseline_path}"

    with open(baseline_path, "r", encoding="utf-8") as f:
        baseline_schema = json.load(f)

    baseline_paths = baseline_schema.get("paths", {})
    baseline_ops = []
    for path, methods in baseline_paths.items():
        for m in methods.keys():
            if m.lower() in http_methods:
                baseline_ops.append((path, m.upper()))

    # 3. Assertions
    assert len(live_paths) == 340, f"Expected 340 paths, got {len(live_paths)}"
    assert len(live_ops) == 399, f"Expected 399 operations, got {len(live_ops)}"

    live_set = set(live_ops)
    base_set = set(baseline_ops)

    missing = base_set - live_set
    added = live_set - base_set

    assert not missing, f"Missing operations in live app: {missing}"
    assert not added, f"Undocumented operations in live app: {added}"
