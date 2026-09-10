#!/usr/bin/env python3
"""Legal Case Companion (LCC) — Production Post-Deployment Smoke Test CLI.

Validates:
1. /api/v1/health/live (Liveness)
2. /api/v1/health/ready (Readiness)
3. /api/v1/health/details (Dependency health + versioning + zero secret exposure)
4. Synthetic User Registration & Login
5. Authenticated Case Creation
6. Evidence Staged Upload URL Generation
7. WebSocket Ticket Issuance
"""

import argparse
import os
import sys
import uuid

import httpx

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def run_smoke_tests(base_url: str) -> bool:
    print("=" * 72)
    print("  LEGAL CASE COMPANION — PRODUCTION POST-DEPLOYMENT SMOKE TESTS")
    print(f"  Target URL: {base_url}")
    print("=" * 72)

    passed_steps = 0
    total_steps = 7

    client = httpx.Client(base_url=base_url, timeout=10.0)

    try:
        # Step 1: Liveness Check
        print("\n[Step 1/7] Probing /api/v1/health/live ...")
        res1 = client.get("/api/v1/health/live")
        if res1.status_code == 200 and res1.json().get("status") == "alive":
            print(f"  -> SUCCESS (Status: {res1.status_code}, Body: {res1.json()})")
            passed_steps += 1
        else:
            print(f"  -> FAILED (Status: {res1.status_code}, Body: {res1.text})")
            return False

        # Step 2: Readiness Check
        print("\n[Step 2/7] Probing /api/v1/health/ready ...")
        res2 = client.get("/api/v1/health/ready")
        if res2.status_code == 200 and res2.json().get("status") == "ready":
            print(f"  -> SUCCESS (Status: {res2.status_code}, Latency: {res2.json().get('latency_ms')}ms)")
            passed_steps += 1
        else:
            print(f"  -> FAILED (Status: {res2.status_code}, Body: {res2.text})")
            return False

        # Step 3: Health Details & Versioning Check
        print("\n[Step 3/7] Probing /api/v1/health/details ...")
        res3 = client.get("/api/v1/health/details")
        if res3.status_code == 200:
            data3 = res3.json()
            version = data3.get("version")
            release = data3.get("release_id")
            print(f"  -> SUCCESS (Overall: {data3.get('status')}, Version: {version}, Release: {release})")
            raw_text = res3.text.lower()
            if "password" in raw_text or "secret" in raw_text or "key" in raw_text and "access_key" in raw_text:
                print("  -> FAILED: Potential credential leakage in health details response!")
                return False
            passed_steps += 1
        else:
            print(f"  -> FAILED (Status: {res3.status_code}, Body: {res3.text})")
            return False

        # Step 4: Synthetic User Registration & Login
        unique_suffix = uuid.uuid4().hex[:8]
        smoke_email = f"smoke_user_{unique_suffix}@synthetic-smoke.local"
        smoke_password = "SmokeP@ssw0rd123!"

        print(f"\n[Step 4/7] Registering synthetic user: {smoke_email} ...")
        reg_payload = {
            "email": smoke_email,
            "password": smoke_password,
            "role": "CLIENT",
            "full_name": "Synthetic Smoke Runner",
        }
        res4_reg = client.post("/api/v1/auth/register", json=reg_payload)
        if res4_reg.status_code not in (200, 201):
            print(f"  -> Registration failed (Status: {res4_reg.status_code}, Body: {res4_reg.text})")
            return False

        print("  Logging in synthetic user ...")
        login_payload = {
            "email": smoke_email,
            "password": smoke_password,
        }
        res4_login = client.post("/api/v1/auth/login", json=login_payload)
        if res4_login.status_code != 200:
            print(f"  -> Login failed (Status: {res4_login.status_code}, Body: {res4_login.text})")
            return False

        login_data = res4_login.json()
        token = login_data.get("token") or login_data.get("access_token")
        auth_headers = {"Authorization": f"Bearer {token}"}
        print("  -> SUCCESS: Authenticated successfully.")
        passed_steps += 1

        # Step 5: Authenticated Case Creation
        print("\n[Step 5/7] Creating test legal case ...")
        case_payload = {
            "title": f"Smoke Test Case {unique_suffix}",
            "description": "Automated smoke verification case.",
        }
        res5 = client.post("/api/v1/cases", headers=auth_headers, json=case_payload)
        if res5.status_code in (200, 201):
            case_data = res5.json()
            case_id = case_data.get("id")
            print(f"  -> SUCCESS: Case created (ID: {case_id})")
            passed_steps += 1
        else:
            print(f"  -> FAILED: Case creation returned {res5.status_code} ({res5.text})")
            return False

        # Step 6: Evidence Staged Upload URL Generation
        print("\n[Step 6/7] Requesting staged evidence upload URL ...")
        upload_init_payload = {
            "case_id": case_id,
            "title": "Smoke Contract Evidence",
            "filename": "contract.pdf",
            "content_type": "application/pdf",
            "file_size_bytes": 1024,
        }
        res6 = client.post("/api/v1/evidence/init-upload", headers=auth_headers, json=upload_init_payload)
        if res6.status_code in (200, 201):
            upload_data = res6.json()
            print(f"  -> SUCCESS: Staged upload initialized (Upload ID: {upload_data.get('upload_id')})")
            passed_steps += 1
        else:
            print(f"  -> FAILED: Init upload returned {res6.status_code} ({res6.text})")
            return False

        # Step 7: WebSocket Ticket Issuance
        print("\n[Step 7/7] Requesting single-use WebSocket ticket ...")
        res7 = client.post("/api/v1/realtime/ws-ticket", headers=auth_headers)
        if res7.status_code in (200, 201):
            ticket_data = res7.json()
            ticket = ticket_data.get("ticket")
            print(f"  -> SUCCESS: WS ticket issued (Prefix: {ticket[:10]}...)")
            passed_steps += 1
        else:
            print(f"  -> FAILED: WS ticket issuance returned {res7.status_code} ({res7.text})")
            return False

    except Exception as e:
        print(f"\n[ERROR] Smoke test exception encountered: {e}")
        return False
    finally:
        client.close()

    print("\n" + "=" * 72)
    print(f"  SMOKE TEST SUMMARY: {passed_steps}/{total_steps} STEPS PASSED")
    print("=" * 72)
    return passed_steps == total_steps


def main():
    parser = argparse.ArgumentParser(description="LCC Production Smoke Test Runner")
    parser.add_argument(
        "--url",
        default=os.environ.get("API_BASE_URL", "http://localhost:8000"),
        help="Base URL of deployed LCC API (e.g. https://api.legalcasecompanion.in)",
    )
    args = parser.parse_args()

    success = run_smoke_tests(args.url)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
