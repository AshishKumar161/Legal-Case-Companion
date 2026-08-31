import logging
import statistics
import time

import requests

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

BASE_URL = "http://127.0.0.1:8000/api/v1"
ITERATIONS = 50


def run_baseline():
    logger.info("Starting Performance Baseline...")

    # We assume the server is running locally on 8000.
    try:
        requests.get("http://127.0.0.1:8000/api/v1/health/live", timeout=2)
    except requests.exceptions.ConnectionError:
        logger.error(
            "Server is not running on 127.0.0.1:8000. Start it with `uvicorn app.main:app` to run the baseline."
        )
        return

    # Create a user to test auth (this might fail if already exists, but we ignore)
    test_user = {
        "email": f"perf_test_{int(time.time())}@example.com",
        "password": "StrongPassword123!",
        "full_name": "Perf Tester",
        "role": "CLIENT",
    }
    reg_resp = requests.post(f"{BASE_URL}/auth/register", json=test_user)
    if reg_resp.status_code != 201:
        logger.error(f"Registration failed: {reg_resp.text}")

    # 1. Login Latency
    login_times = []
    # Only login 3 times to avoid rate limits (5/min)
    for _ in range(3):
        start = time.perf_counter()
        resp = requests.post(
            f"{BASE_URL}/auth/login",
            json={"email": test_user["email"], "password": test_user["password"]},
        )
        login_times.append((time.perf_counter() - start) * 1000)

    if resp.status_code != 200:
        logger.error(f"Login failed, aborting baseline: {resp.text}")
        return

    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Case List Latency
    case_times = []
    for _ in range(ITERATIONS):
        start = time.perf_counter()
        requests.get(f"{BASE_URL}/cases", headers=headers)
        case_times.append((time.perf_counter() - start) * 1000)

    # 3. Lawyer Search Latency
    search_times = []
    for _ in range(ITERATIONS):
        start = time.perf_counter()
        requests.get(f"{BASE_URL}/lawyers", headers=headers)
        search_times.append((time.perf_counter() - start) * 1000)

    # Report
    logger.info("\n--- Performance Results (ms) ---")
    for name, times in [
        ("Login", login_times),
        ("Case List", case_times),
        ("Lawyer Search", search_times),
    ]:
        p50 = statistics.median(times)
        p95 = (
            statistics.quantiles(times, n=100)[94]
            if len(times) >= 100
            else sorted(times)[int(len(times) * 0.95)]
        )
        logger.info(f"{name:<15} | p50: {p50:.2f}ms | p95: {p95:.2f}ms")


if __name__ == "__main__":
    run_baseline()
