import time

import numpy as np
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


def _setup_perf_user(client: TestClient, email: str = "perf_api@example.com") -> tuple[str, dict[str, str]]:
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "PerfPassword123!", "role": "CLIENT", "full_name": "Perf User"},
    )
    login_res = client.post("/api/v1/auth/login", json={"email": email, "password": "PerfPassword123!"})
    token = login_res.json()["access_token"]
    user_id = login_res.json().get("user_id", "")
    return user_id, {"Authorization": f"Bearer {token}"}


def test_core_api_latency_and_p95_benchmarks(client: TestClient, db: Session):
    """Measures latency distributions (p50, p95) for core API read and write endpoints."""
    _, headers = _setup_perf_user(client, "perf_core_bench@example.com")

    # 1. Health Probe Latency Distribution
    health_latencies = []
    for _ in range(25):
        t0 = time.perf_counter()
        res = client.get("/health/live")
        lat = (time.perf_counter() - t0) * 1000.0
        assert res.status_code == 200
        health_latencies.append(lat)

    p50_health = np.percentile(health_latencies, 50)
    p95_health = np.percentile(health_latencies, 95)
    assert p50_health < 50.0  # ms
    assert p95_health < 100.0  # ms

    # 2. Profile Me Latency Distribution
    profile_latencies = []
    for _ in range(20):
        t0 = time.perf_counter()
        res = client.get("/api/v1/profiles/me", headers=headers)
        lat = (time.perf_counter() - t0) * 1000.0
        assert res.status_code == 200
        profile_latencies.append(lat)

    p50_prof = np.percentile(profile_latencies, 50)
    p95_prof = np.percentile(profile_latencies, 95)
    assert p50_prof < 60.0  # ms
    assert p95_prof < 150.0  # ms

    # 3. Case Creation & Workspace Aggregation Latency
    case_res = client.post(
        "/api/v1/cases",
        headers=headers,
        json={"title": "Performance Test Case", "description": "Measuring workspace query latency."},
    )
    assert case_res.status_code == 201
    case_id = case_res.json()["id"]

    ws_latencies = []
    for _ in range(20):
        t0 = time.perf_counter()
        res_ws = client.get(f"/api/v1/cases/{case_id}/workspace", headers=headers)
        lat = (time.perf_counter() - t0) * 1000.0
        assert res_ws.status_code == 200
        ws_latencies.append(lat)

    p50_ws = np.percentile(ws_latencies, 50)
    p95_ws = np.percentile(ws_latencies, 95)
    assert p50_ws < 200.0  # ms
    assert p95_ws < 400.0  # ms


def test_notification_unread_count_latency(client: TestClient, db: Session):
    """Measures notifications query latency under typical user polling frequency."""
    _, headers = _setup_perf_user(client, "perf_notif_bench@example.com")

    notif_latencies = []
    for _ in range(20):
        t0 = time.perf_counter()
        res = client.get("/api/v1/notifications/unread-count", headers=headers)
        lat = (time.perf_counter() - t0) * 1000.0
        assert res.status_code == 200
        notif_latencies.append(lat)

    p50_notif = np.percentile(notif_latencies, 50)
    assert p50_notif < 100.0  # ms
