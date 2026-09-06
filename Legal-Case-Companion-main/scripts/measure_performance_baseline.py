"""
End-to-End Performance Measurement & Latency Baseline Script
Measures p50, p95, p99 latency, payload size, and bundle size across all 9 primary LCC routes.
"""

import json
import os
import sys
import time
from pathlib import Path
import numpy as np

# Ensure app is in path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient
from app.main import app
from app.core.security import create_access_token
from app.db.session import SessionLocal
from app.models.user import User, UserRole, AccountStatus, LawyerProfile
from app.models.case import Case, CaseStatus

def setup_test_context():
    db = SessionLocal()
    try:
        # Find or create client user
        user = db.query(User).filter(User.role == UserRole.CLIENT).first()
        if not user:
            user = User(
                email="test_perf_user@lcc.internal",
                password_hash="hash",
                role=UserRole.CLIENT,
                account_status=AccountStatus.ACTIVE,
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        # Find or create a case
        case = db.query(Case).first()
        if not case:
            case = Case(
                title="Commercial Property Dispute Performance Test",
                description="Performance baseline test case",
                status=CaseStatus.OPEN,
            )
            db.add(case)
            db.commit()
            db.refresh(case)

        # Find a lawyer
        lawyer_profile = db.query(LawyerProfile).first()
        lawyer_id = str(lawyer_profile.id) if lawyer_profile else str(user.id)

        token = create_access_token(subject=str(user.id), role=user.role.value)
        return user, case, lawyer_id, token
    finally:
        db.close()

def benchmark_endpoint(client: TestClient, method: str, url: str, headers: dict, iterations: int = 20):
    latencies = []
    payload_size = 0

    # Warmup
    try:
        resp = client.request(method, url, headers=headers)
        payload_size = len(resp.content)
    except Exception as e:
        print(f"Warmup error for {url}: {e}")

    for _ in range(iterations):
        t0 = time.perf_counter()
        resp = client.request(method, url, headers=headers)
        t1 = time.perf_counter()
        latencies.append((t1 - t0) * 1000.0) # in ms

    p50 = float(np.percentile(latencies, 50))
    p95 = float(np.percentile(latencies, 95))
    p99 = float(np.percentile(latencies, 99))
    return {
        "p50": round(p50, 2),
        "p95": round(p95, 2),
        "p99": round(p99, 2),
        "payload_bytes": payload_size,
    }

def read_bundle_sizes():
    manifest_path = Path(__file__).parent.parent / "frontend" / ".next" / "build-manifest.json"
    if not manifest_path.exists():
        return {}
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        pages = data.get("pages", {})
        sizes = {}
        frontend_dir = Path(__file__).parent.parent / "frontend" / ".next"
        for page_path, files in pages.items():
            total_b = 0
            for f in files:
                fp = frontend_dir / f
                if fp.exists():
                    total_b += os.path.getsize(fp)
            sizes[page_path] = round(total_b / 1024.0, 1) # in KB
        return sizes
    except Exception as e:
        print("Bundle size read error:", e)
        return {}

def main():
    print("==================================================================")
    print("LCC PHASE 7.5 PERFORMANCE BASELINE BENCHMARK")
    print("==================================================================")

    user, case, lawyer_id, token = setup_test_context()
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token}"}

    test_endpoints = [
        ("Dashboard Cases", "GET", "/api/v1/cases", "/dashboard"),
        ("Matter Workspace", "GET", f"/api/v1/cases/{case.id}/workspace", "/cases/[caseId]"),
        ("Matter Documents", "GET", f"/api/v1/cases/{case.id}/documents", "/documents"),
        ("Lawyer Directory", "GET", "/api/v1/lawyers?limit=10", "/lawyers"),
        ("Lawyer Availability", "GET", f"/api/v1/lawyers/{lawyer_id}/slots", "/lawyers/[lawyerId]"),
        ("Consultations", "GET", "/api/v1/consultations", "/consultations"),
        ("Court Cases Search", "GET", "/api/v1/court-cases?search=DLHC", "/court-tracking"),
        ("Calendar Events", "GET", "/api/v1/calendar/events?timeframe=upcoming", "/calendar"),
        ("Notifications", "GET", "/api/v1/notifications?limit=25", "/notifications"),
    ]

    bundle_sizes = read_bundle_sizes()
    results = []

    for name, method, endpoint, route in test_endpoints:
        stats = benchmark_endpoint(client, method, endpoint, headers)
        bundle_kb = bundle_sizes.get(route, "N/A")
        results.append({
            "name": name,
            "route": route,
            "endpoint": endpoint,
            "p50": stats["p50"],
            "p95": stats["p95"],
            "p99": stats["p99"],
            "payload_bytes": stats["payload_bytes"],
            "bundle_kb": bundle_kb,
        })

    print(f"\n{'Route':<20} | {'Endpoint':<35} | {'p50 (ms)':<9} | {'p95 (ms)':<9} | {'p99 (ms)':<9} | {'Payload':<9} | {'JS Bundle':<10}")
    print("-" * 115)
    for r in results:
        payload_str = f"{r['payload_bytes']} B" if r['payload_bytes'] < 1024 else f"{r['payload_bytes']/1024:.1f} KB"
        bundle_str = f"{r['bundle_kb']} KB" if isinstance(r['bundle_kb'], (int, float)) else str(r['bundle_kb'])
        print(f"{r['route']:<20} | {r['endpoint'][:35]:<35} | {r['p50']:<9} | {r['p95']:<9} | {r['p99']:<9} | {payload_str:<9} | {bundle_str:<10}")

    print("\nBenchmark completed successfully.")

if __name__ == "__main__":
    main()
